#!/usr/bin/env python3
"""Generate a C++ constant header from an integer schema file.

Usage:
    python generate.py <input.schema> <output.h>
"""
from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    value = int(Path(sys.argv[1]).read_text(encoding="utf-8").strip())
    output = Path(sys.argv[2])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "#pragma once\n"
        f"#define GENERATED_FACTOR {value}\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
