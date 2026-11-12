# Tutorial i przewodnik referencyjny migracji qmake i Qt 5 → CMake i Qt 6

[English](qmake-cmake-guide.md) | **Polski**

> **Zakres i przeznaczenie:** Ten przewodnik, działający wycinek referencyjny `before`/`after` w [`../examples/qmake-migration/`](../examples/qmake-migration/README.pl.md) oraz sondy Pythona w [`../tools/qmake-migration-kit/`](../tools/qmake-migration-kit/README.pl.md) tworzą **praktyczny poradnik inżynierski, szablon wzorców oraz konfigurowalny szkielet skryptów**. **Nie jest** to uniwersalny automatyczny konwerter dla dowolnych repozytoriów — docelowe wdrożenie wymaga jawnej adaptacji (`adapter.json`, `policy.json`, reguły generatorów kodu, cele `IMPORTED` bibliotek zewnętrznych oraz orkiestracja lokalnych presetów `CMakeUserPresets.json`).

## Pliki referencyjne w repozytorium

| Ścieżka | Zawartość |
| :--- | :--- |
| [`../examples/qmake-migration/`](../examples/qmake-migration/README.pl.md) | Równoległy przykład `before/` (`qmake` `SUBDIRS` + `.prf` + generator ze schematu) i `after/` (`CMake 3.25+` + presety) na wspólnych źródłach C++/Qt w `common/` (`Q_OBJECT`, `Q_NAMESPACE_EXPORT`, izolacja makra eksportu DLL jako `PRIVATE`). |
| [`../examples/qmake-migration/snippets/`](../examples/qmake-migration/snippets/) | Samodzielne szablony CMake i C++20: `target-options.cmake`, `windows-imported-library.cmake`, `dependency-metadata.cmake`, `generated-forms-ordering.cmake`, `install-versioning.cmake`, `allocator-header-example.h`. |
| [`../examples/qmake-migration/uic-guard-case/`](../examples/qmake-migration/uic-guard-case/README.pl.md) | Minimalna reprodukcja kolizji strażników `#ifndef UI_PANEL_H` generowanych przez `uic` w Qt 5.15 dla plików `.ui` z kropkami (`panel.alpha.ui`, `panel.beta.ui`). |
| [`../examples/qmake-migration/parity-checklist.csv`](../examples/qmake-migration/parity-checklist.csv) | Lista kontrolna kryteriów odbioru kolejnych faz (`profile`, `export`, `capture`, `compile`, `headers`, `link`, `codegen`, `install`, `runtime`, `package`, `tests`, `ci`). |
| [`../tools/qmake-migration-kit/`](../tools/qmake-migration-kit/README.pl.md) | Konfigurowalny zestaw skryptów w Pythonie 3.9+ (`qmig.py`, `export_model.py`, `diff_models.py`, `map_to_cmake.py`), sondy `.prf`, statyczny linter pułapek `qmake`, skaner gotowości do Qt 6, przykłady i testy jednostkowe. |

---

## 1. Etapowa separacja zmian

Jednoczesna wymiana systemu budowania, podniesienie standardu C++ oraz port z Qt 5 na Qt 6 miesza błędy składni kompilatora, niezgodności ABI linkera oraz regresje makr. Rozdziel migrację na trzy niezależnie weryfikowalne etapy:

| Etap | Punkt odniesienia | Kandydat | Pytanie kontrolne |
| :--- | :--- | :--- | :--- |
| **1. Zgodność systemu budowania** | `qmake` + Qt 5.15 + C++17 | `CMake 3.25+` + to samo Qt 5.15, kompilator, arch. i C++17 | Czy definicje makr, ścieżki nagłówków, pliki generowane, linkowanie i drzewa instalacji są zgodne? |
| **2. Podniesienie standardu C++** | Zweryfikowany build CMake C++17 | Ten sam build CMake + Qt, przełączony na C++20 | Które źródła własne lub nagłówki publiczne zależności zewnętrznych wymagają poprawki pod C++20? |
| **3. Port Qt 5.15 → Qt 6** | Zweryfikowany build CMake Qt 5.15 (`QT_DISABLE_DEPRECATED_BEFORE=0x050F00`) | Ten sam build CMake przełączony na Qt 6 (`Qt6::*` / `qt_add_*`) | Które usunięte klasy Qt 5, moduły, importy QML lub wtyczki runtime wymagają aktualizacji? |

> **Powiązania toolchainu:** Jeśli docelowe Qt 6 wymaga nowszego kompilatora lub wyższego standardu C++ niż dotychczasowe środowisko Qt 5, potraktuj aktualizację kompilatora jako jawny krok wstępny zamiast diagnozować błędy dialektu C++ jako defekty CMake.

### Zewnętrzne nagłówki zależności przy przejściu na C++20

Przejście z C++17 na C++20 usuwa przestarzałe aliasy biblioteki standardowej, m.in. `std::allocator<T>::pointer`, co potrafi zatrzymać kompilację publicznych nagłówków zewnętrznych pakietów:

