/**
 * @file test_framework.hpp
 * @brief Dual-mode test harness: uses GoogleTest when CPP_TEMPLATE_USE_GTEST is defined,
 *        otherwise provides a zero-dependency C++20 assertion runner.
 */
#ifndef CPP_TEMPLATE_TESTS_TEST_FRAMEWORK_HPP
#define CPP_TEMPLATE_TESTS_TEST_FRAMEWORK_HPP

#if defined(CPP_TEMPLATE_USE_GTEST)
#include <gtest/gtest.h>
#else

#include <array>
#include <cstddef>
#include <cstdlib>
#include <exception>
#include <iostream>
#include <source_location>
#include <span>
#include <sstream>
#include <string_view>

namespace cpp_template::testing {

using test_fn                              = void (*)();
inline constexpr std::size_t kMaxTestCases = 256U;

/**
 * @brief Registered unit test descriptor.
 */
struct test_case {
  std::string_view suite{};
  std::string_view name{};
  test_fn body = nullptr;
};

/**
 * @brief Fixed-capacity registry avoiding dynamic allocation during static initialization.
 */
struct registry_storage {
  std::array<test_case, kMaxTestCases> items{};
  std::size_t count = 0U;
};

/**
 * @brief Returns the process-wide unit test registry.
 * @return Reference to registry_storage.
 */
inline registry_storage& registry() noexcept {
  static registry_storage store{};
  return store;
}

/**
 * @brief Returns the mutable failure counter for the active test run.
 * @return Reference to failure count.
 */
inline int& failure_count() noexcept {
  static int failures = 0;
  return failures;
}

/**
 * @brief Static registrar helper invoked by the TEST() macro without throwing.
 */
struct registrar {
  registrar(std::string_view suite, std::string_view name, test_fn body) noexcept {
    auto& store = registry();
    if (store.count < store.items.size()) {
      store.items.at(store.count) = test_case{.suite = suite, .name = name, .body = body};
      ++store.count;
    }
  }
};

/**
 * @brief Records a failed expectation with source file and line context.
 * @param expr Stringified assertion expression.
 * @param detail Optional diagnostic detail.
 * @param loc Call-site source location.
 */
inline void record_failure(std::string_view expr, std::string_view detail,
                           std::source_location loc = std::source_location::current()) {
  ++failure_count();
  std::cerr << loc.file_name() << ':' << loc.line() << ": Failure\n"
            << "  Expected: " << expr << '\n';
  if (!detail.empty()) {
    std::cerr << "  Detail:   " << detail << '\n';
  }
}

/**
 * @brief Checks that a boolean expression evaluates to true.
 */
inline void expect_true(bool condition, std::string_view expr,
                        std::source_location loc = std::source_location::current()) {
  if (!condition) {
    record_failure(expr, "evaluated to false", loc);
  }
}

/**
 * @brief Checks that a boolean expression evaluates to false.
 */
inline void expect_false(bool condition, std::string_view expr,
                         std::source_location loc = std::source_location::current()) {
  if (condition) {
    record_failure(expr, "evaluated to true", loc);
  }
}

/**
 * @brief Checks equality between two comparable values.
 */
template <typename Lhs, typename Rhs>
void expect_eq(const Lhs& lhs, const Rhs& rhs, std::string_view lhs_str, std::string_view rhs_str,
               std::source_location loc = std::source_location::current()) {
  if (!(lhs == rhs)) {
    std::ostringstream detail;
    detail << lhs_str << " != " << rhs_str;
    record_failure("equality", detail.str(), loc);
  }
}

/**
 * @brief Checks inequality between two comparable values.
 */
template <typename Lhs, typename Rhs>
void expect_ne(const Lhs& lhs, const Rhs& rhs, std::string_view lhs_str, std::string_view rhs_str,
               std::source_location loc = std::source_location::current()) {
  if (!(lhs != rhs)) {
    std::ostringstream detail;
    detail << lhs_str << " == " << rhs_str;
    record_failure("inequality", detail.str(), loc);
  }
}

/**
 * @brief Checks that invoking a callable throws ExpectedException.
 */
template <typename ExpectedException, typename Callable>
void expect_throw(Callable&& fn, std::string_view expr,
                  std::source_location loc = std::source_location::current()) {
  try {
    fn();
  } catch (const ExpectedException&) {
    return;
  } catch (...) {
    record_failure(expr, "threw unexpected exception type", loc);
    return;
  }
  record_failure(expr, "did not throw", loc);
}

/**
 * @brief Runs registered tests, optionally filtered by `--suite=<name>`.
 * @param argc Command-line argument count.
 * @param argv Command-line argument vector.
 * @return EXIT_SUCCESS if at least one test ran and all passed, EXIT_FAILURE otherwise.
 */
inline int run_all(int argc, char* argv[]) noexcept {
  try {
    std::string_view suite_filter{};
    if (argc > 1 && argv != nullptr) {
      const std::span<char* const> raw_args{argv, static_cast<std::size_t>(argc)};
      for (char* raw : raw_args.subspan(1U)) {
        if (raw == nullptr) {
          continue;
        }
        const std::string_view arg{raw};
        if (arg.starts_with("--suite=")) {
          suite_filter = arg.substr(std::string_view{"--suite="}.size());
        }
      }
    }

    std::size_t executed = 0;
    int failed_cases     = 0;
    const auto& store    = registry();
    const std::span<const test_case> active_cases{store.items.data(), store.count};

    for (const auto& tc : active_cases) {
      if (!suite_filter.empty() && tc.suite != suite_filter) {
        continue;
      }

      ++executed;
      const int before = failure_count();
      try {
        tc.body();
      } catch (const std::exception& ex) {
        record_failure("no unhandled exception", ex.what());
      } catch (...) {
        record_failure("no unhandled exception", "unknown non-std exception");
      }

      if (failure_count() > before) {
        ++failed_cases;
        std::cerr << "[  FAILED  ] " << tc.suite << '.' << tc.name << '\n';
      } else {
        std::cout << "[       OK ] " << tc.suite << '.' << tc.name << '\n';
      }
    }

    if (executed == 0U) {
      std::cerr << "No matching test cases executed.\n";
      return EXIT_FAILURE;
    }

    std::cout << "[==========] " << executed << " test(s) ran, " << failed_cases << " failed.\n";
    return (failed_cases == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
  } catch (...) {
    return EXIT_FAILURE;
  }
}

} // namespace cpp_template::testing

#define TEST(suite_name, test_name)                                               \
  static void suite_name##_##test_name##_impl();                                  \
  static const ::cpp_template::testing::registrar suite_name##_##test_name##_reg{ \
      #suite_name, #test_name, &suite_name##_##test_name##_impl};                 \
  static void suite_name##_##test_name##_impl()

#define EXPECT_TRUE(cond) ::cpp_template::testing::expect_true(static_cast<bool>(cond), #cond)

#define EXPECT_FALSE(cond) \
  ::cpp_template::testing::expect_false(static_cast<bool>(cond), "!(" #cond ")")

#define EXPECT_EQ(lhs, rhs) ::cpp_template::testing::expect_eq((lhs), (rhs), #lhs, #rhs)

#define EXPECT_NE(lhs, rhs) ::cpp_template::testing::expect_ne((lhs), (rhs), #lhs, #rhs)

#define EXPECT_THROW(stmt, expected_exception)                               \
  ::cpp_template::testing::expect_throw<expected_exception>([&]() { stmt; }, \
                                                            #stmt " throws " #expected_exception)

#endif // defined(CPP_TEMPLATE_USE_GTEST)

#endif // CPP_TEMPLATE_TESTS_TEST_FRAMEWORK_HPP
