# C++20 CMake Project Template

**English** | [Polski](README.pl.md)

Clean, zero-dependency **C++20** starter template built on modern **CMake 3.25+** target-based architecture, `CMakePresets.json` (v6), CTest, and relocatable `find_package` export rules.

## Highlights

- **Zero mandatory external dependencies:** Compiles out of the box with any C++20 toolchain (`MSVC 19.30+`, `GCC 11+`, `Clang 14+`) and `Ninja`.
- **Target-scoped CMake 3.25+ design:** No global `include_directories()`, no `CMAKE_CXX_FLAGS_*` string concatenation, and no `file(GLOB ...)`.
- **First-class `CMakePresets.json` (v6):** Segmented out-of-source build (`out/build/<preset>`) and install (`out/install/<preset>`) trees for Windows and Linux.
- **Dual-mode unit testing:** Automatically uses `GTest` when available (e.g., via `vcpkg` or system packages) and falls back to a lightweight built-in C++20 assertion runner so `ctest` passes immediately on a fresh clone.
- **Downstream-ready package export:** Installs headers, generated `version.hpp`, and `cpp_templateConfig.cmake` for `find_package(cpp_template CONFIG REQUIRED)`.
- **Non-stale git versioning:** Recomputes semantic version and short commit hash on re-configure without freezing stale values in `CMakeCache.txt`.

## Project Layout

```text
.
├── .github/workflows/ci.yml          # Linux (GCC/Clang) & Windows (MSVC) CI pipeline
├── cmake/
│   ├── Config.cmake.in               # Package configuration template for find_package()
│   ├── add_project_target.cmake      # Common target setup (C++20, unity, IDE folders)
│   ├── git_version.cmake             # Plain-variable git tag & commit version stamp
│   └── target_warnings.cmake         # PRIVATE warnings, sanitizers, and clang-tidy
├── include/cpp_template/
│   ├── cli_parser.hpp                # Zero-dependency C++20 CLI argument parser
│   ├── greeter.hpp                   # Example library API using C++20 concepts
│   ├── version.hpp.in                # Template stamped into <build>/include/cpp_template/
│   └── error/exception.hpp           # Domain & CLI exception hierarchy
├── src/
│   ├── CMakeLists.txt                # Core library target (cpp_template::cpp_template)
│   ├── cli_parser.cpp
│   └── greeter.cpp
├── apps/
│   ├── CMakeLists.txt                # CLI executable target (cpp_template_cli)
│   └── main.cpp
├── tests/
│   ├── CMakeLists.txt                # Unit & CLI smoke tests registered with CTest
│   ├── test_framework.hpp            # GTest bridge + zero-dependency C++20 fallback
│   ├── cli_parser_tests.cpp
│   └── greeter_tests.cpp
├── CMakeLists.txt
├── CMakePresets.json
└── CMakeUserPresets.json.example     # Template for local per-developer overrides
```

## Quick Start (`CMakePresets.json`)

### Linux (GCC / Clang + Ninja)

```bash
cmake --preset linux-gcc-x64-debug-tests
cmake --build --preset linux-gcc-x64-debug-tests
ctest --preset linux-gcc-x64-debug-tests
# Or run configure + build + test in one step (workflow preset):
cmake --workflow --preset linux-gcc-x64-debug-tests
```

### Windows (MSVC x64 + Ninja)

Run inside an **x64 Native Tools Command Prompt for VS 2022** (or initialize `vcvars64.bat`), or open the folder directly in Visual Studio 2022 / VS Code:

```bat
cmake --preset win-msvc-x64-debug-tests
cmake --build --preset win-msvc-x64-debug-tests
ctest --preset win-msvc-x64-debug-tests
:: Or in a single workflow step:
cmake --workflow --preset win-msvc-x64-debug-tests
```

### Available Presets

Host `condition` rules filter `configurePresets`, `buildPresets`, and `testPresets` automatically so Windows tools list only `win-*` presets and Linux tools list only `linux-*` presets.

| Preset | OS | Toolchain | Build Type | Tests |
| :--- | :--- | :--- | :--- | :--- |
| `win-msvc-x64-debug` | Windows | MSVC (`cl`) | `Debug` | `OFF` |
| `win-msvc-x64-relwithdebinfo` | Windows | MSVC (`cl`) | `RelWithDebInfo` | `OFF` |
| `win-msvc-x64-release` | Windows | MSVC (`cl`) | `Release` | `OFF` |
| `win-msvc-x64-debug-tests` | Windows | MSVC (`cl`) | `Debug` | `ON` |
| `win-msvc-x64-relwithdebinfo-tests` | Windows | MSVC (`cl`) | `RelWithDebInfo` | `ON` |
| `win-msvc-x64-release-tests` | Windows | MSVC (`cl`) | `Release` | `ON` |
| `linux-gcc-x64-debug` | Linux | GCC (`g++`) | `Debug` | `OFF` |
| `linux-gcc-x64-relwithdebinfo` | Linux | GCC (`g++`) | `RelWithDebInfo` | `OFF` |
| `linux-gcc-x64-release` | Linux | GCC (`g++`) | `Release` | `OFF` |
| `linux-gcc-x64-debug-tests` | Linux | GCC (`g++`) | `Debug` | `ON` |
| `linux-gcc-x64-relwithdebinfo-tests` | Linux | GCC (`g++`) | `RelWithDebInfo` | `ON` |
| `linux-gcc-x64-release-tests` | Linux | GCC (`g++`) | `Release` | `ON` |
| `linux-clang-x64-debug-tests` | Linux | Clang (`clang++`) | `Debug` | `ON` |
| `linux-clang-x64-release-tests` | Linux | Clang (`clang++`) | `Release` | `ON` |

