# ==== GIT VERSION DETECTION ====
# Resolves semantic version and short commit hash at configure time.
#
# Exposed plain variables (recomputed on every CMake configure run):
#   CPP_TEMPLATE_SEMVER      - Numeric MAJOR.MINOR.PATCH for `project(... VERSION ...)`
#   CPP_TEMPLATE_GIT_COMMIT  - Short 7-char git hash (or "unknown" outside git trees)
#   CPP_TEMPLATE_VERSION     - Full display version string (e.g. "0.1.0+g33771a6")

# ==== OVERRIDE INPUTS ====
# NOTE: Explicit override inputs are stored in the cache so packagers, CI release
# jobs, and source-archive builds (without a `.git` directory) can pin deterministic
# version metadata via `-DCPP_TEMPLATE_VERSION_OVERRIDE=...`.
set(CPP_TEMPLATE_VERSION_OVERRIDE "" CACHE STRING
  "Explicit semantic version override (e.g. 1.2.3) when building outside git")
set(CPP_TEMPLATE_COMMIT_OVERRIDE "" CACHE STRING
  "Explicit short commit hash override when building outside git")

# NOTE: Derived runtime/stamp variables MUST remain plain variables rather than
# CACHE entries. Evicting any legacy/accidental cache entries guarantees that
# switching branches or creating git tags in a long-lived build directory never
# freezes stale version metadata in `CMakeCache.txt`.
unset(CPP_TEMPLATE_SEMVER CACHE)
unset(CPP_TEMPLATE_GIT_COMMIT CACHE)
unset(CPP_TEMPLATE_VERSION CACHE)

set(_cpp_template_default_semver "0.1.0")
set(_cpp_template_semver "${_cpp_template_default_semver}")
set(_cpp_template_commit "unknown")

# ==== GIT QUERY ====
find_package(Git QUIET)

if(CPP_TEMPLATE_VERSION_OVERRIDE)
  string(REGEX REPLACE "^[vV]" "" _override_clean "${CPP_TEMPLATE_VERSION_OVERRIDE}")
  if(_override_clean MATCHES "^([0-9]+\\.[0-9]+\\.[0-9]+)")
    set(_cpp_template_semver "${CMAKE_MATCH_1}")
  else()
    message(WARNING
      "CPP_TEMPLATE_VERSION_OVERRIDE='${CPP_TEMPLATE_VERSION_OVERRIDE}' does not start "
      "with MAJOR.MINOR.PATCH; falling back to ${_cpp_template_default_semver}.")
  endif()
elseif(Git_FOUND AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/.git")
  execute_process(
    COMMAND "${GIT_EXECUTABLE}" describe --tags --abbrev=0 --match "v[0-9]*" --match "[0-9]*"
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    RESULT_VARIABLE _git_tag_rc
    OUTPUT_VARIABLE _git_tag_out
    ERROR_QUIET
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
  if(_git_tag_rc EQUAL 0 AND _git_tag_out MATCHES "^[vV]?([0-9]+\\.[0-9]+\\.[0-9]+)")
    set(_cpp_template_semver "${CMAKE_MATCH_1}")
  endif()
endif()

if(CPP_TEMPLATE_COMMIT_OVERRIDE)
  set(_cpp_template_commit "${CPP_TEMPLATE_COMMIT_OVERRIDE}")
elseif(Git_FOUND AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/.git")
  execute_process(
    COMMAND "${GIT_EXECUTABLE}" rev-parse --short=7 HEAD
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    RESULT_VARIABLE _git_rev_rc
    OUTPUT_VARIABLE _git_rev_out
    ERROR_QUIET
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
  if(_git_rev_rc EQUAL 0 AND NOT _git_rev_out STREQUAL "")
    set(_cpp_template_commit "${_git_rev_out}")
  endif()
endif()

# ==== PLAIN OUTPUT VARIABLES ====
set(CPP_TEMPLATE_SEMVER "${_cpp_template_semver}")
set(CPP_TEMPLATE_GIT_COMMIT "${_cpp_template_commit}")

if(CPP_TEMPLATE_VERSION_OVERRIDE)
  set(CPP_TEMPLATE_VERSION "${CPP_TEMPLATE_VERSION_OVERRIDE}")
elseif(NOT CPP_TEMPLATE_GIT_COMMIT STREQUAL "unknown")
  set(CPP_TEMPLATE_VERSION "${CPP_TEMPLATE_SEMVER}+g${CPP_TEMPLATE_GIT_COMMIT}")
else()
  set(CPP_TEMPLATE_VERSION "${CPP_TEMPLATE_SEMVER}")
endif()

unset(_cpp_template_default_semver)
unset(_cpp_template_semver)
unset(_cpp_template_commit)
unset(_override_clean)
unset(_git_tag_rc)
unset(_git_tag_out)
unset(_git_rev_rc)
unset(_git_rev_out)
