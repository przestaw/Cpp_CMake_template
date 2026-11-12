# ==== APPLICATION CONSUMER (demo) ====
include(../settings.pri)

TEMPLATE = app
TARGET = demo
CONFIG += console
CONFIG -= app_bundle
QT = core

# NOTE: Deliberately omits DEMO_CORE_BUILD so demo/core_export.h selects Q_DECL_IMPORT.
INCLUDEPATH += $$PWD/../../common/include
SOURCES += $$PWD/../../common/src/main.cpp

LIBS += -L$$OUT_PWD/../bin -ldemocore
unix:!macx:QMAKE_RPATHDIR += $$OUT_PWD/../bin

DESTDIR = $$OUT_PWD/../bin
target.path = /bin
INSTALLS += target
