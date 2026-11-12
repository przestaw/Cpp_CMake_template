# Szablon projektu C++20 + CMake

[English](README.md) | **Polski**

Przejrzysty, niewymagający zewnętrznych zależności szablon projektu **C++20** oparty na nowoczesnej architekturze **CMake 3.25+**, `CMakePresets.json` (v6), CTest oraz relokowalnym eksporcie pakietu pod `find_package`.

## Najważniejsze cechy

- **Brak obowiązkowych zależności zewnętrznych:** Kompiluje się od razu po sklonowaniu z dowolnym kompilatorem C++20 (`MSVC 19.30+`, `GCC 11+`, `Clang 14+`) oraz generatorem `Ninja`.
- **Architektura oparta na targetach (CMake 3.25+):** Brak globalnego `include_directories()`, brak doklejania flag do globalnych zmiennych `CMAKE_CXX_FLAGS_*` oraz brak `file(GLOB ...)`.
- **Gotowe presety `CMakePresets.json` (v6):** Odseparowane katalogi budowania (`out/build/<preset>`) i instalacji (`out/install/<preset>`) dla systemów Windows oraz Linux.
- **Dwuwarstwowe testy jednostkowe:** Automatycznie wykrywa i wykorzystuje `GTest` (np. z `vcpkg` lub pakietów systemowych), a w przypadku jego braku przełącza się na wbudowany, lekki runner asercji C++20, dzięki czemu `ctest` działa natychmiast bez dodatkowej konfiguracji.
- **Eksport pakietu dla projektów zewnętrznych:** Instaluje nagłówki, wygenerowany plik `version.hpp` oraz `cpp_templateConfig.cmake` obsługujący `find_package(cpp_template CONFIG REQUIRED)`.
- **Zawsze aktualna wersja z Gita:** Wersja semantyczna i krótki hash commita są wyliczane jako zwykłe zmienne CMake (bez zamrażania nieaktualnych wartości w `CMakeCache.txt` przy zmianie gałęzi).

## Struktura katalogów

```text
.
├── .github/workflows/ci.yml          # Potok CI dla Linux (GCC/Clang) i Windows (MSVC)
├── cmake/
│   ├── Config.cmake.in               # Szablon konfiguracji pakietu dla find_package()
│   ├── add_project_target.cmake      # Wspólna konfiguracja targetów (C++20, unity, foldery IDE)
│   ├── git_version.cmake             # Odczyt wersji i commita z Gita bez zatruwania cache'u
│   └── target_warnings.cmake         # Zakresowe (PRIVATE) ostrzeżenia, sanitizery i clang-tidy
├── docs/
│   ├── qmake-cmake-guide.md          # Dodatek: tutorial migracji qmake i Qt 5 -> CMake i Qt 6 (EN)
│   └── qmake-cmake-guide.pl.md       # Dodatek: tutorial migracji qmake i Qt 5 -> CMake i Qt 6 (PL)
├── examples/
│   └── qmake-migration/              # Dodatek: referencyjny wycinek before/after Qt i szablony CMake
├── include/cpp_template/
│   ├── cli_parser.hpp                # Bez-zależnościowy parser argumentów CLI w C++20
│   ├── greeter.hpp                   # Przykładowe API biblioteki z użyciem konceptów C++20
│   ├── version.hpp.in                # Szablon generowany do <build>/include/cpp_template/
│   └── error/exception.hpp           # Hierarchia wyjątków domenowych i CLI
├── src/
│   ├── CMakeLists.txt                # Target biblioteki rdzeniowej (cpp_template::cpp_template)
│   ├── cli_parser.cpp
│   └── greeter.cpp
├── apps/
│   ├── CMakeLists.txt                # Target aplikacji CLI (cpp_template_cli)
│   └── main.cpp
├── tests/
│   ├── CMakeLists.txt                # Testy jednostkowe i dymne CLI rejestrowane w CTest
│   ├── test_framework.hpp            # Mostek do GTest + wbudowany runner C++20
│   ├── cli_parser_tests.cpp
│   └── greeter_tests.cpp
├── tools/
│   └── qmake-migration-kit/          # CLI qmig, sondy .prf, mapper, przykłady i testy
├── CMakeLists.txt
├── CMakePresets.json
└── CMakeUserPresets.json.example     # Szablon lokalnych nadpisań dewelopera
```

## Szybki start (`CMakePresets.json`)

### Linux (GCC / Clang + Ninja)

```bash
cmake --preset linux-gcc-x64-debug-tests
cmake --build --preset linux-gcc-x64-debug-tests
ctest --preset linux-gcc-x64-debug-tests
# Lub konfiguracja + budowanie + testy jednym krokiem (workflow preset):
cmake --workflow --preset linux-gcc-x64-debug-tests
```

### Windows (MSVC x64 + Ninja)

Uruchom w konsoli **x64 Native Tools Command Prompt for VS 2022** (lub po wywołaniu `vcvars64.bat`), albo otwórz katalog bezpośrednio w Visual Studio 2022 / VS Code:

