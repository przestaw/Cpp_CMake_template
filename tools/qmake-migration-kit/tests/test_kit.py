"""Unit tests that need neither Qt nor CMake: python3 -m unittest discover -s tests"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))

from qmigrate.diff import diff_lists  # noqa: E402
from qmigrate.mapper import Mapper, Report, shell_unescape  # noqa: E402
from qmigrate.model import ModelError, normalize_record, parse_records, select_records  # noqa: E402

SEP = '|@|'


def lines(*rows):
    return '\n'.join(SEP.join(r) for r in rows) + '\n'


class ParseRecords(unittest.TestCase):
    def test_record_with_meta_compiler_and_empty_lines(self):
        raw = lines(('record', 'begin'), ('pro', '/s/a.pro'), ('meta', 'variant', 'debug'),
                    ('var', 'DEFINES', 'A=1|@|2'), ('compiler', 'gen', 'output', 'x.h'),
                    ('compilerinput', 'gen', 'IN', '/s/x.in'), ('record', 'end')) + '\n\n'
        [record] = parse_records(raw)
        self.assertEqual(record['meta'], {'variant': 'debug'})
        self.assertEqual(record['vars']['DEFINES'], ['A=1|@|2'])
        self.assertEqual(record['compilers']['gen'], {'output': ['x.h'], 'inputs': {'IN': ['/s/x.in']}})

    def test_multiline_value_is_an_error_not_silent_data_loss(self):
        raw = lines(('record', 'begin'), ('pro', '/s/a.pro')) + 'continued line\n' + lines(('record', 'end'))
        with self.assertRaises(ValueError):
            parse_records(raw)

    def test_truncated_and_nested(self):
        with self.assertRaises(ValueError):
            parse_records(lines(('record', 'begin'), ('pro', '/s/a.pro')))
        with self.assertRaises(ValueError):
            parse_records(lines(('record', 'begin'), ('record', 'begin')))


def rec(source, variant='release', build_pass=False, **vars_):
    return dict(source=source, variant=variant, buildPass=build_pass, vars=vars_, meta={})


class Selection(unittest.TestCase):
    def test_variant_selection(self):
        model = dict(targets=[rec('a.pro'), rec('a.pro', 'release', True), rec('a.pro', 'debug', True)])
        with self.assertRaises(ModelError):
            select_records(model)
        self.assertEqual(select_records(model, 'debug')['a.pro']['variant'], 'debug')
        self.assertTrue(select_records(model, 'release')['a.pro']['buildPass'])

    def test_normalisation(self):
        model = dict(sourceRoot='/src', runDir='/out/run')
        record = rec('a.pro', INCLUDEPATH=['/out/run/0', '/src/inc', '/opt/x'], OUT_PWD=['/out/run/0'])
        self.assertEqual(normalize_record(record, model)['vars']['INCLUDEPATH'],
                         ['${OUT_PWD}', '${SOURCE_ROOT}/inc', '/opt/x'])


class Diff(unittest.TestCase):
    def test_multiset_and_reorder(self):
        self.assertIsNone(diff_lists(['a'], ['a']))
        self.assertEqual(diff_lists(['-la', '-lb'], ['-lb', '-la']), {'added': [], 'removed': [], 'reordered': True})
        self.assertEqual(diff_lists(['x', 'x'], ['x']), {'added': [], 'removed': ['x']})


class MapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name) / 'src'
        (self.src / 'lib').mkdir(parents=True)
        (self.src / 'app').mkdir()
        (self.src / 'app' / 'gen.py').write_text('')

    def tearDown(self):
        self.tmp.cleanup()

    def model(self):
        run = Path(self.tmp.name) / 'run'
        lib = dict(source='lib/lib.pro', meta={'xspec': 'linux-g++'}, installs={}, compilers={}, vars=dict(
            TEMPLATE=['lib'], TARGET=['util'], CONFIG=['staticlib', 'c++17'], QT=['core'],
            SOURCES=['u.cpp'], _PRO_FILE_PWD_=[str(self.src / 'lib')], OUT_PWD=[str(run / '0/lib')]))
        app = dict(source='app/app.pro', meta={'xspec': 'linux-g++'}, vars=dict(
            TEMPLATE=['app'], TARGET=['tool'], CONFIG=['console', 'c++14', 'strict_c++'], QT=['core', 'gui-private'],
            SOURCES=['main.cpp'], DEFINES=['QT_CORE_LIB', 'QT_NO_DEBUG', 'MY_DEF=1'],
            QMAKE_CXXFLAGS=['-pipe', '-O2', '-std=c++14', '-fno-strict-aliasing'],
            LIBS=[f'-L{run}/0/lib', '-lutil', '-lssl', '-lpthread'],
            TRANSLATIONS=['app_pl.ts'],
            _PRO_FILE_PWD_=[str(self.src / 'app')], OUT_PWD=[str(run / '0/app')]),
            compilers={'gen': dict(input=['IN'], output=['${QMAKE_FILE_BASE}.h'],
                                   commands=['python3', str(self.src / 'app/gen.py'), '${QMAKE_FILE_IN}', '>',
                                             '${QMAKE_FILE_OUT}'],
                                   variable_out=['HEADERS'], inputs={'IN': [str(self.src / 'app/x.def')]})},
            installs={'target': {'path': ['/usr/bin']}})
        return dict(sourceRoot=str(self.src), runDir=str(run), targets=[lib, app])

    def test_mapping(self):
        model = self.model()
        report = Report()
        mapper = Mapper(model, {r['source']: r for r in model['targets']},
                        {'libs': {'-lssl': 'OpenSSL::SSL'}, 'tools': {'python3': '${Python3_EXECUTABLE}'}}, report)
        text = mapper.project_cmake('app/app.pro', model['targets'][1])
        self.assertIn('util\n', text)                       # internal library
        self.assertIn('OpenSSL::SSL', text)                 # adapter mapping
        self.assertIn('Threads::Threads', text)
        self.assertIn('"MY_DEF=1"', text)
        self.assertNotIn('QT_CORE_LIB', text)               # Qt-managed defines dropped
        self.assertNotIn('-O2', text)                       # toolchain flags dropped
        self.assertIn('-fno-strict-aliasing', text)         # project flag kept
        self.assertIn('CXX_EXTENSIONS "OFF"', text)
        self.assertIn('OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/x.h"', text)
        self.assertIn('DESTINATION "usr/bin"', text)
        topics = {(i['severity'], i['topic']) for i in report.items}
        self.assertIn(('unsupported', 'QT'), topics)        # gui-private
        self.assertIn(('unsupported', 'variable'), topics)  # TRANSLATIONS
        self.assertIn(('review', 'QMAKE_EXTRA_COMPILERS gen'), topics)  # shell redirection
        lib_text = mapper.project_cmake('lib/lib.pro', model['targets'][0])
        self.assertIn('add_library(util STATIC)', lib_text)
        self.assertIn('CXX_EXTENSIONS "ON"', lib_text)

    def test_cli_refuses_existing_output_and_strict_exit(self):
        model_path = Path(self.tmp.name) / 'm.json'
        model = self.model()
        model.update(schemaVersion=2, profile='t', failures=[])
        model_path.write_text(json.dumps(model))
        out = Path(self.tmp.name) / 'draft'
        result = subprocess.run([sys.executable, str(KIT / 'map_to_cmake.py'), str(model_path),
                                 '--output', str(out), '--strict'], capture_output=True)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertTrue((out / 'mapping-report.md').is_file())
        again = subprocess.run([sys.executable, str(KIT / 'map_to_cmake.py'), str(model_path),
                                '--output', str(out)], capture_output=True)
        self.assertEqual(again.returncode, 2)


if __name__ == '__main__':
    unittest.main()
