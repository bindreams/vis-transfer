cmake_minimum_required(VERSION 3.25)

include(scripts/cmake/bundled-vcpkg.cmake)
enable_vcpkg(VERSION 2024.03.25)

project(vis-transfer-recv)

file(GLOB_RECURSE sources CONFIGURE_DEPENDS "src/*.cpp" "src/*.hpp")
add_executable(application ${sources})
set_target_properties(application PROPERTIES OUTPUT_NAME "vis-recv")
target_compile_features(application PRIVATE cxx_std_23)
set_target_properties(application PROPERTIES
	MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
)

include(scripts/cmake/warnings.cmake)
target_compile_warnings(application PRIVATE
    GNU all extra pedantic error
    MSVC 4 X
)

find_package(CLI11 CONFIG REQUIRED)
target_link_libraries(application PRIVATE CLI11::CLI11)

find_package(avcpp CONFIG REQUIRED)
target_link_libraries(application PRIVATE avcpp::avcpp avcpp::FFmpeg)

find_package(ZXing CONFIG REQUIRED)
target_link_libraries(application PRIVATE ZXing::ZXing)

find_package(llfio CONFIG REQUIRED)
target_link_libraries(application PRIVATE llfio::sl)

find_package(cryptopp CONFIG REQUIRED)
target_link_libraries(application PRIVATE cryptopp::cryptopp)

find_package(fmt CONFIG REQUIRED)
target_link_libraries(application PRIVATE fmt::fmt)

install(TARGETS application)
