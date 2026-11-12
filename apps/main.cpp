/**
 * @file main.cpp
 * @brief Command-line entry point for cpp_template_cli.
 */
#include <cpp_template/cli_parser.hpp>
#include <cpp_template/error/exception.hpp>
#include <cpp_template/greeter.hpp>
#include <cpp_template/version.hpp>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <iostream>
#include <span>
#include <string_view>

namespace {

void write_error_line(const char* prefix, const char* detail) noexcept {
  (void)std::fputs(prefix, stderr);
  if (detail != nullptr) {
    (void)std::fputs(detail, stderr);
  }
  (void)std::fputc('\n', stderr);
}

} // namespace

/**
 * @brief Application entry point.
 * @param argc Command-line argument count.
 * @param argv Command-line argument vector.
 * @return EXIT_SUCCESS on completion, EXIT_FAILURE on invalid arguments or runtime error.
 */
int main(int argc, char* argv[]) {
  try {
    const auto options = cpp_template::parse_cli(argc, argv);

    if (options.show_help) {
      std::string_view prog = "cpp_template_cli";
      if (argc > 0 && argv != nullptr) {
        const std::span<char* const> raw_args{argv, static_cast<std::size_t>(argc)};
        if (raw_args.front() != nullptr) {
          prog = raw_args.front();
        }
      }
      std::cout << cpp_template::format_help(prog);
      return EXIT_SUCCESS;
    }

    if (options.show_version) {
      const auto info = cpp_template::get_version_info();
      std::cout << info.name << ' ' << info.version << " (commit " << info.git_commit << ")\n";
      return EXIT_SUCCESS;
    }

    const cpp_template::greeter greeter{options.style};
    std::cout << greeter.greet(options.name) << '\n';

    // note: echo collected input paths when provided on the command line
    for (const auto& input_path : options.inputs) {
      std::cout << "input: " << input_path << '\n';
    }
    return EXIT_SUCCESS;
  } catch (const cpp_template::error::exception& ex) {
    write_error_line("error: ", ex.what());
    return EXIT_FAILURE;
  } catch (const std::exception& ex) {
    write_error_line("unexpected error: ", ex.what());
    return EXIT_FAILURE;
  } catch (...) {
    write_error_line("unexpected unknown error", nullptr);
    return EXIT_FAILURE;
  }
}
