cmake_minimum_required(VERSION 3.10)

# Set naming scheme 
set(PROJECT_NAME template)
project(${PROJECT_NAME})

set(PROJECT_DESCRIPTION "Template Cpp project with boost::test")

set(EXECUTABLE ${PROJECT_NAME}-program)
set(LIBRARY ${PROJECT_NAME}-lib)
set(TEST ${PROJECT_NAME}-test)
set(CHECK ${TEST}-check)
set(DOC ${PROJECT_NAME}-doc)

# Add custom cmake modules
list(APPEND CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}/cmake_modules/finders")
list(APPEND CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}/cmake_modules")

# Find external tools
find_package(LATEX)
find_package(Doxygen)

option(Debug_STDLIB "Enable stdlib debug" TRUE)

# Configure Clang-tidy
set(CLANG_TIDY_CHECKS "cppcoreguidelines-*,performance-*,portability-*,-clang-analyzer-*,readability-*,cert-*,bugprone-*")

find_package(CLANG_TIDY)
if(CLANG_TIDY_FOUND)
    set(CMAKE_CXX_CLANG_TIDY
            ${CLANG_TIDY_EXE}
            -checks=${CLANG_TIDY_CHECKS} )
endif()

# Add CTest
include(CTest)
enable_testing()

# Add external libs : boost
find_package(Boost COMPONENTS program_options unit_test_framework REQUIRED)
set(EXTERNAL_LIBS "Boost::program_options")

# CXX standard
set(CMAKE_CXX_STANDARD 23)

# Configure Toolchain
if (CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
    # using Clang
    if(USE_THREAD_CONTROL)
        set(CODE_CONTROL_FLAGS ${CODE_CONTROL_FLAGS} -Wthread-safety -fsanitize=thread)
    endif()
    if(USE_CODE_CONTROL)
        set(CODE_CONTROL_FLAGS ${CODE_CONTROL_FLAGS} -fsanitize=memory -fsanitize=address -fsanitize=undefined)
    endif()
    
    set(CMAKE_CXX_FLAGS_DEBUG   "${CMAKE_CXX_FLAGS_DEBUG}   -O0 -g ${CODE_CONTROL_FLAGS} -Wextra-tokens -Wambiguous-member-template -Wshadow -Wall -pedantic -Wextra -Wold-style-cast")
    set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3 -finline-functions -fmerge-all-constants -fvectorize -flto")

    include(LLVMtoolchain)

    set(CMAKE_EXE_LINKER_FLAGS ${CMAKE_EXE_LINKER_FLAGS} -fuse-ld=lld)

    set(CMAKE_C_ARCHIVE_CREATE "<CMAKE_AR> qcs <TARGET> <LINK_FLAGS> <OBJECTS>")
    set(CMAKE_C_ARCHIVE_FINISH   true)
    set(CMAKE_CXX_ARCHIVE_CREATE "<CMAKE_AR> qcs <TARGET> <LINK_FLAGS> <OBJECTS>")
    set(CMAKE_CXX_ARCHIVE_FINISH true)

elseif (CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    if(CMAKE_BUILD_TYPE EQUAL Release)
        cmake_policy(SET CMP0069 NEW)
        include(CheckIPOSupported)
        check_ipo_supported(IPO_SUPPORT)
        if(IPO_SUPPORT)
            set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)
        endif()
    endif()

    # using GCC
    set(CMAKE_CXX_FLAGS_DEBUG   "${CMAKE_CXX_FLAGS_DEBUG}   -O0 -Og -g -Wshadow -Wall -pedantic -Wextra -Wold-style-cast")
    set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3 -finline-functions -fdevirtualize -fmerge-constants")

    include(GNUtoolchain)
endif()

if(${Debug_STDLIB})
    set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -D_DEBUG -D_GLIBCXX_DEBUG")
endif()

# Set output directories
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/bin/${CMAKE_BUILD_TYPE})
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/bin/${CMAKE_BUILD_TYPE})
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/bin/${CMAKE_BUILD_TYPE})

include_directories(${PROJECT_SOURCE_DIR}/include ${BOOST_INCLUDE_DIR})

# Include src and test for library and test-check
add_subdirectory("include")
add_subdirectory("src")
add_subdirectory("test")

# library
add_library(${LIBRARY} ${LIB_SRC} ${LIB_INC})
add_dependencies(${LIBRARY} ${CHECK})

# Program executable
add_executable(${EXECUTABLE} src/main.cpp)
add_dependencies(${EXECUTABLE} ${LIBRARY})
target_link_libraries(${EXECUTABLE} ${LIBRARY})
target_link_libraries(${EXECUTABLE} ${EXTERNAL_LIBS})

# "all" target
if(LATEX_FOUND OR DOXYGEN_FOUND)
    # Only valid if documentation tools are present
    add_subdirectory(doc)
    add_custom_target(build-all DEPENDS ${DOC} ${PROGRAM} ${LIB} ${CHECK} ${TEST})
else()
    add_custom_target(build-all DEPENDS ${PROGRAM} ${LIB} ${CHECK} ${TEST})
endif()
