# Qt 5 code that needs Qt5Compat (QRegExp, QTextCodec, QLinkedList) to build with Qt 6.
TEMPLATE = app
TARGET = qt5api
QT = core
CONFIG += console c++14
CONFIG -= app_bundle debug_and_release
SOURCES += main.cpp
target.path = /qt5api/bin
INSTALLS += target
