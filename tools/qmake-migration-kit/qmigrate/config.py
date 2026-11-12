"""Workflow configuration (workflow.json + optional workflow.local.json) and the evidence workspace.

Shared settings live in workflow.json (commit it). Host-specific settings, such as qmake
paths or job counts, go into <name>.local.json next to it (do not commit it); it is
deep-merged over the shared file, like CMakeUserPresets.json over CMakePresets.json.
Strings may use ${env:NAME} and ${configDir}.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
from pathlib import Path

DEFAULT_GATES = {'lint': 'error', 'qt6': 'never', 'compare': 'error', 'map': 'never'}
ARTIFACT_KINDS = ('model', 'lint', 'qt6', 'draft', 'buildtree-qmake', 'buildtree-cmake', 'compare')


class ConfigError(ValueError):
    pass


def deep_merge(base, override):
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            merged[key] = deep_merge(base.get(key), value) if key in base else value
        return merged
    return override


def expand(value, config_dir: Path):
    if isinstance(value, str):
        value = value.replace('${configDir}', str(config_dir))

        def env(m):
            if m.group(1) not in os.environ:
                raise ConfigError(f'environment variable {m.group(1)} is not set (used in workflow config)')
            return os.environ[m.group(1)]
        return re.sub(r'\$\{env:(\w+)\}', env, value)
    if isinstance(value, list):
        return [expand(v, config_dir) for v in value]
    if isinstance(value, dict):
        return {k: expand(v, config_dir) for k, v in value.items()}
    return value


class Workflow:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise ConfigError(f'{self.path} not found (create one with `qmig init`)')
        data = json.loads(self.path.read_text(encoding='utf-8'))
        local = self.path.with_name(self.path.stem + '.local.json')
        if local.is_file():
            data = deep_merge(data, json.loads(local.read_text(encoding='utf-8')))
        self.dir = self.path.parent
        self.data = expand(data, self.dir)
        for key in ('sourceRoot', 'workspace', 'projects', 'profiles'):
            if key not in self.data:
                raise ConfigError(f'{self.path}: missing "{key}"')
        if not self.data['profiles']:
            raise ConfigError(f'{self.path}: no profiles')
        self.source_root = self.resolve(self.data['sourceRoot'])
        self.workspace = self.resolve(self.data['workspace'])
        self.gates = dict(DEFAULT_GATES, **self.data.get('gates', {}))

    def resolve(self, path) -> Path | None:
        if path is None:
            return None
        p = Path(path)
        return (p if p.is_absolute() else self.dir / p).resolve()

    def profile(self, name: str | None) -> tuple[str, dict]:
        profiles = self.data['profiles']
        if name is None:
            if len(profiles) != 1:
                raise ConfigError(f'choose a profile with -p: {", ".join(profiles)}')
            name = next(iter(profiles))
        if name not in profiles:
            raise ConfigError(f'unknown profile {name!r}; known: {", ".join(profiles)}')
        prof = dict(profiles[name])
        prof.setdefault('qmake', 'qmake')
        prof.setdefault('qmakeArgs', [])
        prof.setdefault('env', {})
        prof.setdefault('jobs', os.cpu_count() or 2)
        prof.setdefault('cmake', {})
        return name, prof

    def env(self, prof: dict) -> dict:
        env = dict(os.environ)
        env.update({k: str(v) for k, v in prof.get('env', {}).items()})
        return env

    def adapter(self) -> dict:
        path = self.resolve(self.data.get('adapter'))
        return json.loads(path.read_text(encoding='utf-8')) if path else {}

    def policy(self) -> dict:
        path = self.resolve(self.data.get('policy'))
        return json.loads(path.read_text(encoding='utf-8')) if path else {}

    def features(self) -> list[Path]:
        return [self.resolve(f) for f in self.data.get('features', [])]

    # ------------------------------------------------------------- workspace
    def new_artifact(self, kind: str, profile: str, suffix: str = '') -> Path:
        stamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
        base = self.workspace / profile
        base.mkdir(parents=True, exist_ok=True)
        for n in range(1000):
            path = base / f'{kind}-{stamp}{"-" + str(n) if n else ""}{suffix}'
            if not path.exists() and not path.with_suffix('.json').exists():
                return path
        raise ConfigError('cannot allocate an artifact name')

    def index(self) -> list[dict]:
        path = self.workspace / 'index.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []

    def record(self, kind: str, profile: str, path: Path, **info) -> dict:
        entries = self.index()
        entry = dict(kind=kind, profile=profile, path=os.path.relpath(path, self.workspace),
                     created=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), **info)
        entries.append(entry)
        self.workspace.mkdir(parents=True, exist_ok=True)
        tmp = self.workspace / 'index.json.tmp'
        tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        os.replace(tmp, self.workspace / 'index.json')
        return entry

    def latest(self, kind: str, profile: str | None = None, required: bool = True) -> Path | None:
        for entry in reversed(self.index()):
            if entry['kind'] == kind and (profile is None or entry['profile'] == profile):
                return (self.workspace / entry['path']).resolve()
        if required:
            raise ConfigError(f'no {kind} for profile {profile!r} yet; run the step that produces it first')
        return None


def discover(source_root: Path, skip=('.git', '.svn', 'node_modules', '.cmake')) -> tuple[list[str], list[str]]:
    """All .pro files, and those not referenced as a SUBDIRS child of another (suggested roots).
    Text-based and only a suggestion: the list in workflow.json is the authority."""
    pros = []
    for dirpath, dirnames, filenames in os.walk(source_root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip and not d.startswith('build'))
        for name in sorted(filenames):
            if name.endswith('.pro'):
                pros.append(Path(dirpath, name).resolve())
    children = set()
    for pro in pros:
        text = pro.read_text(encoding='utf-8', errors='replace')
        for m in re.finditer(r'^\s*SUBDIRS\s*\+?=\s*((?:[^\n\\]|\\\n)*)', text, re.M):
            for item in m.group(1).replace('\\\n', ' ').split():
                path = (pro.parent / item).resolve()
                children.add(path if path.suffix == '.pro' else path / f'{path.name}.pro')
        for m in re.finditer(r'^\s*(\w+)\.(?:subdir|file)\s*=\s*(\S+)', text, re.M):
            path = (pro.parent / m.group(2)).resolve()
            children.add(path if path.suffix == '.pro' else path / f'{path.name}.pro')
    rel = [p.relative_to(source_root).as_posix() for p in pros]
    roots = [p.relative_to(source_root).as_posix() for p in pros if p not in children]
    return rel, roots


def detect_qt_version(qmake: str) -> str:
    """Query QT_VERSION from qmake, returning '' if qmake is unavailable or fails."""
    try:
        out = subprocess.run([str(qmake), '-query', 'QT_VERSION'], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=15, check=True).stdout.decode(errors='replace').strip()
    except (OSError, subprocess.SubprocessError):
        return ''
    return out if re.match(r'^\d+\.\d+', out) else ''
