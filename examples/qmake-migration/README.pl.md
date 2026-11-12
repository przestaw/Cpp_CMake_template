# Wycinek referencyjny i szablony migracji qmake → CMake

[English](README.md) | **Polski**

Samodzielny przykład referencyjny towarzyszący poradnikowi [`docs/qmake-cmake-guide.pl.md`](../../docs/qmake-cmake-guide.pl.md). Pokazuje równoległą konfigurację `qmake` (`before/`) oraz `CMake 3.25+` (`after/`) na dokładnie tych samych źródłach C++/Qt (`common/`):

- bibliotekę współdzieloną (`democore`) eksportującą klasę `QObject` (`Counter`) oraz meta-obiekt przestrzeni nazw (`Demo::Mode` przez `Q_NAMESPACE_EXPORT`),
- izolację makra eksportu DLL (`DEMO_CORE_BUILD` jako `PRIVATE` — wyciek do `demo` jest blokowany już podczas kompilacji `main.cpp`),
- niestandardową cechę `.prf` (`DEMO_FEATURE_LOADED`) oraz generator nagłówka C++ ze schematu w Pythonie (`generate.py`),
- osobne szablony fragmentów CMake (`snippets/`), reprodukcję kolizji strażników `uic` dla nazw z kropkami (`uic-guard-case/`) oraz listę kontrolną weryfikacji (`parity-checklist.csv`).

> **Zakres:** Katalog stanowi szablon referencyjny i materiał szkoleniowy, a nie gotowy automatyczny konwerter. Fragmenty w `snippets/` należy dostosować do nazw targetów i pakietów zależności docelowego projektu.

## Układ katalogu

```text
examples/qmake-migration/
├── common/                         # Wspólne źródła C++17 / Qt (5.15+ lub 6) i generator kodu
│   ├── factor.schema
│   ├── generate.py
│   ├── include/demo/{core_export.h,counter.h}
│   └── src/{counter.cpp,main.cpp}
├── before/                         # Punkt odniesienia qmake SUBDIRS (.pro / .pri / .prf)
│   ├── demo.pro
│   ├── settings.pri
│   ├── features/demo_rules.prf
│   ├── core/core.pro
│   └── app/app.pro
├── after/                          # Odpowiednik w CMake 3.25+ oparty na targetach i presetach
│   ├── CMakeLists.txt
│   ├── CMakePresets.json
│   └── CMakeUserPresets.json.example
├── snippets/                       # Izolowane wzorce CMake i C++20 do adaptacji
│   ├── allocator-header-example.h
│   ├── dependency-metadata.cmake
│   ├── generated-forms-ordering.cmake
│   ├── install-versioning.cmake
│   ├── target-options.cmake
│   └── windows-imported-library.cmake
├── uic-guard-case/                 # Reprodukcja kolizji strażników uic dla plików .ui z kropkami
└── parity-checklist.csv            # Lista kontrolna kryteriów odbioru migracji
```

## Budowanie i uruchamianie przykładu

Ustaw zmienną `TUTORIAL_QT_ROOT` na lokalną instalację Qt 5.15+ lub Qt 6 (np. `/opt/Qt/5.15.2/gcc_64` na Linuksie lub `C:\Qt\5.15.2\msvc2019_64` na Windows). Oczekiwane wyjście programu dla `common/factor.schema` (`7`):

```text
Counter:7:Normal
```

### Linux — `before/` (punkt odniesienia `qmake`)

```sh
export TUTORIAL_QT_ROOT=/opt/Qt/5.15.2/gcc_64
mkdir -p build-qmake && cd build-qmake
QMAKEFEATURES="$PWD/../before/features" "$TUTORIAL_QT_ROOT/bin/qmake" ../before/demo.pro
make -j2
./bin/demo
```

### Linux — `after/` (odpowiednik `CMake`)

```sh
cmake -S after -B build-cmake -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="$TUTORIAL_QT_ROOT"
cmake --build build-cmake --parallel 2
./build-cmake/bin/demo
cmake --install build-cmake --prefix "$PWD/stage-cmake"
```

Aby zbudować wariant z Qt 6, użyj świeżego katalogu budowania i przekaż jawnie `-DTUTORIAL_QT_MAJOR=6` wraz z `CMAKE_PREFIX_PATH` wskazującym na Qt 6.

### Windows (MSVC x64) — `before/` oraz `after/`

Uruchom w konsoli **x64 Native Tools Command Prompt for VS 2022**:

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

### Konfiguracja przez `CMakeUserPresets.json`

W katalogu `after/` skopiuj `CMakeUserPresets.json.example` do `CMakeUserPresets.json` (ignorowanego przez Gita) i uruchom wybrany preset:

```sh
cd after
cp CMakeUserPresets.json.example CMakeUserPresets.json
cmake --preset local-linux      # lub local-windows w środowisku MSVC x64
cmake --build --preset local-linux
```

## Celowe granice wycinka

- Wersjonowanie dowiązań symbolicznych biblioteki współdzielonej (`VERSION` / `SOVERSION`, zobacz [`snippets/install-versioning.cmake`](snippets/install-versioning.cmake)), docelowe `INSTALL_RPATH`, eksport `Config.cmake` oraz narzędzia wdrożeniowe (`windeployqt` / `macdeployqt`) zostały celowo pominięte w `after/CMakeLists.txt`, aby zachować czytelność podstawowego odwzorowania `SUBDIRS` + eksport DLL + `AUTOMOC` + custom codegen.
