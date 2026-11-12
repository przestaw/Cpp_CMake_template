cmake_minimum_required(VERSION 3.25)

# ==== POLICIES ====
# NOTE: CMP0141 NEW must be set BEFORE `project()` so MSVC debug format selection
# uses `CMAKE_MSVC_DEBUG_INFORMATION_FORMAT` (e.g. `Embedded` -> `/Z7` for sccache)
# instead of hardcoding `/Zi` into default compiler flags.
cmake_policy(SET CMP0141 NEW)

# ==== VERSIONING & PROJECT METADATA ====
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(git_version)

project(
  cpp_template
  VERSION "${CPP_TEMPLATE_SEMVER}"
  DESCRIPTION "Modern C++20 CMake project template"
  LANGUAGES CXX
)

# ==== LANGUAGE & IDE DEFAULTS ====
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set_property(GLOBAL PROPERTY USE_FOLDERS ON)

# ==== OPTIONS ====
# NOTE: `ENABLE_TESTS` defaults to OFF in base configurations so downstream
# `FetchContent` / `add_subdirectory` consumers do not pay for building unit tests;
# developer and CI `*-tests` presets turn it ON explicitly.
option(ENABLE_TESTS "Build unit tests and register CTest suite" OFF)
option(ENABLE_SCCACHE "Use sccache as compiler launcher when available" OFF)
option(ENABLE_UNITY_BUILD "Enable CMake unity builds on internal targets" OFF)
set(UNITY_BUILD_BATCH_SIZE "8" CACHE STRING "Maximum translation units per unity batch")
option(ENABLE_CLANG_TIDY "Run clang-tidy static analysis on internal targets" OFF)
option(ENABLE_SANITIZERS "Enable ASan/UBSan instrumentation on internal targets" OFF)
option(ENABLE_DOCS "Build Doxygen HTML documentation" OFF)
option(CPP_TEMPLATE_INSTALL "Generate install and CMake package export rules" ${PROJECT_IS_TOP_LEVEL})

# ==== DEPENDENCIES & TOOLING ====
if(ENABLE_SCCACHE)
  find_program(SCCACHE_PROGRAM NAMES sccache)
  if(SCCACHE_PROGRAM)
    set(CMAKE_CXX_COMPILER_LAUNCHER "${SCCACHE_PROGRAM}")
    if(MSVC)
      # NOTE: MSVC `/Zi` writes through a shared `mspdbsrv.exe` daemon that prevents
      # sccache from caching object files. `Embedded` emits `/Z7` debug info inline.
      set(CMAKE_MSVC_DEBUG_INFORMATION_FORMAT "$<$<CONFIG:Debug,RelWithDebInfo>:Embedded>")
    endif()
    message(STATUS "sccache enabled: ${SCCACHE_PROGRAM}")
  else()
    message(WARNING "ENABLE_SCCACHE is ON, but 'sccache' was not found on PATH; continuing without cache.")
  endif()
endif()

set(CPP_TEMPLATE_CLANG_TIDY_CMD "")
if(ENABLE_CLANG_TIDY)
  find_program(CLANG_TIDY_PROGRAM NAMES clang-tidy)
  if(CLANG_TIDY_PROGRAM)
    set(CPP_TEMPLATE_CLANG_TIDY_CHECKS
      "bugprone-*,cert-*,cppcoreguidelines-*,modernize-*,performance-*,portability-*,readability-*,-modernize-use-trailing-return-type,-readability-identifier-length,-cppcoreguidelines-avoid-magic-numbers,-readability-magic-numbers"
    )
    set(CPP_TEMPLATE_CLANG_TIDY_CMD
      "${CLANG_TIDY_PROGRAM}"
      "-checks=${CPP_TEMPLATE_CLANG_TIDY_CHECKS}"
    )
    if(MSVC)
      # NOTE: Ensure C++ exception handling semantics are enabled when clang-tidy
      # parses translation units in MSVC `clang-cl` driver mode on Windows.
      list(APPEND CPP_TEMPLATE_CLANG_TIDY_CMD "--extra-arg=/EHsc")
    endif()
    message(STATUS "clang-tidy enabled: ${CLANG_TIDY_PROGRAM}")
  else()
    message(WARNING "ENABLE_CLANG_TIDY is ON, but 'clang-tidy' was not found on PATH; skipping analysis.")
  endif()
