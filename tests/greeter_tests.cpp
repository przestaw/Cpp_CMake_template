#include "test_framework.hpp"

#include <concepts>
#include <cpp_template/error/exception.hpp>
#include <cpp_template/greeter.hpp>
#include <cpp_template/version.hpp>
#include <string>

namespace {

static_assert(std::movable<cpp_template::greeter>);
static_assert(std::copyable<cpp_template::greeter>);

TEST(GreeterTest, CasualGreetingFormatsTrimmedTarget) {
  const cpp_template::greeter greeter{cpp_template::greeting_style::casual};
  EXPECT_EQ(greeter.style(), cpp_template::greeting_style::casual);
  EXPECT_EQ(greeter.greet("  Ada  "), std::string{"Hello, Ada!"});
}

TEST(GreeterTest, FormalGreetingUsesFormalTone) {
  const cpp_template::greeter greeter{cpp_template::greeting_style::formal};
  EXPECT_EQ(greeter.greet_any("Bjarne"), std::string{"Good day, Bjarne."});
}

TEST(GreeterTest, EmptyOrWhitespaceTargetThrowsRuntimeException) {
  const cpp_template::greeter greeter{};
  EXPECT_THROW((void)greeter.greet(""), cpp_template::error::runtime_exception);
  EXPECT_THROW((void)greeter.greet("   \t\n "), cpp_template::error::runtime_exception);
}

TEST(GreeterTest, VersionMetadataIsPopulated) {
  constexpr auto info = cpp_template::get_version_info();
  EXPECT_EQ(info.name, std::string_view{"cpp_template"});
  EXPECT_FALSE(info.version.empty());
  EXPECT_FALSE(info.semver.empty());
  EXPECT_FALSE(info.git_commit.empty());
}

} // namespace

#if !defined(CPP_TEMPLATE_USE_GTEST)
int main(int argc, char* argv[]) {
  return cpp_template::testing::run_all(argc, argv);
}
#endif
