#include <cpp_template/error/exception.hpp>
#include <cpp_template/greeter.hpp>
#include <string>
#include <string_view>

namespace cpp_template {
namespace {

/**
 * @brief Strips leading and trailing ASCII whitespace from a string_view.
 * @param text Input view.
 * @return Trimmed sub-view.
 */
[[nodiscard]] constexpr std::string_view trim_ascii(std::string_view text) noexcept {
  constexpr std::string_view kWhitespace = " \t\r\n\f\v";
  const auto first                       = text.find_first_not_of(kWhitespace);
  if (first == std::string_view::npos) {
    return {};
  }
  const auto last = text.find_last_not_of(kWhitespace);
  return text.substr(first, last - first + 1U);
}

} // namespace

std::string greeter::greet(std::string_view target) const {
  const std::string_view clean_target = trim_ascii(target);
  if (clean_target.empty()) {
    throw error::runtime_exception("Greeting target name must not be empty.");
  }

  // note: keep formatting branch-simple and locale-independent
  if (style_ == greeting_style::formal) {
    return "Good day, " + std::string{clean_target} + ".";
  }
  return "Hello, " + std::string{clean_target} + "!";
}

} // namespace cpp_template
