#include <QtCore/QCoreApplication>
#include <cassert>
#include <cstdio>
#include <cstring>

#if !defined(PRE_A) || !defined(PRE_B)
#error both forced includes are required
#endif
#ifndef HIDDEN_FLAG_DEFINE
#error HIDDEN_FLAG_DEFINE missing
#endif

static int checks = 0;
static bool counted() { ++checks; return true; }

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    assert(counted());  // side effect disappears when NDEBUG is defined
    std::printf("%s level=%d asserts=%s\n", APP_NAME, LEVEL, checks ? "on" : "off");
    return std::strcmp(APP_NAME, "hazards") == 0 ? 0 : 1;
}
