#!/usr/bin/env python3
"""Compatibility entry point; see `python3 qmig.py diff`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qmigrate.diff import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
