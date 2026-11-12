TEMPLATE = lib
TARGET = core
include(../common.pri)
CONFIG += staticlib
DEFINES += CORE_STATIC
HEADERS += counter.h
SOURCES += counter.cpp
