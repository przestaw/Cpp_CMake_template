include_guard(GLOBAL)

# ==== SCOPED COMPILER WARNINGS ====
# Attaches strict warning flags to an internal target with PRIVATE visibility.
function(cpp_template_apply_warnings target_name)
  # NOTE: Warning flags are always attached as `PRIVATE` so downstream consumers
  # linking against `cpp_template::cpp_template` via `find_package()` or
  # `FetchContent` are never forced into our internal warning policy.
  if(MSVC)
    target_compile_options(${target_name}
      PRIVATE
        /W4
        /permissive-
        /Zc:__cplusplus
        /EHsc
    )
  elseif(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target_name}
      PRIVATE
        -Wall
        -Wextra
        -Wpedantic
        -Wshadow
        -Wold-style-cast
        -Wconversion
        -Wnull-dereference
        -Wformat=2
    )
  endif()
endfunction()

# ==== SCOPED SANITIZERS ====
# Attaches runtime sanitizer flags per target when ENABLE_SANITIZERS is active.
function(cpp_template_apply_sanitizers target_name)
  if(NOT ENABLE_SANITIZERS)
    return()
  endif()

  # NOTE: Sanitizer flags are scoped per target rather than appended to global
  # `CMAKE_CXX_FLAGS_*` strings, keeping flag composition explicit and predictable.
  if(MSVC)
    target_compile_options(${target_name} PRIVATE /fsanitize=address /Zi)
    # NOTE: MSVC's incremental linker is incompatible with ASan instrumentation metadata.
    target_link_options(${target_name} PRIVATE /INCREMENTAL:NO)
  elseif(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target_name}
      PRIVATE
        -fsanitize=address,undefined
        -fno-omit-frame-pointer
    )
    target_link_options(${target_name}
      PRIVATE
        -fsanitize=address,undefined
    )
  else()
    message(WARNING
      "ENABLE_SANITIZERS is ON, but compiler '${CMAKE_CXX_COMPILER_ID}' is not configured for sanitizers.")
  endif()
endfunction()

# ==== SCOPED CLANG-TIDY ====
# Attaches clang-tidy execution to an internal target without polluting third-party targets.
function(cpp_template_apply_clang_tidy target_name)
  if(NOT ENABLE_CLANG_TIDY OR NOT CPP_TEMPLATE_CLANG_TIDY_CMD)
    return()
  endif()

  # NOTE: Setting `CXX_CLANG_TIDY` on each owned target avoids running slow or
  # incompatible static analysis checks over external `FetchContent` dependencies.
  set_target_properties(${target_name} PROPERTIES
    CXX_CLANG_TIDY "${CPP_TEMPLATE_CLANG_TIDY_CMD}"
  )
endfunction()
