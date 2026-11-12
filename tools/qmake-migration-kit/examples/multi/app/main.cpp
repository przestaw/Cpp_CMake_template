#include <QtCore/QCoreApplication>
#include "counter.h"

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    Counter counter;
    int last = 0;
    QObject::connect(&counter, &Counter::changed, [&last](int value) { last = value; });
    counter.increment();
    counter.increment();
    return last == 2 && counter.value() == 2 ? 0 : 1;
}
