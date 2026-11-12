/**
 * @file counter.cpp
 * @brief Implementation of Counter reading GENERATED_FACTOR from generated_factor.h.
 */
#include "demo/counter.h"

#include "generated_factor.h"

Counter::Counter(QObject* parent) : QObject(parent) {}

int Counter::value() const {
    return GENERATED_FACTOR;
}
