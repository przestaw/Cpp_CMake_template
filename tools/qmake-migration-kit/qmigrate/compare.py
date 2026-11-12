"""Compare two captured build trees (usually qmake = baseline, CMake = candidate).

Every difference becomes a finding with a rule id, so a policy file can accept known,
justified differences and CI can gate on the rest. Identical differences across many
translation units are merged into one finding with a count and sample files.
"""
from __future__ import annotations

import re

from qmigrate.report import Findings

WINDOWS_IMPLICIT = {'UNICODE', '_UNICODE', 'WIN32', '_WIN32', 'WIN64', '_WIN64', 'NOMINMAX', 'WIN32_LEAN_AND_MEAN',
                    '_ENABLE_EXTENDED_ALIGNED_STORAGE', '_CRT_SECURE_NO_WARNINGS', '_SCL_SECURE_NO_WARNINGS',
                    '_USE_MATH_DEFINES', 'STRICT', '_WINDOWS', '_CONSOLE', '_DLL', 'MINGW_HAS_SECURE_API'}
DEPRECATION = re.compile(r'^QT_(DEPRECATED_WARNINGS|DISABLE_DEPRECATED_BEFORE|DISABLE_DEPRECATED_UP_TO|NO_DEPRECATED\w*)$')
QT_MODULE_DEFINE = re.compile(r'^QT_\w+_LIB$')
LINK_NOISE = {'-pthread'}


def unquote(value):
    if value is None:
        return None
    v = value.strip().replace('\\"', '"')
    while len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'':
        v = v[1:-1]
    return v


