# ==== UNIT & INTEGRATION TESTS ====
# NOTE: Supports `GTest` automatically when installed (e.g. via vcpkg or system
# packages), and falls back to a lightweight built-in C++20 assertion runner so
# `ctest` works out of the box on any C++20 compiler with zero external setup.
find_package(GTest CONFIG QUIET)

set(CPP_TEMPLATE_TEST_SOURCES
  cli_parser_tests.cpp
  greeter_tests.cpp
  test_framework.hpp
)

add_executable(cpp_template_tests ${CPP_TEMPLATE_TEST_SOURCES})

# NOTE: Link tests directly against `cpp_template::cpp_template` instead of
# recompiling `${CPP_TEMPLATE_SOURCES}` a second time.
target_link_libraries(cpp_template_tests
  PRIVATE
    cpp_template::cpp_template
)

target_include_directories(cpp_template_tests
  PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}"
)

cpp_template_configure_target(cpp_template_tests FOLDER "Tests")

if(GTest_FOUND)
  message(STATUS "Tests: using discovered GoogleTest package")
  target_compile_definitions(cpp_template_tests PRIVATE CPP_TEMPLATE_USE_GTEST=1)
  target_link_libraries(cpp_template_tests PRIVATE GTest::gtest_main)

  include(GoogleTest)
  gtest_discover_tests(cpp_template_tests)
else()
  message(STATUS "Tests: GTest not found; using built-in C++20 assertion runner")
  add_test(
    NAME cpp_template.greeter_tests
    COMMAND cpp_template_tests --suite=GreeterTest
  )
  add_test(
    NAME cpp_template.cli_parser_tests
    COMMAND cpp_template_tests --suite=CliParserTest
  )
endif()

# ==== CLI SMOKE TESTS ====
add_test(
  NAME cpp_template.cli_version
  COMMAND $<TARGET_FILE:cpp_template_cli> --version
)
add_test(
  NAME cpp_template.cli_help
  COMMAND $<TARGET_FILE:cpp_template_cli> --help
)
