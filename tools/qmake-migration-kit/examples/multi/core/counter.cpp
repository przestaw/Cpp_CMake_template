#include "counter.h"

void Counter::increment() {
    emit changed(++m_value);
}
