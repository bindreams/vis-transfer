cmake_minimum_required(VERSION 3.14.0)
include(CheckCXXCompilerFlag)

function(_target_try_add_option TARGET VISIBILITY FLAG)
    check_cxx_compiler_flag("${FLAG}" FLAG_SUPPORTED)

    if(FLAG_SUPPORTED)
        target_compile_options(${TARGET} ${VISIBILITY} "${FLAG}")
    endif()
endfunction()

function(_target_compile_warnings_for_visibility TARGET VISIBILITY)
    # Parse arguments --------------------------------------------------------------------------------------------------
    cmake_parse_arguments(ARGS "" "" "GNU;MSVC" ${ARGN})
    if (DEFINED ARGS_UNPARSED_ARGUMENTS)
        list(JOIN ARGS_UNPARSED_ARGUMENTS ", " ARGS_UNPARSED_ARGUMENTS_STRING)
        message(SEND_ERROR "Unrecognized ${VISIBILITY} arguments: ${ARGS_UNPARSED_ARGUMENTS_STRING}.")
        return()
    endif()
    # ------------------------------------------------------------------------------------------------------------------
    set(GNU_SPECIAL_FLAGS_pedantic "-pedantic")

    if (CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "GNU")
        foreach(FLAG IN LISTS ARGS_GNU)
            if (DEFINED GNU_SPECIAL_FLAGS_${FLAG})
                _target_try_add_option(${TARGET} ${VISIBILITY} "${GNU_SPECIAL_FLAGS_${FLAG}}")
            else()
                _target_try_add_option(${TARGET} ${VISIBILITY} "-W${FLAG}")
            endif()
        endforeach()
    elseif(CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
        foreach(FLAG IN LISTS ARGS_MSVC)
            _target_try_add_option(${TARGET} ${VISIBILITY} "/W${FLAG}")
        endforeach()
    endif()
endfunction()

function(target_compile_warnings TARGET)
    # Parse arguments --------------------------------------------------------------------------------------------------
    cmake_parse_arguments(ARGS "" "" "INTERFACE;PUBLIC;PRIVATE" ${ARGN})
    if (DEFINED ARGS_UNPARSED_ARGUMENTS)
        list(JOIN ARGS_UNPARSED_ARGUMENTS ", " ARGS_UNPARSED_ARGUMENTS_STRING)
        set(ERROR_MESSAGE "Unrecognized arguments: ${ARGS_UNPARSED_ARGUMENTS_STRING}.")

        cmake_parse_arguments(NESTED "" "" "GNU;MSVC" ${ARGS_UNPARSED_ARGUMENTS})
        if(NOT DEFINED NESTED_UNPARSED_ARGUMENTS)
            set(ERROR_MESSAGE "${ERROR_MESSAGE} Did you forget to specify INTERFACE/PUBLIC/PRIVATE?")
        endif()

        message(SEND_ERROR "${ERROR_MESSAGE}")
        return()
    endif()
    # ------------------------------------------------------------------------------------------------------------------

    _target_compile_warnings_for_visibility(${TARGET} INTERFACE "${ARGS_INTERFACE}")
    _target_compile_warnings_for_visibility(${TARGET} PUBLIC    "${ARGS_PUBLIC}")
    _target_compile_warnings_for_visibility(${TARGET} PRIVATE   "${ARGS_PRIVATE}")
endfunction()