### Local Developer Overrides (`CMakeUserPresets.json` vs `CMakeSettings.json`)

Machine-specific paths (local `vcpkg` root, custom toolchains, `clang-cl`, `sccache`) belong in `CMakeUserPresets.json`, which is ignored by Git alongside legacy IDE files (`CMakeSettings.json`, `CMakeLists.txt.user*`):

```bash
cp CMakeUserPresets.json.example CMakeUserPresets.json
```

- **Schema version compatibility:** `CMakePresets.json` uses schema `"version": 6` (CMake 3.25+, enabling `workflowPresets`). `CMakeUserPresets.json` implicitly includes `CMakePresets.json` and should also use `"version": 6` (or higher only if your local CMake supports that schema: `v7` = 3.27, `v8` = 3.28 `$schema`, `v10` = 3.31 `$comment`). Keep the file strictly valid JSON — `//` comments are rejected by CLI `cmake`.
- **Visual Studio `CMakeSettings.json`:** When `CMakePresets.json` is present at the repository root, Visual Studio 2022+ uses Presets mode by default and ignores `CMakeSettings.json`. Use `CMakeUserPresets.json` so CLI, VS, VS Code, and CLion share one configuration model.

## Scoped Target Philosophy

1. **Explicit source lists:** Translation units and headers are listed explicitly in `src/CMakeLists.txt`, `apps/CMakeLists.txt`, and `tests/CMakeLists.txt` instead of `file(GLOB ...)`, ensuring reliable build-graph regeneration when files are added or removed.
2. **`PRIVATE` internal diagnostics:** Strict compiler warnings (`/W4 /permissive-` on MSVC; `-Wall -Wextra -Wpedantic -Wshadow -Wold-style-cast -Wconversion` on GCC/Clang), sanitizers, and `CXX_CLANG_TIDY` are attached `PRIVATE` per internal target. Downstream consumers linking `cpp_template::cpp_template` never inherit opinionated warning flags, and third-party dependencies are never slowed down by internal `clang-tidy` checks.
3. **`BUILD_INTERFACE` vs `INSTALL_INTERFACE`:** Include directories use generator expressions so the exact same target definition works in-tree (`add_subdirectory` / `FetchContent`) and from an installed prefix (`find_package`).
4. **Compiler caching on MSVC (`CMP0141 NEW`):** Policy `CMP0141` is set to `NEW` before `project()` so enabling `ENABLE_SCCACHE=ON` switches MSVC debug symbols to `Embedded` (`/Z7`), avoiding shared `mspdbsrv.exe` locks that prevent object caching.

## CMake Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `ENABLE_TESTS` | `OFF` (`ON` in `*-tests` presets) | Synchronizes `BUILD_TESTING`, includes `CTest`, and builds `tests/`. |
| `ENABLE_SCCACHE` | `OFF` | Uses `sccache` as `CMAKE_CXX_COMPILER_LAUNCHER` and selects `/Z7` on MSVC; warns if missing. |
| `ENABLE_UNITY_BUILD` | `OFF` | Enables batched CMake unity builds on internal targets (`UNITY_BUILD_BATCH_SIZE`, default `8`). |
| `ENABLE_CLANG_TIDY` | `OFF` | Runs `clang-tidy` per internal target via `CXX_CLANG_TIDY`; warns if missing. |
| `ENABLE_SANITIZERS` | `OFF` | Enables ASan/UBSan on GCC/Clang and `/fsanitize=address` on MSVC (`PRIVATE`). |
| `ENABLE_DOCS` | `OFF` | Generates Doxygen HTML API docs in `<build>/docs` when `Doxygen` is installed. |
| `CPP_TEMPLATE_INSTALL` | `${PROJECT_IS_TOP_LEVEL}` | Generates `install()` and CMake package export rules. |
| `CPP_TEMPLATE_VERSION_OVERRIDE` | `""` | Explicit `MAJOR.MINOR.PATCH` version override for source-archive/offline builds. |
| `CPP_TEMPLATE_COMMIT_OVERRIDE` | `""` | Explicit short commit hash override for source-archive/offline builds. |

Example combining developer tooling options:

```bash
cmake --preset linux-clang-x64-debug-tests \
  -DENABLE_SCCACHE=ON \
  -DENABLE_CLANG_TIDY=ON \
  -DENABLE_SANITIZERS=ON
```

### Optional GoogleTest Integration

`tests/CMakeLists.txt` probes `find_package(GTest CONFIG QUIET)`. When `GTest` is provided (for example via `-DCMAKE_TOOLCHAIN_FILE=<vcpkg>/scripts/buildsystems/vcpkg.cmake`), `cpp_template_tests` links `GTest::gtest_main` and registers tests via `gtest_discover_tests()`. Otherwise, the built-in C++20 runner executes the exact same `TEST(...)` suites with zero external setup.

## Installing & Downstream Consumption (`find_package`)

Install the built package into the preset's install prefix (or a custom `--prefix`):

```bash
cmake --preset linux-gcc-x64-release
cmake --build --preset linux-gcc-x64-release
cmake --install out/build/linux-gcc-x64-release --prefix out/install/linux-gcc-x64-release
```

Consume the installed package from an external CMake project:

```cmake
cmake_minimum_required(VERSION 3.25)
project(my_app LANGUAGES CXX)

find_package(cpp_template CONFIG REQUIRED)

add_executable(my_app main.cpp)
target_link_libraries(my_app PRIVATE cpp_template::cpp_template)
```

Configure the consumer by pointing `CMAKE_PREFIX_PATH` at the installation directory:

```bash
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH=/path/to/Cpp_CMake_template/out/install/linux-gcc-x64-release
cmake --build build
```

## License

Released under the [MIT License](LICENSE).

