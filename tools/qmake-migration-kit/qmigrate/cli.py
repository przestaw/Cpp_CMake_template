"""qmig — qmake → CMake and Qt 5 → Qt 6 migration workflow.

Typical sequence for one profile (a Qt version + platform + build type):
  qmig init     --source-root .          write workflow.json with discovered .pro files
  qmig export   -p qt5                   qmake model (what qmake evaluates)
  qmig lint     -p qt5                   defines/flags qmake tolerates but CMake treats differently
  qmig qt6      -p qt5                   Qt 6 readiness of the model and the sources
  qmig map      -p qt5 --qt dual         CMake draft + mapping report
  qmig capture qmake -p qt5              build with qmake, record every compiler/linker call
  qmig capture cmake -p qt5              build the draft, record the same
  qmig compare  -p qt5                   classified differences between the two build trees
  qmig status                            latest evidence and gates per profile
  qmig run      -p qt5                   all of the above in order, stopping at a failed gate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qmigrate import __version__
from qmigrate.config import ConfigError, Workflow, detect_qt_version, discover
from qmigrate.model import ModelError, load_model, select_records
from qmigrate.report import Findings

STEPS = ('export', 'lint', 'qt6', 'map', 'capture-qmake', 'capture-cmake', 'compare')


def emit(text: str):
    print(text, flush=True)


def load_records(wf: Workflow, profile: str, model_path: Path | None):
    path = model_path or wf.latest('model', profile)
    model = load_model(path, allow_incomplete=False)
    return path, model, select_records(model, wf.data.get('variant'))


def gate_result(wf: Workflow, step: str, findings: Findings, override: str | None) -> int:
    fail_on = override or wf.gates.get(step, 'never')
    ok = findings.gate(fail_on)
    emit(f'{step}: {json.dumps(findings.summary())} gate(fail-on={fail_on}): {"PASS" if ok else "FAIL"}')
    return 0 if ok else 2


# ------------------------------------------------------------------ commands
def cmd_init(args) -> int:
    config = Path(args.config)
    if config.exists():
        emit(f'{config} exists; not overwritten')
        return 1
    source = Path(args.source_root).resolve()
    candidates, roots = discover(source)
    if not candidates:
        emit(f'no .pro files under {source}')
        return 1
    rel_source = Path(Path(source).relative_to(config.resolve().parent)) if source.is_relative_to(
        config.resolve().parent) else source
    qmake_bin = args.qmake or 'qmake'
    qt_version = detect_qt_version(qmake_bin)
    is_qt6 = qt_version.startswith('6.')
    qt_major = 6 if is_qt6 else 5
    qt6_target = '.'.join(qt_version.split('.')[:2]) if is_qt6 else '6.5'
    profile_name = 'qt6-release' if is_qt6 else 'qt5-release'
    data = {
        'name': source.name,
        'sourceRoot': rel_source.as_posix(),
        'workspace': 'qmig-work',
        'projects': roots,
        'recursive': True,
        'features': [],
        'adapter': None,
        'policy': None,
        'variant': None,
        'gates': {'lint': 'error', 'qt6': 'never', 'compare': 'error'},
        'qt6': {'target': qt6_target, 'qmake': None, 'scanTree': False},
        'profiles': {
            profile_name: {
                'qmake': qmake_bin,
                'qmakeArgs': ['CONFIG+=release'],
                'jobs': 4,
                'cmake': {'generator': 'Ninja', 'buildType': 'Release', 'qt': 'dual', 'qtMajor': qt_major, 'args': []},
            }
        },
        '_candidates': candidates,
    }
    config.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    emit(f'wrote {config}: {len(roots)} suggested root project(s) out of {len(candidates)} .pro files.\n'
         'Review "projects" (the list is the authority, discovery is only a suggestion), put host paths into '
         f'{config.stem}.local.json, then run: qmig export -c {config}')
    return 0


def cmd_export(wf: Workflow, args) -> int:
    from qmigrate.export import export_model
    name, prof = wf.profile(args.profile)
    out = wf.new_artifact('model', name, '.json')
    model = export_model(wf.source_root, [Path(p) for p in wf.data['projects']], qmake=prof['qmake'], profile=name,
                         output=out, qmake_args=prof['qmakeArgs'], features=wf.features(),
                         recursive=wf.data.get('recursive', False), env=wf.env(prof))
    wf.record('model', name, out, counts=model['counts'], qt=model['environment']['qmakeQuery'].get('QT_VERSION'))
    emit(f'model: {out}\n{json.dumps(model["counts"])}')
    for failure in model['failures']:
        emit(f'  FAILED {failure["source"]}: {failure["error"]} (see {model["runDir"]})')
    return 1 if model['failures'] else 0


def cmd_lint(wf: Workflow, args) -> int:
    from qmigrate.lint import lint
    name, _ = wf.profile(args.profile)
    path, model, records = load_records(wf, name, args.model)
    findings = lint(model, records)
    findings.apply_policy(wf.policy())
    base = wf.new_artifact('lint', name)
    md, _ = findings.write(base, f'Model lint: {name}', dict(model=path, profile=name))
    wf.record('lint', name, md, summary=findings.summary())
    emit(f'lint: {md}')
    return gate_result(wf, 'lint', findings, args.fail_on)


def cmd_qt6(wf: Workflow, args) -> int:
    from qmigrate.qt6 import check, installed_qt6_components
    name, _ = wf.profile(args.profile)
    path, model, records = load_records(wf, name, args.model)
    cfg = wf.data.get('qt6', {})
    target = args.target or cfg.get('target', '6.5')
    qt6_qmake = args.qt6_qmake or cfg.get('qmake')
    installed, installed_version = (installed_qt6_components(qt6_qmake) if qt6_qmake else (None, ''))
    extra = []
    if args.scan_tree or cfg.get('scanTree'):
        extra = [p for p in wf.source_root.rglob('*') if p.suffix in ('.cpp', '.cc', '.cxx', '.h', '.hpp', '.qml')]
    findings, components = check(model, records, target=target, installed=installed, extra_files=extra)
    findings.apply_policy(wf.policy())
    base = wf.new_artifact('qt6', name)
    meta = dict(model=path, profile=name, target=target, installedQt6=installed_version or 'not checked',
                components=components)
    md, _ = findings.write(base, f'Qt 6 readiness: {name}', meta,
                           intro='Recommended order: migrate the build to CMake on Qt 5.15 (versionless Qt:: '
                                 'targets, `qmig map --qt dual`), build once with '
                                 '`QT_DISABLE_DEPRECATED_BEFORE=0x050F00`, then switch the same draft to Qt 6.')
    wf.record('qt6', name, md, summary=findings.summary(), target=target)
    emit(f'qt6: {md}')
    return gate_result(wf, 'qt6', findings, args.fail_on)


def cmd_map(wf: Workflow, args) -> int:
    from qmigrate.mapper import generate
    name, prof = wf.profile(args.profile)
    path, model, records = load_records(wf, name, args.model)
    qt_mode = args.qt or prof['cmake'].get('qt', 'model')
    extra = {}
    if qt_mode in ('6', 'dual') and not args.no_qt6_report:
        report = wf.latest('qt6', name, required=False)
        if report:
            extra = json.loads(report.with_suffix('.json').read_text())['meta'].get('components', {})
    out = wf.new_artifact('draft', name)
    report = generate(model, records, out, adapter=wf.adapter(), qt_mode=qt_mode, extra_components=extra,
                      project_name=wf.data.get('name', 'MigratedProject'))
    counts = dict(unsupported=report.count('unsupported'), review=report.count('review'), info=report.count('info'))
    wf.record('draft', name, out, qt=qt_mode, counts=counts)
    emit(f'draft: {out}\nreport: {out / "mapping-report.md"}\n{json.dumps(counts)}')
    return 3 if args.strict and counts['unsupported'] else 0


def cmd_capture(wf: Workflow, args) -> int:
    from qmigrate import capture
    name, prof = wf.profile(args.profile)
    env = wf.env(prof)
    if args.system == 'qmake':
        out = wf.new_artifact('buildtree-qmake', name)
        info = capture.capture_qmake(source_root=wf.source_root, projects=wf.data['projects'], qmake=prof['qmake'],
                                     qmake_args=prof['qmakeArgs'], features=wf.features(), out=out, env=env,
                                     make=prof.get('make'), jobs=prof['jobs'], keep_going=args.keep_going,
                                     install=not args.no_install)
    else:
        cm = prof['cmake']
        source = Path(args.source).resolve() if args.source else wf.resolve(cm.get('source')) or wf.latest('draft', name)
        out = wf.new_artifact('buildtree-cmake', name)
        cmake_args = list(cm.get('args', []))
        major = args.qt_major or cm.get('qtMajor')
        if major:
            cmake_args.append(f'-DQMIG_QT_MAJOR={major}')
        qmake = cm.get('qmake') or prof['qmake']
        info = capture.capture_cmake(cmake_source=source, source_root=wf.source_root, out=out,
                                     cmake=cm.get('cmake', 'cmake'), generator=cm.get('generator'),
                                     build_type=cm.get('buildType', 'Release'), args=cmake_args, env=env,
                                     jobs=prof['jobs'], keep_going=args.keep_going, install=not args.no_install,
                                     qmake=qmake)
    tree = capture.normalise(info, out, name)
    kind = f'buildtree-{args.system}'
    wf.record(kind, name, out, buildOk=tree['buildOk'], counts=tree['counts'], qt=tree['qt'].get('QT_VERSION'))
    emit(f'{kind}: {out}/buildtree.json\nbuild {"OK" if tree["buildOk"] else "FAILED"} {json.dumps(tree["counts"])}')
    return 0 if tree['buildOk'] or args.keep_going else 1


def resolve_tree(wf: Workflow, spec: str | None, default_kind: str, profile: str) -> Path:
    """spec: a path, 'PROFILE', 'KIND', or 'KIND@PROFILE' (KIND = qmake | cmake)."""
    if spec and Path(spec).exists():
        p = Path(spec)
        return p / 'buildtree.json' if p.is_dir() else p
    kind, prof = default_kind, profile
    if spec:
        if '@' in spec:
            kind, prof = spec.split('@', 1)
        elif spec in ('qmake', 'cmake'):
            kind = spec
        else:
            prof = spec
    return wf.latest(f'buildtree-{kind}', prof) / 'buildtree.json'


def cmd_compare(wf: Workflow, args) -> int:
    from qmigrate.compare import compare
    name, _ = wf.profile(args.profile)
    a_path = resolve_tree(wf, args.base, 'qmake', name)
    b_path = resolve_tree(wf, args.candidate, 'cmake', name)
    a, b = (json.loads(p.read_text(encoding='utf-8')) for p in (a_path, b_path))
    findings = compare(a, b)
    findings.apply_policy(wf.policy())
    base = wf.new_artifact('compare', name)
    md, _ = findings.write(base, f'Build tree comparison: {name}', dict(base=a_path, candidate=b_path))
    wf.record('compare', name, md, summary=findings.summary())
    emit(f'compare: {md}')
    return gate_result(wf, 'compare', findings, args.fail_on)


def cmd_status(wf: Workflow, args) -> int:
    entries = wf.index()
    if not entries:
        emit('no evidence yet')
        return 0
    profiles = sorted({e['profile'] for e in entries})
    for profile in profiles:
        emit(f'[{profile}]')
        for kind in ('model', 'lint', 'qt6', 'draft', 'buildtree-qmake', 'buildtree-cmake', 'compare'):
            latest = [e for e in entries if e['profile'] == profile and e['kind'] == kind]
            if not latest:
                emit(f'  {kind:16} -')
                continue
            e = latest[-1]
            detail = e.get('summary') or e.get('counts') or {}
            extra = ''
            if 'buildOk' in e:
                extra = ' build ' + ('OK' if e['buildOk'] else 'FAILED')
            emit(f'  {kind:16} {e["created"]}  {e["path"]}{extra}  {json.dumps(detail)}')
    return 0


def cmd_run(wf: Workflow, args) -> int:
    steps = args.steps.split(',') if args.steps else list(STEPS)
    unknown = [s for s in steps if s not in STEPS]
    if unknown:
        raise ConfigError(f'unknown steps {unknown}; choose from {", ".join(STEPS)}')
    ns = dict(profile=args.profile, model=None, fail_on=None, target=None, qt6_qmake=None, scan_tree=False,
              qt=None, no_qt6_report=False, strict=False, keep_going=args.keep_going, no_install=False,
              source=None, qt_major=None, base=None, candidate=None)
    for step in steps:
        emit(f'== {step}')
        a = argparse.Namespace(**ns)
        if step == 'export':
            rc = cmd_export(wf, a)
        elif step == 'lint':
            rc = cmd_lint(wf, a)
        elif step == 'qt6':
            rc = cmd_qt6(wf, a)
        elif step == 'map':
            rc = cmd_map(wf, a)
        elif step == 'capture-qmake':
            a.system = 'qmake'
            rc = cmd_capture(wf, a)
        elif step == 'capture-cmake':
            a.system = 'cmake'
            rc = cmd_capture(wf, a)
        else:
            rc = cmd_compare(wf, a)
        if rc and not args.continue_on_failure:
            emit(f'stopped after {step} (exit {rc}); --continue-on-failure runs the remaining steps')
            return rc
    return 0


def cmd_diff(args) -> int:
    from qmigrate.diff import main as diff_main
    return diff_main(args.rest)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='qmig', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command', required=True)

    def common(p, profile=True):
        p.add_argument('-c', '--config', default='workflow.json')
        if profile:
            p.add_argument('-p', '--profile')
        return p

    p = sub.add_parser('init', help='write workflow.json with discovered .pro files')
    p.add_argument('-c', '--config', default='workflow.json')
    p.add_argument('--source-root', default='.')
    p.add_argument('--qmake')
    common(sub.add_parser('export', help='export the qmake model'))
    for name, helptext in (('lint', 'lint defines/flags in the model'), ('qt6', 'Qt 6 readiness report')):
        p = common(sub.add_parser(name, help=helptext))
        p.add_argument('--model', type=Path)
        p.add_argument('--fail-on', choices=['error', 'warning', 'info', 'never'])
        if name == 'qt6':
            p.add_argument('--target', help='target Qt 6 version, e.g. 6.5')
            p.add_argument('--qt6-qmake', help='qmake of the target Qt 6: checks installed modules')
            p.add_argument('--scan-tree', action='store_true', help='scan every C++/QML file under sourceRoot, '
                                                                    'not only files listed in the model')
    p = common(sub.add_parser('map', help='generate the CMake draft'))
    p.add_argument('--model', type=Path)
    p.add_argument('--qt', choices=['model', '5', '6', 'dual'])
    p.add_argument('--no-qt6-report', action='store_true', help='ignore components found by the latest qt6 report')
    p.add_argument('--strict', action='store_true')
    p = common(sub.add_parser('capture', help='build and record compiler/linker calls'))
    p.add_argument('system', choices=['qmake', 'cmake'])
    p.add_argument('--keep-going', action='store_true', help='continue after compile errors (e.g. a deprecation build)')
    p.add_argument('--no-install', action='store_true')
    p.add_argument('--source', help='CMake source dir (default: profile cmake.source, else latest draft)')
    p.add_argument('--qt-major', type=int, choices=[5, 6], help='for dual drafts: -DQMIG_QT_MAJOR')
    p = common(sub.add_parser('compare', help='compare two captured build trees'))
    p.add_argument('--base', help='path, KIND@PROFILE, PROFILE or KIND (default: qmake@<profile>)')
    p.add_argument('--candidate', help='path, KIND@PROFILE, PROFILE or KIND (default: cmake@<profile>)')
    p.add_argument('--fail-on', choices=['error', 'warning', 'info', 'never'])
    common(sub.add_parser('status', help='latest evidence per profile'), profile=False)
    p = common(sub.add_parser('run', help='run several steps in order'))
    p.add_argument('--steps', help=f'comma-separated subset of {",".join(STEPS)}')
    p.add_argument('--keep-going', action='store_true')
    p.add_argument('--continue-on-failure', action='store_true')
    p = sub.add_parser('diff', help='compare two qmake models (see diff_models.py --help)')
    p.add_argument('rest', nargs=argparse.REMAINDER)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == 'init':
            return cmd_init(args)
        if args.command == 'diff':
            return cmd_diff(args)
        wf = Workflow(Path(args.config))
        return {'export': cmd_export, 'lint': cmd_lint, 'qt6': cmd_qt6, 'map': cmd_map, 'capture': cmd_capture,
                'compare': cmd_compare, 'status': cmd_status, 'run': cmd_run}[args.command](wf, args)
    except (ConfigError, ModelError, ValueError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
