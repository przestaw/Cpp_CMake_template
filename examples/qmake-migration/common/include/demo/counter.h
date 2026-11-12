/**
 * @file counter.h
 * @brief Shared QObject class and exported Qt meta-namespace used by the reference slice.
 */
#pragma once

#ifndef DEMO_FEATURE_LOADED
#error "Expected DEMO_FEATURE_LOADED from the project feature/compile contract."
#endif

#include <QObject>

#include "demo/core_export.h"

namespace Demo {
// NOTE: Standalone Q_NAMESPACE_EXPORT line ensures CMake AUTOMOC discovers the
// namespace meta-object and exports staticMetaObject across Windows DLL boundaries.
Q_NAMESPACE_EXPORT(DEMO_CORE_EXPORT)

enum class Mode {
    Normal,
    Fast,
};
Q_ENUM_NS(Mode)
} // namespace Demo

/**
 * @brief Minimal QObject backed by a build-time generated schema constant.
 */
class DEMO_CORE_EXPORT Counter : public QObject {
    Q_OBJECT
public:
    explicit Counter(QObject* parent = nullptr);
    [[nodiscard]] int value() const;
};
