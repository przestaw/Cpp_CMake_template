# qmig: workflow migracji qmake → CMake i Qt 5 → Qt 6

[English](README.md) | **Polski**

`qmig` dostarcza konfigurowalne sondy referencyjne i skrypty pomocnicze do migracji projektów Qt opartych na qmake na podstawie dowodów z budowania, a nie tłumaczenia składni na ślepo.

- qmake oblicza projekt, a sonda (`.prf`) eksportuje wynik jako model.
- Linter wskazuje defines i flagi, które qmake przepuszczał bokiem, a które pod CMake zmieniają znaczenie.
- Mapper tworzy szkic CMake oraz raport wszystkiego, czego nie przetłumaczył.
- Oba buildy idą przez wrapper kompilatora i linkera. Każde rzeczywiste polecenie jest zapisywane i eksportowane jako build tree.
- `compare` klasyfikuje różnice: per TU, per artefakt i per zainstalowany plik.
- `qt6` sprawdza model, zainstalowane Qt 6 i źródła pod kątem przejścia na Qt 6.

Każdy krok zapisuje nowy dowód w workspace i niczego nie nadpisuje. Każdy krok może być bramką w CI.

> **Zakres:** `qmig` jest konfigurowalnym szkieletem sond i skryptów referencyjnych, a nie uniwersalnym automatycznym konwerterem dla dowolnych repozytoriów. Wdrożenie produkcyjne wymaga dopasowania do projektu (`adapter.json`, `policy.json`, własne reguły generatorów kodu oraz orkiestracja presetów na docelowych hostach), tak aby każda luka była jawnie obsłużona.

Zasady odwzorowania oraz docelowe idiomy Qt 6 i CMake 3.25+ opisuje [`../../docs/qmake-cmake-guide.pl.md`](../../docs/qmake-cmake-guide.pl.md).

## Wymagania

- Python 3.9+, tylko biblioteka standardowa.
- `qmake` każdego używanego Qt.
- CMake 3.21+ (`<LANG>_LINKER_LAUNCHER`, File API; zalecane 3.25+ dla presetów/workflow).
- Generator Makefile lub Ninja dla przechwytywania CMake. Generator Visual Studio nie obsługuje launcherów.
- Opcjonalnie `readelf`: `RUNPATH` i `NEEDED` w porównaniu instalacji.

## Szybki start

```sh
python3 qmig.py init --source-root /ścieżka/do/repo --qmake /ścieżka/Qt/5.15.2/gcc_64/bin/qmake
#   -> workflow.json: przejrzyj "projects" (wykrywanie tylko proponuje korzenie SUBDIRS)
python3 qmig.py run -p qt5-release            # export, lint, qt6, map, capture obu, compare
python3 qmig.py status                        # najnowsze dowody i wyniki per profil
```

Pojedyncze kroki:

```sh
qmig export  -p P          # model qmake (JSON) + surowe rekordy, Makefile, logi
qmig lint    -p P          # statyczna kontrola defines/flag, które qmake tolerował
qmig qt6     -p P [--qt6-qmake Q] [--target 6.5] [--scan-tree]
qmig map     -p P [--qt 5|6|dual|model] [--strict]
qmig capture qmake -p P [--keep-going] [--no-install]
qmig capture cmake -p P [--source KATALOG] [--qt-major 5|6] [--keep-going]
qmig compare -p P [--base qmake@P] [--candidate cmake@P2] [--fail-on error|warning|info|never]
qmig diff  A.json B.json [--variant release]     # dwa modele qmake (np. Linux vs Windows)
```

`python3 qmig.py ...` i `python3 -m qmigrate ...` działają tak samo. Skrypty `export_model.py`, `diff_models.py` i `map_to_cmake.py` nadal działają jako samodzielne wejścia.

## Pojęcia