```cpp
// Zapis sprzed C++20 (usunięty w C++20):
using pointer = typename std::allocator<T>::pointer;

// Zapis zgodny z C++17 i C++20 (#include <memory>):
using pointer = typename std::allocator_traits<std::allocator<T>>::pointer;
```

W pierwszej kolejności zaktualizuj sam pakiet zależności. Gdy aktualizacja musi poczekać, zastosuj wąską nakładkę nagłówkową (overlay) w drzewie budowania (zobacz [`../examples/qmake-migration/snippets/allocator-header-example.h`](../examples/qmake-migration/snippets/allocator-header-example.h)):

- weryfikuj sumę kontrolną oryginalnego nagłówka pakietu w czasie konfiguracji, aby zmiana wersji biblioteki nie została cicho przysłonięta,
- dodaj ścieżkę nakładki wyłącznie jako `PRIVATE` (przed katalogiem pakietu) dla konkretnych targetów, które jej potrzebują,
- usuń nakładkę natychmiast po podbiciu zależności.

---

## 2. Wycinek referencyjny `before` / `after` (`examples/qmake-migration/`)

Migrację nowego repozytorium zacznij od ręcznego przeprowadzenia małego przekroju pionowego: biblioteki współdzielonej (`democore`) z klasą `Q_OBJECT`, eksportowanym wyliczeniem przestrzeni nazw (`Q_NAMESPACE_EXPORT`), generatorem kodu ze schematu oraz aplikacją konsumencką (`demo`). Kompletne pliki znajdują się w [`../examples/qmake-migration/`](../examples/qmake-migration/README.pl.md).

### Kolejność `SUBDIRS` kontra graf targetów CMake

W `qmake` kolejność budowania podkatalogów definiuje `SUBDIRS` z `.depends`, a konsument powtarza ręcznie `-L`/`-l`. W CMake kolejność budowania, linkowanie oraz propagację ścieżek nagłówków wyraża jedno wywołanie `target_link_libraries()`:

```qmake
# before/demo.pro
TEMPLATE = subdirs
SUBDIRS += core app
app.depends = core

# before/app/app.pro
INCLUDEPATH += $$PWD/../../common/include
LIBS += -L$$OUT_PWD/../bin -ldemocore
```

```cmake
# after/CMakeLists.txt
add_library(democore SHARED
    "${common}/src/counter.cpp"
    "${common}/include/demo/counter.h"
    "${common}/include/demo/core_export.h"
    "${generated}"
)
target_include_directories(democore
    PUBLIC "$<BUILD_INTERFACE:${common}/include>"
    PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/generated"
)

add_executable(demo "${common}/src/main.cpp")
target_link_libraries(demo PRIVATE democore)
```

Pamiętaj, że `add_dependencies(demo democore)` wymusza wyłącznie kolejność budowania — nie linkuje biblioteki ani nie przekazuje katalogów `PUBLIC`.

### Niejawne cechy `.prf` kontra jawny kontrakt targetu

Plik `before/settings.pri` ładuje `before/features/demo_rules.prf` przez zmienną środowiskową `QMAKEFEATURES`, dodając `DEFINES += DEMO_FEATURE_LOADED`. W CMake zastąp ukryte cechy środowiskowe jawnymi właściwościami na targetach (lub wspólną funkcją pomocniczą projektu):

```cmake
target_compile_definitions(democore PRIVATE DEMO_CORE_BUILD DEMO_FEATURE_LOADED)
target_compile_definitions(demo PRIVATE DEMO_FEATURE_LOADED)
```

---

## 3. Eksport modelu konfiguracji przez `qmake` (`qmig export` i `diff_models.py`)

Pliki `.pro` dynamicznie obliczają warunki platformowe (`win32`, `unix:!macx`), dołączenia `.pri`, cechy `.prf`, wywołania `$$system()` oraz testy `exists()`. Nie parsuj składni `.pro` wyrażeniami regularnymi — pozwól natywnemu `qmake` obliczyć projekt i wyeksportować stan zmiennych sondą [`../tools/qmake-migration-kit/features/migration_export.prf`](../tools/qmake-migration-kit/features/migration_export.prf) (`CONFIG+=migration_export`).

```sh
python3 tools/qmake-migration-kit/export_model.py \
  --source-dir tools/qmake-migration-kit/examples/demo \
  --features tools/qmake-migration-kit/examples/demo/features \
  --profile linux-qt5-release \
  --output out/demo-release.json --qmake-arg CONFIG+=release demo.pro

python3 tools/qmake-migration-kit/export_model.py \
  --source-dir tools/qmake-migration-kit/examples/demo \
  --features tools/qmake-migration-kit/examples/demo/features \
  --profile linux-qt5-debug \
  --output out/demo-debug.json --qmake-arg CONFIG+=debug demo.pro

python3 tools/qmake-migration-kit/diff_models.py \
  out/demo-release.json out/demo-debug.json --summary
```

