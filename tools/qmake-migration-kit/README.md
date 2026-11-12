# qmig: qmake → CMake and Qt 5 → Qt 6 migration workflow

**English** | [Polski](README.pl.md)

`qmig` provides customizable reference probes and workflow scripts for migrating qmake-based Qt projects through build-tree evidence rather than blind syntax translation.

- qmake evaluates the project. A probe feature exports the result as a model.
- A linter flags defines and flags that qmake passes through silently but that change meaning under CMake.
- A mapper generates a CMake draft and a report of everything it did not translate.
- Both builds run with their compilers and linkers wrapped. Every real command line is recorded and exported as a build tree.
- `compare` classifies every difference between the two build trees: per translation unit, per artifact and per installed file.
- `qt6` checks the model, the installed Qt 6 and the sources for what changes with Qt 6.

Every step writes new evidence into a workspace and never overwrites earlier results. Each step can act as a gate in CI.

> **Scope:** `qmig` is a customizable reference script skeleton, not a universal automatic converter for arbitrary repositories. Real-world codebases require project-specific adaptation (`adapter.json`, `policy.json`, custom codegen rules, and per-host preset orchestration) so that every unmapped construct or flag difference is resolved explicitly.

Principles behind the mapping and target Qt 6 + CMake 3.25+ idioms are documented in [`../../docs/qmake-cmake-guide.md`](../../docs/qmake-cmake-guide.md).

## Requirements

- Python 3.9+, standard library only.
- The qmake of every Qt you build with.
- CMake 3.21+, needed for `<LANG>_LINKER_LAUNCHER` and the File API (3.25+ recommended for presets/workflows).
- A Makefile or Ninja generator for CMake capture. The Visual Studio generator does not support launchers.
- `readelf` (optional): `RUNPATH` and `NEEDED` in the install comparison.

## Quick start

```sh
python3 qmig.py init --source-root /path/to/repo --qmake /path/to/Qt/5.15.2/gcc_64/bin/qmake
#   -> workflow.json: review "projects" (discovery only suggests SUBDIRS roots)
python3 qmig.py run -p qt5-release            # export, lint, qt6, map, capture both, compare
python3 qmig.py status                        # latest evidence and results per profile
```

Single steps:

```sh
qmig export  -p P          # qmake model (JSON) + raw records, Makefiles, logs
qmig lint    -p P          # static model checks: defines/flags qmake tolerated
qmig qt6     -p P [--qt6-qmake Q] [--target 6.5] [--scan-tree]
qmig map     -p P [--qt 5|6|dual|model] [--strict]
qmig capture qmake -p P [--keep-going] [--no-install]
qmig capture cmake -p P [--source DIR] [--qt-major 5|6] [--keep-going]
qmig compare -p P [--base qmake@P] [--candidate cmake@P2] [--fail-on error|warning|info|never]
qmig diff  A.json B.json [--variant release]     # two qmake models (e.g. Linux vs Windows)
```

`python3 qmig.py ...` and `python3 -m qmigrate ...` are equivalent. The standalone `export_model.py`, `diff_models.py` and `map_to_cmake.py` scripts also remain available as entry points.

## Concepts

- **Profile:** one qmake + platform + build type, plus how to build the CMake side (generator, build type, Qt mode, Qt major, extra arguments). Examples: `linux-qt5-release`, `linux-qt5-deprecated`, `windows-qt5-release`, `linux-qt6-release`.
- **Workspace:** `<workspace>/<profile>/<kind>-<timestamp>` plus `index.json`. Kinds are `model`, `lint`, `qt6`, `draft`, `buildtree-qmake`, `buildtree-cmake` and `compare`. Later steps use the latest artifact of their profile unless told otherwise.
- **Adapter** (`adapter`): project-specific mapping. Keys:
  - `libs`: `-lfoo` → imported target.
  - `tools`: a command token → a CMake expression.
  - `findPackages`.
  - `installPaths`: prefix rewrite.
  - `dropDefines`, `dropFlags`, `ignoreVars`.
  - `qt6Components`: per project.
  - `matchQmakeDefaults`: Release without `NDEBUG`, mkspec `-O2`/`/O2`, `-Wl,-O1`, and `warn_on` → `-Wall -Wextra`/`/W3`.
