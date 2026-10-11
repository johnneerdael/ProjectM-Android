#include "preset_prewarm.h"

#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <android/log.h>
#include <sys/resource.h>
#include <unistd.h>

#include <algorithm>
#include <chrono>

#include "diagnostics_trail.h"
#include "projectM-4/projectM.h"

#define LOG_TAG "projectM-Native"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, LOG_TAG, __VA_ARGS__)

namespace {

// Presets compiled this recently are not compiled again: their programs are still in the cache.
constexpr size_t kRecentNames = 16;

double NowMs() {
    using namespace std::chrono;
    return duration<double, std::milli>(steady_clock::now().time_since_epoch()).count();
}

// An OpenGL ES 3 context on a tiny off-screen surface, current on the calling thread.
class PbufferContext {
public:
    bool Create() {
        display_ = eglGetDisplay(EGL_DEFAULT_DISPLAY);
        if (display_ == EGL_NO_DISPLAY || !eglInitialize(display_, nullptr, nullptr)) return false;
        const EGLint configAttribs[] = {EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT_KHR,
                                        EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
                                        EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8,
                                        EGL_NONE};
        EGLConfig config = nullptr;
        EGLint count = 0;
        if (!eglChooseConfig(display_, configAttribs, &config, 1, &count) || count < 1) return false;
        const EGLint contextAttribs[] = {EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE};
        context_ = eglCreateContext(display_, config, EGL_NO_CONTEXT, contextAttribs);
        const EGLint surfaceAttribs[] = {EGL_WIDTH, 16, EGL_HEIGHT, 16, EGL_NONE};
        surface_ = eglCreatePbufferSurface(display_, config, surfaceAttribs);
        return context_ != EGL_NO_CONTEXT && surface_ != EGL_NO_SURFACE &&
               eglMakeCurrent(display_, surface_, surface_, context_);
    }

    ~PbufferContext() {
        if (display_ == EGL_NO_DISPLAY) return;
        eglMakeCurrent(display_, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        if (surface_ != EGL_NO_SURFACE) eglDestroySurface(display_, surface_);
        if (context_ != EGL_NO_CONTEXT) eglDestroyContext(display_, context_);
        eglReleaseThread();
    }

private:
    EGLDisplay display_ = EGL_NO_DISPLAY;
    EGLContext context_ = EGL_NO_CONTEXT;
    EGLSurface surface_ = EGL_NO_SURFACE;
};

}  // namespace

void PresetPrewarmer::Start(Reader reader) {
    if (thread_.joinable()) return;
    stop_ = false;
    reader_ = std::move(reader);
    projectmtv::TrailCompileOn() = true;  // before the thread runs: its exit clears it
    thread_ = std::thread(&PresetPrewarmer::Run, this);
}

void PresetPrewarmer::Stop() {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        stop_ = true;
    }
    cv_.notify_all();
    if (thread_.joinable()) thread_.join();
    std::lock_guard<std::mutex> lock(mutex_);
    pending_.clear();
    recent_.clear();
    active_.clear();
    activeTexturePaths_.clear();
}

bool PresetPrewarmer::UsesPresetPrefix(const std::string& prefix) {
    std::lock_guard<std::mutex> lock(mutex_);
    return !active_.empty() && active_.compare(0, prefix.size(), prefix) == 0;
}

bool PresetPrewarmer::UsesPresetDirectory(const std::string& directory) {
    std::lock_guard<std::mutex> lock(mutex_);
    return std::find(activeTexturePaths_.begin(), activeTexturePaths_.end(), directory + "/textures") != activeTexturePaths_.end();
}

void PresetPrewarmer::Request(const std::vector<std::string>& names) {
    std::lock_guard<std::mutex> lock(mutex_);
    pending_.clear();
    for (const auto& name : names) {
        if (name.empty()) continue;
        if (std::find(recent_.begin(), recent_.end(), name) != recent_.end()) continue;
        if (std::find(pending_.begin(), pending_.end(), name) != pending_.end()) continue;
        pending_.push_back(name);
    }
    if (!pending_.empty()) cv_.notify_one();
}

void PresetPrewarmer::Run() {
    // However the worker ends (stopped, no EGL context, projectm_create failed), the trail must not
    // claim a background compiler is running.
    struct RunningState {
        ~RunningState() { projectmtv::TrailCompileOn() = false; }
    } runningState;
    // Below the render thread: compiling must not cost it frames.
    setpriority(PRIO_PROCESS, gettid(), 10);
    projectmtv::WriteTrail(projectmtv::kTrailPrewarm, "creating its EGL context");
    PbufferContext context;
    if (!context.Create()) {
        EGLint error = eglGetError();
        LOGW("PREWARM unavailable: no off-screen OpenGL ES 3 context (error 0x%x)", error);
        projectmtv::WriteTrail(projectmtv::kTrailPrewarm, "no EGL context (error 0x%x)", error);
        return;
    }
    projectmtv::WriteTrail(projectmtv::kTrailPrewarm, "idle");
    for (;;) {
        std::string name;
        {
            std::unique_lock<std::mutex> lock(mutex_);
            cv_.wait(lock, [this] { return stop_ || !pending_.empty(); });
            if (stop_) break;
            name = pending_.front();
            pending_.pop_front();
            active_ = name;
            recent_.push_back(name);
            if (recent_.size() > kRecentNames) recent_.pop_front();
        }
        projectmtv::WriteTrail(projectmtv::kTrailPrewarm, "compiling '%s'", name.c_str());
        auto preset = reader_(name);
        {
            std::lock_guard<std::mutex> lock(mutex_);
            activeTexturePaths_ = preset.texturePaths;
        }
        if (preset.data.empty()) {
            projectmtv::WriteTrail(projectmtv::kTrailPrewarm, "idle: could not read '%s'", name.c_str());
            std::lock_guard<std::mutex> lock(mutex_);
            active_.clear();
            activeTexturePaths_.clear();
            continue;
        }
        // A fresh instance per preset, destroyed right after: between switches the prewarmer holds
        // no preset, textures or frame buffers (memory is tight on TV boxes, and running short
        // makes Android take it from the music player).
        double start = NowMs();
        projectm_handle pm = projectm_create();
        if (!pm) {
            LOGW("PREWARM unavailable: projectm_create failed");
            projectmtv::WriteTrail(projectmtv::kTrailPrewarm, "stopped: projectm_create failed");
            std::lock_guard<std::mutex> lock(mutex_);
            active_.clear();
            activeTexturePaths_.clear();
            break;
        }
        std::vector<const char*> paths;
        for (const auto& path : preset.texturePaths) paths.push_back(path.c_str());
        projectm_set_texture_search_paths(pm, paths.data(), paths.size());
        projectm_set_window_size(pm, 64, 36);
        projectm_load_preset_data(pm, preset.data.c_str(), false);
        projectm_destroy(pm);
        {
            std::lock_guard<std::mutex> lock(mutex_);
            active_.clear();
            activeTexturePaths_.clear();
        }
        uint32_t hits = 0, misses = 0;
        projectm_opengl_program_cache_stats(&hits, &misses);
        LOGI("PREWARM preset='%s' ms=%.0f cache_hits=%u cache_misses=%u", name.c_str(), NowMs() - start,
             hits, misses);
        projectmtv::WriteTrail(projectmtv::kTrailPrewarm, "idle after compiling '%s' in %.0f ms", name.c_str(),
                               NowMs() - start);
    }
}
