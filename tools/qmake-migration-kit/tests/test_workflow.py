"""Unit tests for capture parsing, comparison, lint, Qt 6 checks, policy and config (no Qt, no CMake)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))

from qmigrate.capture import read_file_api  # noqa: E402
from qmigrate.cli import main as cli_main  # noqa: E402
from qmigrate.cmdline import lib_identity, parse_compile, parse_link, windows_split  # noqa: E402
from qmigrate.compare import Comparison  # noqa: E402
from qmigrate.config import ConfigError, Workflow, discover  # noqa: E402
from qmigrate.lint import lint  # noqa: E402
from qmigrate.mapper import shell_unescape  # noqa: E402
from qmigrate.qt6 import check as qt6_check, scan_file  # noqa: E402
from qmigrate.report import Findings  # noqa: E402
from verify_demo import same_paths  # noqa: E402


class CommandLines(unittest.TestCase):
    def test_gcc_compile(self):
        p = parse_compile(['ccache', 'g++', '-c', '-pipe', '-O2', '-std=gnu++1z', '-DAPP="x"', '-DFOO', '-UBAR',
                           '-I.', '-isystem', '/q/inc', '-include', 'pre.h', '-fPIC', '-Wall', '-fno-rtti',
                           '-o', 'main.o', '../src/main.cpp'], '/b/app')
        self.assertEqual(p['sources'], ['/b/src/main.cpp'])
        self.assertEqual(p['defines'], [('APP', '"x"'), ('FOO', None)])
        self.assertEqual(p['undefs'], ['BAR'])
        self.assertEqual([i['kind'] for i in p['includes']], ['user', 'system'])
        self.assertEqual(p['forcedIncludes'], ['/b/app/pre.h'])
        self.assertEqual((p['std'], p['opt'], p['pic'], p['warnings'], p['other']),
                         ('gnu++17', ['-O2'], ['-fPIC'], ['-Wall'], ['-fno-rtti']))

    def test_preprocess_only_is_not_a_compile(self):
        self.assertTrue(parse_compile(['g++', '-dM', '-E', '-o', 'moc_predefs.h', 'dummy.cpp'], '/b')['preprocessOnly'])

    def test_msvc_compile_with_response_file(self):
        p = parse_compile(['cl', '-c', '-nologo', '-MD', '-O2', '-DUNICODE', '-DX#1', '-external:I', 'C:/ext',
                           '/FoC:/b/obj/', '@C:/t/r.rsp'], 'C:/b',
                          responses={'@C:/t/r.rsp': '-IC:/inc "C:\\\\src\\\\a b.cpp" -std:c++17'})
        self.assertEqual(p['runtime'], 'MD')
        self.assertEqual(p['defines'], [('UNICODE', None), ('X', '1')])
        self.assertEqual(p['sources'], ['C:/src/a b.cpp'])
        self.assertEqual(p['std'], 'c++17')
        self.assertEqual([i['kind'] for i in p['includes']], ['system', 'user'])

    def test_links(self):
        p = parse_link(['g++', '-Wl,-O1', '-Wl,-rpath,/opt/qt/lib', '-o', 'app', 'main.o', '-L../core', '-lcore',
                        '/usr/lib/libQt5Core.so.5.15.2', '-lpthread'], '/b/app', 'link')
        self.assertEqual((p['rpath'], p['flags'], p['libdirs']), (['/opt/qt/lib'], ['-Wl,-O1'], ['/b/core']))
        self.assertEqual([lib_identity(x) for x in p['libs']], ['core', 'Qt5Core', 'pthread'])
        a = parse_link(['ar', 'cqs', 'libcore.a', 'a.o'], '/b', 'ar')
        self.assertEqual((a['kind'], a['output'], a['objects']), ('static', '/b/libcore.a', ['/b/a.o']))
        m = parse_link(['link', '/NOLOGO', '/DLL', '/OUT:C:/b/x.dll', 'a.obj', 'Qt5Core.lib', '/SUBSYSTEM:WINDOWS'],
                       'C:/b', 'link')
        self.assertEqual((m['kind'], m['libs'], m['flags']), ('shared', ['Qt5Core.lib'], ['/SUBSYSTEM:WINDOWS']))

    def test_windows_split(self):
        self.assertEqual(windows_split(r'a "b c" d\"e "f\\"'), ['a', 'b c', 'd"e', 'f\\'])

    def test_shell_unescape(self):
        self.assertEqual(shell_unescape(r'APP=\"x\"', False), 'APP="x"')
        self.assertEqual(shell_unescape(r'APP=\"x\"', True), 'APP="x"')


def compile_entry(source, **kw):
    entry = dict(source=source, artifact='app', generated=False, failed=False, defines=[], undefs=[], includes=[],
                 forcedIncludes=[], std='c++17', opt=['-O2'], debug=[], pic=[], runtime=None, warnings=[], other=[])
    entry.update(kw)
    return entry


def tree(system, compiles, qt='5.15.2', **kw):
    t = dict(buildSystem=system, profile='p', buildOk=True, steps=[], counts={}, qt={'QT_VERSION': qt},
             compiles=compiles, artifacts={'app': dict(kind='executable', sources=sorted({c['source'] for c in compiles}),
                                                       libs=[], flags=[], rpath=[])}, install=None)
    t.update(kw)
    return t


class Compare(unittest.TestCase):
    def run_cmp(self, a, b):
        return {(i['rule'], i['severity']) for i in Comparison(a, b).run().items}

    def test_define_rules(self):
        a = tree('qmake', [compile_entry('${SRC}/a.cpp', defines=[['APP', '\\"x\\"'], ['KEEP', None], ['UNICODE', None]])])
        b = tree('cmake', [compile_entry('${SRC}/a.cpp', defines=[['APP', '"x"'], ['NDEBUG', None]])])
        got = self.run_cmp(a, b)
        self.assertIn(('define.quoting', 'error'), got)
        self.assertIn(('define.lost', 'error'), got)
        self.assertIn(('define.windows-implicit', 'error'), got)
        self.assertIn(('define.ndebug', 'warning'), got)

    def test_tu_and_flags(self):
        a = tree('qmake', [compile_entry('${SRC}/a.cpp', std='c++14', other=['-fno-rtti']),
                           compile_entry('${SRC}/b.cpp')])
        b = tree('cmake', [compile_entry('${SRC}/a.cpp', std='c++17', opt=['-O3'])], qt='6.5.3')
        got = self.run_cmp(a, b)
        self.assertIn(('tu.missing', 'error'), got)
        self.assertIn(('flags.std-qt6', 'warning'), got)
        self.assertIn(('flags.lost', 'warning'), got)
        self.assertIn(('flags.optimization', 'warning'), got)
        self.assertIn(('artifact.source-lost', 'error'), got)

    def test_include_order_and_aggregation(self):
        inc = lambda *paths: [dict(path=p, kind='user', category='source') for p in paths]
        a = tree('qmake', [compile_entry(f'${{SRC}}/{n}.cpp', includes=inc('${SRC}/x', '${SRC}/y')) for n in 'abc'])
        b = tree('cmake', [compile_entry(f'${{SRC}}/{n}.cpp', includes=inc('${SRC}/y', '${SRC}/x')) for n in 'abc'])
        items = [i for i in Comparison(a, b).run().items if i['rule'] == 'include.order']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['count'], 3)

    def test_empty_compile_set(self):
        empty = tree('qmake', [])
        populated = tree('cmake', [compile_entry('${SRC}/a.cpp')])
        self.assertIn(('capture.empty-compile-set', 'error'), self.run_cmp(empty, populated))
        self.assertIn(('capture.empty-compile-set', 'error'), self.run_cmp(populated, empty))
        self.assertNotIn(('capture.empty-compile-set', 'error'), self.run_cmp(empty, tree('cmake', [])))


class PolicyAndGates(unittest.TestCase):
    def test_policy(self):
        f = Findings()
        f.add('app', 'warning', 'define.ndebug', 'NDEBUG only in cmake')
        f.add('app', 'error', 'define.lost', 'X lost')
        self.assertFalse(f.gate('warning'))
        f.apply_policy({'accept': [{'rule': 'define.*', 'message': 'NDEBUG', 'reason': 'Release asserts off by decision'}]})
        self.assertEqual([i['severity'] for i in f.items], ['accepted', 'error'])
        self.assertFalse(f.gate('error'))
        self.assertTrue(f.gate('never'))
        with self.assertRaises(ValueError):
            f.apply_policy({'accept': [{'rule': '*'}]})


def record(source, pro_dir, **vars_):
    base = dict(_PRO_FILE_PWD_=[str(pro_dir)], OUT_PWD=['/out/0'])
    base.update(vars_)
    return dict(source=source, meta={'xspec': 'linux-g++'}, vars=base)


class LintAndQt6(unittest.TestCase):
    def test_lint(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = record('a.pro', tmp, DEFINES=['A=1', 'A=2', 'S=x;y', 'Q=\\"v\\"', 'F(x)=x'],
                       QMAKE_CXXFLAGS=['-include', 'a.h', '-include', 'b.h', '-DHIDDEN', '-Werror'],
                       LIBS=['-Wl,--whole-archive', '-lfoo', '-Wl,--no-whole-archive'], INCLUDEPATH=['missing'])
            got = {i['rule'] for i in lint({}, {'a.pro': r}).items}
        self.assertTrue({'lint.define.conflict', 'lint.define.semicolon', 'lint.define.quoting',
                         'lint.define.function-like', 'lint.flag.pair-dedup', 'lint.flag.hidden-define',
                         'lint.flag.werror', 'lint.link.order-sensitive', 'lint.include.missing'} <= got)

    def test_qt6_model_and_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'main.cpp'
            src.write_text('#include <QtCore/QRegExp>\n// QTextCodec in a comment is ignored\nQRegExp rx; qsrand(1);\n')
            qml = Path(tmp) / 'Main.qml'
            qml.write_text('import QtQuick.Controls 1.4\nimport QtGraphicalEffects 1.0\n')
            r = record('a.pro', tmp, QT=['core', 'xmlpatterns', 'multimedia', 'opengl'], CONFIG=['c++14'],
                       SOURCES=['main.cpp'], DISTFILES=['Main.qml'])
            f, comps = qt6_check({'sourceRoot': tmp}, {'a.pro': r}, target='6.1', installed={'Core', 'OpenGL'})
        rules = {(i['rule'], i['severity']) for i in f.items}
        self.assertIn(('qt6.removed-module', 'error'), rules)
        self.assertIn(('qt6.module-too-new', 'error'), rules)
        self.assertIn(('qt6.module-not-installed', 'error'), rules)
        self.assertIn(('qt6.cxx-standard', 'error'), rules)
        self.assertIn(('qt6.api.compat-include', 'error'), rules)
        self.assertIn(('qt6.api.qrand', 'error'), rules)
        self.assertIn(('qt6.api.qml-controls1', 'error'), rules)
        self.assertNotIn('qt6.api.qtextcodec', {r for r, _ in rules})
        self.assertEqual(comps, {'a.pro': ['Core5Compat']})


class Config(unittest.TestCase):
    def test_local_override_env_and_discover(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src' / 'lib').mkdir(parents=True)
            (root / 'src' / 'top.pro').write_text('TEMPLATE = subdirs\nSUBDIRS = lib \\\n  tools.pro\n')
            (root / 'src' / 'lib' / 'lib.pro').write_text('TEMPLATE = lib\n')
            (root / 'src' / 'tools.pro').write_text('TEMPLATE = app\n')
            (root / 'src' / 'other.pro').write_text('TEMPLATE = app\n')
            candidates, roots = discover(root / 'src')
            self.assertEqual(roots, ['other.pro', 'top.pro'])
            cfg = root / 'workflow.json'
            cfg.write_text(json.dumps(dict(sourceRoot='src', workspace='w', projects=['top.pro'],
                                           profiles={'p': dict(qmake='${env:QMIG_TEST_QMAKE}')})))
            (root / 'workflow.local.json').write_text(json.dumps({'profiles': {'p': {'jobs': 7}}}))
            import os
            os.environ['QMIG_TEST_QMAKE'] = '/opt/qt/bin/qmake'
            name, prof = Workflow(cfg).profile(None)
            self.assertEqual((name, prof['qmake'], prof['jobs']), ('p', '/opt/qt/bin/qmake', 7))
            del os.environ['QMIG_TEST_QMAKE']
            with self.assertRaises(ConfigError):
                Workflow(cfg)

    def test_read_file_api_selects_matching_build_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build, src = root / 'build', root / 'src'
            reply = build / '.cmake' / 'api' / 'v1' / 'reply'
            reply.mkdir(parents=True)
            src.mkdir()
            (reply / 'index-1.json').write_text(
                json.dumps({'objects': [{'kind': 'codemodel', 'jsonFile': 'codemodel.json'}]}))
            (reply / 'target-dbg.json').write_text(json.dumps({
                'name': 'core', 'type': 'STATIC_LIBRARY',
                'artifacts': [{'path': 'Debug/core.lib'}], 'sources': [{'path': 'core.cpp'}]}))
            (reply / 'target-rel.json').write_text(json.dumps({
                'name': 'core', 'type': 'STATIC_LIBRARY',
                'artifacts': [{'path': 'Release/core.lib'}], 'sources': [{'path': 'core.cpp'}]}))
            (reply / 'codemodel.json').write_text(json.dumps({
                'paths': {'source': str(src)},
                'configurations': [
                    {'name': 'Debug', 'targets': [{'jsonFile': 'target-dbg.json'}]},
                    {'name': 'Release', 'targets': [{'jsonFile': 'target-rel.json'}]},
                ],
            }))
            rel_targets = read_file_api(build, src, 'Release')
            self.assertEqual(rel_targets[0]['artifacts'], [str(build / 'Release/core.lib')])
            fallback_targets = read_file_api(build, src, 'MinSizeRel')
            self.assertEqual(fallback_targets[0]['artifacts'], [str(build / 'Debug/core.lib')])

    def test_init_detects_qt6_and_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / 'src'
            src.mkdir()
            (src / 'app.pro').write_text('TEMPLATE = app\nSOURCES += main.cpp\n')
            if os.name == 'nt':
                fake_qt6 = root / 'fake_qmake6.cmd'
                fake_qt6.write_text('@echo 6.8.2\r\n')
            else:
                fake_qt6 = root / 'fake_qmake6.sh'
                fake_qt6.write_text('#!/bin/sh\necho 6.8.2\n')
                fake_qt6.chmod(0o755)
            cfg6 = root / 'wf6.json'
            self.assertEqual(cli_main(['init', '-c', str(cfg6), '--source-root', str(src), '--qmake', str(fake_qt6)]), 0)
            data6 = json.loads(cfg6.read_text(encoding='utf-8'))
            self.assertEqual(data6['qt6']['target'], '6.8')
            self.assertEqual(data6['profiles']['qt6-release']['cmake']['qtMajor'], 6)

            cfg_fallback = root / 'wf_fallback.json'
            self.assertEqual(cli_main(['init', '-c', str(cfg_fallback), '--source-root', str(src),
                                       '--qmake', str(root / 'missing-qmake')]), 0)
            data5 = json.loads(cfg_fallback.read_text(encoding='utf-8'))
            self.assertEqual(data5['qt6']['target'], '6.5')
            self.assertEqual(data5['profiles']['qt5-release']['cmake']['qtMajor'], 5)

    def test_verify_demo_same_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            schema = Path(tmp) / 'sub' / 'demo.schema'
            schema.parent.mkdir()
            schema.write_text('7\n')
            self.assertTrue(same_paths([schema.as_posix()], [schema.parent / '..' / 'sub' / 'demo.schema']))


if __name__ == '__main__':
    unittest.main()
