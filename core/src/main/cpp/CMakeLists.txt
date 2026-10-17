cmake_minimum_required(VERSION 3.22.1)

project(projectmtv)

set(PROJECTMTV_RENDERING_POLICY "native" CACHE STRING "Core rendering policy: native")
set_property(CACHE PROJECTMTV_RENDERING_POLICY PROPERTY STRINGS native)
if(PROJECTMTV_RENDERING_POLICY STREQUAL "capped")
    message(FATAL_ERROR "The capped core artifact is retired. Configure without PROJECTMTV_RENDERING_POLICY or use native.")
endif()
if(NOT PROJECTMTV_RENDERING_POLICY STREQUAL "native")
    message(FATAL_ERROR "Unknown PROJECTMTV_RENDERING_POLICY: ${PROJECTMTV_RENDERING_POLICY}")
endif()

find_library(log-lib log)
find_library(GLESv3-lib GLESv3)
find_library(EGL-lib EGL)
find_library(android-lib android)

# projectM is built from source: the git submodule third_party/projectm (pinned release, see
# docs/THIRD_PARTY.md) plus the patches in tools/projectm-patches. It is linked statically into
# libprojectmtv.so; local crash capture adds its own library and dumper executable. The playlist library
# is not built: the app manages its own shuffled preset list straight from the APK assets.
get_filename_component(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../.. ABSOLUTE)
set(PROJECTM_SOURCE ${REPO_ROOT}/third_party/projectm)

# Reproducible builds (F-Droid rebuilds the app and compares it with our release APK): keep the
# checkout and NDK locations out of the output. Without this, the debug info that exists until the
# release build strips it still changes the linker's build ID, so every build path gives a
# different libprojectmtv.so. Applies to projectM too, which is added below.
add_compile_options(
    -ffile-prefix-map=${REPO_ROOT}=.
    -ffile-prefix-map=${ANDROID_NDK}=ndk
    -fdebug-compilation-dir=.  # the CMake build directory, which the prefix map does not cover
)
add_subdirectory(xcrash)

if(NOT EXISTS ${PROJECTM_SOURCE}/CMakeLists.txt OR NOT EXISTS ${PROJECTM_SOURCE}/vendor/projectm-eval/CMakeLists.txt)
    message(FATAL_ERROR "projectM sources missing: run `git submodule update --init --recursive`")
endif()

# Apply our patches (a series: later ones change lines next to earlier ones, so each patch can
# only be checked against the result of the ones before it). If the last one is in place, the
# whole series is. Otherwise undo the ones that are (an older series, newest first) and apply the
# series in order.
find_package(Git REQUIRED)
# Every ABI configures in parallel against the one shared checkout; the lock makes the check-and-apply
# below happen once at a time, so a second configure finds the series already in place.
set(PROJECTM_PATCH_LOCK ${REPO_ROOT}/core/.cxx/projectm-patches.lock)
file(MAKE_DIRECTORY ${REPO_ROOT}/core/.cxx)
file(LOCK ${PROJECTM_PATCH_LOCK} GUARD FILE RESULT_VARIABLE patch_lock TIMEOUT 600)
if(NOT patch_lock EQUAL 0)
    message(FATAL_ERROR "Could not lock the projectM checkout for patching: ${patch_lock}")
