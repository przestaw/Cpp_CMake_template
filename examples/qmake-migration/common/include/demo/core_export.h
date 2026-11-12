/**
 * @file core_export.h
 * @brief Symbol visibility macro for the democore shared library.
 *
 * DEMO_CORE_BUILD must be defined PRIVATE on the democore producer target only.
 * Downstream consumers omit DEMO_CORE_BUILD so declarations resolve to Q_DECL_IMPORT.
 */
#pragma once

#include <QtCore/qglobal.h>

#if defined(DEMO_CORE_BUILD)
#  define DEMO_CORE_EXPORT Q_DECL_EXPORT
#else
#  define DEMO_CORE_EXPORT Q_DECL_IMPORT
#endif
