#include <QtCore/QCoreApplication>
#include "demo_generated.h"
#ifndef DEMO_FEATURE_LOADED
#error Missing project feature
#endif
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    return DEMO_VALUE == 7 ? 0 : 1;
}