Zasady pracy z eksporterem modelu:

- **Ewaluacja na docelowym systemie:** Eksport z `-spec win32-msvc` uruchomiony na Linuksie pomaga poznać listę targetów, ale warunki `exists()`, ścieżki SDK i mkspec kompilatora dają wiążący wynik wyłącznie w natywnym środowisku MSVC x64 na Windows.
- **Wielokrotny przebieg `debug_and_release` (`schemaVersion: 2`):** Mkspece MSVC włączają domyślnie `CONFIG += debug_and_release`, przez co każdy plik `.pro` generuje trzy rekordy (główny oraz przebiegi `debug` i `release`). W `diff_models.py` i `map_to_cmake.py` wybieraj wariant jawnie przez `--variant release` lub `--variant debug`, a w profilach `capture` dodawaj `CONFIG -= debug_and_release`.
- **Granice sondy `.prf`:** Sonda widzi zmienne w momencie przetwarzania cech; późniejsze reguły mkspec i generatora Makefile potrafią dopisać kolejne flagi. Traktuj `export` jako model strukturalny, natomiast `qmig capture` (`buildtree.json`) jako ostateczny dowód rzeczywistych linii poleceń kompilatora i linkera.

---

## 4. Flagi kompilacji, cytowanie, granice DLL i semantyka linkowania

### Własność makra eksportu DLL (`PRIVATE` u producenta)

W bibliotece współdzielonej Windows makro wybierające `__declspec(dllexport)` (`Q_DECL_EXPORT`) należy wyłącznie do budowanego targetu producenta. Ustawienie go jako `PUBLIC` sprawia, że konsumenci widzą `__declspec(dllexport)` zamiast `__declspec(dllimport)` (`Q_DECL_IMPORT`), co kończy się nierozwiązanymi symbolami `staticMetaObject` oraz tablic metod wirtualnych podczas linkowania:

```qmake
# qmake: core/core.pro definiuje DEMO_CORE_BUILD; app/app.pro go NIE definiuje
DEFINES += DEMO_CORE_BUILD
```

```cmake
# BŁĄD — propaguje Q_DECL_EXPORT na wszystkich konsumentów:
# target_compile_definitions(democore PUBLIC DEMO_CORE_BUILD)

# POPRAWNIE — producent eksportuje, konsumenci importują:
target_compile_definitions(democore PRIVATE DEMO_CORE_BUILD)
target_link_libraries(demo PRIVATE democore)
```

### `CONFIG += plugin` w Qt Designerze kontra katalog instalacji

Cecha `designer_defines.prf` w Qt dodaje makro `QDESIGNER_EXPORT_WIDGETS` wyłącznie wtedy, gdy target ma aktywne `CONFIG += plugin`:

```qmake
TEMPLATE = lib
CONFIG += plugin designer   # -> definiuje QDESIGNER_EXPORT_WIDGETS
```

Jeżeli zwykła biblioteka współdzielona widgetów jest instalowana do tego samego katalogu co wtyczki Designera przez pomocniczą funkcję z `.pri`, **nie** przypisuj jej automatycznie `QDESIGNER_EXPORT_WIDGETS` ani typu `MODULE` na podstawie samej ścieżki docelowej. Rozdziel trzy niezależne decyzje:

1. **Typ linkowania targetu:** `SHARED` (tworzy bibliotekę importu `.lib` dla konsumentów C++) kontra `MODULE` (wtyczka ładowana wyłącznie dynamicznie).
2. **Własność makr eksportu:** własne makro `PRIVATE` dla każdej biblioteki `SHARED`; `QDESIGNER_EXPORT_WIDGETS` wyłącznie dla rzeczywistych pluginów Designera.
3. **Katalog instalacji:** `RUNTIME DESTINATION bin` i `ARCHIVE DESTINATION lib` dla zwykłych bibliotek DLL oraz dedykowany podkatalog pluginów dla `QPluginLoader`.

### `NDEBUG` w trybie `Release` oraz lokalne `/permissive-` na MSVC

- **`NDEBUG` w konfiguracji `Release`:** CMake automatycznie dodaje `-DNDEBUG` / `/DNDEBUG` w trybach `Release`, `RelWithDebInfo` i `MinSizeRel`, podczas gdy `qmake` przy `CONFIG += release` definiuje jedynie `QT_NO_DEBUG`, zostawiając standardowe `assert()` aktywne. Podejmij świadomą decyzję: zaakceptuj standardowe zachowanie CMake w `policy.json` albo zachowaj aktywne asercje na wybranych targetach:

```cmake
if(MSVC)
    target_compile_options(legacy_component PRIVATE "$<$<CONFIG:Release>:/UNDEBUG>")
else()
    target_compile_options(legacy_component PRIVATE "$<$<CONFIG:Release>:-UNDEBUG>")
endif()
```

