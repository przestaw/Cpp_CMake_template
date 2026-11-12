#!/usr/bin/env python3
"""qmig: qmake -> CMake and Qt 5 -> Qt 6 migration workflow. See README.md."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qmigrate.cli import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
