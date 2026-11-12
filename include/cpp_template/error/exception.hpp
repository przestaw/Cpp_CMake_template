/**
 * @file exception.hpp
 * @brief Domain and command-line exception hierarchy for cpp_template.
 */
#ifndef CPP_TEMPLATE_ERROR_EXCEPTION_HPP
#define CPP_TEMPLATE_ERROR_EXCEPTION_HPP

#include <stdexcept>
#include <string>

namespace cpp_template::error {

/**
 * @brief Base exception type for all recoverable cpp_template errors.
 */
class exception : public std::runtime_error {
public:
  /**
   * @brief Constructs an exception with a human-readable diagnostic message.
   * @param message Diagnostic description of the failure.
   */
  explicit exception(const std::string& message) : std::runtime_error(message) {}
};

/**
 * @brief Exception thrown when domain validation or runtime preconditions fail.
 */
class runtime_exception : public exception {
public:
  /**
   * @brief Constructs a runtime domain exception.
   * @param message Diagnostic description of the runtime failure.
   */
  explicit runtime_exception(const std::string& message) : exception(message) {}
};

/**
 * @brief Exception thrown when command-line arguments are malformed or unknown.
 */
class cli_parse_error : public exception {
public:
  /**
   * @brief Constructs a command-line parsing error.
   * @param message Diagnostic description of the invalid option or value.
   */
  explicit cli_parse_error(const std::string& message) : exception(message) {}
};

} // namespace cpp_template::error

#endif // CPP_TEMPLATE_ERROR_EXCEPTION_HPP
