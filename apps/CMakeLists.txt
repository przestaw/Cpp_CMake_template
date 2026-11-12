# ==== CLI EXECUTABLE TARGET ====
add_executable(cpp_template_cli
  main.cpp
)

# NOTE: Link against the namespaced alias `cpp_template::cpp_template` with
# `PRIVATE` scope so missing target names fail at CMake configure time rather
# than producing cryptic unresolved linker errors.
target_link_libraries(cpp_template_cli
  PRIVATE
    cpp_template::cpp_template
)

cpp_template_configure_target(cpp_template_cli FOLDER "Apps")
