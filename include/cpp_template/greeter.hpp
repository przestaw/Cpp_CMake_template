/**
 * @file greeter.hpp
 * @brief Example C++20 greeting component illustrating library target design.
 */
#ifndef CPP_TEMPLATE_GREETER_HPP
#define CPP_TEMPLATE_GREETER_HPP

#include <concepts>
#include <string>
#include <string_view>

namespace cpp_template {

/**
 * @brief Supported output tone styles for formatted greetings.
 */
enum class greeting_style {
  casual,
  formal,
};

/**
 * @brief Concept matching string-like types convertible to std::string_view.
 */
template <typename T>
concept string_like = std::convertible_to<const T&, std::string_view>;

/**
 * @brief Formats validated greeting messages in a chosen style.
 */
class greeter {
public:
  /**
   * @brief Constructs a greeter with the requested style.
   * @param style Output greeting tone (defaults to casual).
   */
  explicit constexpr greeter(greeting_style style = greeting_style::casual) noexcept
      : style_(style) {}

  /**
   * @brief Formats a greeting message for a non-empty recipient name.
   * @param target Recipient name (leading/trailing ASCII whitespace is trimmed).
   * @return Formatted greeting string.
   * @throws error::runtime_exception If target is empty or whitespace-only.
   */
  [[nodiscard]] std::string greet(std::string_view target) const;

  /**
   * @brief Generic overload accepting any string_like type via C++20 concepts.
   * @tparam T Type satisfying string_like.
   * @param target Recipient name.
   * @return Formatted greeting string.
   */
  template <string_like T> [[nodiscard]] std::string greet_any(const T& target) const {
    return greet(std::string_view{target});
  }

  /**
   * @brief Returns the active greeting style.
   * @return Configured greeting_style value.
   */
  [[nodiscard]] constexpr greeting_style style() const noexcept { return style_; }

private:
  greeting_style style_;
};

} // namespace cpp_template

#endif // CPP_TEMPLATE_GREETER_HPP
