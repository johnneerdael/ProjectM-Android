#include <SDL.h>
#include <CommonCrypto/CommonDigest.h>
#include <glad/gl.h>
#include <projectM-4/projectM.h>
#include <dlfcn.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>

static std::set<GLuint> lineShaders, linePrograms;
static std::string rejection;
static int rejected = 0, instancedDraws = 0, failedLoads = 0;
static void Source(GLuint shader, GLsizei count, const GLchar* const* strings, const GLint* lengths)
{
    std::string text;
    for (int i = 0; i < count; ++i) text.append(strings[i], lengths && lengths[i] >= 0 ? lengths[i] : std::char_traits<char>::length(strings[i]));
    lineShaders.erase(shader);
    if (text.find("point_previous") != std::string::npos || text.find("vector_start") != std::string::npos) lineShaders.insert(shader);
    glad_glShaderSource(shader, count, strings, lengths);
}
static void ShaderStatus(GLuint shader, GLenum parameter, GLint* value)
{
    glad_glGetShaderiv(shader, parameter, value);
    if (rejection == "compile" && parameter == GL_COMPILE_STATUS && lineShaders.count(shader)) { *value = GL_FALSE; ++rejected; }
}
static GLuint CreateProgram()
{
    auto program = glad_glCreateProgram();
    linePrograms.erase(program);
    return program;
}
static void Attach(GLuint program, GLuint shader)
{
    if (lineShaders.count(shader)) linePrograms.insert(program);
    glad_glAttachShader(program, shader);
}
static void ProgramStatus(GLuint program, GLenum parameter, GLint* value)
{
    glad_glGetProgramiv(program, parameter, value);
    if (rejection == "link" && parameter == GL_LINK_STATUS && linePrograms.count(program)) { *value = GL_FALSE; ++rejected; }
}
static void Instanced(GLenum mode, GLint first, GLsizei vertices, GLsizei instances)
{
    ++instancedDraws;
    glad_glDrawArraysInstanced(mode, first, vertices, instances);
}
static void* Resolve(const char* name, void*)
{
    if (std::string(name) == "glShaderSource") return reinterpret_cast<void*>(&Source);
    if (std::string(name) == "glGetShaderiv") return reinterpret_cast<void*>(&ShaderStatus);
    if (std::string(name) == "glCreateProgram") return reinterpret_cast<void*>(&CreateProgram);
    if (std::string(name) == "glAttachShader") return reinterpret_cast<void*>(&Attach);
    if (std::string(name) == "glGetProgramiv") return reinterpret_cast<void*>(&ProgramStatus);
    if (std::string(name) == "glDrawArraysInstanced") return reinterpret_cast<void*>(&Instanced);
    return SDL_GL_GetProcAddress(name);
}
static void Failed(const char* name, const char* message, void*)
{
    ++failedLoads;
    std::cerr << "Preset failed: " << name << ": " << message << '\n';
}
template<typename T> T Symbol(void* library, const char* name)
{
    auto function = reinterpret_cast<T>(dlsym(library, name));
    if (!function) { std::cerr << dlerror() << '\n'; std::exit(2); }
    return function;
}
int main(int argc, char** argv)
{
    if (argc != 11) { std::cerr << "library preset output width height reference aa rejection frames native_alpha\n"; return 2; }
    const int width = std::stoi(argv[4]), height = std::stoi(argv[5]), reference = std::stoi(argv[6]);
    const int frames = std::stoi(argv[9]);
    rejection = argv[8];
    if (SDL_Init(SDL_INIT_VIDEO)) { std::cerr << SDL_GetError(); return 2; }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 4);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 1);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    auto* window = SDL_CreateWindow("PR1047 validation", 0, 0, 64, 64, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    auto context = SDL_GL_CreateContext(window);
    if (!context || !gladLoadGL(reinterpret_cast<GLADloadfunc>(SDL_GL_GetProcAddress))) { std::cerr << SDL_GetError(); return 2; }
    std::cerr << glGetString(GL_RENDERER) << " / " << glGetString(GL_VERSION) << '\n';
    auto* library = dlopen(argv[1], RTLD_LOCAL | RTLD_NOW);
    if (!library) { std::cerr << dlerror(); return 2; }
#define LOAD(name) auto name = Symbol<decltype(&::name)>(library, #name)
    LOAD(projectm_create_with_opengl_load_proc); LOAD(projectm_destroy);
    LOAD(projectm_set_window_size); LOAD(projectm_set_frame_time); LOAD(projectm_set_fps);
    LOAD(projectm_set_preset_locked); LOAD(projectm_set_preset_start_clean);
    LOAD(projectm_load_preset_file); LOAD(projectm_pcm_add_float);
    LOAD(projectm_opengl_render_frame_fbo); LOAD(projectm_opengl_set_line_reference_size);
    LOAD(projectm_opengl_set_line_antialiasing); LOAD(projectm_opengl_set_feedback_detail); LOAD(projectm_opengl_get_feedback_detail_status); LOAD(projectm_set_preset_switch_failed_event_callback);
#undef LOAD
    GLuint fbo, texture;
    glGenFramebuffers(1, &fbo); glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glGenTextures(1, &texture); glBindTexture(GL_TEXTURE_2D, texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) return 3;
    srand(12345);
    auto instance = projectm_create_with_opengl_load_proc(Resolve, nullptr);
    if (!instance) return 4;
    projectm_set_preset_switch_failed_event_callback(instance, Failed, nullptr);
    projectm_set_window_size(instance, width, height);
    projectm_set_frame_time(instance, 0.0); projectm_set_fps(instance, 30);
    projectm_set_preset_locked(instance, true); projectm_set_preset_start_clean(instance, true);
    const float nativeAlpha = std::stof(argv[10]);
    projectm_opengl_set_line_reference_size(instance, reference ? (nativeAlpha >= 0 ? 1280 : 1024) : 0,
                                           reference ? (nativeAlpha >= 0 ? 720 : 768) : 0);
    projectm_opengl_set_feedback_detail(instance, nativeAlpha);
    projectm_opengl_set_line_antialiasing(instance, std::stoi(argv[7]) != 0);
    projectm_load_preset_file(instance, argv[2], false);
    std::ofstream out(argv[3], std::ios::binary);
    std::vector<float> pcm(1024);
    std::vector<unsigned char> pixels(static_cast<size_t>(width) * height * 4);
    std::vector<double> times;
    for (int frame = 0; frame < frames; ++frame)
    {
        for (int i = 0; i < 512; ++i)
        {
            pcm[i*2] = 0.35f * std::sin((frame * 512 + i) * 0.071);
            pcm[i*2+1] = 0.25f * std::sin((frame * 512 + i) * 0.047);
        }
        projectm_pcm_add_float(instance, pcm.data(), 512, PROJECTM_STEREO);
        projectm_set_frame_time(instance, frame / 30.0);
        glFinish();
        auto start = std::chrono::steady_clock::now();
        projectm_opengl_render_frame_fbo(instance, fbo);
        glFinish();
        times.push_back(std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count());
        GLenum error = glGetError();
        if (error) { std::cerr << "GL error " << error << " frame " << frame << '\n'; return 5; }
        // Capture only the explicitly selected final output FBO, never an intermediate read target.
        glBindFramebuffer(GL_READ_FRAMEBUFFER, fbo);
        glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
        std::vector<unsigned char> rgb(static_cast<size_t>(width) * height * 3);
        for (size_t i = 0, j = 0; i < pixels.size(); i += 4, j += 3) std::copy_n(pixels.data()+i, 3, rgb.data()+j);
        unsigned char digest[CC_SHA256_DIGEST_LENGTH];
        CC_SHA256(rgb.data(), static_cast<CC_LONG>(rgb.size()), digest);
        out.write(reinterpret_cast<const char*>(digest), sizeof(digest));
        if (frame == frames - 1 && width == 640)
        {
            std::ofstream image(std::string(argv[3])+".ppm", std::ios::binary);
            image << "P6\n" << width << " " << height << "\n255\n";
            image.write(reinterpret_cast<const char*>(rgb.data()), rgb.size());
        }
    }
    const int nativeStatus = projectm_opengl_get_feedback_detail_status(instance);
    if (nativeAlpha >= 0 && nativeStatus < 2) { std::cerr << "Native canvas did not activate: " << nativeStatus; return 8; }
    projectm_destroy(instance);
    glDeleteTextures(1, &texture); glDeleteFramebuffers(1, &fbo);
    if (glGetError()) return 6;
    std::sort(times.begin() + std::min(5, frames), times.end());
    std::cout << "{\"frames\":" << frames << ",\"instanced_draws\":" << instancedDraws
              << ",\"native_status\":" << nativeStatus << ",\"rejected\":" << rejected << ",\"failed_loads\":" << failedLoads
              << ",\"median_ms\":" << times[(frames + std::min(5, frames))/2] << "}\n";
    SDL_GL_DeleteContext(context); SDL_DestroyWindow(window); SDL_Quit();
    return failedLoads ? 7 : 0;
}