```bat
cmake --preset win-msvc-x64-debug-tests
cmake --build --preset win-msvc-x64-debug-tests
ctest --preset win-msvc-x64-debug-tests
:: Lub w jednym kroku workflow:
cmake --workflow --preset win-msvc-x64-debug-tests
```

### Dostępne presety

Reguły `condition` filtrują `configurePresets`, `buildPresets` oraz `testPresets` po systemie operacyjnym, dzięki czemu na Windows widoczne są wyłącznie presety `win-*`, a na Linuksie wyłącznie `linux-*`.

| Preset | System | Kompilator | Typ budowania | Testy |
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

### Lokalne nadpisania dewelopera (`CMakeUserPresets.json` vs `CMakeSettings.json`)

Ścieżki lokalne dla danej maszyny (katalog `vcpkg`, niestandardowe kompilatory jak `clang-cl`, `sccache`) należy trzymać w pliku `CMakeUserPresets.json`, który jest ignorowany przez Gita razem z lokalnymi plikami IDE (`CMakeSettings.json`, `CMakeLists.txt.user*`):

```bash
cp CMakeUserPresets.json.example CMakeUserPresets.json
```

- **Zgodność wersji schematu:** `CMakePresets.json` używa schematu `"version": 6` (CMake 3.25+, obsługa `workflowPresets`). Plik `CMakeUserPresets.json` niejawnie dołącza `CMakePresets.json` i również powinien używać `"version": 6` (lub wyższej tylko wtedy, gdy lokalna wersja CMake ją wspiera: `v7` = 3.27, `v8` = 3.28 `$schema`, `v10` = 3.31 `$comment`). Plik musi być poprawnym JSON-em — komentarze `//` są odrzucane przez CLI `cmake`.
- **Visual Studio `CMakeSettings.json`:** Gdy w katalogu głównym istnieje `CMakePresets.json`, Visual Studio 2022+ domyślnie przełącza się w tryb Presets i ignoruje `CMakeSettings.json`. Korzystanie z `CMakeUserPresets.json` zapewnia jedną spójną konfigurację dla CLI, VS, VS Code i CLion.

## Filozofia izolowanych targetów

1. **Jawne listy źródeł:** Pliki `.cpp` oraz nagłówki są wymienione jawnie w `src/CMakeLists.txt`, `apps/CMakeLists.txt` i `tests/CMakeLists.txt` zamiast `file(GLOB ...)`, co gwarantuje poprawne wykrywanie nowych lub usuniętych plików przez system budowania.
2. **Flagi diagnostyczne jako `PRIVATE`:** Rygorystyczne ostrzeżenia kompilatora (`/W4 /permissive-` dla MSVC; `-Wall -Wextra -Wpedantic -Wshadow -Wold-style-cast -Wconversion` dla GCC/Clang), sanitizery oraz właściwość `CXX_CLANG_TIDY` są przypisywane wyłącznie z widocznością `PRIVATE` do wewnętrznych targetów projektu. Projekty konsumenckie linkujące `cpp_template::cpp_template` nie dziedziczą wymuszonych flag ostrzeżeń, a zewnętrzne zależności `FetchContent` nie są spowalniane przez `clang-tidy`.
3. **`BUILD_INTERFACE` oraz `INSTALL_INTERFACE`:** Ścieżki nagłówków używają wyrażeń generatorowych, dzięki czemu ten sam target działa identycznie wewnątrz drzewa źródeł (`add_subdirectory` / `FetchContent`) jak i po instalacji (`find_package`).
4. **Pamięć podręczna kompilacji na MSVC (`CMP0141 NEW`):** Polityka `CMP0141` jest ustawiona na `NEW` przed `project()`, dzięki czemu włączenie `ENABLE_SCCACHE=ON` automatycznie przełącza format symboli debugowania MSVC na `Embedded` (`/Z7`), unikając blokad współdzielonego procesu `mspdbsrv.exe`.

## Opcje CMake

| Opcja | Domyślnie | Opis |
| :--- | :--- | :--- |
| `ENABLE_TESTS` | `OFF` (`ON` w presetach `*-tests`) | Synchronizuje `BUILD_TESTING`, dołącza `CTest` i buduje katalog `tests/`. |
| `ENABLE_SCCACHE` | `OFF` | Ustawia `sccache` jako `CMAKE_CXX_COMPILER_LAUNCHER` oraz `/Z7` na MSVC; ostrzega, gdy brak narzędzia. |
| `ENABLE_UNITY_BUILD` | `OFF` | Włącza grupowanie jednostek translacji (unity build) na wewnętrznych targetach (`UNITY_BUILD_BATCH_SIZE`, domyślnie `8`). |
| `ENABLE_CLANG_TIDY` | `OFF` | Uruchamia analizę statyczną `clang-tidy` per target (`CXX_CLANG_TIDY`); ostrzega, gdy brak narzędzia. |
| `ENABLE_SANITIZERS` | `OFF` | Włącza ASan/UBSan na GCC/Clang oraz `/fsanitize=address` na MSVC (`PRIVATE`). |
| `ENABLE_DOCS` | `OFF` | Buduje dokumentację HTML Doxygen w `<build>/docs`, jeśli `Doxygen` jest dostępny. |
| `CPP_TEMPLATE_INSTALL` | `${PROJECT_IS_TOP_LEVEL}` | Generuje reguły `install()` oraz eksport pakietu CMake. |
| `CPP_TEMPLATE_VERSION_OVERRIDE` | `""` | Jawne nadpisanie wersji `MAJOR.MINOR.PATCH` dla budowania ze zrzutu źródeł bez `.git`. |
| `CPP_TEMPLATE_COMMIT_OVERRIDE` | `""` | Jawne nadpisanie krótkiego hasha commita dla budowania poza repozytorium Git. |

