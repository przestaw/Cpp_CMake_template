TEMPLATE = app
TARGET = demo
QT = core
# strict_c++ selects -std=c++17 instead of gnu++17, matching CXX_EXTENSIONS OFF in CMakeLists.txt.
CONFIG += console c++17 strict_c++
CONFIG -= app_bundle debug_and_release
include(settings.pri)
load(demo_settings)
SOURCES += main.cpp
INCLUDEPATH += $$OUT_PWD
# PYTHON can be overridden on the qmake command line (Windows has no python3 by default).
isEmpty(PYTHON): PYTHON = python3
SCHEMAS = $$PWD/demo.schema
schema.input = SCHEMAS
schema.output = demo_generated.h
schema.commands = $$shell_quote($$PYTHON) $$shell_quote($$PWD/generate_header.py) ${QMAKE_FILE_IN} ${QMAKE_FILE_OUT}
schema.depends = $$PWD/generate_header.py
schema.variable_out = GENERATED_FILES
schema.CONFIG += no_link target_predeps
QMAKE_EXTRA_COMPILERS += schema
PRE_TARGETDEPS += demo_generated.h
INSTALLS += target
target.path = /demo/bin
