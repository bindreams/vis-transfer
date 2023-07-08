cmake_minimum_required(VERSION 3.25)
project(vis-transfer-recv)

file(GLOB_RECURSE sources CONFIGURE_DEPENDS "src/*.cpp" "src/*.hpp")
add_executable(application ${sources})
set_target_properties(application PROPERTIES OUTPUT_NAME "vis-recv")
target_compile_features(application PRIVATE cxx_std_23)

target_include_directories(application PRIVATE ${OpenCV_INCLUDE_DIRS})
find_package(OpenCV CONFIG REQUIRED)
target_link_libraries(application PRIVATE ${OpenCV_LIBS})
find_package(ZXing CONFIG REQUIRED)
target_link_libraries(application PRIVATE ZXing::ZXing)
find_package(llfio CONFIG REQUIRED)
target_link_libraries(application PRIVATE llfio::dl)
find_package(cryptopp CONFIG REQUIRED)
target_link_libraries(application PRIVATE cryptopp::cryptopp)
find_package(fmt CONFIG REQUIRED)
target_link_libraries(application PRIVATE fmt::fmt)

include(InstallRequiredSystemLibraries)
install(TARGETS application)
install(IMPORTED_RUNTIME_ARTIFACTS application RUNTIME_DEPENDENCY_SET application_RUNTIME_DEPENDENCY_SET)
set(system32_regex "^$ENV{SystemRoot}\\system32")
string(REPLACE "\\" "[\\/\\\\]" system32_regex "${system32_regex}")
install(RUNTIME_DEPENDENCY_SET application_RUNTIME_DEPENDENCY_SET
	PRE_EXCLUDE_REGEXES "api-ms-.*"
	POST_EXCLUDE_REGEXES "${system32_regex}"
)
