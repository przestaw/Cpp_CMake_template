cmake_minimum_required(VERSION 3.25)

project(MigrationExample LANGUAGES CXX)

# ==== QT MAJOR SELECTION ====
# NOTE: Keep Qt major selection explicit (`5` for same-Qt parity against qmake/Qt 5.15,
# `6` for the staged Qt 6 upgrade check) so CMake never silently switches Qt majors.
set(TUTORIAL_QT_MAJOR "5" CACHE STRING "Qt major version (5 or 6) for this build")
if(NOT TUTORIAL_QT_MAJOR MATCHES "^[56]$")
    message(FATAL_ERROR "TUTORIAL_QT_MAJOR must be 5 or 6")
endif()

find_package(Qt${TUTORIAL_QT_MAJOR} REQUIRED COMPONENTS Core)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
include(GNUInstallDirs)

# ==== TARGET & OUTPUT DEFAULTS ====
set(CMAKE_AUTOMOC ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")

set(common "${CMAKE_CURRENT_SOURCE_DIR}/../common")
set(generated "${CMAKE_CURRENT_BINARY_DIR}/generated/generated_factor.h")

# ==== CUSTOM CODE GENERATOR ====
# NOTE: List generated headers that drive compilation as explicit `OUTPUT` files
# with `VERBATIM` argument handling and script + schema `DEPENDS` edges.
add_custom_command(
    OUTPUT "${generated}"
    COMMAND "${Python3_EXECUTABLE}" "${common}/generate.py"
            "${common}/factor.schema" "${generated}"
    DEPENDS "${common}/generate.py" "${common}/factor.schema"
    VERBATIM
)

# ==== SHARED LIBRARY PRODUCER (democore) ====
# NOTE: List `counter.h` explicitly so `AUTOMOC` discovers both `Q_OBJECT` and
# `Q_NAMESPACE_EXPORT` without relying on fragile transitive source scans.
add_library(democore SHARED
    "${common}/src/counter.cpp"
    "${common}/include/demo/counter.h"
    "${common}/include/demo/core_export.h"
    "${generated}"
)
target_compile_features(democore PUBLIC cxx_std_17)
set_target_properties(democore PROPERTIES CXX_EXTENSIONS OFF)

# NOTE: `DEMO_CORE_BUILD` MUST stay `PRIVATE` so `Q_DECL_EXPORT` never leaks to
# consumers (`main.cpp` enforces this at compile time).
target_compile_definitions(democore PRIVATE DEMO_CORE_BUILD DEMO_FEATURE_LOADED)
target_include_directories(democore
    PUBLIC "$<BUILD_INTERFACE:${common}/include>"
    PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/generated"
)
target_link_libraries(democore PUBLIC Qt${TUTORIAL_QT_MAJOR}::Core)

# ==== APPLICATION CONSUMER (demo) ====
add_executable(demo "${common}/src/main.cpp")
set_target_properties(demo PROPERTIES CXX_EXTENSIONS OFF)
target_compile_definitions(demo PRIVATE DEMO_FEATURE_LOADED)
target_link_libraries(demo PRIVATE democore)

# ==== RUNTIME STAGING ====
# NOTE: Minimal install rule for staging comparison. Shared-library `VERSION`/`SOVERSION`
# symlinks (see `../snippets/install-versioning.cmake`), `INSTALL_RPATH`, CMake package
# exports, and Qt runtime deployment (`windeployqt`) are explicit follow-up choices.
install(TARGETS demo democore
    RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
    LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
    ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
)