- **Zakresowe `/permissive-` na MSVC:** Zgubienie flagi `/permissive-` z pliku `.pro` psuje kompilację nagłówków C++ używających słownych operatorów ISO (`not`, `and`, `or`, częstych m.in. w Boost). Przypisuj `/permissive-` jako `PRIVATE` wyłącznie dla języka `CXX` na targetach, które tego wymagają (zobacz [`../examples/qmake-migration/snippets/target-options.cmake`](../examples/qmake-migration/snippets/target-options.cmake)):

```cmake
target_compile_options(legacy_component PRIVATE
    "$<$<COMPILE_LANG_AND_ID:CXX,MSVC>:/permissive->"
)
```

### Cytowanie argumentów, grupowanie `SHELL:` i pliki response MSVC

Definicje i opcje przechodzą przez inne warstwy escapowania w `qmake` (surowy tekst Makefile) niż w CMake (tablice argumentów Ninja oraz pliki odpowiedzi `.rsp` dla `cl.exe` / `link.exe`):

- **Definicje będące literałami napisowymi:** Zdejmij jeden poziom cytowania powłokowego przy przenoszeniu definicji do `target_compile_definitions`:

```qmake
# qmake
DEFINES += APP_LABEL=\\\"demo\\\"
```

```cmake
# CMake
target_compile_definitions(demo PRIVATE APP_LABEL="demo")
```

- **Powtarzane opcje dwuargumentowe (`SHELL:`):** CMake deduplikuje powtórzone słowa opcji takie jak `-include a.h -include b.h` do błędnego `-include a.h b.h`, jeśli nie zostaną zgrupowane prefiksem `SHELL:` (dla GCC/Clang):

```cmake
target_compile_options(component PRIVATE
    "SHELL:-include \"${CMAKE_CURRENT_SOURCE_DIR}/compat/first.h\""
    "SHELL:-include \"${CMAKE_CURRENT_SOURCE_DIR}/compat/second.h\""
)
```

- **Wieloczłonowe flagi linkera Windows oraz `/Fo`:** Przekazuj złożone przełączniki linkera MSVC, np. `/MANIFESTDEPENDENCY:"type='win32' ..."`, jako pojedyncze niespodzielone wartości, aby podział argumentów w pliku `.rsp` nie zamienił części przełącznika w fałszywy plik `.obj`. W parserach linii poleceń `cl.exe` obsługuj wszystkie udokumentowane warianty `/Fo` (`/Fofile.obj`, `/Fodir/` oraz `/Fo: file.obj`).

### Targety `IMPORTED`, `PkgConfig::`, kolejność linkowania i `VERSION` / `SOVERSION`

Zastąp surowe flagi `-L/ścieżka -lfoo` targetami `IMPORTED` przenoszącymi katalogi nagłówków, definicje oraz ścieżki binarek per konfiguracja:

- **Biblioteki `SHARED IMPORTED` na Windows:** Zawsze ustawiaj jednocześnie `IMPORTED_LOCATION_<CONFIG>` (plik `.dll`) oraz `IMPORTED_IMPLIB_<CONFIG>` (biblioteka importu `.lib`), a także jawne mapowanie `MAP_IMPORTED_CONFIG_RELWITHDEBINFO`, gdy zewnętrzny pakiet dostarcza wyłącznie binarki `Debug` i `Release` (zobacz [`../examples/qmake-migration/snippets/windows-imported-library.cmake`](../examples/qmake-migration/snippets/windows-imported-library.cmake)):

```cmake
add_library(Vendor::Transport SHARED IMPORTED)
set_target_properties(Vendor::Transport PROPERTIES
    IMPORTED_CONFIGURATIONS "DEBUG;RELEASE"
    IMPORTED_LOCATION_RELEASE "${TRANSPORT_ROOT}/bin/transport.dll"
    IMPORTED_IMPLIB_RELEASE "${TRANSPORT_ROOT}/lib/transport.lib"
    IMPORTED_LOCATION_DEBUG "${TRANSPORT_ROOT}/bin/transportd.dll"
    IMPORTED_IMPLIB_DEBUG "${TRANSPORT_ROOT}/lib/transportd.lib"
    MAP_IMPORTED_CONFIG_RELWITHDEBINFO Release
    INTERFACE_INCLUDE_DIRECTORIES "${TRANSPORT_ROOT}/include"
)
target_link_libraries(network_component PRIVATE Vendor::Transport)
```