- **Profil**: qmake, platforma i build type, plus sposób budowania strony CMake (generator, build type, tryb Qt, major Qt, dodatkowe argumenty). Przykłady: `linux-qt5-release`, `linux-qt5-deprecated`, `windows-qt5-release`, `linux-qt6-release`.
- **Workspace**: `<workspace>/<profil>/<rodzaj>-<znacznik czasu>` oraz `index.json`. Rodzaje to `model`, `lint`, `qt6`, `draft`, `buildtree-qmake`, `buildtree-cmake` i `compare`. Kolejne kroki biorą najnowszy artefakt profilu.
- **Adapter** (`adapter`): reguły projektowe. Klucze:
  - `libs`: `-lfoo` → imported target.
  - `tools`: token polecenia → wyrażenie CMake.
  - `findPackages`.
  - `installPaths`: zamiana prefiksu.
  - `dropDefines`, `dropFlags`, `ignoreVars`.
  - `qt6Components`: per projekt.
  - `matchQmakeDefaults`: Release bez `NDEBUG`, `-O2`/`/O2` z mkspec, `-Wl,-O1`, oraz `warn_on` → `-Wall -Wextra`/`/W3`.
- **Polityka** (`policy`): zaakceptowane różnice, każda z obowiązkowym `reason`. Dopasowanie po `rule` (glob), `project` (glob) i `message` (fragment). Zaakceptowane pozycje zostają w raporcie jako `accepted`.
- **Bramki** (`gates`): per krok `error|warning|info|never`. Niezaliczona bramka daje kod 2. `run` zatrzymuje się na pierwszej, chyba że podasz `--continue-on-failure`.
- **Ustawienia lokalne**: `workflow.local.json` obok `workflow.json` jest scalany głęboko, jak `CMakeUserPresets.json`. Napisy mogą zawierać `${env:NAZWA}` i `${configDir}`. Przykłady: `examples/workflow.example.json`, `examples/adapter.example.json`, `examples/policy.example.json`.

## Zalecana kolejność

1. Baseline per profil przez `export` + `lint`. Błędy lint napraw lub zaakceptuj przed mapowaniem.
2. `map --qt dual` na Qt 5.15 (bezwersjowe cele `Qt::`). Potem `capture qmake`, `capture cmake` i `compare`, aż bramka przejdzie. Rozszerzaj adapter zamiast ręcznie poprawiać szkic. Świadomie wybierz `matchQmakeDefaults` albo akceptację różnic Release w polityce.
3. Build „deprecation”: profil z `-DCMAKE_CXX_FLAGS=-DQT_DISABLE_DEPRECATED_BEFORE=0x050F00` i `capture cmake --keep-going`. Każde nieudane TU używa API usuniętego w Qt 6. W Qt 6.5+ makro nazywa się `QT_DISABLE_DEPRECATED_UP_TO`.
4. `qt6 --qt6-qmake <qmake Qt 6>`:
   - moduły usunięte lub dostępne dopiero w późniejszym Qt 6,
   - moduły brakujące w zainstalowanym Qt 6,
   - wymóg C++17,
   - `/permissive-` na MSVC,
   - skan źródeł.

   Komponenty potrzebne według skanu (`Core5Compat`, `OpenGLWidgets`, `SvgWidgets`, `StateMachine`) same trafiają do następnego `map`.
5. Przeportuj kod i zbuduj ten sam szkic dual z Qt 6 (`qtMajor: 6`). Porównaj z baseline qmake/Qt 5: różnice wynikające z wersji Qt są porównywane łagodnie, reszta ściśle.
6. Wycofaj qmake per produkt, gdy `compare` przechodzi na każdym profilu, a drzewa instalacji się zgadzają, po czym przejdź na natywne funkcje Qt 6 `qt_standard_project_setup()` / `qt_add_executable()` / `qt_add_library()` (zobacz [`../../docs/qmake-cmake-guide.pl.md`](../../docs/qmake-cmake-guide.pl.md)).

## Eksport build tree

Kroki capture zapisują to, co build naprawdę uruchomił:

