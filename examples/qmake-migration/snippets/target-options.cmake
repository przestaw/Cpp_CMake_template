# ==== TARGET-SCOPED COMPILER, MACRO & LINKER OPTIONS ====
# Keep MSVC conformance flags PRIVATE to C++ compilation on targets that require them
# (for example, targets including headers that use ISO operator keywords such as `not`).
target_compile_options(legacy_component PRIVATE
    "$<$<COMPILE_LANG_AND_ID:CXX,MSVC>:/permissive->"
)

# DLL producer macro stays PRIVATE so consumers resolve declarations to Q_DECL_IMPORT.
target_compile_definitions(shared_component PRIVATE DEMO_SHARED_BUILD)

# Optional ELF link check rejecting unresolved symbols at shared-library link time.
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    target_link_options(shared_component PRIVATE "LINKER:--no-undefined")
endif()
