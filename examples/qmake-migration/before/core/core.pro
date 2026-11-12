# ==== SHARED LIBRARY PRODUCER (democore) ====
include(../settings.pri)

TEMPLATE = lib
TARGET = democore
CONFIG += shared
QT = core

# NOTE: Producer-only macro; selects Q_DECL_EXPORT inside core_export.h.
DEFINES += DEMO_CORE_BUILD

INCLUDEPATH += $$PWD/../../common/include $$OUT_PWD
HEADERS += \
    $$PWD/../../common/include/demo/counter.h \
    $$PWD/../../common/include/demo/core_export.h
SOURCES += $$PWD/../../common/src/counter.cpp

# ==== CUSTOM SCHEMA CODE GENERATOR ====
SCHEMAS = $$PWD/../../common/factor.schema
schema.input = SCHEMAS
schema.output = generated_factor.h
schema.commands = $$PYTHON $$shell_quote($$PWD/../../common/generate.py) ${QMAKE_FILE_IN} ${QMAKE_FILE_OUT}
schema.depends = $$PWD/../../common/generate.py
schema.variable_out = HEADERS
schema.CONFIG += target_predeps no_link
QMAKE_EXTRA_COMPILERS += schema

# ==== OUTPUT & INSTALL LAYOUT ====
DESTDIR = $$OUT_PWD/../bin
win32:target.path = /bin
else:target.path = /lib
INSTALLS += target
