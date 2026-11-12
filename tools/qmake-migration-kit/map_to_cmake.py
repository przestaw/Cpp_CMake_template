#!/usr/bin/env python3
"""Compatibility entry point; see `python3 qmig.py map`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qmigrate.mapper import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
