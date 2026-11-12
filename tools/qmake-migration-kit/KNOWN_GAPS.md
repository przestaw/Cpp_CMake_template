# Known gaps

**English** | [Polski](KNOWN_GAPS.pl.md)

Highest risk first (detailed breakdown also available in [`KNOWN_GAPS.pl.md`](KNOWN_GAPS.pl.md)):

- **Capture not yet executed on Windows/MSVC (`nmake`/`jom`) or macOS.** Riskiest areas: `nmake` inline response files (`@<<`), `;` launcher lists with Windows paths, `cl` batch mode with `/Fo<dir>`, `link.exe`/`lib.exe` parsing, missing Windows DLL dependency inventory (`dumpbin`), and missing Mach-O/`@rpath` handling.
- **Generators**: Visual Studio and Xcode do not support compiler/linker launchers. `read_file_api` matches `build_type` by configuration name before falling back to the first File API configuration, while `capture cmake` invokes single-config `CMAKE_BUILD_TYPE` builds unless adapted to pass `--config` for Ninja Multi-Config.
- **`moc`/`uic`/`rcc`/`rc.exe` calls are not captured**, so `moc`-level defines/includes and Windows `.rc` resources are not compared directly. Generated TUs are counted, not compared file by file.
- **Unity builds and PCH** produce `tu.missing` / `include.forced` findings that require policy entries. Capture profiles must disable `debug_and_release` (`CONFIG-=debug_and_release`); this is not enforced automatically.
- **Install comparison** checks relative paths, ELF `NEEDED`/`RUNPATH`, and the executable bit, not file contents (qmake strips binaries on install). Final packages (`CPack` vs legacy packagers, as required by the completion criteria in [`../../docs/qmake-cmake-guide.md`](../../docs/qmake-cmake-guide.md)) are not compared by `qmig`. Performance on very large repositories has not been benchmarked.
- **Mapper, reported only**: `TRANSLATIONS`, QML modules, `lex`/`yacc`, `QMAKE_SUBSTITUTES`, pre/post link hooks, extra targets, private Qt modules, mobile/wasm/static-Qt finalisation, deployment tools (`windeployqt`/`macdeployqt`), `INSTALL_RPATH`, and DLL export header generation (see DLL boundary rules in [`../../docs/qmake-cmake-guide.md`](../../docs/qmake-cmake-guide.md)).
- **Qt 6**: the source scan is regex-based and finds API names, not runtime behaviour changes (`QList`/`QHash`, `qsizetype`, `QVariant`, UTF-8 defaults, Multimedia). The built-in module table covers up to Qt 6.5 (the installed Qt 6 remains authoritative). `QT_DISABLE_DEPRECATED_UP_TO` (Qt 6.5+) was not verified at run time because the test host used Qt 6.4.2. Draft mode `6` emits standard CMake targets; switching to `qt_standard_project_setup()` / `qt_add_executable()` / `qt_add_qml_module()` after retiring Qt 5 is documented in [`../../docs/qmake-cmake-guide.md`](../../docs/qmake-cmake-guide.md).
- **Workflow**: policy entries do not carry owner or expiry metadata; `init` discovery of `SUBDIRS` roots is text-based; `pkg-config` mapping has no end-to-end runnable example.