- qmake używa `CONFIG+=migration_capture` (`features/migration_capture.prf`), który owija `QMAKE_CC`, `QMAKE_CXX`, `QMAKE_LINK*`, `QMAKE_AR` i `QMAKE_LIB` przez `qmigrate/ccwrap.py`.
- CMake używa `CMAKE_<LANG>_COMPILER_LAUNCHER` i `CMAKE_<LANG>_LINKER_LAUNCHER`. Biblioteki statyczne (bez launchera) i przynależność do targetów pochodzą z CMake File API (codemodel v2).

Wrapper zapisuje jeden plik JSON na wywołanie, więc buildy równoległe są bezpieczne. Zapisuje też treść plików response, które nmake od razu usuwa.

`buildtree.json` zawiera:
- per TU: źródło, artefakt, defines (z kolejnością i wartościami), undefs, katalogi include z rodzajem i kategorią, wymuszone include, standard C++, optymalizację, debug info, PIC, runtime MSVC, ostrzeżenia, pozostałe flagi, stan błędu;
- per artefakt: rodzaj, źródła, biblioteki po tożsamości, katalogi bibliotek, RPATH, flagi linkera;
- drzewo instalacji: pliki, bit wykonywalności, ELF `NEEDED` i `RUNPATH`.

Ścieżki są tokenizowane jako `${SRC}`, `${BUILD}` i `${QT}`. Parser obsługuje GCC/Clang, MSVC `cl`/`clang-cl`, `link`, `lib`, `ar` oraz launchery `ccache`/`sccache`/`distcc`. Nieznane opcje trafiają do `other` i nigdy nie giną.

## Co jest sprawdzane

### `lint`: model qmake, bez budowania

| Reguła | Dlaczego ma znaczenie pod CMake |
|---|---|
| `lint.define.conflict` | `A=1` i `A=2`: qmake przekazuje oba, kompilator bierze ostatni z ostrzeżeniem. |
| `lint.define.semicolon` | `;` dzieli listę CMake na dwie definicje. |
| `lint.define.quoting` | qmake wkleja wartość do powłoki bez zmian, CMake escapuje za ciebie. Szkic zdejmuje jeden poziom cytowania. |
| `lint.define.function-like`, `.hash`, `.dollar`, `.whitespace` | Escapowanie różni się między generatorami. |
| `lint.flag.pair-dedup` | Powtórzona para `-include`/`-isystem`/`-Xclang`…: CMake deduplikuje słowa opcji. Szkic używa `SHELL:`. |
| `lint.flag.hidden-define`, `.hidden-include` | `-D`/`-I` w `QMAKE_CXXFLAGS`: pod qmake moc ich nie widzi, a `AUTOMOC` w CMake bierze tylko definicje i include dirs. |
| `lint.flag.space` | Jeden element qmake ze spacjami staje się w CMake jednym argumentem. |
| `lint.flag.dialect`, `.werror`, `.std-conflict`, `.linker-in-cflags` | Opcje, które działały przypadkiem. |
| `lint.link.order-sensitive`, `.repeated-lib` | `--whole-archive` i `--start-group`: CMake przestawia elementy linkowania. Użyj `LINK_LIBRARY`/`LINK_GROUP` (CMake 3.24+). |
| `lint.include.missing` | qmake ignoruje brakujące katalogi, imported target się na nich wywraca. |

### `compare`: dwa build tree

