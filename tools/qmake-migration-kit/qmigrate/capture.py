"""Capture what a qmake or CMake build actually executes and export it as a build tree.

Both builds run their compilers, linkers and archivers through ccwrap.py:
qmake via the migration_capture feature, CMake via <LANG>_COMPILER_LAUNCHER and
<LANG>_LINKER_LAUNCHER (Makefile and Ninja generators). CMake static libraries,
which have no launcher, come from the CMake File API.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from qmigrate.cmdline import artifact_key, lib_identity, parse_compile, parse_link
from qmigrate.export import feature_env, qmake_query

KIT = Path(__file__).resolve().parent.parent
WRAPPER = Path(__file__).resolve().parent / 'ccwrap.py'
WINDOWS = os.name == 'nt'
GENERATED_NAME = re.compile(r'^(moc_|qrc_|ui_|mocs_compilation|qmlcache_|qmltyperegistrations)|_autogen[\\/]|\.rcc[\\/]')


class CaptureError(RuntimeError):
    pass


def shell_join(parts: list[str]) -> str:
    return subprocess.list2cmdline(parts) if WINDOWS else ' '.join(shlex.quote(p) for p in parts)


def run_logged(command: list, log: Path, **kwargs) -> int:
    with open(log, 'ab') as fh:
        fh.write(('$ ' + shell_join([str(c) for c in command]) + '\n').encode())
        fh.flush()
        return subprocess.run([str(c) for c in command], stdout=fh, stderr=subprocess.STDOUT, **kwargs).returncode


def default_make(jobs: int, keep_going: bool) -> list[str]:
    if WINDOWS:
        tool = ['jom', f'-j{jobs}'] if shutil.which('jom') else ['nmake', '/nologo']
        return tool + (['/K'] if keep_going else [])
    return ['make', f'-j{jobs}'] + (['-k'] if keep_going else [])


def space_free_tempdir(prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    if ' ' in str(path):
        raise CaptureError(f'temporary directory {path} contains spaces; qmake install rules do not quote '
                           'INSTALL_ROOT. Set TMPDIR/TEMP to a path without spaces')
    return path


# ---------------------------------------------------------------- qmake build
def capture_qmake(*, source_root: Path, projects: list[str], qmake: str, qmake_args: list[str],
                  features: list[Path], out: Path, env: dict | None = None, make: list[str] | None = None,
                  jobs: int = 2, keep_going: bool = False, install: bool = True) -> dict:
    out = Path(out).resolve()
    source_root = Path(source_root).resolve()
    out.mkdir(parents=True)
    log_dir, build_root = out / 'log', out / 'build'
    build_root.mkdir()
    base_env = feature_env(features, env)
    base_env['MIGRATION_CAPTURE_PREFIX'] = shell_join([sys.executable, str(WRAPPER), str(log_dir)])
    make_cmd = list(make) if make else default_make(jobs, keep_going)
    if make and keep_going:
        make_cmd += ['/K'] if 'nmake' in make[0].lower() else ['-k']
    steps, ok = [], True
    install_root = space_free_tempdir('qmig_install_') if install else None
    for index, project in enumerate(projects):
        build = build_root / str(index)
        build.mkdir()
        log = out / f'build-{index}.log'
        rc = run_logged([qmake, '-r', source_root / project, 'CONFIG+=migration_capture', *qmake_args],
                        log, cwd=build, env=base_env)
        steps.append(dict(project=project, step='qmake', rc=rc))
        if rc:
            ok = False
            continue
        rc = run_logged(make_cmd, log, cwd=build, env=base_env)
        steps.append(dict(project=project, step='make', rc=rc))
        ok = ok and rc == 0
        if install_root and rc == 0:
            rc = run_logged(make_cmd + ['install', f'INSTALL_ROOT={install_root}'], log, cwd=build, env=base_env)
            steps.append(dict(project=project, step='install', rc=rc))
            ok = ok and rc == 0
    if install_root:
        shutil.copytree(install_root, out / 'install', symlinks=True)
        shutil.rmtree(install_root, ignore_errors=True)
    query = qmake_query(qmake, base_env)
    return dict(buildSystem='qmake', sourceRoot=str(source_root), buildRoot=str(build_root), logDir=str(log_dir),
                steps=steps, buildOk=ok, qt=query, installDir=str(out / 'install') if install else None)


# ---------------------------------------------------------------- CMake build
def capture_cmake(*, cmake_source: Path, source_root: Path, out: Path, cmake: str = 'cmake',
                  generator: str | None = None, build_type: str = 'Release', args: list[str] = (),
                  env: dict | None = None, jobs: int = 2, keep_going: bool = False, install: bool = True,
                  qmake: str | None = None) -> dict:
    out, cmake_source, source_root = Path(out).resolve(), Path(cmake_source).resolve(), Path(source_root).resolve()
    out.mkdir(parents=True)
    log_dir, build = out / 'log', out / 'build'
    query_dir = build / '.cmake' / 'api' / 'v1' / 'query' / 'client-qmigrate'
    query_dir.mkdir(parents=True)
    (query_dir / 'query.json').write_text(json.dumps({'requests': [{'kind': 'codemodel', 'version': 2}]}))
    launcher = ';'.join([sys.executable.replace('\\', '/'), str(WRAPPER).replace('\\', '/'), str(log_dir).replace('\\', '/')])
    env = dict(os.environ if env is None else env)
    gen = ['-G', generator] if generator else (['-G', 'NMake Makefiles'] if WINDOWS else [])
    configure = [cmake, '-S', cmake_source, '-B', build, *gen, f'-DCMAKE_BUILD_TYPE={build_type}',
                 '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
                 f'-DCMAKE_C_COMPILER_LAUNCHER={launcher};cc', f'-DCMAKE_CXX_COMPILER_LAUNCHER={launcher};cxx',
                 f'-DCMAKE_C_LINKER_LAUNCHER={launcher};link', f'-DCMAKE_CXX_LINKER_LAUNCHER={launcher};link', *args]
    log = out / 'build.log'
    steps = []
    rc = run_logged(configure, log, env=env)
    steps.append(dict(step='configure', rc=rc))
    ok = rc == 0
    if ok:
        native = []
        if keep_going:
            name = (generator or '').lower()
            native = ['--', '-k', '0'] if 'ninja' in name else (['--', '/K'] if WINDOWS and not generator else ['--', '-k'])
        rc = run_logged([cmake, '--build', build, '--parallel', str(jobs), *native], log, env=env)
        steps.append(dict(step='build', rc=rc))
        ok = rc == 0
        if install and ok:
            rc = run_logged([cmake, '--install', build, '--prefix', out / 'install'], log, env=env)
            steps.append(dict(step='install', rc=rc))
            ok = rc == 0
    return dict(buildSystem='cmake', sourceRoot=str(source_root), cmakeSource=str(cmake_source),
                buildRoot=str(build), logDir=str(log_dir), steps=steps, buildOk=ok,
                qt=qmake_query(qmake, env) if qmake else {}, installDir=str(out / 'install') if install else None,
                fileApi=read_file_api(build, cmake_source, build_type))


def read_file_api(build: Path, source: Path, build_type: str | None = None) -> list[dict]:
    reply = build / '.cmake' / 'api' / 'v1' / 'reply'
    indexes = sorted(reply.glob('index-*.json'))
    if not indexes:
        return []
    index = json.loads(indexes[-1].read_text())
    codemodel = next((o for o in index.get('objects', []) if o.get('kind') == 'codemodel'), None)
    if not codemodel:
        return []
    model = json.loads((reply / codemodel['jsonFile']).read_text())
    src_dir = Path(model.get('paths', {}).get('source', str(source)))
    configs = model.get('configurations', [])
    matched = [c for c in configs if build_type and (c.get('name') or '').lower() == build_type.lower()]
    targets = []
    for config in (matched[:1] or configs[:1]):
        for ref in config.get('targets', []):
            t = json.loads((reply / ref['jsonFile']).read_text())
            sources = []
            for s in t.get('sources', []):
                path = Path(s['path'])
                sources.append(str(path if path.is_absolute() else src_dir / path))
            targets.append(dict(name=t['name'], type=t['type'],
                                artifacts=[str(build / a['path']) if not Path(a['path']).is_absolute() else a['path']
                                           for a in t.get('artifacts', [])],
                                sources=sources))
    return targets


# ---------------------------------------------------------------- normalisation
class Tokens:
    def __init__(self, source_root: str, build_root: str, qt_headers: list[str]):
        prefixes = [(build_root, '${BUILD}'), (source_root, '${SRC}')] + [(h, '${QT}') for h in qt_headers if h]
        self.prefixes = sorted(((self._n(p), t) for p, t in prefixes if p), key=lambda x: -len(x[0]))
        self.build_root = self._n(build_root)
        self.source_root = self._n(source_root)
        self.qt_headers = [self._n(h) for h in qt_headers if h]

    @staticmethod
    def _n(path: str) -> str:
        path = os.path.normpath(path).replace('\\', '/')
        return path.lower() if WINDOWS else path

    def tok(self, path: str | None) -> str | None:
        if path is None:
            return None
        n = self._n(path)
        for prefix, token in self.prefixes:
            if n == prefix or n.startswith(prefix + '/'):
                return token + n[len(prefix):]
        return n

    def category(self, path: str) -> str:
        n = self._n(path)
        if n == self.build_root or n.startswith(self.build_root + '/'):
            return 'generated'
        if any(n == h or n.startswith(h + '/') for h in self.qt_headers) or '/mkspecs/' in n + '/' \
                or re.search(r'/(include|headers)(/[^/]+-linux-gnu)?/qt[56](/|$)', n, re.I):
            return 'qt'
        if n == self.source_root or n.startswith(self.source_root + '/'):
            return 'source'
        return 'external'


def readelf_info(path: Path) -> dict | None:
    if not shutil.which('readelf'):
        return None
    try:
        out = subprocess.run(['readelf', '-d', str(path)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=60).stdout.decode(errors='replace')
    except (OSError, subprocess.SubprocessError):
        return None
    info = dict(needed=[], runpath=[], rpath=[])
    for line in out.splitlines():
        m = re.search(r'\((NEEDED|RUNPATH|RPATH)\).*\[(.*)\]', line)
        if m:
            key = {'NEEDED': 'needed', 'RUNPATH': 'runpath', 'RPATH': 'rpath'}[m.group(1)]
            info[key] += m.group(2).split(':') if key != 'needed' else [m.group(2)]
    return info


def inventory(root: Path, tokens: Tokens) -> dict:
    files = {}
    if not root.is_dir():
        return files
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            files[path.relative_to(root).as_posix()] = dict(symlink=os.readlink(path))
            continue
        if not path.is_file():
            continue
        entry = dict(size=path.stat().st_size, executable=os.access(path, os.X_OK))
        with open(path, 'rb') as fh:
            if fh.read(4) == b'\x7fELF':
                elf = readelf_info(path)
                if elf:
                    elf['runpath'] = [tokens.tok(p) if p.startswith('/') else p for p in elf['runpath']]
                    elf['rpath'] = [tokens.tok(p) if p.startswith('/') else p for p in elf['rpath']]
                    entry['elf'] = elf
        files[path.relative_to(root).as_posix()] = entry
    return files


def normalise(info: dict, out: Path, profile: str) -> dict:
    qt = info.get('qt') or {}
    headers = [qt.get('QT_INSTALL_HEADERS', '')]
    tokens = Tokens(info['sourceRoot'], info['buildRoot'], headers)
    compiles, links, preprocess, unparsed = [], [], 0, []
    object_to_compile = {}
    for record_file in sorted(Path(info['logDir']).glob('*.json')):
        rec = json.loads(record_file.read_text(encoding='utf-8'))
        kind = rec['kind']
        try:
            if kind in ('cc', 'cxx'):
                p = parse_compile(rec['argv'], rec['cwd'], responses=rec.get('responses'))
                if p['preprocessOnly'] or not p['sources'] or not p['compileOnly']:
                    preprocess += 1
                    continue
                for src in p['sources']:
                    obj = p['output']
                    if obj and (len(p['sources']) > 1 or obj.endswith('/') or Path(obj).is_dir()):
                        obj = obj.rstrip('/') + '/' + Path(src).stem + '.obj'
                    entry = dict(
                        source=tokens.tok(src), object=obj, lang=p['lang'], tool=p['tool'], dialect=p['dialect'],
                        defines=[[n, v] for n, v in p['defines']], undefs=p['undefs'],
                        includes=[dict(path=tokens.tok(i['path']), kind=i['kind'], category=tokens.category(i['path']))
                                  for i in p['includes']],
                        forcedIncludes=[tokens.tok(f) for f in p['forcedIncludes']],
                        std=p['std'], opt=p['opt'], debug=p['debug'], pic=p['pic'], runtime=p['runtime'],
                        warnings=p['warnings'], other=p['other'], failed=rec['rc'] != 0,
                        generated=tokens.category(src) == 'generated' or bool(GENERATED_NAME.search(src.replace('\\', '/'))),
                        artifact=None)
                    compiles.append(entry)
                    if obj:
                        object_to_compile[Tokens._n(obj)] = entry
            elif kind in ('link', 'ar', 'lib'):
                p = parse_link(rec['argv'], rec['cwd'], kind, responses=rec.get('responses'))
                if p['preprocessOnly'] or not p['output']:
                    preprocess += 1
                    continue
                p['failed'] = rec['rc'] != 0
                links.append(p)
        except Exception as error:  # keep the evidence, never abort the export on one odd command
            unparsed.append(dict(file=record_file.name, error=str(error)))
    artifacts = {}
    for p in links:
        key = artifact_key(p['output'])
        members = [object_to_compile.get(Tokens._n(o)) for o in p['objects']]
        for m in members:
            if m is not None:
                m['artifact'] = key
        artifacts[key] = dict(kind=p['kind'], output=tokens.tok(p['output']), failed=p['failed'],
                              libs=sorted({lib_identity(l.split()[-1]) for l in p['libs']}),
                              libdirs=[tokens.tok(d) for d in p['libdirs']],
                              rpath=[tokens.tok(r) if r.startswith('/') else r for r in p['rpath']],
                              flags=p['flags'], objects=len(p['objects']),
                              unmatchedObjects=sum(1 for m in members if m is None))
    for target in info.get('fileApi', []):
        if target['type'] != 'STATIC_LIBRARY' or not target['artifacts']:
            continue
        key = artifact_key(target['artifacts'][0])
        wanted = {Tokens._n(s) for s in target['sources']}
        for c in compiles:
            if c['artifact'] is None and c['source'] and Tokens._n(
                    c['source'].replace('${SRC}', info['sourceRoot']).replace('${BUILD}', info['buildRoot'])) in wanted:
                c['artifact'] = key
        artifacts.setdefault(key, dict(kind='static', output=tokens.tok(target['artifacts'][0]), failed=False,
                                       libs=[], libdirs=[], rpath=[], flags=[], objects=None, unmatchedObjects=0,
                                       fromFileApi=True))
    for key, art in artifacts.items():
        mine = [c for c in compiles if c['artifact'] == key]
        art['sources'] = sorted({c['source'] for c in mine if not c['generated']})
        art['generatedSources'] = sum(1 for c in mine if c['generated'])
    tree = dict(schemaVersion=1, buildSystem=info['buildSystem'], profile=profile,
                created=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
                sourceRoot=info['sourceRoot'], buildRoot=info['buildRoot'], qt=qt, steps=info['steps'],
                buildOk=info['buildOk'],
                counts=dict(compiles=len(compiles), failedCompiles=sum(c['failed'] for c in compiles),
                            links=len(links), preprocessOnly=preprocess, unparsed=len(unparsed)),
                unparsed=unparsed, compiles=compiles, artifacts=artifacts,
                install=inventory(Path(info['installDir']), tokens) if info.get('installDir') else None)
    (out / 'buildtree.json').write_text(json.dumps(tree, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return tree
