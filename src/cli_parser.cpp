#include <cpp_template/cli_parser.hpp>
#include <cpp_template/error/exception.hpp>
#include <cstddef>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

namespace cpp_template {

cli_options parse_cli_args(std::span<const std::string_view> args) {
  cli_options opts{};

  for (std::size_t idx = 0; idx < args.size(); ++idx) {
    const std::string_view token = args[idx];

    if (token == "-h" || token == "--help") {
      opts.show_help = true;
    } else if (token == "-v" || token == "--version") {
      opts.show_version = true;
    } else if (token == "--formal") {
      opts.style = greeting_style::formal;
    } else if (token == "-n" || token == "--name") {
      if (idx + 1U >= args.size()) {
        throw error::cli_parse_error("Missing value after option '" + std::string{token} + "'.");
      }
      opts.name = std::string{args[++idx]};
    } else if (token.starts_with("--name=")) {
      // note: support `--name=<value>` inline syntax in addition to `-n <value>`
      opts.name = std::string{token.substr(std::string_view{"--name="}.size())};
    } else if (token == "-i" || token == "--input") {
      if (idx + 1U >= args.size()) {
        throw error::cli_parse_error("Missing path after option '" + std::string{token} + "'.");
      }
      opts.inputs.emplace_back(args[++idx]);
    } else if (token.starts_with("--input=")) {
      const std::string_view path = token.substr(std::string_view{"--input="}.size());
      if (path.empty()) {
        throw error::cli_parse_error("Empty path in '--input='.");
      }
      opts.inputs.emplace_back(path);
    } else {
      throw error::cli_parse_error("Unknown command-line argument: '" + std::string{token} + "'.");
    }
  }

  return opts;
}

cli_options parse_cli(int argc, const char* const* argv) {
  if (argc <= 1 || argv == nullptr) {
    return cli_options{};
  }

  const std::span<const char* const> raw_args{argv, static_cast<std::size_t>(argc)};
  std::vector<std::string_view> tokens;
  tokens.reserve(raw_args.size() - 1U);
  for (const char* arg : raw_args.subspan(1U)) {
    if (arg != nullptr) {
      tokens.emplace_back(arg);
    }
  }
  return parse_cli_args(tokens);
}

std::string format_help(std::string_view program_name) {
  const std::string_view display_name = program_name.empty() ? "cpp_template_cli" : program_name;

  std::ostringstream out;
  out << "Usage: " << display_name << " [options]\n\n"
      << "Options:\n"
      << "  -h, --help           Show this help message and exit\n"
      << "  -v, --version        Print project version and git commit\n"
      << "  -n, --name <text>    Recipient name for greeting (default: World)\n"
      << "      --formal         Use formal greeting tone\n"
      << "  -i, --input <path>   Add an input path (may be repeated)\n";
  return out.str();
}

} // namespace cpp_template
