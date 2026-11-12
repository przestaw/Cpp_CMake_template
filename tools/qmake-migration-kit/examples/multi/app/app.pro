TEMPLATE = app
TARGET = multi_app
include(../common.pri)
CONFIG += console
SOURCES += main.cpp
INCLUDEPATH += $$PWD/../core
LIBS += -L$$OUT_PWD/../core -lcore
win32: PRE_TARGETDEPS += $$OUT_PWD/../core/core.lib
else: PRE_TARGETDEPS += $$OUT_PWD/../core/libcore.a
target.path = /multi/bin
data.files = data/config.txt
data.path = /multi/share
INSTALLS += target data