| Reguła | Przykład |
|---|---|
| `define.ndebug` | CMake Release definiuje `NDEBUG`, release qmake nie. `assert()` znika. |
| `define.qt-no-debug`, `define.windows-implicit` (`UNICODE`…), `define.lost`/`added`/`value`/`quoting`/`undef`, `define.deprecation`, `define.qt-module` | Różnice makr per TU. |
| `include.lost`/`added`/`order`/`kind`/`qt`/`qt-system`/`forced` | Inne wyszukiwanie nagłówków, w tym Qt jako `-isystem`. |
| `flags.std`, `std-extensions` (gnu++ vs c++), `std-qt6`, `optimization`, `msvc-runtime`, `werror`, `lost`/`added`, `pic`, `debug-info`, `warnings` | Różnice opcji kompilatora. |
| `tu.missing`/`extra`/`artifact`, `artifact.missing`/`kind`/`source-lost` | Różnice grafu: co się kompiluje i do czego trafia. |
| `link.no-undefined`, `link.subsystem`, `link.lib-lost`, `link.flag-lost`, `link.rpath` | Różnice linkowania. |
| `install.missing`/`extra`/`mode`/`rpath`/`needed` | CMake domyślnie usuwa build RPATH przy instalacji. |
| `build.failed`, `build.compile-failed`, `capture.empty-compile-set` | Nieudane buildy lub pusty zrzut kompilacji (0 TU po jednej stronie przy >0 po drugiej); tak raportuje też build „deprecation”. |

Identyczne różnice z wielu plików są scalane w jedną pozycję z licznikiem i próbkami.

### `qt6`: gotowość do Qt 6

- Moduły:
  - usunięte (XmlPatterns, Script, X11/Win/MacExtras…);
  - dostępne później niż cel (Multimedia/SerialPort/Positioning/… 6.2, TextToSpeech 6.4, Location 6.5);
  - niezainstalowane w docelowym Qt 6 (na podstawie jego `Qt6<Moduł>Config.cmake`);
  - uwagi per moduł.
- Build: standard poniżej C++17 (Qt 6 dodaje konsumentom compile feature `cxx_std_17`), a na MSVC `-Zc:__cplusplus -permissive-` dodawane każdemu konsumentowi (sprawdzone w `QtFlagHandlingHelpers.cmake` Qt 6.4.2).
- Także: `qtquickcompiler` i poziom deprecation.
- Skan źródeł z modelu (`--scan-tree`: całe drzewo), z pominięciem komentarzy:
  - C++: `QRegExp`, `QTextCodec`, `QLinkedList`, `QStringRef`, SAX XML, `QDesktopWidget`, `qrand`, `QMatrix`, QtAlgorithms, `SkipEmptyParts`, `insertMulti`, `QVariant::Type`, `qVariant*`, `MidButton`, `sprintf`, `QFontMetrics::width`, atrybuty high-DPI, `QSound`, `QGL*`, przeniesione klasy OpenGL/SVG/state machine, Qt Script, bearer management, `QDirModel`, `grabWidget`, wersjonowane style options, `toSet()`, `QDateTime(QDate)`, `Q_ENUMS`;
  - include w stylu `<QtCore/QRegExp>`, który nie znajdzie nagłówka w `Core5Compat`;
  - QML: Controls 1, `QtGraphicalEffects`, Dialogs 1.

Tabela modułów to wskazówka, rozstrzyga zainstalowane Qt 6. Skan opiera się na regexach: służy do znalezienia pracy, a dowodem są build „deprecation” i `compare`.

## Tryby szkicu CMake (`map --qt`)

- `model`: Qt 5 lub 6, jak w eksporcie.
- `5` / `6`: cele `Qt5::`/`Qt6::`. Tryb `6` podnosi C++ do 17.
- `dual`: bezwersjowe cele `Qt::` (Qt 5.15+). Dodaje `find_package(QT NAMES Qt6 Qt5)` i linkuje komponenty tylko z Qt 6 (`Core5Compat`…) pod `if(QT_VERSION_MAJOR GREATER_EQUAL 6)`. `-DQMIG_QT_MAJOR=5|6` czyni wybór deterministycznym; bez niego, gdy znalezione są oba, wygrywa Qt 6. Standard C++ zostaje jak w qmake, a Qt 6 podnosi go do 17 przez `cxx_std_17`.

## CI

```sh
python3 qmig.py run -c ci/workflow.json -p linux-qt5-release   # kod 0 = wszystkie bramki zaliczone
python3 qmig.py run -c ci/workflow.json -p linux-qt6-release --steps map,capture-cmake,compare \
        --keep-going --continue-on-failure
```

