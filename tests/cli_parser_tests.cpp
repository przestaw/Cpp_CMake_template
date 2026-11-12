#include "test_framework.hpp"

#include <array>
#include <cpp_template/cli_parser.hpp>
#include <cpp_template/error/exception.hpp>
#include <string>
#include <string_view>

namespace {

TEST(CliParserTest, DefaultOptionsWhenNoArgumentsProvided) {
  const std::array<std::string_view, 0> args{};
  const auto opts = cpp_template::parse_cli_args(args);

  EXPECT_FALSE(opts.show_help);
  EXPECT_FALSE(opts.show_version);
  EXPECT_EQ(opts.name, std::string{"World"});
  EXPECT_EQ(opts.style, cpp_template::greeting_style::casual);
  EXPECT_TRUE(opts.inputs.empty());
}

TEST(CliParserTest, ParsesNameStyleAndMultipleInputs) {
  constexpr std::array<std::string_view, 6> args{
      "--name", "Grace", "--formal", "-i", "a.txt", "--input=b.txt",
  };
  const auto opts = cpp_template::parse_cli_args(args);

  EXPECT_EQ(opts.name, std::string{"Grace"});
  EXPECT_EQ(opts.style, cpp_template::greeting_style::formal);
  EXPECT_EQ(opts.inputs.size(), std::size_t{2});
  EXPECT_EQ(opts.inputs[0], std::string{"a.txt"});
  EXPECT_EQ(opts.inputs[1], std::string{"b.txt"});
}

TEST(CliParserTest, ParsesHelpAndVersionFlags) {
  constexpr std::array<std::string_view, 2> args{"-h", "--version"};
  const auto opts = cpp_template::parse_cli_args(args);

  EXPECT_TRUE(opts.show_help);
  EXPECT_TRUE(opts.show_version);
  EXPECT_NE(cpp_template::format_help("cpp_template_cli").find("--help"), std::string::npos);
}

TEST(CliParserTest, RejectsUnknownAndIncompleteFlags) {
  constexpr std::array<std::string_view, 1> unknown{"--unknown-flag"};
  EXPECT_THROW((void)cpp_template::parse_cli_args(unknown), cpp_template::error::cli_parse_error);

  constexpr std::array<std::string_view, 1> missing_name{"--name"};
  EXPECT_THROW((void)cpp_template::parse_cli_args(missing_name),
               cpp_template::error::cli_parse_error);

  constexpr std::array<std::string_view, 1> missing_input{"-i"};
  EXPECT_THROW((void)cpp_template::parse_cli_args(missing_input),
               cpp_template::error::cli_parse_error);
}

} // namespace
