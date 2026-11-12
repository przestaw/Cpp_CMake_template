# ==== CORE LIBRARY TARGET ====
# NOTE: Sources and public headers are listed explicitly rather than collected
# via `file(GLOB ...)`, ensuring CMake detects added/removed files reliably.
set(CPP_TEMPLATE_PUBLIC_HEADERS
  "${PROJECT_SOURCE_DIR}/include/cpp_template/cli_parser.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpp_template/greeter.hpp"
  "${PROJECT_SOURCE_DIR}/include/cpp_template/error/exception.hpp"
  "${PROJECT_BINARY_DIR}/include/cpp_template/version.hpp"
)

set(CPP_TEMPLATE_SOURCES
  cli_parser.cpp
  greeter.cpp
)

add_library(cpp_template ${CPP_TEMPLATE_SOURCES} ${CPP_TEMPLATE_PUBLIC_HEADERS})
add_library(cpp_template::cpp_template ALIAS cpp_template)

# NOTE: Generator expressions separate in-tree build include paths from the
# relocatable installed package layout (`find_package(cpp_template CONFIG)`).
target_include_directories(cpp_template
  PUBLIC
    $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
    $<BUILD_INTERFACE:${PROJECT_BINARY_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)

# NOTE: `cxx_std_20` is `PUBLIC` because public headers (`greeter.hpp`,
# `cli_parser.hpp`) use C++20 `<concepts>`, `<span>`, and designated initializers.
target_compile_features(cpp_template PUBLIC cxx_std_20)

cpp_template_configure_target(cpp_template FOLDER "Libraries")
