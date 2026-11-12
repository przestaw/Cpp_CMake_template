/**
 * @file allocator-header-example.h
 * @brief Reference snippet: replacing C++17-deprecated std::allocator<T>::pointer for C++20.
 *
 * Pre-C++20 spelling removed in C++20:
 *   using pointer = typename std::allocator<T>::pointer;
 *
 * When a third-party header cannot be upgraded immediately, apply a build-tree
 * header overlay scoped PRIVATE to the affected target and gated on the exact
 * package version hash.
 */
#pragma once

#include <memory>

template <class T>
struct DemoAllocatorTypes {
    using pointer = typename std::allocator_traits<std::allocator<T>>::pointer;
};
