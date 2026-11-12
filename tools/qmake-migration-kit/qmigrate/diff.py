"""Compare qmake models and report configuration differences.

Example: python3 diff_models.py linux.json windows.json --summary

Absolute paths are normalised to ${SOURCE_ROOT}, ${OUT_PWD} and ${RUN_DIR}
before comparison. Exit code: 0, or 2 with --fail-on-diff when differences exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from qmigrate.model import ModelError, load_model, normalize_record, select_records

NOISE = {
    "OBJECTS_DIR", "MOC_DIR", "UI_DIR", "RCC_DIR", "DESTDIR",
    "QMAKE_EXTENSION_SHLIB", "OUT_PWD", "_PRO_FILE_", "_PRO_FILE_PWD_",
}

CONFIG_NOISE = {
    "debug", "release", "debug_and_release_target", "debug_info",
    "incremental", "flat", "build_pass",
}

STRUCTURED = ("installs", "compilers", "extraTargets", "subdirs", "substitutes")


def diff_lists(va: list, vb: list) -> dict | None:
    """Multiset difference; a pure reordering is reported, because order matters
    for LIBS, INCLUDEPATH and command lines."""
    if va == vb:
        return None
    ca, cb = Counter(va), Counter(vb)
    added = list((cb - ca).elements())
    removed = list((ca - cb).elements())
    change = {"added": added, "removed": removed}
    if not added and not removed:
        change["reordered"] = True
    return change


def flatten(record: dict, section: str) -> dict[str, list]:
    """installs/compilers/... -> {'name.key': [values]} (compiler inputs as name.inputs.VAR)."""
    flat: dict[str, list] = {}
    for name, keys in record.get(section, {}).items():
        for key, values in keys.items():
            if key == "inputs" and isinstance(values, dict):
                for var, items in values.items():
                    flat[f"{name}.inputs.{var}"] = items
            else:
                flat[f"{name}.{key}"] = values
    return flat


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base", type=Path, help="baseline model (usually Linux)")
    ap.add_argument("other", type=Path, help="comparison model (usually Windows)")
    ap.add_argument("--var", action="append", default=None,
                    help="compare selected variables (repeatable)")
    ap.add_argument("--all-vars", action="store_true",
                    help="include intermediate-directory variables")
    ap.add_argument("--variant", choices=["debug", "release"],
                    help="select records from debug_and_release exports")
    ap.add_argument("--no-normalize", action="store_true",
                    help="compare absolute paths literally")
    ap.add_argument("--no-structured", action="store_true",
                    help="skip INSTALLS, custom compilers, extra targets, subdirs and substitutes")
    ap.add_argument("--allow-incomplete", action="store_true",
                    help="compare models that recorded failed projects")
    ap.add_argument("--summary", action="store_true",
                    help="summarize project differences by variable")
    ap.add_argument("--fail-on-diff", action="store_true",
                    help="exit with code 2 when any difference is found")
    ap.add_argument("--json", type=Path, default=None,
                    help="write the full difference report to JSON")
    args = ap.parse_args(argv)

    try:
        models = [load_model(p, args.allow_incomplete) for p in (args.base, args.other)]
        base, other = (select_records(m, args.variant) for m in models)
    except ModelError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if not args.no_normalize:
        base = {k: normalize_record(v, models[0]) for k, v in base.items()}
        other = {k: normalize_record(v, models[1]) for k, v in other.items()}
    skip = set() if args.all_vars else NOISE
    wanted = set(args.var) if args.var else None

    only_base = sorted(set(base) - set(other))
    only_other = sorted(set(other) - set(base))

    per_var: Counter[str] = Counter()
    diffs: dict[str, dict] = {}

    for src in sorted(set(base) & set(other)):
        entry: dict[str, dict] = {}
        sections = [("", base[src]["vars"], other[src]["vars"])]
        if not args.no_structured and not wanted:
            sections += [(f"{s}:", flatten(base[src], s), flatten(other[src], s)) for s in STRUCTURED]
        for prefix, a, b in sections:
            for key in sorted(set(a) | set(b)):
                if not prefix and (key in skip or (wanted and key not in wanted)):
                    continue
                change = diff_lists(a.get(key, []), b.get(key, []))
                if change is None:
                    continue
                if key == "CONFIG" and not prefix:
                    change["added"] = [x for x in change["added"] if x not in CONFIG_NOISE]
                    change["removed"] = [x for x in change["removed"] if x not in CONFIG_NOISE]
                    if not change["added"] and not change["removed"]:
                        continue
                entry[prefix + key] = change
                per_var[prefix + key] += 1
        if entry:
            diffs[src] = entry

    print(f"shared projects     : {len(set(base) & set(other))}")
    print(f"only in {args.base.name}: {len(only_base)}")
    print(f"only in {args.other.name}: {len(only_other)}")
    print(f"projects with differences   : {len(diffs)}")
    print()
    print("differences by variable (project count):")
    for key, count in per_var.most_common():
        print(f"  {count:5d}  {key}")

    if not args.summary:
        for label, items in ((args.base.name, only_base), (args.other.name, only_other)):
            if items:
                print(f"\nonly in {label}:")
                for src in items:
                    print(f"    {src}")
        print()
        for src, entry in diffs.items():
            print(f"# {src}")
            for key, change in entry.items():
                if change["added"]:
                    print(f"    {key} +: {change['added']}")
                if change["removed"]:
                    print(f"    {key} -: {change['removed']}")
                if change.get("reordered"):
                    print(f"    {key} : same items, different order")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({
                "base": str(args.base),
                "other": str(args.other),
                "variant": args.variant,
                "normalized": not args.no_normalize,
                "onlyInBase": only_base,
                "onlyInOther": only_other,
                "perVariable": dict(per_var),
                "differences": diffs,
            }, fh, indent=2, ensure_ascii=False)
        print(f"\nwritten: {args.json}")

    has_diff = bool(diffs or only_base or only_other)
    return 2 if args.fail_on_diff and has_diff else 0