endif()

include(GNUInstallDirs)
include(add_project_target)

# ==== GENERATED HEADERS ====
configure_file(
  "${PROJECT_SOURCE_DIR}/include/cpp_template/version.hpp.in"
  "${PROJECT_BINARY_DIR}/include/cpp_template/version.hpp"
  @ONLY
)

# ==== TARGETS ====
add_subdirectory(src)
add_subdirectory(apps)

# ==== TESTING ====
# NOTE: Synchronize `BUILD_TESTING` before including `CTest` so CTest's built-in
# `option(BUILD_TESTING ... ON)` respects `ENABLE_TESTS`.
set(BUILD_TESTING "${ENABLE_TESTS}" CACHE BOOL "Build the testing tree." FORCE)
if(ENABLE_TESTS)
  include(CTest)
  enable_testing()
  add_subdirectory(tests)
endif()

# ==== DOCUMENTATION ====
if(ENABLE_DOCS)
  find_package(Doxygen QUIET)
  if(Doxygen_FOUND)
    set(DOXYGEN_PROJECT_NAME "${PROJECT_NAME}")
    set(DOXYGEN_PROJECT_NUMBER "${CPP_TEMPLATE_VERSION}")
    set(DOXYGEN_PROJECT_BRIEF "${PROJECT_DESCRIPTION}")
    set(DOXYGEN_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/docs")
    set(DOXYGEN_GENERATE_HTML YES)
    set(DOXYGEN_GENERATE_LATEX NO)
    set(DOXYGEN_GENERATE_MAN NO)
    set(DOXYGEN_EXTRACT_ALL YES)
    set(DOXYGEN_GENERATE_TREEVIEW YES)
    set(DOXYGEN_USE_MDFILE_AS_MAINPAGE "${PROJECT_SOURCE_DIR}/README.md")

    doxygen_add_docs(
      cpp_template_docs
      "${PROJECT_SOURCE_DIR}/include"
      "${PROJECT_SOURCE_DIR}/src"
      "${PROJECT_SOURCE_DIR}/README.md"
      ALL
      COMMENT "Generating HTML API documentation in ${CMAKE_BINARY_DIR}/docs"
    )
    set_target_properties(cpp_template_docs PROPERTIES FOLDER "Docs")
  else()
    message(WARNING "ENABLE_DOCS is ON, but Doxygen was not found; skipping documentation build.")
  endif()
endif()

# ==== INSTALLATION & PACKAGE EXPORT ====
if(CPP_TEMPLATE_INSTALL)
  include(CMakePackageConfigHelpers)

  install(
    TARGETS cpp_template cpp_template_cli
    EXPORT cpp_templateTargets
    ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
    LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
    RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
    INCLUDES DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
  )

  install(
    DIRECTORY "${PROJECT_SOURCE_DIR}/include/"
    DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
    FILES_MATCHING PATTERN "*.hpp"
  )

  install(
    FILES "${PROJECT_BINARY_DIR}/include/cpp_template/version.hpp"
    DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/cpp_template"
  )

  install(
    EXPORT cpp_templateTargets
    FILE cpp_templateTargets.cmake
    NAMESPACE cpp_template::
    DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/cpp_template"
  )

  configure_package_config_file(
    "${PROJECT_SOURCE_DIR}/cmake/Config.cmake.in"
    "${PROJECT_BINARY_DIR}/cpp_templateConfig.cmake"
    INSTALL_DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/cpp_template"
  )

  write_basic_package_version_file(
    "${PROJECT_BINARY_DIR}/cpp_templateConfigVersion.cmake"
    VERSION "${PROJECT_VERSION}"
    COMPATIBILITY SameMajorVersion
  )

  install(
    FILES
      "${PROJECT_BINARY_DIR}/cpp_templateConfig.cmake"
      "${PROJECT_BINARY_DIR}/cpp_templateConfigVersion.cmake"
    DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/cpp_template"
  )
endif()

