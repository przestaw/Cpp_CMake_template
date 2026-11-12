# ==== SHARED LIBRARY VERSION & SONAME ====
# qmake `TEMPLATE = lib` with `VERSION = 1.0.0` creates `.so.1.0.0`, `.so.1.0`,
# `.so.1`, and `.so` symlinks on Unix, whereas CMake omits version suffixes unless
# VERSION and SOVERSION are set explicitly.
set_target_properties(shared_component PROPERTIES
    VERSION 1.0.0
    SOVERSION 1
)
# Note: CMake creates `.so.1.0.0` -> `.so.1` -> `.so` (omitting `.so.1.0`).
# Add an install symlink step only if an external loader or package spec requires `.so.1.0`.