- **Policy** (`policy`): accepted differences, each with a mandatory `reason`. Matching uses `rule` (glob), `project` (glob) and `message` (substring). Accepted findings stay in the report as `accepted`.
- **Gates** (`gates`): per step, `error|warning|info|never`. A failed gate returns exit code 2. `run` stops at the first failure unless `--continue-on-failure` is given.
- **Local settings:** `workflow.local.json` next to `workflow.json` is deep-merged over it, like `CMakeUserPresets.json`. Strings may use `${env:NAME}` and `${configDir}`. See `examples/workflow.example.json`, `examples/adapter.example.json` and `examples/policy.example.json`.

## Recommended order

1. Build a baseline per profile with `export` + `lint`. Fix or accept lint errors before mapping.
2. Run `map --qt dual` on Qt 5.15, which uses versionless `Qt::` targets. Then `capture qmake`, `capture cmake` and `compare` until the gate passes, extending the adapter instead of hand-editing the draft. Choose `matchQmakeDefaults`, or accept the Release differences in the policy deliberately.
3. Run a deprecation build: a profile with `-DCMAKE_CXX_FLAGS=-DQT_DISABLE_DEPRECATED_BEFORE=0x050F00` and `capture cmake --keep-going`. Every failed translation unit uses API that Qt 6 removed. Qt 6.5+ calls the macro `QT_DISABLE_DEPRECATED_UP_TO`.
4. Run `qt6 --qt6-qmake <Qt 6 qmake>`:
   - modules removed or too new for the target,
   - modules missing from the installed Qt 6,
   - the C++17 requirement,
   - MSVC `/permissive-`,
   - a source scan.

   Components the scan needs, such as `Core5Compat`, `OpenGLWidgets`, `SvgWidgets` and `StateMachine`, flow into the next `map` automatically.
5. Port the code, then build the same dual draft with Qt 6 (`qtMajor: 6`). Compare it with the qmake/Qt 5 baseline: Qt-major differences are compared loosely, everything else strictly.
6. Retire qmake per product once `compare` passes on every profile and the install trees match, then adopt native Qt 6 `qt_standard_project_setup()` / `qt_add_executable()` / `qt_add_library()` targets (see [`../../docs/qmake-cmake-guide.md`](../../docs/qmake-cmake-guide.md)).

## Build tree export

The capture steps record what the build really ran:

- qmake builds use `CONFIG+=migration_capture` (`features/migration_capture.prf`). It wraps `QMAKE_CC`, `QMAKE_CXX`, `QMAKE_LINK*`, `QMAKE_AR` and `QMAKE_LIB` with `qmigrate/ccwrap.py`.
- CMake builds use `CMAKE_<LANG>_COMPILER_LAUNCHER` and `CMAKE_<LANG>_LINKER_LAUNCHER`. Static libraries, which have no launcher, and target membership come from the CMake File API (codemodel v2).

The wrapper writes one JSON file per call, which keeps parallel builds safe. It also stores the contents of response files, because nmake deletes them.

`buildtree.json` contains:
- per translation unit: source, artifact, defines (ordered, with values), undefs, include dirs with kind and category, forced includes, C++ standard, optimisation, debug info, PIC, MSVC runtime, warnings, other flags, failed state;
- per artifact: kind, sources, libraries by identity, library dirs, RPATH, link flags;
- the installed tree: files, executable bit, ELF `NEEDED` and `RUNPATH`.

Paths are tokenised as `${SRC}`, `${BUILD}` and `${QT}`, so builds from different directories compare on content. The parser handles GCC/Clang, MSVC `cl`/`clang-cl`, `link`, `lib` and `ar`, as well as `ccache`/`sccache`/`distcc` launchers. Unknown options go to `other` and are never dropped.

## What is checked

### `lint`: the qmake model, no build needed