- **Targety `PkgConfig::`:** Dla bibliotek dostarczających metadane `.pc` (np. `xmlsec1`) używaj `pkg_check_modules(... IMPORTED_TARGET)` zamiast ręcznego kopiowania flag `-D` z pojedynczej dystrybucji Linuksa (zobacz [`../examples/qmake-migration/snippets/dependency-metadata.cmake`](../examples/qmake-migration/snippets/dependency-metadata.cmake)).
- **Kolejność bibliotek statycznych:** Linkery uniksowe rozwiązują archiwa `.a` od lewej do prawej, a `--as-needed` pomija nieużyte bezpośrednio biblioteki współdzielone. Deklaruj bezpośrednie zależności `target_link_libraries()` na każdym konsumencie, a `$<LINK_GROUP:RESCAN,a,b>` (CMake 3.24+) stosuj wyłącznie dla rzeczywistych cykli bibliotek statycznych.
- **`VERSION` i `SOVERSION` bibliotek współdzielonych:** `qmake` domyślnie tworzy łańcuch dowiązań `.so.<major>.<minor>.<patch>`, natomiast CMake tworzy niewersjonowane `.so`, dopóki nie ustawisz jawnie właściwości `VERSION` oraz `SOVERSION` (zobacz [`../examples/qmake-migration/snippets/install-versioning.cmake`](../examples/qmake-migration/snippets/install-versioning.cmake)).

---

## 5. Generatory kodu Qt: `AUTOMOC`, `AUTOUIC`, `AUTORCC`, własny codegen i QML

### Katalogi źródeł i shadow-buildu oraz wykrywanie nagłówków przez `AUTOMOC`

`qmake` domyślnie dołącza katalog `.pro` (`$$PWD`) oraz katalog shadow-buildu (`$$OUT_PWD`) do ścieżek wyszukiwania nagłówków (o ile nie podano `CONFIG += no_include_pwd`). W CMake deklaruj ścieżki źródłowe i katalogi wygenerowanych nagłówków jawnie na targetach oraz przestrzegaj reguł skanera `AUTOMOC`:

1. **Jawna lista nagłówków w `target_sources()`:** Nie polegaj wyłącznie na odgadywaniu nazw `.h` z plików `.cpp` — dopisuj wszystkie nagłówki z `Q_OBJECT`, `Q_GADGET` oraz `Q_NAMESPACE` do źródeł targetu.
2. **`Q_NAMESPACE` / `Q_NAMESPACE_EXPORT` w osobnej linii:**

```cpp
namespace Demo {
Q_NAMESPACE_EXPORT(DEMO_CORE_EXPORT)   // osobna linia gwarantuje wykrycie przez AUTOMOC
enum class Mode { Normal, Fast };
Q_ENUM_NS(Mode)
} // namespace Demo
```

3. **Higiena strażników `#ifndef` / `#define`:** CMake kompiluje wygenerowane pliki moc w zbiorczym pliku `mocs_compilation.cpp`, co natychmiast ujawnia literówki w strażnikach nagłówków oraz zduplikowane deklaracje `Q_DECLARE_METATYPE`.
4. **Konwencja `#include "foo.moc"`:** Jeśli plik `.cpp` definiuje lokalną klasę z `Q_OBJECT` i kończy się dyrektywą `#include "foo.moc"`, pozostaw jej obsługę mechanizmowi `AUTOMOC` — nie dodawaj równoległego `qt_wrap_cpp()`, które powoduje duplikację symboli.
5. **Wąskie wyłączenia `SKIP_AUTOMOC`:** Gdy plik zawiera słowo `Q_OBJECT` wyłącznie w komentarzu dokumentacyjnym lub stałej tekstowej, wyłącz skanowanie tylko dla tego pliku źródłowego:

```cmake
set_property(SOURCE src/doc_snippet.cpp PROPERTY SKIP_AUTOMOC ON)
```

### `AUTOUIC_SEARCH_PATHS`, publiczne nagłówki `ui_*.h` i kolizje strażników UIC

- **`AUTOUIC_SEARCH_PATHS`:** Gdy `#include "ui_editor.h"` odwołuje się do formularzy `.ui` w podkatalogach lub w katalogu plików generowanych, wskaż je jawnie przez `AUTOUIC_SEARCH_PATHS` (nie doklejając katalogu źródeł do ścieżek już bezwzględnych):

```cmake
set_property(TARGET panel PROPERTY AUTOUIC_SEARCH_PATHS
    "${CMAKE_CURRENT_SOURCE_DIR}/forms"
    "${CMAKE_CURRENT_BINARY_DIR}/generated/forms"
)
target_sources(panel PRIVATE forms/editor.ui)
```

- **Publiczne nagłówki włączające `ui_*.h`:** Docelowo ukrywaj szczegóły UI za deklaracją wyprzedzającą `namespace Ui { class Editor; }` w nagłówku publicznym. Jeśli na etapie zgodności 1:1 nagłówek publiczny musi włączać `ui_*.h`, pamiętaj o różnicy między generatorem jednokonfiguracyjnym (`<target>_autogen/include`) a wielokonfiguracyjnym (`<target>_autogen/include_$<CONFIG>`) i nigdy nie eksportuj ścieżek drzewa budowania do instalowanego pakietu SDK.
- **Kolizja strażników UIC dla nazw formularzy z kropkami:** W Qt 5.15 narzędzie `uic` wyznacza nazwę makra `#ifndef`, ucinając nazwę pliku na pierwszej kropce:

| Wejściowy plik `.ui` | Wygenerowany nagłówek | Strażnik z `uic` (Qt 5.15) |
| :--- | :--- | :--- |
| `panel.alpha.ui` | `ui_panel.alpha.h` | `UI_PANEL_H` **(kolizja)** |
| `panel.beta.ui` | `ui_panel.beta.h` | `UI_PANEL_H` **(kolizja)** |
| `panel.alpha.ui` | `ui_alpha_panel.h` | `UI_ALPHA_PANEL_H` |
| `panel.beta.ui` | `ui_beta_panel.h` | `UI_BETA_PANEL_H` |

Pełna reprodukcja znajduje się w [`../examples/qmake-migration/uic-guard-case/README.pl.md`](../examples/qmake-migration/uic-guard-case/README.pl.md). Zamień kropki na podkreślenia (`ui_alpha_panel.h`) zamiast globalnie wyłączać ochronę nagłówków flagą `AUTOUIC_OPTIONS "-p"`.

### Własne generatory kodu, `AUTOGEN_TARGET_DEPENDS` oraz `QT_PLUGIN_PATH`

Gdy narzędzie czasu budowania generuje kod C++, nagłówki z `Q_OBJECT` oraz formularze `.ui`, zamodeluj pełny łańcuch zależności:

```text
generator hosta + biblioteki runtime DLL / wtyczki Designera
  -> wygenerowane .cpp / .h / .ui (jawna lista OUTPUT z jednym właścicielem)
  -> <target>_autogen (MOC / UIC spięte przez AUTOGEN_TARGET_DEPENDS)
  -> kompilacja C++ -> linkowanie
```

Kluczowe reguły (pełny szablon w [`../examples/qmake-migration/snippets/generated-forms-ordering.cmake`](../examples/qmake-migration/snippets/generated-forms-ordering.cmake)):

- **Jawne `OUTPUT` zamiast samego `BYPRODUCTS`:** Wszystkie wygenerowane pliki `.h`, `.cpp` i `.ui` napędzające kompilację wymieniaj w `OUTPUT` (generatory Makefile nie odtwarzają brakujących plików z `BYPRODUCTS`). Każdy współdzielony nagłówek musi mieć dokładnie jedną regułę produkującą.
- **Kolejność przed `AUTOMOC` / `AUTOUIC`:** Połącz cel pomocniczy (`add_custom_target(panel_forms DEPENDS ${outputs})`) z właściwością `AUTOGEN_TARGET_DEPENDS`, aby `moc` i `uic` nie wystartowały przed wygenerowaniem plików wejściowych.
- **Lokalne `QT_PLUGIN_PATH` dla generatora formularzy:** Jeśli generator formularzy ładuje w czasie budowania własne wtyczki widgetów Qt Designera, dodaj targety wtyczek do `DEPENDS` i przekaż `QT_PLUGIN_PATH` wyłącznie do procesu generatora przez `${CMAKE_COMMAND} -E env`:

```cmake
add_custom_command(
    OUTPUT ${outputs}
    COMMAND "${CMAKE_COMMAND}" -E make_directory "${form_dir}"
    COMMAND "${CMAKE_COMMAND}" -E env
        "QT_PLUGIN_PATH=${CMAKE_BINARY_DIR}/tool-plugins"
        "$<TARGET_FILE:form_generator>" "${schema}" "${form_dir}"
    DEPENDS form_generator designer_widgets "${schema}"
    VERBATIM
)
```

- **Wczesny test uruchomieniowy generatora:** Na Windows błąd uruchomienia świeżo zlinkowanego generatora jeszcze przed `main()` (np. `0xC0000135` `STATUS_DLL_NOT_FOUND`) oznacza brak biblioteki DLL w `PATH`, a nie błąd schematu wejściowego. Zweryfikuj wywołanie `<generator> --help` przed startem pełnego buildu.

### Zasoby `.qrc` (`AUTORCC`) kontra `install()` oraz lista kontrolna QML

- **`.qrc` kontra pliki na dysku:** Dodanie pliku `.qrc` do źródeł targetu osadza zasoby pod prefiksem `qrc:/...` przez `AUTORCC`, ale nie instaluje luźnych plików na dysku. Odwrotnie, `install(FILES ...)` kopiuje pliki do drzewa instalacji bez rejestracji w `qrc:/`. Zweryfikuj oba kontrakty z regułami paczkowania produktu.
- **Lista kontrolna dla modułów QML:** Samo zlinkowanie `Qt5::Qml` / `Qt6::Qml` nie dowodzi poprawności modułów QML w runtime. Sprawdź:
  1. URI i wersję modułu, plik `qmldir` oraz wygenerowane `.qmltypes`.
  2. Prefiksy zasobów i adresy `qrc:/` ładowane przez `QQmlApplicationEngine`.
  3. Natywne wtyczki C++ stojące za modułem oraz `QML_IMPORT_PATH` w drzewie instalacji.
  4. Kompilację cache (`qmlcachegen`) oraz test dymny ładowania silnika QML z zainstalowanego katalogu stagingu.
  5. Po przejściu na Qt 6 przenieś definicję modułu do `qt_add_qml_module()` wraz z `qt_standard_project_setup(REQUIRES 6.5)` (polityki `QTP0001` i `QTP0004`).

