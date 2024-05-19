set(BUNDLED_VCPKG_PATH "${CMAKE_CURRENT_SOURCE_DIR}/.vcpkg")
set(BUNDLED_VCPKG_TAG "2024.03.25")

if (NOT EXISTS "${BUNDLED_VCPKG_PATH}")
	find_program(GIT_EXECUTABLE git REQUIRED)
	execute_process(
		COMMAND "${GIT_EXECUTABLE}"
			-c advice.detachedHead=false
			clone https://github.com/microsoft/vcpkg
			--branch "${BUNDLED_VCPKG_TAG}"
			"${BUNDLED_VCPKG_PATH}"
		COMMAND_ERROR_IS_FATAL ANY
	)
endif()

if(WIN32)
	# Windows is the only platform with dynamic linkage by default. Force static.
	if (DEFINED ENV{VCPKG_TARGET_TRIPLET})
		set(VCPKG_TARGET_TRIPLET "$ENV{VCPKG_TARGET_TRIPLET}")  # To print a message later
		unset(ENV{VCPKG_TARGET_TRIPLET})
	endif()

	if (DEFINED VCPKG_TARGET_TRIPLET)
		string(REGEX REPLACE "^(\\w+)-windows$" "\\1-windows-static" NEW_VCPKG_TARGET_TRIPLET "${VCPKG_TARGET_TRIPLET}")
		message(WARNING "Vcpkg target triplet has been redefined from \"${VCPKG_TARGET_TRIPLET}\" to \"${NEW_VCPKG_TARGET_TRIPLET}\"")
	else()
		set(NEW_VCPKG_TARGET_TRIPLET "x64-windows-static")
	endif()

	unset(VCPKG_TARGET_TRIPLET)
	set(VCPKG_TARGET_TRIPLET "${NEW_VCPKG_TARGET_TRIPLET}" CACHE STRING "" FORCE)
endif()

include("${BUNDLED_VCPKG_PATH}/scripts/buildsystems/vcpkg.cmake")
