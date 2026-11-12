# ==== SHARED PROJECT SETTINGS ====
# Single-variant release baseline (disables MSVC default debug_and_release multi-pass).
CONFIG += release c++17
CONFIG -= debug debug_and_release

# Allow Windows nmake invocations to override `PYTHON=python` when `python3` is absent.
isEmpty(PYTHON): PYTHON = python3

# Load `before/features/demo_rules.prf` resolved via the QMAKEFEATURES environment variable.
load(demo_rules)