class Comparison:
    def __init__(self, a: dict, b: dict, findings: Findings | None = None):
        self.a, self.b = a, b
        self.la, self.lb = a['buildSystem'], b['buildSystem']
        if self.la == self.lb:
            self.la, self.lb = f'{self.la}:{a["profile"]}', f'{self.lb}:{b["profile"]}'
        self.f = findings or Findings()
        qa, qb = a.get('qt', {}).get('QT_VERSION', ''), b.get('qt', {}).get('QT_VERSION', '')
        self.qt_major_differs = bool(qa and qb and qa.split('.')[0] != qb.split('.')[0])

    def add(self, artifact, severity, rule, message, sample=''):
        self.f.add(artifact or '(no artifact)', severity, rule, message, key='', sample=sample)

    # ------------------------------------------------------------- per TU
    def defines(self, art, src, ca, cb):
        da, db = dict(), dict()
        for n, v in ca['defines']:
            da[n] = v
        for n, v in cb['defines']:
            db[n] = v
        for name in sorted(set(da) | set(db)):
            in_a, in_b = name in da, name in db
            if in_a and in_b:
                if da[name] == db[name]:
                    continue
                if unquote(da[name]) == unquote(db[name]):
                    self.add(art, 'error', 'define.quoting',
                             f'{name}: same text, different quoting ({self.la}: {da[name]!r}, {self.lb}: {db[name]!r}); '
                             'string literal vs. token', src)
                else:
                    sev = 'warning' if DEPRECATION.match(name) else 'error'
                    self.add(art, sev, 'define.value', f'{name}: {self.la}={da[name]!r}, {self.lb}={db[name]!r}', src)
                continue
            side, other = (self.la, self.lb) if in_a else (self.lb, self.la)
            shown = name if (da.get(name) if in_a else db.get(name)) is None else f'{name}={da.get(name) if in_a else db.get(name)}'
            if name == 'NDEBUG':
                self.add(art, 'warning', 'define.ndebug',
                         f'NDEBUG only in {side}: assert() is compiled out there (CMake adds it in Release, '
                         'RelWithDebInfo and MinSizeRel; qmake release does not)', src)
            elif name == 'QT_NO_DEBUG':
                self.add(art, 'error', 'define.qt-no-debug',
                         f'QT_NO_DEBUG only in {side}: Qt debug/release mismatch (Q_ASSERT, qDebug checks); '
                         'check CMAKE_BUILD_TYPE', src)
            elif QT_MODULE_DEFINE.match(name) and self.qt_major_differs:
                self.add(art, 'info', 'define.qt-module', f'{name} only in {side} (Qt major differs)', src)
            elif QT_MODULE_DEFINE.match(name):
                self.add(art, 'warning', 'define.qt-module', f'{name} only in {side}: the Qt module sets differ', src)
            elif name == '_REENTRANT':
                self.add(art, 'info', 'define.reentrant',
                         f'_REENTRANT only in {side} (qmake thread.prf); GCC -pthread defines it implicitly', src)
            elif name in WINDOWS_IMPLICIT:
                sev = 'error' if name in ('UNICODE', '_UNICODE') else 'warning'
                self.add(art, sev, 'define.windows-implicit',
                         f'{shown} only in {side}: a qmake mkspec default that CMake does not set '
                         '(UNICODE switches TCHAR and WinAPI A/W functions)', src)
            elif DEPRECATION.match(name):
                self.add(art, 'warning', 'define.deprecation', f'{shown} only in {side}: available deprecated API differs', src)
            elif name.startswith('QT_TESTCASE_'):
                self.add(art, 'info', 'define.testcase', f'{name} only in {side}', src)
            elif in_a:
                self.add(art, 'error', 'define.lost', f'{shown} only in {self.la}: lost in {self.lb}', src)
            else:
                self.add(art, 'error', 'define.added', f'{shown} only in {self.lb}: not set by {self.la}', src)
        for name in sorted(set(ca['undefs']) ^ set(cb['undefs'])):
            side = self.la if name in ca['undefs'] else self.lb
            self.add(art, 'error', 'define.undef', f'-U{name} only in {side}', src)

    def includes(self, art, src, ca, cb):
        def pick(c, categories):
            return [i for i in c['includes'] if i['category'] in categories]
        ia, ib = pick(ca, ('source', 'external')), pick(cb, ('source', 'external'))
        pa, pb = [i['path'] for i in ia], [i['path'] for i in ib]
        for path in pa:
            if path not in pb:
                self.add(art, 'warning', 'include.lost', f'include dir {path} only in {self.la}', src)
        for path in pb:
            if path not in pa:
                self.add(art, 'info', 'include.added', f'include dir {path} only in {self.lb}', src)
        common_a = [p for p in pa if p in pb]
        common_b = [p for p in pb if p in pa]
        if list(dict.fromkeys(common_a)) != list(dict.fromkeys(common_b)):
            self.add(art, 'warning', 'include.order',
                     'same include dirs in a different order: a header that exists in two dirs may resolve differently', src)
        kinds_a = {i['path']: i['kind'] for i in ia}
        for i in ib:
            if i['path'] in kinds_a and kinds_a[i['path']] != i['kind']:
                self.add(art, 'info', 'include.kind', f'{i["path"]}: {kinds_a[i["path"]]} in {self.la}, '
                                                      f'{i["kind"]} in {self.lb}', src)
        if not self.qt_major_differs:
            qa = {i['path'] for i in ca['includes'] if i['category'] == 'qt'}
            qb = {i['path'] for i in cb['includes'] if i['category'] == 'qt'}
            for path in sorted(qa - qb):
                if '/mkspecs/' not in path + '/':
                    self.add(art, 'warning', 'include.qt', f'Qt include dir {path} only in {self.la}', src)
            sys_a = {i['kind'] for i in ca['includes'] if i['category'] == 'qt'}
            sys_b = {i['kind'] for i in cb['includes'] if i['category'] == 'qt'}
            if sys_a and sys_b and sys_a != sys_b:
                self.add(art, 'info', 'include.qt-system',
                         f'Qt headers as {"/".join(sorted(sys_a))} in {self.la}, {"/".join(sorted(sys_b))} in {self.lb} '
                         '(-isystem hides Qt warnings and searches Qt after all -I dirs)', src)
        fa, fb = ca['forcedIncludes'], cb['forcedIncludes']
        if fa != fb:
            self.add(art, 'error', 'include.forced', f'forced includes differ: {fa} vs {fb}', src)

    def flags(self, art, src, ca, cb):
        sa, sb = ca['std'], cb['std']
        if sa != sb:
            if sa and sb and sa.split('++')[-1] == sb.split('++')[-1]:
                self.add(art, 'warning', 'flags.std-extensions', f'-std {sa} in {self.la}, {sb} in {self.lb} '
                                                                 '(GNU extensions differ)', src)
            elif not sa or not sb:
                self.add(art, 'warning', 'flags.std-default', f'-std {sa or "compiler default"} in {self.la}, '
                                                              f'{sb or "compiler default"} in {self.lb}', src)
            elif self.qt_major_differs and sb.split('++')[-1].isdigit() and int(sb.split('++')[-1]) >= 17:
                self.add(art, 'warning', 'flags.std-qt6', f'C++ standard {sa} in {self.la}, {sb} in {self.lb}: '
                                                          'Qt 6 requires C++17; check code that changes meaning '
                                                          '(e.g. removed std::auto_ptr, register, dynamic exception specs)', src)
            else:
                self.add(art, 'error', 'flags.std', f'C++/C standard {sa} in {self.la}, {sb} in {self.lb}', src)
        if ca['opt'][-1:] != cb['opt'][-1:]:
            self.add(art, 'warning', 'flags.optimization', f'optimisation {" ".join(ca["opt"]) or "none"} in {self.la}, '
                                                            f'{" ".join(cb["opt"]) or "none"} in {self.lb}', src)
        if bool(ca['debug']) != bool(cb['debug']):
            self.add(art, 'info', 'flags.debug-info', f'debug info {ca["debug"]} vs {cb["debug"]}', src)
        if ca['runtime'] != cb['runtime']:
            self.add(art, 'error', 'flags.msvc-runtime', f'MSVC runtime {ca["runtime"]} in {self.la}, '
                                                         f'{cb["runtime"]} in {self.lb}: ODR/heap mismatch across DLLs', src)
        if set(ca['pic']) != set(cb['pic']):
            self.add(art, 'info', 'flags.pic', f'PIC {ca["pic"]} vs {cb["pic"]}', src)
        wa, wb = set(ca['warnings']), set(cb['warnings'])
        werror = {w for w in wa ^ wb if w in ('-Werror', '/WX') or w.startswith('-Werror=')}
        for w in sorted(werror):
            self.add(art, 'warning', 'flags.werror', f'{w} only in {self.la if w in wa else self.lb}', src)
        rest = (wa ^ wb) - werror
        if rest:
            self.add(art, 'info', 'flags.warnings',
                     f'warning options only in {self.la}: {sorted(wa - wb)}; only in {self.lb}: {sorted(wb - wa)}', src)
        oa, ob = ca['other'], cb['other']
        for flag in sorted(set(oa) - set(ob)):
            self.add(art, 'warning', 'flags.lost', f'{flag} only in {self.la}', src)
        for flag in sorted(set(ob) - set(oa)):
            self.add(art, 'info', 'flags.added', f'{flag} only in {self.lb}', src)

    # ------------------------------------------------------------- whole build
    def run(self) -> Findings:
        a, b = self.a, self.b
        for tree, label in ((a, self.la), (b, self.lb)):
            if not tree['buildOk']:
                self.add('(build)', 'error', 'build.failed', f'{label} build did not complete: {tree["steps"]}')
            failed = [c['source'] for c in tree['compiles'] if c['failed']]
            for src in failed:
                self.add('(build)', 'error', 'build.compile-failed', f'compile failed in {label}', src)
            if tree['counts'].get('unparsed'):
                self.add('(capture)', 'warning', 'capture.unparsed', f'{tree["counts"]["unparsed"]} recorded commands '
                                                                     f'could not be parsed in {label}')
        if bool(a['compiles']) != bool(b['compiles']):
            empty, other, count = ((self.la, self.lb, len(b['compiles'])) if not a['compiles']
                                   else (self.lb, self.la, len(a['compiles'])))
            self.add('(capture)', 'error', 'capture.empty-compile-set',
                     f'0 compiled translation units recorded in {empty} while {other} recorded {count}')
        if self.qt_major_differs:
            self.add('(build)', 'info', 'qt.major',
                     f'Qt {a["qt"].get("QT_VERSION")} vs {b["qt"].get("QT_VERSION")}: Qt include/library differences '
                     'are expected and compared loosely')

        def index(tree):
            result = {}
            for c in tree['compiles']:
                if not c['generated'] and not c['failed']:
                    result.setdefault((c['source'], c['artifact']), c)
            return result

        ia, ib = index(a), index(b)
        by_source_b = {}
        for (src, art), c in ib.items():
            by_source_b.setdefault(src, []).append(c)
        matched_b = set()
        for (src, art), ca in sorted(ia.items(), key=lambda x: (x[0][0], x[0][1] or '')):
            cb = ib.get((src, art))
            if cb is None and len(by_source_b.get(src, [])) == 1:
                cb = by_source_b[src][0]
                if cb['artifact'] != art:
                    self.add(art, 'warning', 'tu.artifact', f'compiled into {art} by {self.la}, '
                                                            f'into {cb["artifact"]} by {self.lb}', src)
            if cb is None:
                self.add(art, 'error', 'tu.missing', f'compiled by {self.la}, not by {self.lb}', src)
                continue
            matched_b.add(id(cb))
            self.defines(art, src, ca, cb)
            self.includes(art, src, ca, cb)
            self.flags(art, src, ca, cb)
        for (src, art), cb in ib.items():
            if id(cb) not in matched_b:
                self.add(art, 'warning', 'tu.extra', f'compiled by {self.lb}, not by {self.la}', src)
        ga = sum(c['generated'] for c in a['compiles'])
        gb = sum(c['generated'] for c in b['compiles'])
        self.add('(build)', 'info', 'tu.generated', f'generated translation units: {ga} in {self.la}, {gb} in {self.lb} '
                                                    '(moc/rcc/uic are organised differently; compared per artifact)')
        self.artifacts()
        self.install()
        return self.f

    def lib_set(self, art):
        libs = set(art['libs'])
        if self.qt_major_differs:
            libs = {re.sub(r'^Qt[56]', 'Qt', lib) for lib in libs}
        return libs

    def artifacts(self):
        aa, ab = self.a['artifacts'], self.b['artifacts']
        for key in sorted(set(aa) | set(ab)):
            if key not in ab:
                self.add(key, 'error', 'artifact.missing', f'{key} built by {self.la}, not by {self.lb}')
                continue
            if key not in aa:
                self.add(key, 'warning', 'artifact.extra', f'{key} built by {self.lb}, not by {self.la}')
                continue
            x, y = aa[key], ab[key]
            if x['kind'] != y['kind']:
                self.add(key, 'error', 'artifact.kind', f'{x["kind"]} in {self.la}, {y["kind"]} in {self.lb}')
            for src in sorted(set(x['sources']) - set(y['sources'])):
                self.add(key, 'error', 'artifact.source-lost', f'source part of {key} in {self.la} only', src)
            for src in sorted(set(y['sources']) - set(x['sources'])):
                self.add(key, 'warning', 'artifact.source-added', f'source part of {key} in {self.lb} only', src)
            la, lb = self.lib_set(x), self.lib_set(y)
            for lib in sorted(la - lb):
                sev = 'info' if lib in ('pthread', 'rt', 'dl', 'm') else 'warning'
                self.add(key, sev, 'link.lib-lost', f'links {lib} in {self.la} only')
            for lib in sorted(lb - la):
                self.add(key, 'info', 'link.lib-added', f'links {lib} in {self.lb} only')
            fa, fb = set(x['flags']) - LINK_NOISE, set(y['flags']) - LINK_NOISE
            for flag in sorted(fa - fb):
                if flag in ('-Wl,--no-undefined', '-Wl,-z,defs', '/FORCE:UNRESOLVED'):
                    self.add(key, 'warning', 'link.no-undefined',
                             f'{flag} only in {self.la}: unresolved symbols are no longer rejected at link time in {self.lb}')
                elif flag.upper().startswith('/SUBSYSTEM'):
                    self.add(key, 'error', 'link.subsystem', f'{flag} only in {self.la} (console vs GUI entry point)')
                else:
                    self.add(key, 'warning' if flag not in ('-Wl,-O1',) else 'info', 'link.flag-lost',
                             f'link flag {flag} only in {self.la}')
            for flag in sorted(fb - fa):
                self.add(key, 'info', 'link.flag-added', f'link flag {flag} only in {self.lb}')
            if [r for r in x['rpath'] if not r.startswith('${BUILD}')] != [r for r in y['rpath'] if not r.startswith('${BUILD}')]:
                self.add(key, 'warning', 'link.rpath', f'build RPATH {x["rpath"]} vs {y["rpath"]} (build-tree entries ignored)')

    def install(self):
        ia, ib = self.a.get('install'), self.b.get('install')
        if ia is None or ib is None:
            self.add('(install)', 'info', 'install.skipped', 'install trees not captured on both sides')
            return
        for path in sorted(set(ia) - set(ib)):
            self.add('(install)', 'error', 'install.missing', f'installed by {self.la}, not by {self.lb}', path)
        for path in sorted(set(ib) - set(ia)):
            self.add('(install)', 'warning', 'install.extra', f'installed by {self.lb}, not by {self.la}', path)
        for path in sorted(set(ia) & set(ib)):
            x, y = ia[path], ib[path]
            if x.get('executable') != y.get('executable'):
                self.add('(install)', 'warning', 'install.mode', 'executable bit differs', path)
            ex, ey = x.get('elf'), y.get('elf')
            if ex and ey:
                rx = ex['runpath'] + ex['rpath']
                ry = ey['runpath'] + ey['rpath']
                if rx != ry:
                    self.add('(install)', 'warning', 'install.rpath',
                             f'installed RPATH/RUNPATH {rx} vs {ry} (CMake drops the build RPATH on install unless '
                             'INSTALL_RPATH is set)', path)
                nx, ny = set(ex['needed']), set(ey['needed'])
                if self.qt_major_differs:
                    nx = {re.sub(r'^libQt[56](\w+)\.so\.[56]$', r'libQt\1.so', n) for n in nx}
                    ny = {re.sub(r'^libQt[56](\w+)\.so\.[56]$', r'libQt\1.so', n) for n in ny}
                if nx != ny:
                    self.add('(install)', 'warning', 'install.needed',
                             f'DT_NEEDED only in {self.la}: {sorted(nx - ny)}; only in {self.lb}: {sorted(ny - nx)}', path)


def compare(a: dict, b: dict) -> Findings:
    return Comparison(a, b).run()
