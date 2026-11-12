#!/usr/bin/env python3
"""End-to-end check of the qmig workflow on the bundled examples.

  python3 verify_workflow.py --qt5-qmake /path/qt5/bin/qmake [--qt6-qmake /path/qt6/bin/qmake]

Runs in a temporary directory whose path contains spaces. Requires CMake >= 3.21 and
Ninja (or pass --generator). Without --qt6-qmake the Qt 6 scenarios are skipped.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent
EXAMPLES = KIT / 'examples'
CHECKS: list[str] = []


class CheckFailed(RuntimeError):
    pass


def check(condition, message):
    if not condition:
        raise CheckFailed(message)
    CHECKS.append(message)


def qmig(*args, expect=0, cwd=None):
    result = subprocess.run([sys.executable, str(KIT / 'qmig.py'), *map(str, args)], cwd=cwd,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if expect is not None and result.returncode != expect:
        print(result.stdout.decode(errors='replace'))
        raise CheckFailed(f'qmig {" ".join(map(str, args))}: exit {result.returncode}, expected {expect}')
    return result.stdout.decode(errors='replace')


def latest(work: Path, profile: str, kind: str) -> Path:
    index = json.loads((work / 'index.json').read_text())
    entry = [e for e in index if e['kind'] == kind and e['profile'] == profile][-1]
    return work / entry['path']


def findings(path: Path) -> list[dict]:
    return json.loads(path.with_suffix('.json').read_text())['items']


def rules(items, severity=None):
    return {i['rule'] for i in items if severity is None or i['severity'] == severity}


def write_config(root: Path, name: str, data: dict) -> Path:
    path = root / f'{name}.json'
    path.write_text(json.dumps(data, indent=2))
    return path


def run_binary(path: Path) -> str:
    return subprocess.run([str(path)], stdout=subprocess.PIPE, check=True).stdout.decode()


def find_binary(capture_dir: Path, name: str) -> Path:
    hits = [p for p in (capture_dir / 'build').rglob(name) if p.is_file()]
    if not hits:
        raise CheckFailed(f'{name} not found in {capture_dir}')
    return hits[0]


def scenario_init(root: Path, qt5: str):
    src = root / 'init src'
    shutil.copytree(EXAMPLES / 'multi', src)
    out = qmig('init', '-c', root / 'init.json', '--source-root', src, '--qmake', qt5)
    data = json.loads((root / 'init.json').read_text())
    check(data['projects'] == ['multi.pro'], 'init: SUBDIRS children are not suggested as separate roots')
    check(sorted(data['_candidates']) == ['app/app.pro', 'core/core.pro', 'multi.pro'], 'init: all .pro files listed')
    qmig('init', '-c', root / 'init.json', '--source-root', src, expect=1)
    check('not overwritten' in qmig('init', '-c', root / 'init.json', '--source-root', src, expect=1),
          'init: existing config is never overwritten')


def scenario_hazards(root: Path, qt5: str, generator: str):
    policy = root / 'hazards-policy.json'
    policy.write_text(json.dumps({'accept': [
        {'rule': 'define.ndebug', 'reason': 'verification: demonstrates acceptance; real projects decide per product'}]}))
    cfg = write_config(root, 'hazards', dict(
        name='hazards', sourceRoot=str(EXAMPLES / 'hazards'), workspace='work hazards', projects=['hazards.pro'],
        policy=str(policy), gates={'lint': 'never', 'compare': 'warning'},
        profiles={'qt5': dict(qmake=qt5, qmakeArgs=['CONFIG+=release'], jobs=2,
                              cmake=dict(generator=generator, qt='5'))}))
    out = qmig('run', '-c', cfg, '-p', 'qt5', expect=2)
    work = root / 'work hazards'
    lint = rules(findings(latest(work, 'qt5', 'lint')), 'error')
    check({'lint.define.conflict', 'lint.flag.pair-dedup'} <= lint, 'hazards lint: conflicting define and repeated -include are errors')
    warn = rules(findings(latest(work, 'qt5', 'lint')), 'warning')
    check({'lint.define.quoting', 'lint.flag.hidden-define'} <= warn, 'hazards lint: quoting and hidden define flagged')
    draft = latest(work, 'qt5', 'draft')
    text = (draft / '_root' / 'CMakeLists.txt').read_text()
    check('SHELL:-include' in text, 'hazards map: paired -include options use SHELL:')
    check('"APP_NAME=\\"hazards\\""' in text, 'hazards map: one shell quoting level removed from APP_NAME')
    items = findings(latest(work, 'qt5', 'compare'))
    check(not [i for i in items if i['rule'].startswith(('define.value', 'define.quoting', 'include.forced'))],
          'hazards compare: define values and forced includes identical in both builds')
    ndebug = [i for i in items if i['rule'] == 'define.ndebug']
    check(ndebug and ndebug[0]['severity'] == 'accepted', 'hazards compare: NDEBUG difference detected and accepted by policy')
    check('flags.optimization' in rules(items, 'warning'), 'hazards compare: -O2 vs -O3 reported')
    check('gate(fail-on=warning): FAIL' in out, 'hazards: compare gate fails on the remaining warning')
    q = run_binary(find_binary(latest(work, 'qt5', 'buildtree-qmake'), 'hazards'))
    c = run_binary(find_binary(latest(work, 'qt5', 'buildtree-cmake'), 'hazards'))
    check('asserts=on' in q and 'asserts=off' in c, 'hazards: the reported NDEBUG difference is real at run time')


def scenario_multi(root: Path, qt5: str, generator: str):
    adapter = root / 'multi-adapter.json'
    adapter.write_text(json.dumps({'matchQmakeDefaults': True}))
    cfg = write_config(root, 'multi', dict(
        name='multi', sourceRoot=str(EXAMPLES / 'multi'), workspace='work multi', projects=['multi.pro'],
        recursive=True, adapter=str(adapter), gates={'compare': 'warning'},
        profiles={'qt5': dict(qmake=qt5, qmakeArgs=['CONFIG+=release'], jobs=2,
                              cmake=dict(generator=generator, qt='dual', qtMajor=5))}))
    qmig('run', '-c', cfg, '-p', 'qt5')
    work = root / 'work multi'
    items = findings(latest(work, 'qt5', 'compare'))
    check(not rules(items, 'error') and not rules(items, 'warning'),
          'multi: with matchQmakeDefaults the CMake build matches qmake (no errors, no warnings)')
    tree = json.loads((latest(work, 'qt5', 'buildtree-qmake') / 'buildtree.json').read_text())
    check(tree['artifacts']['libcore.a']['sources'] == ['${SRC}/core/counter.cpp'], 'multi: qmake ar call captured')
    tree = json.loads((latest(work, 'qt5', 'buildtree-cmake') / 'buildtree.json').read_text())
    check(tree['artifacts']['libcore.a'].get('fromFileApi'), 'multi: CMake static library taken from the File API')
    check('multi/bin/multi_app' in tree['install'], 'multi: install inventory captured')
    status = qmig('status', '-c', cfg)
    check('compare' in status and 'build OK' in status, 'multi: status lists the evidence')


def scenario_qt6(root: Path, qt5: str, qt6: str | None, generator: str):
    profiles = {
        'qt5': dict(qmake=qt5, qmakeArgs=['CONFIG+=release'], jobs=2, cmake=dict(generator=generator, qt='dual', qtMajor=5)),
        'qt5-deprecated': dict(qmake=qt5, qmakeArgs=['CONFIG+=release'], jobs=2, cmake=dict(
            generator=generator, qt='dual', qtMajor=5, args=['-DCMAKE_CXX_FLAGS=-DQT_DISABLE_DEPRECATED_BEFORE=0x050F00'])),
    }
    if qt6:
        profiles['qt6'] = dict(qmake=qt5, qmakeArgs=['CONFIG+=release'], jobs=2,
                               cmake=dict(generator=generator, qt='dual', qtMajor=6, qmake=qt6))
    cfg = write_config(root, 'qt5api', dict(
        name='qt5api', sourceRoot=str(EXAMPLES / 'qt5api'), workspace='work qt5api', projects=['qt5api.pro'],
        qt6=dict(target='6.4', qmake=qt6), gates={'compare': 'error'}, profiles=profiles))
    work = root / 'work qt5api'
    qmig('run', '-c', cfg, '-p', 'qt5', '--steps', 'export,qt6,map,capture-qmake,capture-cmake,compare')
    report = latest(work, 'qt5', 'qt6')
    items = findings(report)
    check({'qt6.api.qregexp', 'qt6.api.qtextcodec', 'qt6.api.qlinkedlist', 'qt6.cxx-standard'} <= rules(items, 'error'),
          'qt6: removed APIs and C++14 reported')
    meta = json.loads(report.with_suffix('.json').read_text())['meta']
    check(meta['components'] == {'qt5api.pro': ['Core5Compat']}, 'qt6: Core5Compat derived from the source scan')
    draft = latest(work, 'qt5', 'draft') / '_root' / 'CMakeLists.txt'
    check('Qt::Core5Compat' in draft.read_text(), 'map: dual draft links Core5Compat for Qt 6 only')
    qmig('run', '-c', cfg, '-p', 'qt5-deprecated', '--steps', 'export,map,capture-cmake', '--keep-going')
    tree = json.loads((latest(work, 'qt5-deprecated', 'buildtree-cmake') / 'buildtree.json').read_text())
    check(tree['counts']['failedCompiles'] == 1 and not tree['buildOk'],
          'Qt 5.15 deprecation build turns API removed in Qt 6 into recorded compile failures')
    if not qt6:
        return
    qmig('run', '-c', cfg, '-p', 'qt6', '--steps', 'export,qt6,map,capture-qmake,capture-cmake,compare')
    capture = latest(work, 'qt6', 'buildtree-cmake')
    tree = json.loads((capture / 'buildtree.json').read_text())
    check(tree['buildOk'] and tree['qt']['QT_VERSION'].startswith('6.'), 'Qt 6: dual draft builds against Qt 6')
    run_binary(find_binary(capture, 'qt5api'))
    check(True, 'Qt 6: the ported binary runs')
    items = findings(latest(work, 'qt6', 'compare'))
    check(not rules(items, 'error'), 'Qt 6: qmake/Qt 5 vs CMake/Qt 6 comparison without errors')
    check('flags.std-qt6' in rules(items, 'warning'), 'Qt 6: C++14 -> C++17 change reported as a Qt 6 requirement')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--qt5-qmake', required=True)
    parser.add_argument('--qt6-qmake')
    parser.add_argument('--generator', default='Ninja')
    parser.add_argument('--keep', action='store_true')
    args = parser.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix='qmig verify '))
    try:
        scenario_init(tmp, args.qt5_qmake)
        scenario_hazards(tmp, args.qt5_qmake, args.generator)
        scenario_multi(tmp, args.qt5_qmake, args.generator)
        scenario_qt6(tmp, args.qt5_qmake, args.qt6_qmake, args.generator)
    except CheckFailed as error:
        print(f'FAIL: {error}\nwork directory kept: {tmp}')
        return 1
    for item in CHECKS:
        print(f'  ok  {item}')
    print(f'OK: {len(CHECKS)} checks{"" if args.qt6_qmake else " (Qt 6 scenarios skipped: no --qt6-qmake)"}')
    if not args.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
