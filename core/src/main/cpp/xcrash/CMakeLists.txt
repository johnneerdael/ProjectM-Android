# Keep upstream source and its build file unchanged. Scope NDK compatibility options to
# these targets instead of inheriting the old -Weverything policy into the engine.
set(XCRASH_SOURCE_DIR "${REPO_ROOT}/third_party/xcrash/xcrash_lib/src/main/cpp")
add_subdirectory("${XCRASH_SOURCE_DIR}" "${CMAKE_CURRENT_BINARY_DIR}/upstream")
foreach(target xcrash xcrash_dumper)
    # New Clang releases add warnings to -Weverything. Retain useful warnings and
    # -Werror without treating every newly introduced diagnostic as an upstream bug.
    target_compile_options(${target} PRIVATE
        -Wno-everything -Wall -Wextra -Wno-unused-but-set-variable)
    set_target_properties(${target} PROPERTIES DEBUG_POSTFIX "")
endforeach()
# AGP packages shared libraries automatically, but this .so-named executable is a
# separate native-build output. Include it even when AGP requests only shared targets.
add_dependencies(xcrash xcrash_dumper)