Archiwizuj `<workspace>/<profil>/*.md|*.json` oraz `buildtree.json`; katalogi builda możesz potem usunąć. Zablokuj `gates` w `workflow.json`, a każdą akceptowaną różnicę wpisz z uzasadnieniem do polityki.

## Sprawdzone środowiska i ograniczenia

- **Zweryfikowane środowiska:**
  - **Linux (buildy end-to-end i capture):** Sprawdzone na Linuksie (Ubuntu 24.04, GCC 13, Qt 5.15.13 oraz 5.15.15, Qt 6.4.2, CMake 3.28, Ninja, w tym ścieżki tymczasowe ze spacjami): `verify_workflow.py` przechodzi 25 kontroli (`init`, `hazards` z uruchomieniowym sprawdzeniem `NDEBUG` i polityką akceptacji, `multi` z `matchQmakeDefaults` bez błędów i ostrzeżeń, `qt5api` z buildem deprecation oraz porównaniem qmake/Qt 5 kontra CMake/Qt 6), a `verify_demo.py` przechodzi 35 kontroli (`debug_and_release`, przebudowa inkrementalna i odtworzenie usuniętego nagłówka oraz pełna zgodność drzew instalacji z `INSTALL_ROOT`).
  - **Testy jednostkowe (`tests/`):** 25 testów niewymagających Qt (parsowanie rekordów, linii poleceń i plików response dla GCC/Clang i MSVC, porównywanie build tree w tym bramka pustego zrzutu kompilacji, wybór konfiguracji File API, detekcja Qt 6 w `qmig init`, linter, reguły Qt 6, konfiguracja) — uruchamianych automatycznie na Linuksie i Windows w `.github/workflows/ci.yml`.
  - **Nieuruchomione hosty capture:** Ścieżki kodu dla natywnego przechwytywania qmake/CMake na Windows/MSVC (`cl`, `nmake`/`jom`) oraz macOS istnieją w parserze i wrapperze, ale nie były jeszcze weryfikowane end-to-end. Pełną listę opisuje [`KNOWN_GAPS.pl.md`](KNOWN_GAPS.pl.md).
- Sonda widzi stan qmake w trakcie przetwarzania feature'ów; późniejsze fazy mogą coś dodać. `capture` pokazuje stan końcowy, `export` plan.
- TU są parowane po ścieżce źródła i artefakcie. Unity build, PCH i źródła kompilowane dwukrotnie z różnymi flagami wymagają wpisu w polityce lub ręcznej analizy. TU generowane (`moc`/`rcc`/`uic`) są liczone, nie porównywane pojedynczo.
- `make install` z qmake nie cytuje `INSTALL_ROOT`. Capture używa katalogu tymczasowego bez spacji i kończy się czytelnym błędem, jeśli `TMPDIR`/`TEMP` zawiera spacje.
- Mapper tworzy szkic; produkty dalej potrzebują adaptera. Wszystko nieprzetłumaczone jest w `mapping-report.md`.

## Weryfikacja

```sh
python3 -m unittest discover -s tests -v
python3 verify_demo.py --qmake /ścieżka/qt5/bin/qmake
python3 verify_workflow.py --qt5-qmake /ścieżka/qt5/bin/qmake --qt6-qmake /ścieżka/qt6/bin/qmake
```

Przykłady:
- `examples/demo`: custom compiler i instalacja;
- `examples/multi`: `SUBDIRS`, biblioteka statyczna, `AUTOMOC`;
- `examples/hazards`: define z literałem, podwójne `-include`, ukryty define, sprzeczne wartości, `assert` kontra `NDEBUG`;
- `examples/qt5api`: API tylko z Qt 5, C++14.

Kontrola `hazards` uruchamia obie binarki. Build qmake wypisuje `asserts=on`, build CMake Release `asserts=off`, i `compare` raportuje dokładnie tę różnicę.

## Licencja

Zestaw udostępniany jako część `Cpp_CMake_template` na warunkach licencji [MIT](../../LICENSE).