| Rule | Why it matters under CMake |
|---|---|
| `lint.define.conflict` | `A=1` and `A=2`: qmake passes both, the compiler keeps the last one with a warning. |
| `lint.define.semicolon` | `;` splits a CMake list into two definitions. |
| `lint.define.quoting` | qmake pastes values into the shell unchanged; CMake escapes them for you. The draft removes one quoting level. |
| `lint.define.function-like`, `.hash`, `.dollar`, `.whitespace` | Escaping differs between generators. |
| `lint.flag.pair-dedup` | A repeated `-include`/`-isystem`/`-Xclang`… pair: CMake de-duplicates option words. The draft uses `SHELL:`. |
| `lint.flag.hidden-define`, `.hidden-include` | `-D`/`-I` in `QMAKE_CXXFLAGS`: moc does not see them under qmake, and CMake `AUTOMOC` uses only definitions and include dirs. |
| `lint.flag.space` | One qmake item containing spaces becomes one argument in CMake. |
| `lint.flag.dialect`, `.werror`, `.std-conflict`, `.linker-in-cflags` | Options that only worked by accident. |
| `lint.link.order-sensitive`, `.repeated-lib` | `--whole-archive` and `--start-group`: CMake reorders link items. Use `LINK_LIBRARY`/`LINK_GROUP` (CMake 3.24+). |
| `lint.include.missing` | qmake ignores missing dirs; imported targets fail on them. |

### `compare`: two build trees

| Rule | Example |
|---|---|
| `define.ndebug` | CMake Release defines `NDEBUG`, qmake release does not. `assert()` disappears. |
| `define.qt-no-debug`, `define.windows-implicit` (`UNICODE`…), `define.lost`/`added`/`value`/`quoting`/`undef`, `define.deprecation`, `define.qt-module` | Macro differences per translation unit. |
| `include.lost`/`added`/`order`/`kind`/`qt`/`qt-system`/`forced` | Header lookup differences, including Qt as `-isystem`. |
| `flags.std`, `std-extensions` (gnu++ vs c++), `std-qt6`, `optimization`, `msvc-runtime`, `werror`, `lost`/`added`, `pic`, `debug-info`, `warnings` | Compiler option differences. |
| `tu.missing`/`extra`/`artifact`, `artifact.missing`/`kind`/`source-lost` | Graph differences: what is compiled, and into what. |
| `link.no-undefined`, `link.subsystem`, `link.lib-lost`, `link.flag-lost`, `link.rpath` | Link differences. |
| `install.missing`/`extra`/`mode`/`rpath`/`needed` | CMake drops the build RPATH on install by default. |
| `build.failed`, `build.compile-failed`, `capture.empty-compile-set` | Failed builds or empty compile captures (0 TUs on one side vs >0 on the other); also how the deprecation build reports its findings. |

Identical differences across many files are merged into one finding with a count and sample files.

### `qt6`: Qt 5 → Qt 6 readiness

- Modules:
  - removed modules (XmlPatterns, Script, X11/Win/MacExtras, …);
  - modules that returned later than the target (Multimedia/SerialPort/Positioning/… 6.2, TextToSpeech 6.4, Location 6.5);
  - modules not installed in the target Qt 6, read from its `Qt6<Module>Config.cmake` files;
  - per-module notes.