endif()
# Patches are applied only while CMake configures, so the build must configure again when the series
# changes: CONFIGURE_DEPENDS re-checks the glob on every build (a patch added or removed), and the
# configure dependency covers a patch whose content changes.
file(GLOB PROJECTM_PATCHES CONFIGURE_DEPENDS ${REPO_ROOT}/tools/projectm-patches/*.patch)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${PROJECTM_PATCHES})
list(SORT PROJECTM_PATCHES)
list(GET PROJECTM_PATCHES -1 PROJECTM_LAST_PATCH)
execute_process(COMMAND ${GIT_EXECUTABLE} apply --reverse --check ${PROJECTM_LAST_PATCH}
    WORKING_DIRECTORY ${PROJECTM_SOURCE} RESULT_VARIABLE series_applied OUTPUT_QUIET ERROR_QUIET)
if(NOT series_applied EQUAL 0)
    set(PROJECTM_PATCHES_NEWEST_FIRST ${PROJECTM_PATCHES})
    list(REVERSE PROJECTM_PATCHES_NEWEST_FIRST)
    foreach(patch IN LISTS PROJECTM_PATCHES_NEWEST_FIRST)
        execute_process(COMMAND ${GIT_EXECUTABLE} apply --reverse --check ${patch}
            WORKING_DIRECTORY ${PROJECTM_SOURCE} RESULT_VARIABLE applied OUTPUT_QUIET ERROR_QUIET)
        if(applied EQUAL 0)
            execute_process(COMMAND ${GIT_EXECUTABLE} apply --reverse ${patch} WORKING_DIRECTORY ${PROJECTM_SOURCE})
        endif()
    endforeach()
    foreach(patch IN LISTS PROJECTM_PATCHES)
        execute_process(COMMAND ${GIT_EXECUTABLE} apply ${patch}
            WORKING_DIRECTORY ${PROJECTM_SOURCE} RESULT_VARIABLE result)
        if(NOT result EQUAL 0)
            message(FATAL_ERROR "projectM patch does not apply: ${patch}. Reset the submodule: "
                                "git submodule foreach --recursive git checkout -- .")
        endif()
        message(STATUS "Applied projectM patch ${patch}")
    endforeach()
endif()
file(LOCK ${PROJECTM_PATCH_LOCK} RELEASE)

set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(ENABLE_PLAYLIST OFF CACHE BOOL "" FORCE)
set(ENABLE_SYSTEM_PROJECTM_EVAL OFF CACHE BOOL "" FORCE)
set(ENABLE_SYSTEM_GLM OFF CACHE BOOL "" FORCE)
set(ENABLE_SDL_UI OFF CACHE BOOL "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)  # static projectM ends up in a shared library
# projectm-eval regenerates its parser (Scanner.c, Compiler.c) whenever flex/bison are installed,
# and each flex/bison version writes slightly different code: the line numbers in the debug info,
# and so the build ID, then depend on the build machine. Always use the pre-generated sources.
set(CMAKE_DISABLE_FIND_PACKAGE_FLEX ON)
set(CMAKE_DISABLE_FIND_PACKAGE_BISON ON)
# projectM writes its version.h from CMAKE_PROJECT_VERSION*, which belong to the top-level project
# (ours, unversioned): a first configure happens to get projectM's version, but a re-configure of an
# existing build directory gets empty values and fails to compile. Set them from projectM's own
# project() call so every configure produces the same header.
file(STRINGS ${PROJECTM_SOURCE}/CMakeLists.txt PROJECTM_VERSION_LINE REGEX "^[ \t]*VERSION [0-9]+\\.[0-9]+\\.[0-9]+")
string(REGEX MATCH "([0-9]+)\\.([0-9]+)\\.([0-9]+)" CMAKE_PROJECT_VERSION "${PROJECTM_VERSION_LINE}")
if(NOT CMAKE_PROJECT_VERSION)
    message(FATAL_ERROR "projectM version not found in ${PROJECTM_SOURCE}/CMakeLists.txt")
endif()
set(CMAKE_PROJECT_VERSION_MAJOR ${CMAKE_MATCH_1})
set(CMAKE_PROJECT_VERSION_MINOR ${CMAKE_MATCH_2})
set(CMAKE_PROJECT_VERSION_PATCH ${CMAKE_MATCH_3})
add_subdirectory(${PROJECTM_SOURCE} projectm EXCLUDE_FROM_ALL)

add_library(projectmtv SHARED native-lib.cpp snapshot_fade.cpp preset_prewarm.cpp)

# Always optimise the JNI layer, also in debug builds that are sideloaded onto TVs.
target_compile_options(projectmtv PRIVATE -O2 -Wall -Wextra -Wno-unused-parameter)

target_link_libraries(projectmtv
    libprojectM::projectM
    ${log-lib}
    ${GLESv3-lib}
    ${EGL-lib}
    ${android-lib}
)

# projectM sets CMAKE_DEBUG_POSTFIX "d", which would name the debug build libprojectmtvd.so, a
# library ProjectMJNI never loads.
set_target_properties(projectmtv PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON
    DEBUG_POSTFIX ""
)
