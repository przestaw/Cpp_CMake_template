"""Exported qmake model: record parsing, loading, variant selection, path normalisation."""
from __future__ import annotations

import json
from pathlib import Path

SEP = '|@|'
SCHEMA_VERSION = 2
SUPPORTED_SCHEMAS = {1, 2}


class ModelError(ValueError):
    pass


def parse_records(raw: str) -> list[dict]:
    """Parse probe output. Empty lines are ignored; unknown kinds are an error."""
    records = []
    current = None
    buckets = {'install': 'installs', 'compiler': 'compilers', 'extratarget': 'extraTargets',
               'subdir': 'subdirs', 'substitute': 'substitutes'}
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split(SEP)
        kind = fields[0]
        if fields == ['record', 'begin']:
            if current is not None:
                raise ValueError(f'line {number}: nested export record')
            current = dict(pro=None, meta={}, vars={}, installs={}, compilers={},
                           extraTargets={}, subdirs={}, substitutes={})
        elif fields == ['record', 'end']:
            if current is None or not current['pro']:
                raise ValueError(f'line {number}: incomplete export record')
            records.append(current)
            current = None
        elif current is None:
            raise ValueError(f'line {number}: data outside a record (multiline value?)')
        elif kind == 'pro':
            current['pro'] = SEP.join(fields[1:])
        elif kind == 'meta' and len(fields) >= 3:
            current['meta'][fields[1]] = SEP.join(fields[2:])
        elif kind == 'var' and len(fields) >= 3:
            current['vars'].setdefault(fields[1], []).append(SEP.join(fields[2:]))
        elif kind in buckets and len(fields) >= 4:
            entry = current[buckets[kind]].setdefault(fields[1], {})
            entry.setdefault(fields[2], []).append(SEP.join(fields[3:]))
        elif kind == 'compilerinput' and len(fields) >= 4:
            inputs = current['compilers'].setdefault(fields[1], {}).setdefault('inputs', {})
            inputs.setdefault(fields[2], []).append(SEP.join(fields[3:]))
        else:
            raise ValueError(f'line {number}: unrecognised record line {line[:80]!r} (multiline value?)')
    if current is not None:
        raise ValueError('truncated export record')
    return records


def load_model(path: Path, allow_incomplete: bool = False) -> dict:
    with open(path, encoding='utf-8') as fh:
        model = json.load(fh)
    if model.get('schemaVersion') not in SUPPORTED_SCHEMAS:
        raise ModelError(f'{path}: unsupported schemaVersion {model.get("schemaVersion")!r}')
    if model.get('failures') and not allow_incomplete:
        raise ModelError(f'{path}: incomplete export ({len(model["failures"])} failed projects); '
                         'fix the export or pass --allow-incomplete')
    return model


def select_records(model: dict, variant: str | None = None) -> dict[str, dict]:
    """One record per project. debug_and_release yields a top-level record plus one
    build-pass record per variant; without a variant such duplicates are rejected."""
    groups: dict[str, list[dict]] = {}
    for record in model['targets']:
        groups.setdefault(record['source'], []).append(record)
    selected = {}
    for source, records in groups.items():
        if variant:
            matching = [r for r in records if r.get('variant') == variant]
            matching = [r for r in matching if r.get('buildPass')] or matching
        else:
            matching = records
        if len(matching) != 1:
            hint = ('pass --variant debug|release' if not variant
                    else f'{len(matching)} records match variant {variant!r}')
            raise ModelError(f'{source}: {len(records)} records ({hint}; or export variants separately)')
        selected[source] = matching[0]
    return selected


def _replace_prefixes(value, prefixes):
    if isinstance(value, str):
        for old, new in prefixes:
            for form in {old, old.replace('\\', '/'), old.replace('/', '\\')}:
                if form and form in value:
                    value = value.replace(form, new)
        return value
    if isinstance(value, list):
        return [_replace_prefixes(v, prefixes) for v in value]
    if isinstance(value, dict):
        return {k: _replace_prefixes(v, prefixes) for k, v in value.items()}
    return value


def normalize_record(record: dict, model: dict) -> dict:
    """Replace run-specific absolute paths with ${OUT_PWD}, ${RUN_DIR}, ${SOURCE_ROOT}."""
    prefixes = []
    out_pwd = record['vars'].get('OUT_PWD', [''])[0]
    if out_pwd:
        prefixes.append((out_pwd, '${OUT_PWD}'))
    prefixes.append((model.get('runDir', ''), '${RUN_DIR}'))
    prefixes.append((model.get('sourceRoot', ''), '${SOURCE_ROOT}'))
    prefixes = sorted((p for p in prefixes if p[0]), key=lambda p: -len(p[0]))
    return _replace_prefixes(record, prefixes)


def model_files(record: dict, variables=('SOURCES', 'HEADERS', 'FORMS', 'RESOURCES', 'OBJECTIVE_SOURCES')) -> list[Path]:
    """Absolute paths of the files a record lists (relative entries resolve against the .pro dir)."""
    pro_dir = Path(record['vars']['_PRO_FILE_PWD_'][0])
    result = []
    for var in variables:
        for item in record['vars'].get(var, []):
            path = Path(item)
            result.append(path if path.is_absolute() else pro_dir / path)
    return result
