cmake_minimum_required(VERSION 3.22)
project(projectm_regressions VERSION 4.2.0 LANGUAGES C CXX)

if(NOT PROJECTM_SOURCE)
    message(FATAL_ERROR "PROJECTM_SOURCE must point to the patched projectM checkout")
endif()
option(SANITIZERS "Enable ASan/UBSan" ON)
if(SANITIZERS)
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address,undefined)
endif()
if(APPLE)
    # The app's GLES framebuffer-discard hint has no equivalent in macOS OpenGL 3.2.
    add_compile_options("$<$<COMPILE_LANGUAGE:CXX>:-include${CMAKE_CURRENT_SOURCE_DIR}/macos_gl.hpp>")
endif()
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(ENABLE_PLAYLIST OFF CACHE BOOL "" FORCE)
set(ENABLE_SYSTEM_PROJECTM_EVAL OFF CACHE BOOL "" FORCE)
set(ENABLE_SDL_UI OFF CACHE BOOL "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(CMAKE_DISABLE_FIND_PACKAGE_FLEX ON)
set(CMAKE_DISABLE_FIND_PACKAGE_BISON ON)
if(APPLE)
    find_library(REGRESSION_OPENGL_FRAMEWORK OpenGL REQUIRED)
endif()
if(NOT APPLE)
    set(ENABLE_GLES ON CACHE BOOL "" FORCE)
    if(GL_LIBS)
        # projectM also calls find_package(OpenGL COMPONENTS GLES3). Use the same
        # supplied EGL/GLES flags for both consumers instead of system discovery.
        list(PREPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/gl-overrides")
        # projectM accepts supplied GL_LIBS without invoking discovery itself.
        # Instantiate the global override here for this parent harness too.
        find_package(OpenGL MODULE REQUIRED COMPONENTS GLES3)
        set(REGRESSION_GL_TARGET OpenGL::GLES3)
    else()
        find_package(PkgConfig REQUIRED)
        pkg_check_modules(EGL REQUIRED IMPORTED_TARGET egl)
        set(REGRESSION_GL_TARGET PkgConfig::EGL)
        if(GL_CFLAGS)
            add_compile_options("SHELL:${GL_CFLAGS}")
        endif()
    endif()
endif()
# Internal renderer headers use GLAD; load its declarations before forced GL shims.
include_directories("${PROJECTM_SOURCE}/vendor/glad/include")
add_subdirectory("${PROJECTM_SOURCE}" projectm)
add_executable(projectm-regressions regression_test.cpp)
add_executable(random-texture-regressions random_texture_test.cpp)
target_compile_features(projectm-regressions PRIVATE cxx_std_17)
target_compile_definitions(projectm-regressions PRIVATE GL_SILENCE_DEPRECATION)
target_include_directories(projectm-regressions PRIVATE
    "${PROJECTM_SOURCE}/src/libprojectM"
    "${PROJECTM_SOURCE}/vendor/hlslparser/src"
    "${PROJECTM_SOURCE}/vendor"
    "${PROJECTM_SOURCE}/vendor/projectm-eval/projectm-eval/api")
target_link_libraries(projectm-regressions PRIVATE libprojectM::projectM)
if(APPLE)
    target_link_libraries(projectm-regressions PRIVATE "${REGRESSION_OPENGL_FRAMEWORK}")
endif()
if(NOT APPLE)
    target_compile_definitions(projectm-regressions PRIVATE USE_GLES)
    target_link_libraries(projectm-regressions PRIVATE ${REGRESSION_GL_TARGET})
endif()
enable_testing()
add_executable(eel-constants-regressions eel_constants_test.cpp)
target_compile_features(eel-constants-regressions PRIVATE cxx_std_17)
target_include_directories(eel-constants-regressions PRIVATE "${PROJECTM_SOURCE}/vendor/projectm-eval/projectm-eval/api")
target_link_libraries(eel-constants-regressions PRIVATE libprojectM::projectM)
add_test(NAME eel-named-constants COMMAND eel-constants-regressions)
set_tests_properties(eel-named-constants PROPERTIES TIMEOUT 10 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0")
add_executable(warp-rotation-regressions warp_rotation_test.cpp)
target_compile_features(warp-rotation-regressions PRIVATE cxx_std_17)
target_compile_definitions(warp-rotation-regressions PRIVATE GL_SILENCE_DEPRECATION)
target_include_directories(warp-rotation-regressions PRIVATE
    "${PROJECTM_SOURCE}/src/libprojectM"
    "${PROJECTM_SOURCE}/vendor"
    "${PROJECTM_SOURCE}/vendor/projectm-eval/projectm-eval/api")
target_link_libraries(warp-rotation-regressions PRIVATE libprojectM::projectM)
if(APPLE)
    target_link_libraries(warp-rotation-regressions PRIVATE "${REGRESSION_OPENGL_FRAMEWORK}")
else()
    target_compile_definitions(warp-rotation-regressions PRIVATE USE_GLES)
    target_link_libraries(warp-rotation-regressions PRIVATE ${REGRESSION_GL_TARGET})
endif()
add_test(NAME warp-rotation-regressions COMMAND warp-rotation-regressions)
add_test(NAME legacy-warp-deformation COMMAND warp-rotation-regressions deformation)
add_test(NAME legacy-warp-diagonal COMMAND warp-rotation-regressions diagonal)
add_test(NAME warp-mesh-cache COMMAND warp-rotation-regressions cache)
add_test(NAME legacy-pixel-traversal COMMAND warp-rotation-regressions traversal)
set_tests_properties(legacy-pixel-traversal PROPERTIES TIMEOUT 30 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
set_tests_properties(warp-mesh-cache PROPERTIES TIMEOUT 30 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
set_tests_properties(legacy-warp-diagonal PROPERTIES TIMEOUT 30 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
set_tests_properties(legacy-warp-deformation PROPERTIES TIMEOUT 30 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
set_tests_properties(warp-rotation-regressions PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")

add_executable(user-texture-premultiplication-regressions user_texture_premultiplication_test.cpp)
target_compile_features(user-texture-premultiplication-regressions PRIVATE cxx_std_17)
target_compile_definitions(user-texture-premultiplication-regressions PRIVATE GL_SILENCE_DEPRECATION)
target_include_directories(user-texture-premultiplication-regressions PRIVATE
    "${PROJECTM_SOURCE}/src/libprojectM"
    "${PROJECTM_SOURCE}/vendor")
target_link_libraries(user-texture-premultiplication-regressions PRIVATE libprojectM::projectM)
if(APPLE)
    target_link_libraries(user-texture-premultiplication-regressions PRIVATE "${REGRESSION_OPENGL_FRAMEWORK}")
else()
    target_compile_definitions(user-texture-premultiplication-regressions PRIVATE USE_GLES)
    target_link_libraries(user-texture-premultiplication-regressions PRIVATE ${REGRESSION_GL_TARGET})
endif()
add_test(NAME user-texture-premultiplication-regressions COMMAND user-texture-premultiplication-regressions
    "${CMAKE_CURRENT_BINARY_DIR}/user-texture-premultiplication-fixtures")
set_tests_properties(user-texture-premultiplication-regressions PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
add_executable(texture-routing-regressions texture_routing_test.cpp)
target_compile_features(texture-routing-regressions PRIVATE cxx_std_17)
target_compile_definitions(texture-routing-regressions PRIVATE GL_SILENCE_DEPRECATION)
target_include_directories(texture-routing-regressions PRIVATE
    "${PROJECTM_SOURCE}/src/libprojectM"
    "${PROJECTM_SOURCE}/src/libprojectM/MilkdropPreset"
    "${PROJECTM_SOURCE}/vendor"
    "${PROJECTM_SOURCE}/vendor/projectm-eval/projectm-eval/api")
target_link_libraries(texture-routing-regressions PRIVATE libprojectM::projectM)
if(APPLE)
    target_link_libraries(texture-routing-regressions PRIVATE "${REGRESSION_OPENGL_FRAMEWORK}")
else()
    target_compile_definitions(texture-routing-regressions PRIVATE USE_GLES)
    target_link_libraries(texture-routing-regressions PRIVATE ${REGRESSION_GL_TARGET})
endif()
add_test(NAME texture-routing-regressions COMMAND texture-routing-regressions "${CMAKE_CURRENT_BINARY_DIR}/routing-fixtures")
set_tests_properties(texture-routing-regressions PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
add_executable(warp-zoom-regressions warp_zoom_test.cpp)
target_compile_features(warp-zoom-regressions PRIVATE cxx_std_17)
target_compile_definitions(warp-zoom-regressions PRIVATE GL_SILENCE_DEPRECATION)
target_include_directories(warp-zoom-regressions PRIVATE "${PROJECTM_SOURCE}/src/libprojectM")
# Use the engine's exported GL dependencies: system discovery creates its GLES
# imported target in the projectM subdirectory, outside this target's scope.
target_link_libraries(warp-zoom-regressions PRIVATE libprojectM::projectM)
if(APPLE)
    target_link_libraries(warp-zoom-regressions PRIVATE "${REGRESSION_OPENGL_FRAMEWORK}")
endif()
if(NOT APPLE)
    target_link_libraries(warp-zoom-regressions PRIVATE ${REGRESSION_GL_TARGET})
endif()
add_test(NAME warp-zoom-regressions COMMAND warp-zoom-regressions
    "${PROJECTM_SOURCE}/src/libprojectM/MilkdropPreset/Shaders/PresetWarpVertexShaderGlsl330.vert")
set_tests_properties(warp-zoom-regressions PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
foreach(control shape-sampler blur-range dynamic-controls legacy-compatibility custom-wave-inputs preset-inputs wave-colour border-topology sample-cap circle-geometry motion-uv-freshness program-cache framebuffer-lifetime)
    string(REPLACE "-" "_" source_name "${control}")
    add_executable(${control}-regressions ${source_name}_test.cpp)
    target_compile_features(${control}-regressions PRIVATE cxx_std_17)
    target_compile_definitions(${control}-regressions PRIVATE GL_SILENCE_DEPRECATION)
    target_include_directories(${control}-regressions PRIVATE
        "${PROJECTM_SOURCE}/src/libprojectM"
        "${PROJECTM_SOURCE}/src/libprojectM/MilkdropPreset"
        "${PROJECTM_SOURCE}/vendor"
        "${PROJECTM_SOURCE}/vendor/projectm-eval/projectm-eval/api")
    target_link_libraries(${control}-regressions PRIVATE libprojectM::projectM ${CMAKE_DL_LIBS})
    if(APPLE)
        target_link_libraries(${control}-regressions PRIVATE "${REGRESSION_OPENGL_FRAMEWORK}")
    endif()
    if(NOT APPLE)
        target_compile_definitions(${control}-regressions PRIVATE USE_GLES)
        target_link_libraries(${control}-regressions PRIVATE ${REGRESSION_GL_TARGET})
    endif()
endforeach()
add_test(NAME framebuffer-lifetime COMMAND framebuffer-lifetime-regressions)
set_tests_properties(framebuffer-lifetime PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
add_test(NAME program-cache-switch COMMAND program-cache-regressions)
set_tests_properties(program-cache-switch PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
add_test(NAME original-border-fan-topology COMMAND border-topology-regressions)
set_tests_properties(original-border-fan-topology PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
add_test(NAME source-wave-sample-caps COMMAND sample-cap-regressions)
add_test(NAME source-circle-closure COMMAND circle-geometry-regressions)
add_test(NAME authored-custom-dots COMMAND custom-wave-inputs-regressions dots)
add_test(NAME authored-single-custom-dot COMMAND custom-wave-inputs-regressions single)
set_tests_properties(source-wave-sample-caps source-circle-closure authored-custom-dots authored-single-custom-dot
    PROPERTIES TIMEOUT 30 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
add_test(NAME per-pixel-inverse-aspect COMMAND preset-inputs-regressions)
set_tests_properties(per-pixel-inverse-aspect PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
add_test(NAME custom-wave-input-windows COMMAND custom-wave-inputs-regressions)
add_test(NAME custom-wave-readonly-inputs COMMAND custom-wave-inputs-regressions readonly)
set_tests_properties(custom-wave-readonly-inputs PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
set_tests_properties(custom-wave-input-windows PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
foreach(control hue wave-alpha wave-topology opacity gamma echo-orientation)
    add_test(NAME legacy-${control} COMMAND legacy-compatibility-regressions ${control})
    set_tests_properties(legacy-${control} PROPERTIES TIMEOUT 30
        ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
endforeach()
set(DYNAMIC_PRESETS
    "319.milk"
    "Hexcollie - now entering the wormhole2 - mash0000 - if you like this, maybe you, like me, are insane.milk"
    "idiot - Forty Six and 2 (pushit!).milk")
set(DYNAMIC_HASHES
    ce88b6ef2083122dc103e270fbfee6f6abab02517e56932164f3c7faa456a989
    df44c85b71513f603fdff7e5d8b751b4de81a969d0af66f8acada49fd76e8449
    e0747d71b11ae571f9c6917962b62d197757a05379342c11ca350bb28d43e693)
foreach(index RANGE 0 2)
    list(GET DYNAMIC_PRESETS ${index} name)
    list(GET DYNAMIC_HASHES ${index} expected)
    file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/../../../main/assets/presets/${name}" actual)
    if(NOT actual STREQUAL expected)
        message(FATAL_ERROR "Dynamic-control witness changed: ${name}")
    endif()
endforeach()
add_test(NAME dynamic-original-presets COMMAND dynamic-controls-regressions presets
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../main/assets")
set_tests_properties(dynamic-original-presets PROPERTIES TIMEOUT 120
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
foreach(control wave display)
    add_test(NAME dynamic-${control}-controls COMMAND dynamic-controls-regressions ${control})
    set_tests_properties(dynamic-${control}-controls PROPERTIES TIMEOUT 60
        ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
endforeach()
add_test(NAME shape-sampler-regressions COMMAND shape-sampler-regressions
    "${CMAKE_CURRENT_BINARY_DIR}/shape-sampler-fixtures")
set(SHAPE_PRESET "${CMAKE_CURRENT_SOURCE_DIR}/../../../main/assets/presets/widest swing.milk")
file(SHA256 "${SHAPE_PRESET}" SHAPE_PRESET_HASH)
if(NOT SHAPE_PRESET_HASH STREQUAL "91fbdd07995c8a820c78513c899f60a0cbc950fcf52c90bbbf42cc51fb7b4604")
    message(FATAL_ERROR "The textured-shape witness preset changed")
endif()
add_test(NAME shape-sampler-preset COMMAND shape-sampler-regressions
    "${CMAKE_CURRENT_BINARY_DIR}/shape-sampler-preset-fixtures" "${SHAPE_PRESET}")
add_test(NAME blur-range-regressions COMMAND blur-range-regressions)
file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/blur-range-presets.tsv" BLUR_PRESET_ROWS)
foreach(row IN LISTS BLUR_PRESET_ROWS)
    string(REGEX MATCH "^([0-9a-f]+)\t(.+)$" matched "${row}")
    if(NOT matched)
        message(FATAL_ERROR "Invalid blur witness manifest row: ${row}")
    endif()
    set(expected "${CMAKE_MATCH_1}")
    set(preset_name "${CMAKE_MATCH_2}")
    file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/../../../main/assets/presets/${preset_name}" actual)
    if(NOT actual STREQUAL expected)
        message(FATAL_ERROR "Blur witness preset changed: ${preset_name}")
    endif()
endforeach()
add_test(NAME blur-range-render COMMAND blur-range-regressions gl
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../main/assets")
set_tests_properties(shape-sampler-regressions shape-sampler-preset blur-range-regressions PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
set_tests_properties(blur-range-render PROPERTIES TIMEOUT 120
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
add_executable(float-literal-regressions float_literal_test.cpp)
target_compile_features(float-literal-regressions PRIVATE cxx_std_17)
target_include_directories(float-literal-regressions PRIVATE "${PROJECTM_SOURCE}/vendor/hlslparser/src")
target_link_libraries(float-literal-regressions PRIVATE libprojectM::projectM)
add_test(NAME float-literal-regressions COMMAND float-literal-regressions)
set_tests_properties(float-literal-regressions PROPERTIES TIMEOUT 10 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0")
target_compile_features(random-texture-regressions PRIVATE cxx_std_17)
target_compile_definitions(random-texture-regressions PRIVATE GL_SILENCE_DEPRECATION)
target_compile_definitions(random-texture-regressions PRIVATE
    BUNDLED_ASSETS="${CMAKE_CURRENT_SOURCE_DIR}/../../../main/assets")
target_include_directories(random-texture-regressions PRIVATE
    "${PROJECTM_SOURCE}/src/libprojectM"
    "${PROJECTM_SOURCE}/src/libprojectM/MilkdropPreset"
    "${PROJECTM_SOURCE}/vendor"
    "${PROJECTM_SOURCE}/vendor/projectm-eval/projectm-eval/api")
target_include_directories(random-texture-regressions PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../tools/preset-lab/src/preset_lab/native")
target_link_libraries(random-texture-regressions PRIVATE libprojectM::projectM)
if(APPLE)
    target_link_libraries(random-texture-regressions PRIVATE "${REGRESSION_OPENGL_FRAMEWORK}")
endif()
if(NOT APPLE)
    target_compile_definitions(random-texture-regressions PRIVATE USE_GLES)
    target_link_libraries(random-texture-regressions PRIVATE ${REGRESSION_GL_TARGET})
endif()
foreach(control manager stages shorthand numerical lifecycle blur-framebuffers midgit-render)
    add_test(NAME random-texture-${control} COMMAND random-texture-regressions
        ${control} "${CMAKE_CURRENT_BINARY_DIR}/textures-${control}")
    set_tests_properties(random-texture-${control} PROPERTIES TIMEOUT 30
        ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
endforeach()
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_executable(shader-parser-regressions shader_parser_test.cpp)
target_compile_features(shader-parser-regressions PRIVATE cxx_std_17)
target_include_directories(shader-parser-regressions PRIVATE "${PROJECTM_SOURCE}/vendor/hlslparser/src")
target_link_libraries(shader-parser-regressions PRIVATE libprojectM::projectM)
add_test(NAME shader-parser-regressions COMMAND shader-parser-regressions)
set_tests_properties(shader-parser-regressions PROPERTIES
    TIMEOUT 10 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0")
add_test(NAME hlsl-self-reference COMMAND projectm-regressions macro)
add_test(NAME custom-waveform-bounds COMMAND projectm-regressions waveform)
add_test(NAME shader-render-regressions COMMAND projectm-regressions shader-render)
add_test(NAME float-literal-render COMMAND projectm-regressions float-render "${CMAKE_CURRENT_SOURCE_DIR}/float-literal-control.milk")
set_tests_properties(float-literal-render PROPERTIES TIMEOUT 30 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
add_test(NAME parser-presets COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/check_preset_hashes.py"
    "$<TARGET_FILE:projectm-regressions>" parser-presets
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../main/assets"
    "${CMAKE_CURRENT_SOURCE_DIR}/parser-presets.tsv")
# A broken self-referencing macro grows indefinitely; stop it before it exhausts memory.
set_tests_properties(hlsl-self-reference custom-waveform-bounds shader-render-regressions parser-presets PROPERTIES
    TIMEOUT 30 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")

add_executable(implicit-global-regressions implicit_global_test.cpp)
target_compile_features(implicit-global-regressions PRIVATE cxx_std_17)
target_include_directories(implicit-global-regressions PRIVATE "${PROJECTM_SOURCE}/vendor/hlslparser/src")
target_link_libraries(implicit-global-regressions PRIVATE libprojectM::projectM)
add_test(NAME implicit-global-regressions COMMAND implicit-global-regressions)
set_tests_properties(implicit-global-regressions PROPERTIES TIMEOUT 10 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0")

add_test(NAME implicit-input-bindings COMMAND projectm-regressions implicit-bindings)
set_tests_properties(implicit-input-bindings PROPERTIES TIMEOUT 30 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")

add_test(NAME initialization-presets COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/check_preset_hashes.py"
    "$<TARGET_FILE:projectm-regressions>" initialization-presets
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../main/assets"
    "${CMAKE_CURRENT_SOURCE_DIR}/initialization-presets.tsv")
set_tests_properties(initialization-presets PROPERTIES TIMEOUT 30 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")

add_test(NAME float-literal-presets COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/check_preset_hashes.py"
    "$<TARGET_FILE:projectm-regressions>" float-presets
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../main/assets"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../tools/milk-analyzer/fixtures/float-literal-presets.json")
set_tests_properties(float-literal-presets PROPERTIES TIMEOUT 120 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")

# Load the GLES implementation in isolated processes, separate from desktop projectM's
# GLAD globals and resolver singleton. The fixtures still exercise the production checks.
find_package(Threads REQUIRED)
add_executable(gles-loader-regressions
    gles_loader_test.cpp
    "${PROJECTM_SOURCE}/src/libprojectM/Renderer/Platform/GladLoader.cpp"
    "${PROJECTM_SOURCE}/src/libprojectM/Renderer/Platform/GLProbe.cpp"
    "${PROJECTM_SOURCE}/src/libprojectM/Renderer/Platform/GLResolver.cpp"
    "${PROJECTM_SOURCE}/src/libprojectM/Renderer/Platform/DynamicLibrary.cpp"
    "${PROJECTM_SOURCE}/src/libprojectM/Renderer/Platform/DynamicLibrary_posix.cpp"
    "${PROJECTM_SOURCE}/src/libprojectM/Renderer/Platform/DynamicLibrary_win32.cpp"
    "${PROJECTM_SOURCE}/src/libprojectM/Renderer/Platform/DynamicLibrary_emscripten.cpp"
    "${PROJECTM_SOURCE}/src/libprojectM/Logging.cpp"
    "${PROJECTM_SOURCE}/vendor/glad/src/gles2.c"
    "${PROJECTM_SOURCE}/vendor/glad/src/egl.c")
target_compile_features(gles-loader-regressions PRIVATE cxx_std_17)
target_compile_definitions(gles-loader-regressions PRIVATE USE_GLES PROJECTM_CXX_STATIC_DEFINE)
target_include_directories(gles-loader-regressions PRIVATE
    "${PROJECTM_SOURCE}/src/libprojectM"
    "${CMAKE_CURRENT_BINARY_DIR}/projectm/src/api/include")
target_link_libraries(gles-loader-regressions PRIVATE Threads::Threads ${CMAKE_DL_LIBS})
if(APPLE)
    # This GLES-only executable must not include desktop GLAD through the macOS shim.
    get_target_property(GLES_LOADER_COMPILE_OPTIONS gles-loader-regressions COMPILE_OPTIONS)
    list(REMOVE_ITEM GLES_LOADER_COMPILE_OPTIONS
        "$<$<COMPILE_LANGUAGE:CXX>:-include${CMAKE_CURRENT_SOURCE_DIR}/macos_gl.hpp>")
    set_property(TARGET gles-loader-regressions PROPERTY COMPILE_OPTIONS "${GLES_LOADER_COMPILE_OPTIONS}")
endif()
foreach(control gles30 gles20 glsl100)
    add_test(NAME gles-loader-${control} COMMAND gles-loader-regressions ${control})
    set_tests_properties(gles-loader-${control} PROPERTIES TIMEOUT 10
        ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0")
endforeach()

add_executable(shape-pixel-center-regressions shape_pixel_center_test.cpp)
target_compile_features(shape-pixel-center-regressions PRIVATE cxx_std_17)
target_include_directories(shape-pixel-center-regressions PRIVATE "${PROJECTM_SOURCE}/src/libprojectM" "${PROJECTM_SOURCE}/vendor" "${PROJECTM_SOURCE}/vendor/projectm-eval/projectm-eval/api")
target_link_libraries(shape-pixel-center-regressions PRIVATE libprojectM::projectM)
if(APPLE)
    target_compile_definitions(shape-pixel-center-regressions PRIVATE GL_SILENCE_DEPRECATION)
    target_link_libraries(shape-pixel-center-regressions PRIVATE "${REGRESSION_OPENGL_FRAMEWORK}")
else()
    target_compile_definitions(shape-pixel-center-regressions PRIVATE USE_GLES)
    target_link_libraries(shape-pixel-center-regressions PRIVATE ${REGRESSION_GL_TARGET})
endif()
add_test(NAME shape-pixel-center-regressions COMMAND shape-pixel-center-regressions)
set_tests_properties(shape-pixel-center-regressions PROPERTIES TIMEOUT 30 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")

add_executable(composite-texel-center-regressions composite_texel_center_test.cpp)
target_compile_features(composite-texel-center-regressions PRIVATE cxx_std_17)
target_include_directories(composite-texel-center-regressions PRIVATE
    "${PROJECTM_SOURCE}/src/libprojectM" "${PROJECTM_SOURCE}/vendor"
    "${PROJECTM_SOURCE}/vendor/projectm-eval/projectm-eval/api")
target_link_libraries(composite-texel-center-regressions PRIVATE libprojectM::projectM)
if(APPLE)
    target_compile_definitions(composite-texel-center-regressions PRIVATE GL_SILENCE_DEPRECATION)
    target_link_libraries(composite-texel-center-regressions PRIVATE "${REGRESSION_OPENGL_FRAMEWORK}")
else()
    target_compile_definitions(composite-texel-center-regressions PRIVATE USE_GLES)
    target_link_libraries(composite-texel-center-regressions PRIVATE ${REGRESSION_GL_TARGET})
endif()
add_test(NAME composite-texel-center-regressions COMMAND composite-texel-center-regressions)
set_tests_properties(composite-texel-center-regressions PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")

add_test(NAME legacy-angle-seam COMMAND warp-rotation-regressions angle-seam)
set_tests_properties(legacy-angle-seam PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")

add_test(NAME wave-colour-submission COMMAND wave-colour-regressions)
set_tests_properties(wave-colour-submission PROPERTIES TIMEOUT 30
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")

# Integrate in the existing production-regression CMakeLists.txt.
# This explicit target avoids depending on concurrent changes to the shared foreach.
add_executable(shape-thickness-regressions shape_thickness_test.cpp)
target_compile_features(shape-thickness-regressions PRIVATE cxx_std_17)
target_compile_definitions(shape-thickness-regressions PRIVATE GL_SILENCE_DEPRECATION)
target_include_directories(shape-thickness-regressions PRIVATE
    "${PROJECTM_SOURCE}/src/libprojectM"
    "${PROJECTM_SOURCE}/src/libprojectM/MilkdropPreset"
    "${PROJECTM_SOURCE}/vendor"
    "${PROJECTM_SOURCE}/vendor/projectm-eval/projectm-eval/api")
target_link_libraries(shape-thickness-regressions PRIVATE libprojectM::projectM ${CMAKE_DL_LIBS})
if(APPLE)
    target_link_libraries(shape-thickness-regressions PRIVATE "${REGRESSION_OPENGL_FRAMEWORK}")
else()
    target_compile_definitions(shape-thickness-regressions PRIVATE USE_GLES)
    target_link_libraries(shape-thickness-regressions PRIVATE ${REGRESSION_GL_TARGET})
endif()
add_test(NAME shape-thickness-style COMMAND shape-thickness-regressions style)
add_test(NAME shape-thickness-domain COMMAND shape-thickness-regressions domain)
set(SHAPE_THICKNESS_PRESETS
    "martin - city lights v2(1).milk"
    "martin - city lights v2 c.milk")
set(SHAPE_THICKNESS_HASHES
    ac990a2a323950ca4213a763451e6b95835848bbb4569c401a614e6fc26423d5
    685868904bb3194d0d3fb9ea30c180dad0af46068d66bcce55828f46024ce8f1)
foreach(index RANGE 0 1)
    list(GET SHAPE_THICKNESS_PRESETS ${index} name)
    list(GET SHAPE_THICKNESS_HASHES ${index} expected)
    file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/../../../main/assets/presets/${name}" actual)
    if(NOT actual STREQUAL expected)
        message(FATAL_ERROR "Shape thickness witness changed: ${name}")
    endif()
endforeach()
add_test(NAME shape-thickness-original COMMAND shape-thickness-regressions original
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../main/assets/presets/martin - city lights v2(1).milk"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../main/assets/presets/martin - city lights v2 c.milk")
set_tests_properties(shape-thickness-style shape-thickness-domain shape-thickness-original PROPERTIES
    TIMEOUT 120 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")

foreach(uv_mode temporal producer lifecycle transition context)
    add_test(NAME motion-uv-${uv_mode} COMMAND motion-uv-freshness-regressions ${uv_mode})
    set_tests_properties(motion-uv-${uv_mode} PROPERTIES TIMEOUT 120
        ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
endforeach()

# Packed half UV storage is a GLES-only fallback. Desktop retains RG16F.
if(NOT APPLE)
 foreach(control packed-no-extension packed-fbo-reject packed-bilinear core-float-no-extension)
  add_test(NAME motion-uv-${control} COMMAND motion-uv-freshness-regressions ${control})
  set_tests_properties(motion-uv-${control} PROPERTIES TIMEOUT 180 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
 endforeach()
 add_executable(motion-uv-precision-edges-regressions motion_uv_precision_edges_test.cpp)
 target_compile_features(motion-uv-precision-edges-regressions PRIVATE cxx_std_17)
 target_compile_definitions(motion-uv-precision-edges-regressions PRIVATE USE_GLES GL_SILENCE_DEPRECATION)
 target_include_directories(motion-uv-precision-edges-regressions PRIVATE
  "${PROJECTM_SOURCE}/src/libprojectM" "${PROJECTM_SOURCE}/src/libprojectM/MilkdropPreset"
  "${PROJECTM_SOURCE}/vendor" "${PROJECTM_SOURCE}/vendor/glad/include"
  "${PROJECTM_SOURCE}/vendor/projectm-eval/projectm-eval/api")
 target_link_libraries(motion-uv-precision-edges-regressions PRIVATE libprojectM::projectM ${REGRESSION_GL_TARGET})
 foreach(control fractional nonfinite edge)
  add_test(NAME motion-uv-${control} COMMAND motion-uv-precision-edges-regressions ${control})
  set_tests_properties(motion-uv-${control} PROPERTIES TIMEOUT 180 ENVIRONMENT "ASAN_OPTIONS=detect_leaks=0;EGL_PLATFORM=surfaceless")
 endforeach()
endif()
