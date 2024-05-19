cmake_minimum_required(VERSION 3.20)

#[=======================================================================[.rst:
.. command:: enable_vcpkg

  Load a bundled copy of vcpkg as if by specifying its toolchain file.

  ::

    enable_vcpkg(VERSION version [PATH path])

  The ``VERSION`` argument accepts any git ref (a tag or a commit hash) and
  vcpkg will be checked out to that ref. You can also specify a branch such
  as ``master``, but branches will not get automatically pulled from origin
  unless you delete and re-clone vcpkg. In addition, tracking a branch is not
  recommended because your dependencies will not be pinned to a specific
  version and your project will eventually fail to build.

  The ``PATH`` argument can be used to specify a different directory for vcpkg
  (default is ``.vcpkg``). If ``PATH`` is relative, it is interpreted relative
  to ``CMAKE_CURRENT_BINARY_DIR``. You can place vcpkg outside the build
  directory to skip re-cloning with clean builds.

#]=======================================================================]
macro(enable_vcpkg)
	_enable_vcpkg(${ARGN})
	include("${ENABLE_VCPKG_PATH}/scripts/buildsystems/vcpkg.cmake")  # Needs to happen at global scope
	unset(ENABLE_VCPKG_PATH)
endmacro()


function(_enable_vcpkg)
    # Parse arguments --------------------------------------------------------------------------------------------------
	cmake_parse_arguments(ARGS "" "PATH;VERSION" "" ${ARGN})

    if (DEFINED ARGS_UNPARSED_ARGUMENTS)
		list(JOIN ARGS_UNPARSED_ARGUMENTS ", " ARGS_UNPARSED_ARGUMENTS_STRING)
        message(SEND_ERROR "enable_vcpkg: unrecognized arguments: ${ARGS_UNPARSED_ARGUMENTS_STRING}.")
        return()
    endif()

	if (NOT DEFINED ARGS_PATH)
		set(ARGS_PATH ".vcpkg")
	endif()

	if (NOT DEFINED ARGS_VERSION)
		message(SEND_ERROR "enable_vcpkg: missing value for parameter `VERSION`.")
        return()
	endif()
    # ------------------------------------------------------------------------------------------------------------------

	find_program(GIT_EXECUTABLE git REQUIRED)

	if(NOT IS_ABSOLUTE "${ARGS_PATH}")
		cmake_path(ABSOLUTE_PATH ARGS_PATH BASE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}" NORMALIZE)
	endif()
	set(ENABLE_VCPKG_PATH "${ARGS_PATH}" PARENT_SCOPE)

	if (NOT EXISTS "${ARGS_PATH}")
		# Initial clone
		message(STATUS "Downloading bundled vcpkg (ref: ${ARGS_VERSION})")
		execute_process(
			COMMAND "${GIT_EXECUTABLE}"
				-c advice.detachedHead=false
				clone https://github.com/microsoft/vcpkg
				--branch "${ARGS_VERSION}"
				"${ARGS_PATH}"
			COMMAND_ERROR_IS_FATAL ANY
		)

	else()
		# Already cloned; verify that HEAD is at the correct position
		execute_process(
			COMMAND "${GIT_EXECUTABLE}" rev-parse HEAD "${ARGS_VERSION}"
			WORKING_DIRECTORY "${ARGS_PATH}"
			OUTPUT_VARIABLE REV_PARSE_OUTPUT
			RESULT_VARIABLE REV_PARSE_RESULT
		)

		message(DEBUG "git rev-parse exited with ${REV_PARSE_RESULT} and returned:\n${REV_PARSE_OUTPUT}")
		if(REV_PARSE_RESULT EQUAL 0)
			set(VCPKG_NEEDS_FETCH 0)

			string(STRIP "${REV_PARSE_OUTPUT}" REV_PARSE_OUTPUT)
			string(REPLACE "\n" ";" REV_PARSE_OUTPUT "${REV_PARSE_OUTPUT}")

			list(GET REV_PARSE_OUTPUT 0 CURRENT_COMMIT)
			list(GET REV_PARSE_OUTPUT 1 TARGET_COMMIT)

			if(CURRENT_COMMIT STREQUAL TARGET_COMMIT)
				set(VCPKG_NEEDS_CHECKOUT 0)
			else()
				set(VCPKG_NEEDS_CHECKOUT 1)
			endif()
		else()
			set(VCPKG_NEEDS_FETCH 1)
			set(VCPKG_NEEDS_CHECKOUT 1)
		endif()

		if(VCPKG_NEEDS_FETCH)
			message(VERBOSE "Running git fetch")
			execute_process(
				COMMAND "${GIT_EXECUTABLE}" fetch
				WORKING_DIRECTORY "${ARGS_PATH}"
				COMMAND_ERROR_IS_FATAL ANY
			)
		endif()

		if(VCPKG_NEEDS_CHECKOUT)
			message(VERBOSE "Running git checkout \"${ARGS_VERSION}\"")
			execute_process(
				COMMAND "${GIT_EXECUTABLE}"
					-c advice.detachedHead=false
					checkout "${ARGS_VERSION}"
				WORKING_DIRECTORY "${ARGS_PATH}"
				COMMAND_ERROR_IS_FATAL ANY
			)
		endif()
	endif()


	if(WIN32)
		# Windows is the only platform with dynamic linkage by default. Force static.
		if (DEFINED ENV{VCPKG_TARGET_TRIPLET})
			set(VCPKG_TARGET_TRIPLET "$ENV{VCPKG_TARGET_TRIPLET}")
			unset(ENV{VCPKG_TARGET_TRIPLET})
		endif()

		if (DEFINED VCPKG_TARGET_TRIPLET)
			string(REGEX REPLACE "^(\\w+)-windows$" "\\1-windows-static" NEW_VCPKG_TARGET_TRIPLET "${VCPKG_TARGET_TRIPLET}")

			if (NOT VCPKG_TARGET_TRIPLET STREQUAL NEW_VCPKG_TARGET_TRIPLET)
				message(WARNING "Vcpkg target triplet has been redefined from \"${VCPKG_TARGET_TRIPLET}\" to \"${NEW_VCPKG_TARGET_TRIPLET}\"")
			endif()
		else()
			set(NEW_VCPKG_TARGET_TRIPLET "x64-windows-static")
		endif()

		unset(VCPKG_TARGET_TRIPLET)
		set(VCPKG_TARGET_TRIPLET "${NEW_VCPKG_TARGET_TRIPLET}" CACHE STRING "" FORCE)
	endif()
endfunction()
