# Constructs that qmake accepts silently but that a naive CMake port gets wrong.
TEMPLATE = app
TARGET = hazards
QT = core
CONFIG += console c++17 strict_c++
CONFIG -= app_bundle debug_and_release
SOURCES += main.cpp
HEADERS += pre_a.h pre_b.h
# String-literal define: qmake pastes the value into the shell command unchanged.
DEFINES += APP_NAME=\\\"hazards\\\"
# Two forced includes: target_compile_options() would de-duplicate the second "-include".
QMAKE_CXXFLAGS += -include $$PWD/pre_a.h -include $$PWD/pre_b.h
# A define hidden in compiler flags (moc does not see it under qmake).
QMAKE_CXXFLAGS += -DHIDDEN_FLAG_DEFINE=1
include(levels.pri)
target.path = /hazards/bin
INSTALLS += target
