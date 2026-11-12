cmake_minimum_required(VERSION 3.25)
project(MigrationDemo LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
find_package(Qt5 REQUIRED COMPONENTS Core)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/demo_generated.h"
    COMMAND Python3::Interpreter "${CMAKE_CURRENT_SOURCE_DIR}/generate_header.py"
            "${CMAKE_CURRENT_SOURCE_DIR}/demo.schema"
            "${CMAKE_CURRENT_BINARY_DIR}/demo_generated.h"
    DEPENDS generate_header.py demo.schema VERBATIM)
add_executable(demo main.cpp "${CMAKE_CURRENT_BINARY_DIR}/demo_generated.h")
target_include_directories(demo PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
target_compile_definitions(demo PRIVATE DEMO_FEATURE_LOADED
    "$<$<PLATFORM_ID:Windows>:DEMO_WINDOWS>"
    "$<$<NOT:$<PLATFORM_ID:Windows>>:DEMO_UNIX>")
target_link_libraries(demo PRIVATE Qt5::Core)
install(TARGETS demo RUNTIME DESTINATION bin COMPONENT runtime)
