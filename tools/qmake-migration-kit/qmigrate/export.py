"""Run native qmake with the migration_export probe and write a JSON model."""
from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

from qmigrate.model import SCHEMA_VERSION, parse_records

KIT = Path(__file__).resolve().parent.parent
QUERY_KEYS = ('QT_VERSION', 'QMAKE_SPEC', 'QMAKE_XSPEC', 'QT_INSTALL_PREFIX',
              'QT_INSTALL_BINS', 'QT_INSTALL_LIBS', 'QT_INSTALL_HEADERS')


def qmake_query(qmake: str, env: dict | None = None) -> dict:
    try:
        out = subprocess.run([qmake, '-query'], env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=60, check=True).stdout
    except (OSError, subprocess.SubprocessError) as error:
        return {'error': str(error)}
    result = {}
    for line in out.decode(errors='replace').splitlines():
        key, _, value = line.partition(':')
        if key in QUERY_KEYS:
            result[key] = value
    return result


def git_state(source: Path) -> dict:
    def git(*args):
        return subprocess.run(['git', '-C', str(source), *args], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=60, check=True).stdout.decode().strip()
    try:
        return dict(revision=git('rev-parse', 'HEAD'),
                    dirty=bool(git('status', '--porcelain', '--untracked-files=no')))
    except (OSError, subprocess.SubprocessError):
        return {}


def feature_env(features: list[Path], env: dict | None = None) -> dict:
    env = dict(os.environ if env is None else env)
    dirs = [KIT / 'features'] + [Path(p).resolve() for p in features]
    env['QMAKEFEATURES'] = os.pathsep.join([str(p) for p in dirs] +
                                         ([env['QMAKEFEATURES']] if env.get('QMAKEFEATURES') else []))
    return env


def export_model(source: Path, projects: list[Path], *, qmake: str, profile: str, output: Path,
                 qmake_args: list[str] = (), features: list[Path] = (), recursive: bool = False,
                 timeout: int = 180, env: dict | None = None) -> dict:
    source = source.resolve()
    resolved = []
    for item in projects:
        project = (source / item).resolve()
        if not project.is_relative_to(source) or not project.is_file() or project.suffix != '.pro':
            raise ValueError(f'Expected a .pro under the source root: {item}')
        if project not in resolved:
            resolved.append(project)
    output = output.resolve()
    if output.exists():
        raise ValueError(f'{output} exists; an existing model is never overwritten')
    output.parent.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix=output.stem + '-run-', dir=output.parent))
    env = feature_env(list(features), env)
    model = dict(schemaVersion=SCHEMA_VERSION, profile=profile, sourceRoot=str(source),
                 runDir=str(run_dir), qmake=str(qmake), qmakeArgs=list(qmake_args), recursive=recursive,
                 environment=dict(qmakeQuery=qmake_query(str(qmake), env), git=git_state(source),
                                  host=platform.platform(), python=platform.python_version(),
                                  exportedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(
                                      timespec='seconds')),
                 targets=[], failures=[])
    for index, project in enumerate(resolved):
        work = run_dir / str(index)
        work.mkdir()
        dump = work / 'records.txt'
        # Through the environment: command-line assignments are re-split on whitespace.
        project_env = dict(env, MIGRATION_EXPORT_FILE=str(dump))
        command = [str(qmake), '-nocache', *(['-r'] if recursive else []), str(project),
                   '-o', 'Makefile.probe', 'CONFIG+=migration_export', *qmake_args]
        rel = project.relative_to(source).as_posix()
        try:
            result = subprocess.run(command, cwd=work, env=project_env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=timeout)
            (work / 'qmake.log').write_bytes(result.stdout)
            if result.returncode:
                raise RuntimeError(f'qmake exit {result.returncode}')
            if not dump.is_file():
                raise ValueError('Feature produced no records (migration_export not loaded?)')
            records = parse_records(dump.read_text(encoding='utf-8'))
            if not records:
                raise ValueError('Feature produced no records')
            accepted = []
            for record in records:
                origin = Path(record['pro']).resolve()
                if not origin.is_relative_to(source):
                    raise ValueError(f'record outside the source root: {origin}')
                record['source'] = origin.relative_to(source).as_posix()
                record['exportedFrom'] = rel
                record['variant'] = record['meta'].get('variant', '')
                record['buildPass'] = record['meta'].get('buildPass') == '1'
                accepted.append(record)
            model['targets'].extend(accepted)  # all records of a project, or none
        except subprocess.TimeoutExpired as error:
            (work / 'qmake.log').write_bytes(error.stdout or b'')
            model['failures'].append(dict(source=rel, error='qmake timeout'))
        except (OSError, ValueError, RuntimeError, UnicodeDecodeError) as error:
            model['failures'].append(dict(source=rel, error=str(error)))
    model['counts'] = dict(requestedProjects=len(resolved), records=len(model['targets']),
                           failures=len(model['failures']))
    output.write_text(json.dumps(model, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return model


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('projects', nargs='+', type=Path, help='Explicit .pro files relative to source-dir')
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--qmake', default='qmake', help='Native qmake executable; preferably absolute')
    parser.add_argument('--profile', required=True, help='Evidence label only, does not configure qmake')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--qmake-arg', action='append', default=[], help='Repeat; use --qmake-arg=-spec for flags')
    parser.add_argument('--features', type=Path, action='append', default=[])
    parser.add_argument('--recursive', action='store_true', help='Pass -r so SUBDIRS children get records')
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args(argv)
    try:
        model = export_model(args.source_dir, args.projects, qmake=args.qmake, profile=args.profile,
                             output=args.output, qmake_args=args.qmake_arg, features=args.features,
                             recursive=args.recursive, timeout=args.timeout)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(model['counts']))
    return 1 if model['failures'] else 0
