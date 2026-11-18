cmake_minimum_required(VERSION 3.20)
set(PSXRECOMP_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/psxrecomp" CACHE PATH
    "Path to psxrecomp")
if(NOT EXISTS "${PSXRECOMP_ROOT}/runtime/runtime.cmake")
    message(FATAL_ERROR
        "PSXRecomp runtime is missing: ${PSXRECOMP_ROOT}/runtime/runtime.cmake\n"
        "This project expects the psxrecomp framework checkout at ${PSXRECOMP_ROOT}.\n"
        "Run: git submodule update --init --recursive\n"
        "If psxrecomp/ is not a submodule, set -DPSXRECOMP_ROOT=<path-to-psxrecomp>.")
endif()

project(RogueTripRecomp LANGUAGES C CXX)

set(PSX_RECOMP_UI ON CACHE BOOL "Launcher" FORCE)
set(PSX_SETUP_WIZARD ON CACHE BOOL "Setup wizard" FORCE)
set(PSX_REWIND OFF CACHE BOOL "Rewind requires the optional rollback backend")
include("${PSXRECOMP_ROOT}/runtime/runtime.cmake")

set(PSX_PRELOADED_MODS "${CMAKE_CURRENT_SOURCE_DIR}/mods/preloaded")
if(NOT IS_DIRECTORY "${PSX_PRELOADED_MODS}")
    set(PSX_PRELOADED_MODS "NONE")
endif()

set(_RT_US_DISPATCH "${CMAKE_CURRENT_SOURCE_DIR}/generated/us/SLUS_006.43_dispatch.c")
set(_RT_EU_DISPATCH "${CMAKE_CURRENT_SOURCE_DIR}/generated/eu/SLES_014.17_dispatch.c")
set(_RT_US_REMAP    "${CMAKE_CURRENT_SOURCE_DIR}/generated/us_remap.h")
set(_RT_EU_REMAP    "${CMAKE_CURRENT_SOURCE_DIR}/generated/eu_remap.h")

if(EXISTS "${_RT_US_DISPATCH}" AND EXISTS "${_RT_EU_DISPATCH}" AND
   EXISTS "${_RT_US_REMAP}"    AND EXISTS "${_RT_EU_REMAP}" AND
   NOT PSXRECOMP_FORCE_SETUP_HOST)
    message(STATUS "RogueTripRecomp: Unified multi-region build (SLUS-00643 US/RUS + SLES-01417 Europe)")
    file(GLOB _RT_US_SHARDS "${CMAKE_CURRENT_SOURCE_DIR}/generated/us/SLUS_006.43_full_*.c")
    file(GLOB _RT_EU_SHARDS "${CMAKE_CURRENT_SOURCE_DIR}/generated/eu/SLES_014.17_full_*.c")

    set_source_files_properties(${_RT_US_SHARDS} "${_RT_US_DISPATCH}" PROPERTIES
        COMPILE_OPTIONS "-include;${_RT_US_REMAP}")
    set_source_files_properties(${_RT_EU_SHARDS} "${_RT_EU_DISPATCH}" PROPERTIES
        COMPILE_OPTIONS "-include;${_RT_EU_REMAP}")

    psxrecomp_add_game_runtime(psx-runtime
        PRELOADED_MODS_DIR "${PSX_PRELOADED_MODS}"
        ENABLE_SETUP_WIZARD
        WINDOW_TITLE "Rogue Trip Recompiled"
        DEFAULT_GAME_CONFIG_PATH "game.toml"
        MAX_PLAYERS 2
        GEN_MARKER "multi_region_dispatch.c"
        GEN_FULL_GLOB
            "generated/us/SLUS_006.43_full_*.c"
            "generated/us/SLUS_006.43_dispatch.c"
            "generated/eu/SLES_014.17_full_*.c"
            "generated/eu/SLES_014.17_dispatch.c"
        CODEGEN_SETUP_SOURCES codegen_setup.c
    )
    target_compile_definitions(psx-runtime PRIVATE PSX_MULTI_REGION_DISPATCH=1)
    set_property(SOURCE
        "${PSXRECOMP_ROOT}/runtime/src/game_dispatch_compat.c"
        APPEND PROPERTY COMPILE_DEFINITIONS
        PSX_GAME_DISPATCH_HAS_NATIVE_OK=1
        PSX_GAME_DISPATCH_HAS_NATIVE_OK_FULL=1)
else()
    psxrecomp_add_game_runtime(psx-runtime
        PRELOADED_MODS_DIR "${PSX_PRELOADED_MODS}"
        ENABLE_SETUP_WIZARD
        WINDOW_TITLE "Rogue Trip Recompiled"
        DEFAULT_GAME_CONFIG_PATH "game.toml"
        MAX_PLAYERS 2
        GEN_MARKER "generated/SLUS_006.43_dispatch.c"
        GEN_FULL_GLOB "generated/SLUS_006.43_full_*.c"
        CODEGEN_SETUP_SOURCES codegen_setup.c
    )
endif()

foreach(_PSX_RUNTIME_CONFIG game.toml game_options.toml)
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${_PSX_RUNTIME_CONFIG}")
        add_custom_command(TARGET psx-runtime POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${CMAKE_CURRENT_SOURCE_DIR}/${_PSX_RUNTIME_CONFIG}"
                "$<TARGET_FILE_DIR:psx-runtime>/${_PSX_RUNTIME_CONFIG}"
            COMMENT "Staging ${_PSX_RUNTIME_CONFIG}"
            VERBATIM)
    endif()
endforeach()
