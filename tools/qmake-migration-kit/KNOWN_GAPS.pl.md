# Znane braki i ograniczenia

[English](KNOWN_GAPS.md) | **Polski**

Lista obszarów, których zestaw nie automatyzuje lub których jeszcze nie zweryfikowano uruchomieniowo. Kolejność: od największego ryzyka.

## Nieuruchomione platformy capture

- **Windows / MSVC / `nmake` / `jom`**: obsługa w parserze i wrapperze istnieje (pokryta testami jednostkowymi), ale przechwytywanie buildów nie było jeszcze uruchamiane end-to-end. Najbardziej wrażliwe miejsca:
  - pliki inline `@<<` z `nmake` w wrapperze;
  - launcher CMake przekazywany jako lista z `;` przy ścieżkach Windows;
  - tryb wsadowy `cl` (`/Fo` jako katalog, nazwy `.obj` wyprowadzane ze źródeł);
  - parsowanie `link.exe`/`lib.exe`;
  - `TEMP` ze spacjami (capture instalacji `qmake` przerywa wtedy czytelnym błędem).
- **macOS**: framework bundles, `install_name` oraz `@rpath` nie są modelowane ani porównywane. Inwentarz instalacji analizuje wyłącznie pliki ELF (`readelf`), bez Mach-O.
- **Windows — brak inwentarza zależności DLL** (brak obsługi `dumpbin /dependents`). Reguły `install.needed` oraz `install.rpath` działają wyłącznie dla binarek ELF.
- **Generatory**: Visual Studio i Xcode nie obsługują launcherów kompilatora/linkera, więc `capture cmake` wymaga generatora Ninja lub Makefiles. Funkcja `read_file_api` dopasowuje konfigurację File API po nazwie `build_type` (z powrotem do pierwszej konfiguracji jako fallback), natomiast samo wywołanie `capture cmake` zakłada generator jednokonfiguracyjny (`CMAKE_BUILD_TYPE`), o ile nie zostanie rozszerzone o `--config` dla Ninja Multi-Config.

## Luki w przechwytywaniu i porównaniu

- **`moc` / `uic` / `rcc` / `rc.exe` nie są przechwytywane.** Wrapper obejmuje kompilator, linker i archiwizer — nie porównuje bezpośrednio definicji ani ścieżek przekazywanych do `moc` (stąd reguła statyczna `lint.flag.hidden-define`) ani zasobów Windows (`.rc`).
- **Jednostki generowane** (`moc_*`, `qrc_*`, `mocs_compilation`) są zliczane, ale nie porównywane pojedynczo.
- **Unity build i PCH**: parowanie TU odbywa się po ścieżce źródła i artefakcie. Unity build zmienia jednostki kompilacji i generuje `tu.missing`, a PCH (`-include cmake_pch.hxx`) zgłasza `include.forced` — wymaga to świadomego wpisu w polityce.
- **`debug_and_release` w `capture qmake`**: oba warianty budują artefakty o tej samej nazwie. Profile capture powinny wyłączać ten tryb (`CONFIG-=debug_and_release`, jak w `examples/workflow.example.json`), czego narzędzie samo nie wymusza.
- **Porównanie instalacji** sprawdza ścieżki względne, bit wykonywalności oraz pola ELF `NEEDED`/`RUNPATH`, bez porównywania zawartości binarnej (qmake domyślnie uruchamia `strip` przy instalacji, CMake nie).
- **Brak porównania gotowych paczek** (`CPack` vs dotychczasowy packager). Kryteria domknięcia opisane w [`../../docs/qmake-cmake-guide.pl.md`](../../docs/qmake-cmake-guide.pl.md) wymagają tej weryfikacji poza samym drzewem instalacji.
- **Wydajność na bardzo dużych repozytoriach** nie była mierzona (wrapper w Pythonie zapisuje osobny plik JSON na każde wywołanie kompilatora).

## Mapper (szkic CMake)

Elementy wyłącznie raportowane w `mapping-report.md` (bez automatycznego tłumaczenia):
- `TRANSLATIONS` (`qt_add_translations`), moduły QML (`qt_add_qml_module`), `LEXSOURCES`/`YACCSOURCES`, `QMAKE_SUBSTITUTES` (`configure_file`), `QMAKE_PRE_LINK`/`POST_LINK`, `QMAKE_EXTRA_TARGETS`, prywatne moduły Qt;
- Android / iOS / WebAssembly, statyczne Qt (import pluginów, finalizacja targetów), narzędzia wdrożeniowe (`windeployqt`, `macdeployqt`);
- `INSTALL_RPATH` nie jest ustawiany automatycznie, więc `install.rpath` pojawi się tam, gdzie qmake zachowywał RPATH;
- makra eksportu DLL i `GenerateExportHeader` (zobacz zasady granic DLL w [`../../docs/qmake-cmake-guide.pl.md`](../../docs/qmake-cmake-guide.pl.md)); propagacja `PUBLIC`/`PRIVATE` jest zachowawcza (`QT` jako `PUBLIC` dla bibliotek, reszta `PRIVATE`).

## Qt 5 → Qt 6

- **Skan źródeł opiera się na wyrażeniach regularnych.** Wykrywa nazwy wycofanych klas i funkcji, ale nie zmiany semantyki czasu wykonania (`QList`/`QVector`, kolejność `QHash`, `int` → `qsizetype`, konwersje `QVariant`, domyślne UTF-8, nowe API Multimedia — warto uzupełnić analizę o `clazy`).
- **Wbudowana tabela modułów** sięga wersji Qt 6.5 (`Location`, `TextToSpeech`); rozstrzygającym źródłem jest docelowa instalacja Qt 6 wskazana przez `--qt6-qmake`.
- **`QT_DISABLE_DEPRECATED_UP_TO` (Qt 6.5+)**: środowisko weryfikacyjne używało Qt 6.4.2 (`QT_DISABLE_DEPRECATED_BEFORE`).
- Tryb `6` mappera generuje klasyczne targety CMake; docelowe przejście na `qt_standard_project_setup()`, `qt_add_executable()` oraz `qt_add_qml_module()` po wycofaniu Qt 5 opisuje [`../../docs/qmake-cmake-guide.pl.md`](../../docs/qmake-cmake-guide.pl.md).

## Workflow i organizacja

- **Polityka** nie posiada pól właściciela ani daty wygaśnięcia akceptacji.
- **`init`** wykrywa korzenie `SUBDIRS` tekstowo (bez pełnej ewaluacji `qmake`) — listę projektów w `workflow.json` należy zawsze przejrzeć.
- **`pkg-config` → `pkg_check_modules`** jest zaimplementowane w mapperze, ale nie ma osobnego przykładu integracyjnego end-to-end.
