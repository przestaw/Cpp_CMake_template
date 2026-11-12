/**
 * @file main.cpp
 * @brief Consumer executable verifying DLL import boundaries, AUTOMOC enums, and codegen.
 */
#ifdef DEMO_CORE_BUILD
#error "Consumer target must NOT receive the producer macro DEMO_CORE_BUILD."
#endif

#include "demo/counter.h"

#include <QCoreApplication>
#include <QMetaEnum>

#include <iostream>

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    Counter counter;
    std::cout << Counter::staticMetaObject.className() << ':'
              << counter.value() << ':'
              << QMetaEnum::fromType<Demo::Mode>().valueToKey(0) << '\n';
    return counter.value() > 0 ? 0 : 1;
}
