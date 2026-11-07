cmake_minimum_required(VERSION 3.28.3)

project(YosysPass LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)

# ------------------------------------------------------------
# Yosys
# ------------------------------------------------------------

find_program(YOSYS_CONFIG yosys-config REQUIRED)

execute_process(
    COMMAND ${YOSYS_CONFIG} --cxxflags
    OUTPUT_VARIABLE YOSYS_CXXFLAGS
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

execute_process(
    COMMAND ${YOSYS_CONFIG} --ldflags
    OUTPUT_VARIABLE YOSYS_LDFLAGS
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

execute_process(
    COMMAND ${YOSYS_CONFIG} --ldlibs
    OUTPUT_VARIABLE YOSYS_LDLIBS
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

separate_arguments(YOSYS_CXXFLAGS)
separate_arguments(YOSYS_LDFLAGS)
separate_arguments(YOSYS_LDLIBS)

# ------------------------------------------------------------
# Yosys pass
# ------------------------------------------------------------

add_library(ListofPass MODULE
    MiterStutteringaPass.cc
    RegMemInitPass.cc
)

target_compile_options(
    ListofPass
    PRIVATE
        ${YOSYS_CXXFLAGS}
)

target_link_options(
    ListofPass
    PRIVATE
        ${YOSYS_LDFLAGS}
)

target_link_libraries(
    ListofPass
    PRIVATE
        ${YOSYS_LDLIBS}
)

# Yosys expects a plugin called something like:
# MiterStutteringaPass.so
set_target_properties(
    ListofPass
    PROPERTIES
        PREFIX ""
        OUTPUT_NAME "MiterStutteringaPass"
)

target_compile_options(
    ListofPass
    PRIVATE
        ${YOSYS_CXXFLAGS}
        -std=c++20
)