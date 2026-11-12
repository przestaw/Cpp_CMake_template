/**
 * @file cli_parser.hpp
 * @brief Lightweight zero-dependency C++20 command-line option parser.
 */
#ifndef CPP_TEMPLATE_CLI_PARSER_HPP
#define CPP_TEMPLATE_CLI_PARSER_HPP

#include <cpp_template/greeter.hpp>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace cpp_template {

/**
 * @brief Parsed command-line configuration for the CLI executable.
 */
struct cli_options {
  bool show_help       = false;
  bool show_version    = false;
  std::string name     = "World";
  greeting_style style = greeting_style::casual;
  std::vector<std::string> inputs{};
};

/**
 * @brief Parses command-line argument tokens (excluding program name at argv[0]).
 * @param args Span of raw argument views after the executable name.
 * @return Populated cli_options structure.
 * @throws error::cli_parse_error On unknown flags or missing option values.
 */
[[nodiscard]] cli_options parse_cli_args(std::span<const std::string_view> args);

/**
 * @brief Convenience entry point converting standard main(argc, argv) arguments.
 * @param argc Argument count passed to main().
 * @param argv Argument vector passed to main().
 * @return Populated cli_options structure.
 * @throws error::cli_parse_error On unknown flags or missing option values.
 */
[[nodiscard]] cli_options parse_cli(int argc, const char* const* argv);

/**
 * @brief Builds the formatted `--help` usage text.
 * @param program_name Executable display name (typically argv[0]).
 * @return Multi-line help text suitable for printing to stdout.
 */
[[nodiscard]] std::string format_help(std::string_view program_name);

} // namespace cpp_template

#endif // CPP_TEMPLATE_CLI_PARSER_HPP