---

## 6. Cztery poziomy weryfikacji („zielonego buildu”)

Traktuj odbiór migracji jako cztery kolejne bramki (zebrane w [`../examples/qmake-migration/parity-checklist.csv`](../examples/qmake-migration/parity-checklist.csv)):

1. **Konfiguracja i generacja grafu:** Sprawdź wybrane Qt, kompilator, architekturę i korzenie zależności w `CMakeCache.txt` oraz odpowiedziach CMake File API. Przy generatorach wielokonfiguracyjnych wybieraj nazwaną konfigurację w File API i przekazuj spójnie `--config <cfg>`. Upewnij się, że wersja Ninja na hoście wspiera format `depslog` używany przez `AUTOMOC` (Ninja ≥ 1.10; starsze Ninja 1.8 przerywa pracę błędem `multiple outputs aren't supported by depslog`).
2. **Zgodność kompilacji i linkowania:** Paruj jednostki translacji po krotce `(źródło, artefakt)`, zachowując kolejność katalogów `-I` oraz cytowanie makr. Pilnuj bramki kompletności zrzutu (`capture.empty-compile-set`: 0 przechwyconych jednostek kompilacji po jednej stronie przy >0 po drugiej oznacza uszkodzony zrzut i musi kończyć się błędem).
3. **Zgodność instalacji i paczkowania:** Porównaj znormalizowane ścieżki względne drzew instalacji (`make install INSTALL_ROOT=...` kontra `cmake --install ... --prefix ...`), rozdział `bin/` i `lib/`, prawa wykonywalności oraz pola ELF `DT_NEEDED` i `RUNPATH` (CMake domyślnie czyści buildowy `RPATH` przy instalacji, jeśli nie ustawiono `INSTALL_RPATH`). Uruchom docelowy packager na drzewie stagingu CMake i sprawdź niepustość globów zasobów. Na Windows weryfikuj rzeczywiste uruchomienie procesu w czystym środowisku zamiast polegać wyłącznie na statycznych skanach nazw DLL (które dają fałszywe alarmy na wirtualnych kontraktach API-set systemu Windows).
4. **Testy uruchomieniowe i przebudowy inkrementalnej:** Na każdym migrowanym wycinku wykonaj 8 kroków:
   - czysty build i potwierdzenie identycznego wyniku działania programu,
   - ponowny build bez zmian potwierdzający brak zbędnego uruchamiania generatorów kodu,
   - edycja pliku schematu potwierdzająca przebudowę konsumenta i zmianę wyniku,
   - usunięcie wygenerowanego nagłówka i potwierdzenie automatycznego odtworzenia bez `clean`,
   - dotknięcie nagłówka z `Q_OBJECT` i potwierdzenie rekompilacji `moc` oraz przelinkowania,
   - instalacja do pustego katalogu stagingu i inspekcja ścieżek względnych,
   - uruchomienie zainstalowanej binarki i wtyczek poza drzewem budowania,
   - jawne uruchomienie `ctest` (sama kompilacja binarek testowych nie wykonuje testów).

---

## 7. Presety w CI, natywne API Qt 6.5+ oraz adaptacja `tools/qmake-migration-kit/`

### Przenośny `CMakePresets.json` i lokalny `CMakeUserPresets.json` w CI

Utrzymuj [`../CMakePresets.json`](../CMakePresets.json) bez ścieżek specyficznych dla maszyny, a lokalne lokalizacje Qt (`CMAKE_PREFIX_PATH` / `Qt6_DIR`) oraz limity równoległości przekazuj przez ignorowany w Gicie `CMakeUserPresets.json` (lub zmienne środowiskowe):

```sh
# Na agentach Windows najpierw zainicjalizuj środowisko vcvars64.bat przed wywołaniem Ninja.
cmake --preset agent-release
cmake --build --preset agent-release --verbose
cmake --install out/build/agent-release --prefix out/install/agent-release
ctest --preset agent-release --output-on-failure
```

W logach CI weryfikuj, czy etapy budowania, testów i paczkowania faktycznie wykonały pracę dla oczekiwanego commita i presetu — potok, w którym parametry warunkowe pominęły etapy walidacji, nie stanowi potwierdzenia migracji.

### Docelowe idiomy Qt 6.5+ i CMake 3.25+

