# qmake → CMake Reference Slice & Snippets

**English** | [Polski](README.pl.md)

Self-contained reference example accompanying [`docs/qmake-cmake-guide.md`](../../docs/qmake-cmake-guide.md). Demonstrates a side-by-side `qmake` (`before/`) and `CMake 3.25+` (`after/`) build over the exact same C++/Qt source tree (`common/`):

- a shared library (`democore`) exporting both a `QObject` class (`Counter`) and a Qt namespace meta-object (`Demo::Mode` via `Q_NAMESPACE_EXPORT`),
- `PRIVATE` Windows DLL export macro ownership (`DEMO_CORE_BUILD` rejected at compile time if leaked to `demo`),
- a custom `.prf` feature contract (`DEMO_FEATURE_LOADED`) and a Python schema-to-header code generator (`generate.py`),
- isolated CMake snippet templates (`snippets/`), a dotted `.ui` header-guard collision reproduction (`uic-guard-case/`), and a phase-by-phase verification checklist (`parity-checklist.csv`).

> **Scope note:** This directory is a reference template and learning slice, not a drop-in converter. Snippets under `snippets/` are standalone patterns meant to be adapted to your own target names and dependency packages.

## Directory Layout

```text
examples/qmake-migration/
├── common/                         # Shared C++17 / Qt (5.15+ or 6) sources & schema generator
│   ├── factor.schema
│   ├── generate.py
│   ├── include/demo/{core_export.h,counter.h}
│   └── src/{counter.cpp,main.cpp}
├── before/                         # Legacy qmake SUBDIRS baseline (.pro / .pri / .prf)
│   ├── demo.pro
│   ├── settings.pri
│   ├── features/demo_rules.prf
│   ├── core/core.pro
│   └── app/app.pro
├── after/                          # Target-based CMake 3.25+ equivalent & presets
│   ├── CMakeLists.txt
│   ├── CMakePresets.json
│   └── CMakeUserPresets.json.example
├── snippets/                       # Isolated CMake & C++20 reference patterns
│   ├── allocator-header-example.h
│   ├── dependency-metadata.cmake
│   ├── generated-forms-ordering.cmake
│   ├── install-versioning.cmake
│   ├── target-options.cmake
│   └── windows-imported-library.cmake
├── uic-guard-case/                 # Dotted .ui filename guard-collision reproduction
└── parity-checklist.csv            # Phase-by-phase migration acceptance checklist
```

## Building & Running the Reference Slice

Set `TUTORIAL_QT_ROOT` to your local Qt 5.15+ (or Qt 6) prefix (for example `/opt/Qt/5.15.2/gcc_64` on Linux or `C:\Qt\5.15.2\msvc2019_64` on Windows). Expected runtime output for `common/factor.schema` (`7`) is:

```text
Counter:7:Normal
```

### Linux — `before/` (`qmake` baseline)

```sh
export TUTORIAL_QT_ROOT=/opt/Qt/5.15.2/gcc_64
mkdir -p build-qmake && cd build-qmake
QMAKEFEATURES="$PWD/../before/features" "$TUTORIAL_QT_ROOT/bin/qmake" ../before/demo.pro
make -j2
./bin/demo
```

### Linux — `after/` (`CMake` candidate)

```sh
cmake -S after -B build-cmake -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="$TUTORIAL_QT_ROOT"
cmake --build build-cmake --parallel 2
./build-cmake/bin/demo
cmake --install build-cmake --prefix "$PWD/stage-cmake"
```

To build against Qt 6 instead of Qt 5, use a fresh build directory and pass `-DTUTORIAL_QT_MAJOR=6` with a Qt 6 `CMAKE_PREFIX_PATH` so CMake never switches Qt majors implicitly.

### Windows (MSVC x64) — `before/` and `after/`

Open an **x64 Native Tools Command Prompt for VS 2022**:

```bat
set "TUTORIAL_QT_ROOT=C:\Qt\5.15.2\msvc2019_64"
set "PATH=%TUTORIAL_QT_ROOT%\bin;%PATH%"

mkdir build-qmake-win && pushd build-qmake-win
set "QMAKEFEATURES=%CD%\..\before\features"
"%TUTORIAL_QT_ROOT%\bin\qmake.exe" ..\before\demo.pro PYTHON=python
nmake /nologo
bin\demo.exe
popd

cmake -S after -B build-cmake-win -G Ninja ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_PREFIX_PATH="%TUTORIAL_QT_ROOT%"
cmake --build build-cmake-win --parallel 2
build-cmake-win\bin\demo.exe
```

### Using `CMakeUserPresets.json`

Inside `after/`, copy `CMakeUserPresets.json.example` to `CMakeUserPresets.json` (git-ignored) and configure via preset:

```sh
cd after
cp CMakeUserPresets.json.example CMakeUserPresets.json
cmake --preset local-linux      # or local-windows on MSVC x64
cmake --build --preset local-linux
```

## Intentional Boundaries of This Slice

- Shared-library `VERSION` / `SOVERSION` symlinks (see [`snippets/install-versioning.cmake`](snippets/install-versioning.cmake)), installed `INSTALL_RPATH`, `Config.cmake` SDK exports, and `windeployqt` / `macdeployqt` bundling are omitted from `after/CMakeLists.txt` so the core `SUBDIRS` + DLL export + `AUTOMOC` + custom codegen mapping stays minimal.