- Build: C++ standard below 17 (Qt 6 adds the `cxx_std_17` compile feature to its consumers), and on MSVC specs the `-Zc:__cplusplus -permissive-` that Qt 6 adds to every consumer (verified in Qt 6.4.2's `QtFlagHandlingHelpers.cmake`).
- Also: `qtquickcompiler` and the deprecation level.
- Source scan of the files listed in the model (`--scan-tree`: the whole tree). Comments are ignored.
  - C++: `QRegExp`, `QTextCodec`, `QLinkedList`, `QStringRef`, SAX XML, `QDesktopWidget`, `qrand`, `QMatrix`, QtAlgorithms, `SkipEmptyParts`, `insertMulti`, `QVariant::Type`, `qVariant*`, `MidButton`, `sprintf`, `QFontMetrics::width`, high-DPI attributes, `QSound`, `QGL*`, moved OpenGL/SVG/state machine classes, Qt Script, bearer management, `QDirModel`, `grabWidget`, versioned style options, `toSet()`, `QDateTime(QDate)`, `Q_ENUMS`.
  - Includes: `<QtCore/QRegExp>`-style includes that do not resolve against `Core5Compat`.
  - QML: Controls 1, `QtGraphicalEffects`, Dialogs 1.

The module table is guidance; the installed Qt 6 is the authority. The scan is regex-based. Use it to find work, and use the deprecation build and `compare` as the proof.

## CMake draft modes (`map --qt`)

- `model`: Qt 5 or 6, as exported.
- `5` / `6`: `Qt5::`/`Qt6::` targets. `6` raises C++ to 17.
- `dual`: versionless `Qt::` targets (Qt 5.15+). It adds `find_package(QT NAMES Qt6 Qt5)` and links Qt 6-only components (`Core5Compat`, …) under `if(QT_VERSION_MAJOR GREATER_EQUAL 6)`. `-DQMIG_QT_MAJOR=5|6` makes the choice deterministic; without it, Qt 6 wins when both are found. The C++ standard stays as in qmake, and Qt 6 raises it to 17 through `cxx_std_17`.

## CI

```sh
python3 qmig.py run -c ci/workflow.json -p linux-qt5-release   # exit 0 = all gates passed
python3 qmig.py run -c ci/workflow.json -p linux-qt6-release --steps map,capture-cmake,compare \
        --keep-going --continue-on-failure
```

Archive `<workspace>/<profile>/*.md|*.json` and `buildtree.json`. Build directories can be deleted after that. Pin `gates` in `workflow.json` and put every accepted difference with its reason in the policy.

## Validated environments & limits

- **Validated environments:**
  - **Linux end-to-end builds & capture:** Verified on Linux with Qt 5.15 (5.15.13 & 5.15.15) and Qt 6.4.2, GCC 13, CMake 3.28, and Ninja (including temporary build paths with spaces): `verify_workflow.py` passes 25 checks (`init`, `hazards` runtime `NDEBUG` check + policy gates, `multi` with `matchQmakeDefaults`, and `qt5api` deprecation + dual Qt 5/Qt 6 build comparison) and `verify_demo.py` passes 35 checks (`debug_and_release` variants, custom codegen incremental rebuild & deleted-header regeneration, and `INSTALL_ROOT` layout parity).
  - **Unit test suite (`tests/`):** 25 Qt-free unit tests covering record parsing, command-line/response-file parsing (GCC/Clang & MSVC), build-tree comparison (including empty-capture gating), File API configuration matching, `qmig init` Qt 6 version detection, hazard linting, Qt 6 readiness rules, and config overrides — run continuously on Linux and Windows in `.github/workflows/ci.yml`.
  - **Unverified capture hosts:** Native Windows/MSVC (`cl`, `nmake`/`jom`) and macOS qmake/CMake build capture code paths exist in the wrapper/parser, but end-to-end capture on Windows/MSVC and macOS has not been executed yet. See [`KNOWN_GAPS.md`](KNOWN_GAPS.md) for details.
- The probe sees qmake's state during feature processing. Later phases can add settings. `capture` shows the final truth; `export` is the plan.
- Translation units are matched by source path and artifact. Unity builds, PCH, or sources compiled twice with different flags need a policy entry or a closer look. Generated units (`moc`/`rcc`/`uic`) are counted, not compared one by one.
- qmake's `make install` does not quote `INSTALL_ROOT`. The capture uses a temporary directory without spaces and fails clearly if `TMPDIR`/`TEMP` contains spaces.
- The mapper writes a draft; products still need their adapter. Everything it does not translate is listed in `mapping-report.md`.

## Verification

```sh
python3 -m unittest discover -s tests -v
python3 verify_demo.py --qmake /path/to/qt5/bin/qmake
python3 verify_workflow.py --qt5-qmake /path/to/qt5/bin/qmake --qt6-qmake /path/to/qt6/bin/qmake
```

The examples are:
- `examples/demo`: custom compiler and install;
- `examples/multi`: `SUBDIRS`, static library, `AUTOMOC`;
- `examples/hazards`: string define, double `-include`, hidden define, conflicting values, `assert` vs `NDEBUG`;
- `examples/qt5api`: Qt 5-only API, C++14.

The `hazards` check runs both binaries. The qmake build prints `asserts=on`, the CMake Release build prints `asserts=off`, and `compare` reports exactly that.

## License

Distributed as part of `Cpp_CMake_template` under the [MIT License](../../LICENSE).