Podczas równoległej weryfikacji Etapu 1 i Etapu 3 tryb `qmig map --qt dual` generuje `find_package(QT NAMES Qt6 Qt5 REQUIRED ...)` oraz bezwersjowe targety `Qt::*`. Po wycofaniu wsparcia dla Qt 5 przejdź na natywne funkcje CMake z Qt 6.5+ połączone z izolowanymi helperami ostrzeżeń i sanitizerów z tego szablonu ([`../cmake/add_project_target.cmake`](../cmake/add_project_target.cmake)):

```cmake
cmake_minimum_required(VERSION 3.25)
cmake_policy(SET CMP0141 NEW)

project(moja_aplikacja_qt6 VERSION 1.0.0 LANGUAGES CXX)

find_package(Qt6 6.5 REQUIRED COMPONENTS Core Widgets Quick)
qt_standard_project_setup(REQUIRES 6.5)

qt_add_library(app_core STATIC
    src/session_model.cpp
    include/app/session_model.hpp
)
target_compile_features(app_core PUBLIC cxx_std_20)
target_include_directories(app_core
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)
target_link_libraries(app_core PUBLIC Qt6::Core)
cpp_template_configure_target(app_core)

qt_add_executable(moja_aplikacja_qt6 apps/main.cpp)
qt_add_qml_module(moja_aplikacja_qt6
    URI App.UI
    QML_FILES qml/Main.qml
)
target_link_libraries(moja_aplikacja_qt6 PRIVATE app_core Qt6::Widgets Qt6::Quick)
cpp_template_configure_target(moja_aplikacja_qt6)
```

### Adaptacja i orkiestracja `tools/qmake-migration-kit/`

Zestaw [`../tools/qmake-migration-kit/`](../tools/qmake-migration-kit/README.pl.md) udostępnia modułowe skrypty bazowe (`qmig.py`, `export_model.py`, `diff_models.py`, `map_to_cmake.py`), które należy dostosować do własnego repozytorium:

```sh
# 1. Wygeneruj plik startowy workflow.json (automatycznie wykrywa Qt 6, gdy --qmake wskazuje na Qt 6)
python3 tools/qmake-migration-kit/qmig.py init \
  --source-root /ścieżka/do/repo-qt \
  --qmake /ścieżka/do/Qt/5.15.2/gcc_64/bin/qmake

# 2. Dostosuj workflow.local.json (ścieżki hosta), adapter.json (biblioteki/narzędzia/ścieżki instalacji)
#    oraz policy.json (udokumentowane różnice akceptowalne, np. define.ndebug).

# 3. Uruchom potok export -> lint -> qt6 -> map -> capture-qmake -> capture-cmake -> compare
python3 tools/qmake-migration-kit/qmig.py run -p qt5-release
```

Kierunki adaptacji w docelowym projekcie:

- **`adapter.json`:** Odwzoruj zewnętrzne flagi `-lfoo` na targety `IMPORTED` (`"libs"`), przypisz tokeny generatorów kodu do wyrażeń CMake (`"tools"`), zadeklaruj pakiety `find_package(...)` (`"findPackages"`), przepisz prefiksy instalacyjne (`"installPaths"`) oraz w razie potrzeby włącz `"matchQmakeDefaults": true` dla zgodności braku `NDEBUG` w Etapie 1.
- **`policy.json`:** Zapisuj świadomie zaakceptowane różnice flag lub makr wraz z obowiązkowym polem `"reason"`, dzięki czemu bramka `compare` w CI blokuje wyłącznie nowe, niezbadane rozbieżności.
- **Rozszerzanie `qmigrate/`:** Dodawaj specyficzne wzorce generatorów w `qmigrate/mapper.py` lub dodatkowe zmienne do sondy `.prf` przez `--qmake-arg 'MIGRATION_EXTRA_VARS+=MY_SCHEMA_FILES'` zamiast ręcznie edytować wygenerowane szkice CMake.

Testy jednostkowe zestawu (niewymagające Qt) oraz opcjonalne skrypty weryfikacji end-to-end uruchomisz z katalogu głównego repozytorium:

```sh
python3 -m unittest discover -s tools/qmake-migration-kit/tests -v
python3 tools/qmake-migration-kit/verify_demo.py --qmake /ścieżka/do/qt5/bin/qmake
python3 tools/qmake-migration-kit/verify_workflow.py \
  --qt5-qmake /ścieżka/do/qt5/bin/qmake \
  --qt6-qmake /ścieżka/do/qt6/bin/qmake
```

Szczegółowy opis komend CLI oraz ograniczeń znajduje się w [`../tools/qmake-migration-kit/README.pl.md`](../tools/qmake-migration-kit/README.pl.md) oraz [`../tools/qmake-migration-kit/KNOWN_GAPS.pl.md`](../tools/qmake-migration-kit/KNOWN_GAPS.pl.md).

## Licencja

Materiał udostępniany jako część repozytorium `Cpp_CMake_template` na warunkach licencji [MIT](../LICENSE).