Przykład konfiguracji z dodatkowymi narzędziami deweloperskimi:

```bash
cmake --preset linux-clang-x64-debug-tests \
  -DENABLE_SCCACHE=ON \
  -DENABLE_CLANG_TIDY=ON \
  -DENABLE_SANITIZERS=ON
```

### Opcjonalna integracja z GoogleTest

Plik `tests/CMakeLists.txt` wywołuje `find_package(GTest CONFIG QUIET)`. Jeśli pakiet `GTest` jest dostępny (np. przez `-DCMAKE_TOOLCHAIN_FILE=<vcpkg>/scripts/buildsystems/vcpkg.cmake`), target `cpp_template_tests` linkuje `GTest::gtest_main` i rejestruje testy przez `gtest_discover_tests()`. W przeciwnym razie używany jest wbudowany runner C++20 obsługujący te same makra `TEST(...)`.

## Instalacja i użycie w zewnętrznym projekcie (`find_package`)

Zbuduj i zainstaluj bibliotekę do prefiksu instalacyjnego:

```bash
cmake --preset linux-gcc-x64-release
cmake --build --preset linux-gcc-x64-release
cmake --install out/build/linux-gcc-x64-release --prefix out/install/linux-gcc-x64-release
```

Użycie zainstalowanego pakietu w zewnętrznym projekcie CMake:

```cmake
cmake_minimum_required(VERSION 3.25)
project(moja_aplikacja LANGUAGES CXX)

find_package(cpp_template CONFIG REQUIRED)

add_executable(moja_aplikacja main.cpp)
target_link_libraries(moja_aplikacja PRIVATE cpp_template::cpp_template)
```

Konfiguracja projektu konsumenckiego ze wskazaniem `CMAKE_PREFIX_PATH`:

```bash
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH=/sciezka/do/Cpp_CMake_template/out/install/linux-gcc-x64-release
cmake --build build
```

## Dodatek: Tutorial i szablony migracji qmake i Qt 5 -> CMake i Qt 6

Jako opcjonalne uzupełnienie dla zespołów przenoszących projekty Qt na nowoczesny CMake 3.25+ i Qt 6 repozytorium zawiera dwujęzyczny przewodnik, działający wycinek referencyjny `before`/`after` oraz konfigurowalne skrypty pomocnicze w Pythonie (wymagające adaptacji do docelowego projektu, a nie działające jako automatyczny konwerter):

- **[Tutorial migracji (`docs/qmake-cmake-guide.pl.md`)](docs/qmake-cmake-guide.pl.md)** ([English](docs/qmake-cmake-guide.md)) — etapowa weryfikacja zgodności (`qmake` → `CMake` → C++20 → Qt 6), granice eksportu DLL (`PRIVATE`) oraz pluginów Qt Designera, reguły `AUTOMOC`/`AUTOUIC` i kolizje strażników `uic` dla nazw z kropkami, kolejność generatorów kodu (`AUTOGEN_TARGET_DEPENDS`) oraz docelowe funkcje Qt 6.5+ (`qt_standard_project_setup()`, `qt_add_*`).
- **[Wycinek referencyjny i szablony (`examples/qmake-migration/`)](examples/qmake-migration/README.pl.md)** ([English](examples/qmake-migration/README.md)) — równoległy build `before/` (`qmake`) i `after/` (`CMake 3.25+`) na wspólnych źródłach C++/Qt, izolowane fragmenty CMake (`snippets/`), reprodukcja kolizji strażników UIC oraz lista kontrolna [`parity-checklist.csv`](examples/qmake-migration/parity-checklist.csv).
- **[Konfigurowalne skrypty `qmig` (`tools/qmake-migration-kit/`)](tools/qmake-migration-kit/README.pl.md)** ([English](tools/qmake-migration-kit/README.md) · [Znane ograniczenia](tools/qmake-migration-kit/KNOWN_GAPS.pl.md)) — sondy `.prf` eksportu modelu i przechwytywania kompilacji w czystym Pythonie 3.9+, statyczny linter pułapek `qmake`, generator szkiców CMake, porównywarka jednostek translacji i drzew instalacji oraz 25 testów jednostkowych (`python3 -m unittest discover -s tools/qmake-migration-kit/tests -v`).

## Licencja

Projekt udostępniany na warunkach licencji [MIT](LICENSE).
