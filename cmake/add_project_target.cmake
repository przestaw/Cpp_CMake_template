include_guard(GLOBAL)

include(target_warnings)

# ==== PROJECT TARGET CONFIGURATION ====
# Applies standard C++20 requirements, scoped warnings, sanitizers, static analysis,
# unity build batching, and IDE folder organization to an internal target.
function(cpp_template_configure_target target_name)
  set(_options "")
  set(_one_value_args FOLDER)
  set(_multi_value_args "")
  cmake_parse_arguments(ARG "${_options}" "${_one_value_args}" "${_multi_value_args}" ${ARGN})

  set_target_properties(${target_name} PROPERTIES
    CXX_STANDARD 20
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF
  )

  if(ARG_FOLDER)
    set_target_properties(${target_name} PROPERTIES FOLDER "${ARG_FOLDER}")
  endif()

  # NOTE: Apply unity builds per target rather than globally so generated or
  # third-party targets with conflicting anonymous-namespace symbols stay isolated.
  if(ENABLE_UNITY_BUILD)
    set_target_properties(${target_name} PROPERTIES
      UNITY_BUILD ON
      UNITY_BUILD_BATCH_SIZE "${UNITY_BUILD_BATCH_SIZE}"
    )
  endif()

  cpp_template_apply_warnings(${target_name})
  cpp_template_apply_sanitizers(${target_name})
  cpp_template_apply_clang_tidy(${target_name})
endfunction()
