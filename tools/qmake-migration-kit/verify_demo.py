#!/usr/bin/env python3
"""End-to-end check of the kit: export, diff, qmake build, hand-written CMake build,
generated CMake draft build, and install-layout comparison, for both examples.

Example: python3 verify_demo.py --qmake /path/to/Qt/bin/qmake
"""
from __future__ import annotations

import argparse
import filecmp
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parent
DEMO = KIT / 'examples' / 'demo'
MULTI = KIT / 'examples' / 'multi'
WINDOWS = os.name == 'nt'
EXE = '.exe' if WINDOWS else ''
PY = sys.executable
CHECKS: list[str] = []


class CheckFailed(RuntimeError):
    pass


def check(condition: bool, message: str):
    if not condition:
        raise CheckFailed(message)
    CHECKS.append(message)


def run(*cmd, expect=0, **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
    if expect is not None and result.returncode != expect:
        print(result.stdout.decode(errors='replace'))
        raise CheckFailed(f'exit {result.returncode} (expected {expect}): {" ".join(map(str, cmd))}')
    return result


def tree(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file())


def same_paths(actual: list[str], expected: list[Path]) -> bool:
    return [Path(p).resolve() for p in actual] == [Path(p).resolve() for p in expected]


class Toolchain:
    def __init__(self, args):
        self.qmake = Path(args.qmake) if args.qmake else Path(args.qt_root) / 'bin' / f'qmake{EXE}'
        query = run(self.qmake, '-query').stdout.decode()
        q = dict(line.split(':', 1) for line in query.splitlines() if ':' in line)
        self.qt_version = q.get('QT_VERSION', '?')
        libs, bins, prefix = Path(q['QT_INSTALL_LIBS']), Path(q['QT_INSTALL_BINS']), Path(q['QT_INSTALL_PREFIX'])
        major = self.qt_version.split('.')[0]
        config_dir = libs / 'cmake' / f'Qt{major}'
        self.cmake_qt = ([f'-DQt{major}_DIR={config_dir}'] if config_dir.is_dir()
                         else [f'-DCMAKE_PREFIX_PATH={prefix}'])
        self.cmake = args.cmake
        self.env = dict(os.environ)
        if WINDOWS:
            self.env['PATH'] = os.pathsep.join([str(bins), self.env.get('PATH', '')])
            self.make = ['jom'] if shutil.which('jom') else ['nmake', '/nologo']
            self.generator = ['-G', 'NMake Makefiles']
        else:
            self.env['LD_LIBRARY_PATH'] = os.pathsep.join(
                p for p in [str(libs), self.env.get('LD_LIBRARY_PATH', '')] if p)
            self.make = ['make', f'-j{args.jobs}']
            self.generator = []
        self.jobs = str(args.jobs)

    def configure(self, source: Path, build: Path):
        run(self.cmake, '-S', source, '-B', build, *self.generator, '-DCMAKE_BUILD_TYPE=Release',
            *self.cmake_qt, env=self.env)

    def build(self, build: Path):
        run(self.cmake, '--build', build, '--parallel', self.jobs, env=self.env)

    def install(self, build: Path, prefix: Path, component: str | None = None):
        run(self.cmake, '--install', build, '--prefix', prefix,
            *(['--component', component] if component else []), env=self.env)

    def export(self, source: Path, pro: str, output: Path, *extra, expect=0, profile='verify'):
        return run(PY, KIT / 'export_model.py', '--source-dir', source, '--qmake', self.qmake,
                   '--profile', profile, '--output', output, *extra, pro, expect=expect, env=self.env)

    def qmake_build(self, pro: Path, build: Path, install_root: Path, *extra, features: Path | None = None):
        build.mkdir()
        env = dict(self.env, **({'QMAKEFEATURES': str(features)} if features else {}))
        run(self.qmake, pro, 'CONFIG+=release', *extra, cwd=build, env=env)
        run(*self.make, cwd=build, env=env)
        run(*self.make, 'install', f'INSTALL_ROOT={install_root}', cwd=build, env=env)


def verify_debug_and_release(tc: Toolchain, root: Path):
    src = root / 'dar src'
    src.mkdir()
    (src / 'dar.pro').write_text('TEMPLATE = app\nCONFIG += debug_and_release console\nSOURCES = x.cpp\n')
    (src / 'x.cpp').write_text('int main() { return 0; }\n')
    model = root / 'dar.json'
    tc.export(src, 'dar.pro', model)
    records = json.loads(model.read_text())['targets']
    check(len(records) == 3, 'debug_and_release export yields top-level + 2 build-pass records')
    check(sorted(r['variant'] for r in records if r['buildPass']) == ['debug', 'release'],
          'build-pass records carry their variant')
    run(PY, KIT / 'diff_models.py', model, model, expect=1)
    check(True, 'diff rejects ambiguous debug_and_release records without --variant')
    run(PY, KIT / 'diff_models.py', model, model, '--variant', 'debug', '--fail-on-diff')
    check(True, 'diff selects a variant with --variant')


def verify_demo(tc: Toolchain, root: Path, plain: Path):
    models = {}
    for mode in ('release', 'debug'):
        output = root / 'models' / f'demo {mode}.json'
        tc.export(DEMO, 'demo.pro', output, '--features', DEMO / 'features',
                  '--qmake-arg', f'CONFIG+={mode}', profile=f'verify-{mode}')
        data = json.loads(output.read_text())
        check(data['counts']['failures'] == 0, f'demo {mode}: export without failures')
        t = data['targets'][0]
        check('DEMO_FEATURE_LOADED' in t['vars']['DEFINES'], f'demo {mode}: project .prf evaluated')
        check(('DEMO_WINDOWS' if WINDOWS else 'DEMO_UNIX') in t['vars']['DEFINES'], f'demo {mode}: .pri evaluated')
        check(t['compilers']['schema']['output'] == ['demo_generated.h'], f'demo {mode}: custom compiler output')
        check(same_paths(t['compilers']['schema']['inputs']['SCHEMAS'], [DEMO / 'demo.schema']),
              f'demo {mode}: custom compiler inputs')
        check(t['installs']['target']['path'] == ['/demo/bin'], f'demo {mode}: INSTALLS')
        check(t['variant'] == mode, f'demo {mode}: variant recorded')
        check('QT_VERSION' in data['environment']['qmakeQuery'], f'demo {mode}: toolchain recorded')
        models[mode] = output
    diff_json = root / 'models' / 'demo diff.json'
    run(PY, KIT / 'diff_models.py', models['release'], models['debug'], '--summary', '--json', diff_json)
    diff = json.loads(diff_json.read_text())['differences'].get('demo.pro', {})
    check('INCLUDEPATH' not in diff, 'diff: run-specific OUT_PWD paths normalised away')
    check('QMAKE_CXXFLAGS' in diff, 'diff: compiler flag differences reported')

    # qmake's generated install rules do not quote INSTALL_ROOT; it must not contain spaces.
    qb, qinst = root / 'qmake build', plain / 'demo'
    tc.qmake_build(DEMO / 'demo.pro', qb, qinst, *([f'PYTHON={PY}'] if WINDOWS else []),
                   features=DEMO / 'features')
    run(qb / f'demo{EXE}', env=tc.env)
    check(True, 'demo: qmake build runs')

    cb = root / 'cmake build'
    tc.configure(DEMO, cb)
    tc.build(cb)
    run(cb / f'demo{EXE}', env=tc.env)
    generated = cb / 'demo_generated.h'
    check(filecmp.cmp(generated, qb / 'demo_generated.h', shallow=False),
          'demo: qmake and CMake generate identical headers')
    stamp = generated.stat().st_mtime_ns
    tc.build(cb)
    check(generated.stat().st_mtime_ns == stamp, 'demo: incremental build keeps unchanged generated header')
    generated.unlink()
    tc.build(cb)
    check(generated.is_file(), 'demo: deleted generated header is regenerated')
    run(cb / f'demo{EXE}', env=tc.env)
    tc.install(cb, root / 'cmake install', 'runtime')
    check((root / f'cmake install/bin/demo{EXE}').is_file(), 'demo: hand-written CMake installs component')

    draft = root / 'demo draft'
    run(PY, KIT / 'map_to_cmake.py', models['release'], '--output', draft,
        '--adapter', DEMO / 'adapter.json', '--strict', '--project-name', 'DemoDraft')
    db = root / 'demo draft build'
    tc.configure(draft, db)
    tc.build(db)
    run(db / '_root' / f'demo{EXE}', env=tc.env)
    check(True, 'demo: generated CMake draft builds and runs')
    dinst = root / 'demo draft install'
    tc.install(db, dinst)
    check(tree(dinst) == tree(qinst), 'demo: draft install layout equals qmake INSTALL_ROOT layout')


def verify_multi(tc: Toolchain, root: Path, plain: Path):
    model = root / 'models' / 'multi release.json'
    tc.export(MULTI, 'multi.pro', model, '--recursive', '--qmake-arg', 'CONFIG+=release')
    data = json.loads(model.read_text())
    sources = sorted(t['source'] for t in data['targets'])
    check(sources == ['app/app.pro', 'core/core.pro', 'multi.pro'], 'multi: --recursive exports SUBDIRS children')

    qb, qinst = root / 'multi qmake build', plain / 'multi'
    tc.qmake_build(MULTI / 'multi.pro', qb, qinst)
    run(qb / 'app' / f'multi_app{EXE}', env=tc.env)
    check(True, 'multi: qmake build runs')

    draft = root / 'multi draft'
    run(PY, KIT / 'map_to_cmake.py', model, '--output', draft, '--strict', '--project-name', 'MultiDraft')
    top = (draft / 'CMakeLists.txt').read_text()
    check('add_dependencies(multi_app core)' in top, 'multi: SUBDIRS .depends mapped')
    app = (draft / 'app' / 'CMakeLists.txt').read_text()
    check('    core\n' in app, 'multi: -lcore mapped to the internal target')
    db = root / 'multi draft build'
    tc.configure(draft, db)
    tc.build(db)
    run(db / 'app' / f'multi_app{EXE}', env=tc.env)
    check(True, 'multi: generated draft builds and runs (AUTOMOC, static lib)')
    dinst = root / 'multi draft install'
    tc.install(db, dinst)
    check(tree(dinst) == tree(qinst), 'multi: draft install layout equals qmake INSTALL_ROOT layout')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--qt-root', type=Path, help='Qt installation containing bin/qmake')
    group.add_argument('--qmake', type=Path, help='qmake executable (layout read from qmake -query)')
    parser.add_argument('--cmake', default='cmake')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--keep', action='store_true', help='Keep the temporary directory after success')
    args = parser.parse_args()
    tmp = tempfile.mkdtemp(prefix='migration demo ')
    plain = tempfile.mkdtemp(prefix='migration_install_')
    try:
        tc = Toolchain(args)
        root = Path(tmp)
        verify_debug_and_release(tc, root)
        verify_demo(tc, root, Path(plain))
        verify_multi(tc, root, Path(plain))
    except CheckFailed as error:
        print(f'FAIL: {error}\nwork directories kept: {tmp} | {plain}')
        return 1
    print(f'Qt {tc.qt_version}; temporary path with spaces: {tmp}')
    for item in CHECKS:
        print(f'  ok  {item}')
    print(f'OK: {len(CHECKS)} checks')
    if not args.keep:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(plain, ignore_errors=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
