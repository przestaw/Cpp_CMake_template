"""Lint an exported qmake model for constructs that qmake passes through silently but that
change meaning or break under CMake. Static: needs no build. Confirm with `qmig compare`."""
from __future__ import annotations

import re
from pathlib import Path

from qmigrate.mapper import PAIRED_FLAGS
from qmigrate.report import Findings

LINK_ONLY = re.compile(r'^(-Wl,|-l|-L|/LIBPATH:|-rpath|-shared$|-static$)')
MSVC_STYLE = re.compile(r'^/[A-Za-z]')
GCC_ONLY = re.compile(r'^-(f|m|W[^0-4]|std=|pedantic|isystem|include$)')
WHOLE_ARCHIVE = re.compile(r'^-Wl,(--whole-archive|--no-whole-archive|--start-group|--end-group|-force_load|-all_load)')


def is_msvc(record: dict) -> bool:
    spec = record.get('meta', {}).get('xspec', '') + record.get('meta', {}).get('compiler', '')
    return 'msvc' in spec or spec.endswith('cl')


def lint(model: dict, records: dict, findings: Findings | None = None) -> Findings:
    f = findings or Findings()
    for source, record in sorted(records.items()):
        v = record['vars']
        msvc = is_msvc(record)
        add = lambda sev, rule, msg, ev='': f.add(source, sev, rule, msg, evidence=ev)
        # ---------------------------------------------------------------- DEFINES
        values: dict[str, set] = {}
        for d in v.get('DEFINES', []):
            name, _, value = d.partition('=')
            values.setdefault(name, set()).add(value if '=' in d else None)
            if ';' in d:
                add('error', 'lint.define.semicolon', f'{d}: ";" splits a CMake list into two definitions', d)
            if '#' in d:
                add('warning', 'lint.define.hash', f'{d}: "#" is a Makefile comment / MSVC "=" substitute; '
                                                   'generators escape it differently', d)
            if re.match(r'^\w+\(', name):
                add('warning', 'lint.define.function-like', f'{name}: function-like macro definitions are not supported '
                                                            'by every CMake generator (Visual Studio)', d)
            if '"' in d or '\\' in d or "'" in d:
                add('warning', 'lint.define.quoting',
                    f'{d}: qmake passes the value through the shell unchanged, CMake escapes it for you; the draft '
                    'removes one quoting level — verify the value with qmig compare', d)
            if re.search(r'\s', d):
                add('warning', 'lint.define.whitespace', f'{d!r}: whitespace in a definition; qmake splits or quotes '
                                                         'it differently from CMake', d)
            if '$' in d:
                add('warning', 'lint.define.dollar', f'{d}: "$" is expanded by make/CMake generators differently', d)
            if name.startswith('-D') or name.startswith('/D'):
                add('error', 'lint.define.prefix', f'{d}: DEFINES entries must not carry -D', d)
        for name, vals in sorted(values.items()):
            if len(vals) > 1:
                add('error', 'lint.define.conflict',
                    f'{name} defined with different values {sorted(map(str, vals))}: the compiler kept the last one '
                    '(with a redefinition warning); CMake keeps definition order but may de-duplicate', name)
        dupes = [d for d in set(v.get('DEFINES', [])) if v.get('DEFINES', []).count(d) > 1]
        for d in sorted(dupes):
            add('info', 'lint.define.duplicate', f'{d} listed more than once (CMake de-duplicates)', d)
        # ---------------------------------------------------------------- compiler flags
        for var in ('QMAKE_CXXFLAGS', 'QMAKE_CFLAGS', 'MIGRATION_PKGCONFIG_CFLAGS'):
            flags = v.get(var, [])
            seen_pairs: dict[str, int] = {}
            i = 0
            while i < len(flags):
                flag = flags[i]
                i += 1
                if flag in PAIRED_FLAGS:
                    arg = flags[i] if i < len(flags) else ''
                    i += 1
                    seen_pairs[flag] = seen_pairs.get(flag, 0) + 1
                    if seen_pairs[flag] == 2:
                        add('error', 'lint.flag.pair-dedup',
                            f'{var}: {flag} occurs more than once; plain target_compile_options() de-duplicates the '
                            f'option word and the second argument becomes an input file — use "SHELL:{flag} <arg>"',
                            f'{flag} {arg}')
                    continue
                if var != 'MIGRATION_PKGCONFIG_CFLAGS' and re.match(r'^[-/]D', flag):
                    add('warning', 'lint.flag.hidden-define',
                        f'{var}: {flag} bypasses DEFINES — moc does not see it under qmake, while CMake AUTOMOC passes '
                        'only COMPILE_DEFINITIONS; move it to DEFINES / target_compile_definitions', flag)
                if re.match(r'^[-/]I', flag):
                    add('warning', 'lint.flag.hidden-include', f'{var}: {flag} bypasses INCLUDEPATH (and moc); '
                                                               'use target_include_directories', flag)
                if LINK_ONLY.match(flag):
                    add('warning', 'lint.flag.linker-in-cflags', f'{var}: {flag} is a link option in compile flags', flag)
                if ' ' in flag:
                    add('error', 'lint.flag.space', f'{var}: {flag!r} is one qmake item with spaces; CMake passes it as '
                                                    'ONE argument, the compiler under qmake saw separate words', flag)
                if msvc and GCC_ONLY.match(flag):
                    add('warning', 'lint.flag.dialect', f'{var}: GCC-style {flag} on an MSVC spec (cl ignores or '
                                                        'rejects it; check a scope like gcc:)', flag)
                if not msvc and MSVC_STYLE.match(flag):
                    add('warning', 'lint.flag.dialect', f'{var}: MSVC-style {flag} on a non-MSVC spec', flag)
                if flag in ('-Werror', '/WX') or flag.startswith('-Werror='):
                    add('warning', 'lint.flag.werror', f'{var}: {flag} with a different warning set in CMake '
                                                       '(Qt as -isystem, other defaults) changes which code fails', flag)
            stds = sorted({x for x in flags if re.match(r'^(-std=|[-/]std:)', x)})
            if len(stds) > 1:
                add('warning', 'lint.flag.std-conflict',
                    f'{var}: several language standards {stds}; the last one wins under qmake, CMake adds its own '
                    'from CXX_STANDARD', ' '.join(stds))
        # ---------------------------------------------------------------- link flags / libs
        libs = v.get('LIBS', []) + v.get('LIBS_PRIVATE', [])
        for item in libs + v.get('QMAKE_LFLAGS', []):
            if WHOLE_ARCHIVE.match(item):
                add('error', 'lint.link.order-sensitive',
                    f'{item}: position-dependent linker option; CMake reorders and de-duplicates link items — use '
                    '$<LINK_LIBRARY:WHOLE_ARCHIVE,...> or $<LINK_GROUP:RESCAN,...> (CMake 3.24+)', item)
        static_libs = [l for l in libs if l.startswith('-l')]
        if len(static_libs) != len(set(static_libs)):
            add('warning', 'lint.link.repeated-lib',
                f'repeated -l entries {sorted({l for l in static_libs if static_libs.count(l) > 1})}: static-library '
                'cycles resolved by repetition need LINK_INTERFACE_MULTIPLICITY or link groups in CMake')
        if any(i.startswith('-L') for i in libs) and any(i.startswith('-l') for i in libs):
            add('info', 'lint.link.search-path', '-L/-l pairs: the library actually found depends on search order; '
                                                 'CMake prefers full paths or imported targets')
        for item in v.get('QMAKE_LFLAGS', []):
            if item in ('-Wl,--no-undefined', '-Wl,-z,defs'):
                add('info', 'lint.link.no-undefined', f'{item}: keep it on shared libraries in CMake (not a default there)')
        # ---------------------------------------------------------------- include paths
        pro_dir = Path(v['_PRO_FILE_PWD_'][0])
        out_pwd = v.get('OUT_PWD', [''])[0]
        for inc in v.get('INCLUDEPATH', []):
            path = Path(inc) if Path(inc).is_absolute() else pro_dir / inc
            if out_pwd and str(path).startswith(out_pwd):
                continue
            if not path.exists():
                add('warning', 'lint.include.missing', f'INCLUDEPATH {inc} does not exist (qmake ignores it; an imported '
                                                       'target with this path fails at configure time)', inc)
        # ---------------------------------------------------------------- CONFIG
        config = v.get('CONFIG', [])
        if 'debug_and_release' in config and record.get('meta', {}).get('debugAndRelease') == '1':
            add('info', 'lint.config.debug-and-release', 'debug_and_release: export and compare each variant separately')
        if v.get('QMAKE_CXXFLAGS_RELEASE') and any(f.startswith(('-O3', '/Ox', '-Ofast')) for f in v['QMAKE_CXXFLAGS_RELEASE']):
            add('info', 'lint.config.release-flags', f'project-modified release flags {v["QMAKE_CXXFLAGS_RELEASE"]}: '
                                                     'map to CMAKE_CXX_FLAGS_RELEASE or a per-config genex')
    return f
