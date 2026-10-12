// Host test harness for core/src/main/cpp/native-lib.cpp. Run via run_native_tests.sh.
// Compiles native-lib.cpp against fakes of projectM, AAssetManager and GL.
#include <cstring>
#include <cstdarg>
#include <cstdlib>
#include <jni.h>
#include <cassert>
#include <cstdio>
#include <dirent.h>
#include <map>
#include <string>
#include <vector>
#include <set>
#include <thread>
#include <chrono>
#include <fstream>
#include <sstream>
#include <type_traits>
#include <unistd.h>
#include <sys/types.h>
#include "android/asset_manager.h"
#include "GLES3/gl3.h"
#include "projectM-4/projectM.h"

// ---- fake asset manager backed by a directory ----
struct AAssetManager { std::string root; };
struct AAssetDir { std::vector<std::string> names; size_t i = 0; };
struct AAsset { std::string data; };
extern "C" {
AAssetDir* AAssetManager_openDir(AAssetManager* am, const char* dir) {
  auto* d = new AAssetDir; DIR* h = opendir((am->root + "/" + dir).c_str());
  while (dirent* e = readdir(h)) if (e->d_name[0] != '.' || strlen(e->d_name) > 2) { std::string n = e->d_name; if (n != "." && n != "..") d->names.push_back(n); }
  closedir(h); return d; }
const char* AAssetDir_getNextFileName(AAssetDir* d) { return d->i < d->names.size() ? d->names[d->i++].c_str() : nullptr; }
void AAssetDir_close(AAssetDir* d) { delete d; }
AAsset* AAssetManager_open(AAssetManager* am, const char* p, int) {
  FILE* f = fopen((am->root + "/" + p).c_str(), "rb"); if (!f) return nullptr;
  auto* a = new AAsset; char buf[4096]; size_t n; while ((n = fread(buf, 1, sizeof buf, f)) > 0) a->data.append(buf, n); fclose(f); return a; }
const void* AAsset_getBuffer(AAsset* a) { return a->data.data(); }
off_t AAsset_getLength(AAsset* a) { return a->data.size(); }
void AAsset_close(AAsset* a) { delete a; }
AAssetManager* AAssetManager_fromJava(JNIEnv*, jobject) { return nullptr; }
std::vector<std::string> g_logLines;
int __android_log_print(int, const char* tag, const char* fmt, ...) {
  char buf[2048]; va_list ap; va_start(ap, fmt); vsnprintf(buf, sizeof buf, fmt, ap); va_end(ap);
  fprintf(stderr, "%s\n", buf); g_logLines.push_back(buf); return 0; }
int __system_property_get(const char* name, char* value) {
  if (strcmp(name, "vendor.display-size") == 0) { strcpy(value, "3840x2160"); return 9; }
  value[0] = 0; return 0; }
// ---- fake GL ----
unsigned char g_pixel = 0;
int g_readFbo = -1;  // framebuffer bound for reading during glReadPixels
unsigned char g_noise = 0;  // when set, pixels alternate between g_pixel and g_pixel + g_noise
GLuint g_packBuffer = 0; std::vector<unsigned char> g_pbo; int g_fences = 0, g_mapped = 0;
void glViewport(GLint, GLint, GLsizei, GLsizei) {}
void glBindFramebuffer(GLenum target, GLuint fbo) { if (target != GL_DRAW_FRAMEBUFFER) g_readFbo = (int)fbo; }
int g_blits = 0; int g_blitSrcW = 0, g_blitSrcH = 0, g_blitDstW = 0, g_blitDstH = 0;
void glGenFramebuffers(GLsizei, GLuint* f) { *f = 77; }
void glDeleteFramebuffers(GLsizei, const GLuint*) {}
void glGenTextures(GLsizei, GLuint* t) { *t = 78; }
void glDeleteTextures(GLsizei, const GLuint*) {}
void glBindTexture(GLenum, GLuint) {}
void glTexImage2D(GLenum, GLint, GLint, GLsizei, GLsizei, GLint, GLenum, GLenum, const void*) {}
void glTexParameteri(GLenum, GLenum, GLint) {}
void glFramebufferTexture2D(GLenum, GLenum, GLenum, GLuint, GLint) {}
GLenum g_framebufferStatus = GL_FRAMEBUFFER_COMPLETE;
GLenum glCheckFramebufferStatus(GLenum) { return g_framebufferStatus; }
void glBlitFramebuffer(GLint, GLint, GLint sw, GLint sh, GLint, GLint, GLint dw, GLint dh, GLbitfield, GLenum) {
  ++g_blits; g_blitSrcW = sw; g_blitSrcH = sh; g_blitDstW = dw; g_blitDstH = dh; }
void glGetIntegerv(GLenum e, GLint* v) { *v = e == GL_PIXEL_PACK_BUFFER_BINDING ? (GLint)g_packBuffer : e == GL_PACK_ALIGNMENT ? 4 : 7; }
void glGenBuffers(GLsizei, GLuint* b) { *b = 42; }
void glDeleteBuffers(GLsizei, const GLuint*) {}
void glBindBuffer(GLenum, GLuint b) { g_packBuffer = b; }
void glBufferData(GLenum, GLsizeiptr n, const void*, GLenum) { g_pbo.assign((size_t)n, 0); }
void glPixelStorei(GLenum, GLint) {}
void* glMapBufferRange(GLenum, GLintptr, GLsizeiptr, GLbitfield) { ++g_mapped; return g_pbo.data(); }
unsigned char glUnmapBuffer(GLenum) { return 1; }
GLsync glFenceSync(GLenum, GLbitfield) { ++g_fences; return (GLsync)(intptr_t)g_fences; }
GLenum glClientWaitSync(GLsync, GLbitfield, GLuint64) { return GL_ALREADY_SIGNALED; }
void glDeleteSync(GLsync) { --g_fences; }
void glFlush() {}
void glReadPixels(GLint, GLint, GLsizei w, GLsizei h, GLenum, GLenum, GLvoid* out) {
  if (g_readFbo != 0) { fprintf(stderr, "FAIL glReadPixels not reading the window\n"); exit(1); }
  if (g_packBuffer != 42) { fprintf(stderr, "FAIL glReadPixels without the pixel pack buffer (would stall)\n"); exit(1); }
  size_t offset = (size_t)(intptr_t)out;
  if (offset + (size_t)w * h * 4 > g_pbo.size()) { fprintf(stderr, "FAIL glReadPixels past the buffer\n"); exit(1); }
  unsigned char* p = g_pbo.data() + offset;
  for (size_t i = 0; i < (size_t)w * h; ++i) memset(p + i * 4, (i / 4) % 2 ? g_pixel + g_noise : g_pixel, 4); }
}
// ---- fake transition overlay (the real one is tested on Mesa by fade_gl_test.cpp) ----
#include "snapshot_fade.h"
int g_captures = 0, g_fadeStarts = 0, g_fadeDraws = 0; double g_fadeSeconds = 0; bool g_captureOk = true;
bool SnapshotFade::Capture(int, int) { Stop(); ++g_captures; texture_ = g_captureOk ? 1 : 0; return g_captureOk; }
void SnapshotFade::Start(double now, double seconds) { if (!texture_) return; ++g_fadeStarts; active_ = true; start_ = now; duration_ = seconds; g_fadeSeconds = seconds; }
void SnapshotFade::Draw(double now) { if (!active_) return; ++g_fadeDraws; if (now - start_ >= duration_) Stop(); }
void SnapshotFade::Stop() { active_ = false; texture_ = 0; }
void SnapshotFade::Forget() { Stop(); }
void SnapshotFade::Release() { Stop(); }
// ---- fake shader prewarmer (the real one needs EGL) ----
#include "preset_prewarm.h"
#include "diagnostics_trail.h"
std::vector<std::string> g_prewarmRequests; int g_prewarmStarts = 0, g_prewarmStops = 0;
PresetPrewarmer::Reader g_prewarmReader;
std::string g_prewarmActive;
// Like the real worker: the trail's compile= is on while it runs.
void PresetPrewarmer::Start(Reader reader) { ++g_prewarmStarts; g_prewarmReader = std::move(reader); projectmtv::TrailCompileOn() = true; }
void PresetPrewarmer::Stop() { ++g_prewarmStops; g_prewarmActive.clear(); projectmtv::TrailCompileOn() = false; }
bool PresetPrewarmer::UsesPresetPrefix(const std::string& prefix) { return g_prewarmActive.compare(0, prefix.size(), prefix) == 0; }
std::vector<std::vector<std::string>> g_prewarmLists;
void PresetPrewarmer::Request(const std::vector<std::string>& names) {
  g_prewarmLists.push_back(names); g_prewarmRequests.push_back(names.empty() ? "" : names.front()); }
extern "C" {
// ---- fake projectM ----
struct projectm {};
static projectm_preset_switch_failed_event g_failCb; static projectm_preset_switch_requested_event g_reqCb;
static projectm_preset_initialization_warning_event g_warnCb;
std::vector<std::string> g_loaded; bool g_locked = false; size_t g_pcmFed = 0;
bool g_lastSmooth = false; int g_meshCalls = 0;
bool g_fakeTransitioning = false;
bool projectm_is_transitioning(projectm_handle) { return g_fakeTransitioning; }
std::vector<std::string> g_texturePathCalls; size_t g_loadsAtTextureCall = 0;
std::vector<std::vector<std::string>> g_textureSearchPaths;
// Direct output (patch 0016): like projectM, a frame that requests a switch is stored anyway. A
// preset load right after a direct frame would start the new preset from an old image.
bool g_directOutput = false, g_lastFrameDirect = false;
int g_loadsAfterDirectFrame = 0;
void projectm_opengl_set_direct_output(projectm_handle, bool enabled) { g_directOutput = enabled; }
float g_feedbackDetailAlpha = -1.f;
void projectm_opengl_set_feedback_detail(projectm_handle, float alpha) { g_feedbackDetailAlpha = alpha; }
int projectm_opengl_get_feedback_detail_status(projectm_handle) { return g_feedbackDetailAlpha < 0 ? -1 : 3; }
uint32_t g_lineReferenceWidth = 0;
uint32_t g_lineReferenceHeight = 0;
void projectm_opengl_set_line_reference_size(projectm_handle, uint32_t width, uint32_t height) {
  g_lineReferenceWidth = width;
  g_lineReferenceHeight = height;
}
projectm_handle projectm_create() { g_lastFrameDirect = false; g_fakeTransitioning = false; return new projectm; }
void projectm_destroy(projectm_handle p) { g_fakeTransitioning = false; delete p; }
int g_loadSleepMs = 0;
int g_failNextLoads = 0;
int g_warnNextLoads = 0;  // loads that leave out uncompilable code but succeed (patch 0035)
void (*g_loadObserver)() = nullptr;
void projectm_load_preset_data(projectm_handle, const char* data, bool smooth) {
  if (g_lastFrameDirect) ++g_loadsAfterDirectFrame;
  g_lastSmooth = smooth;
  if (g_loadObserver) g_loadObserver();
  if (g_failNextLoads > 0) { --g_failNextLoads; g_failCb("", "compile error", nullptr); return; }
  if (g_loadSleepMs) std::this_thread::sleep_for(std::chrono::milliseconds(g_loadSleepMs));
  if (strstr(data, "BROKEN")) { g_failCb("", "compile error", nullptr); return; }
  if (g_warnNextLoads > 0) { --g_warnNextLoads; g_warnCb("", "Could not compile per-pixel code: syntax error (line 2, column 5)", nullptr); }
  g_loaded.push_back(data); g_fakeTransitioning = smooth; }
void projectm_set_preset_switch_requested_event_callback(projectm_handle, projectm_preset_switch_requested_event cb, void*) { g_reqCb = cb; }
void projectm_set_preset_switch_failed_event_callback(projectm_handle, projectm_preset_switch_failed_event cb, void*) { g_failCb = cb; }
void projectm_set_preset_initialization_warning_event_callback(projectm_handle, projectm_preset_initialization_warning_event cb, void*) { g_warnCb = cb; }
void projectm_set_hard_cut_enabled(projectm_handle, bool) {}
void projectm_set_beat_sensitivity(projectm_handle, float) {}
void projectm_set_preset_duration(projectm_handle, double) {}
double g_appliedSoftCutSeconds = 7;
void projectm_set_soft_cut_duration(projectm_handle, double seconds) { g_appliedSoftCutSeconds = seconds; }
void projectm_set_preset_locked(projectm_handle, bool l) { g_locked = l; }
void projectm_set_mesh_size(projectm_handle, size_t, size_t) { ++g_meshCalls; }
void projectm_set_texture_search_paths(projectm_handle, const char** paths, size_t count) {
  g_textureSearchPaths.emplace_back(paths, paths + count);
  g_texturePathCalls.push_back(count ? paths[0] : "");
  g_loadsAtTextureCall = g_loaded.size(); }
size_t g_windowW = 0, g_windowH = 0; int g_windowSizeCalls = 0;
void projectm_set_window_size(projectm_handle, size_t w, size_t h) { g_windowW = w; g_windowH = h; ++g_windowSizeCalls; }
void projectm_set_fps(projectm_handle, int32_t) {}
unsigned int projectm_pcm_get_max_samples() { return 576; }
void projectm_pcm_add_uint8(projectm_handle, const uint8_t*, unsigned int n, projectm_channels) { g_pcmFed += n; }
int g_renderSleepMs = 0, g_renderSleepMsSmooth = 0;  // simulated render cost (smooth: during a soft cut)
bool g_requestInRender = false;  // like projectM: the timed switch request fires inside the render call
void projectm_opengl_render_frame(projectm_handle) {
  bool requested = false;
  if (g_requestInRender) { g_requestInRender = false; g_reqCb(false, nullptr); requested = true; }
  g_lastFrameDirect = g_directOutput && !requested;
  int ms = g_renderSleepMs; if (g_lastSmooth && g_renderSleepMsSmooth) ms = g_renderSleepMsSmooth;
  if (ms) std::this_thread::sleep_for(std::chrono::milliseconds(ms)); }
int g_fboFrames = 0;
void projectm_opengl_render_frame_fbo(projectm_handle p, uint32_t) { ++g_fboFrames; projectm_opengl_render_frame(p); }
uint32_t g_outgoingDivisor = 1;
void projectm_opengl_set_outgoing_preset_frame_divisor(projectm_handle, uint32_t d) { g_outgoingDivisor = d; }
size_t g_poolLimit = 0; int g_poolForgets = 0;
void projectm_opengl_set_texture_pool_limit(size_t bytes) { g_poolLimit = bytes; }
void projectm_opengl_forget_texture_pool() { ++g_poolForgets; }
size_t projectm_opengl_texture_pool_bytes() { return 0; }
uint32_t g_cacheHits = 0, g_cacheMisses = 0;
void projectm_opengl_program_cache_stats(uint32_t* hits, uint32_t* misses) { *hits = g_cacheHits; *misses = g_cacheMisses; }
bool g_programCacheEnabled = true;
void projectm_opengl_set_program_cache_enabled(bool enabled) { g_programCacheEnabled = enabled; }
char* projectm_get_version_string() { return strdup("4.2.0"); }
void projectm_free_string(const char* s) { free((void*)s); }
}

#include "native-lib.cpp"

#define CHECK(c) do { if (!(c)) { fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #c); exit(1); } else printf("  ok: %s\n", #c); } while (0)

template<class T, class = void> struct HasOfficialPack : std::false_type {};
template<class T> struct HasOfficialPack<T, std::void_t<decltype(&T::RequestOfficialPack)>> : std::true_type {};

template<class T> void CheckOfficialPack(T& library, const std::string& root, const std::string& custom) {
  CHECK(HasOfficialPack<T>::value);
  if constexpr (HasOfficialPack<T>::value) {
    std::string directory = root + "/official-one";
    mkdir(directory.c_str(), 0700); mkdir((directory + "/0").c_str(), 0700);
    mkdir((directory + "/preset-genres").c_str(), 0700);
    mkdir((directory + "/preset-genres/genres").c_str(), 0700);
    auto write = [](const std::string& path, const char* text) { std::ofstream(path) << text; };
    write(directory + "/0/0.milk", "official first");
    write(directory + "/0/1.milk", "official second");
    write(directory + "/official-presets.idx", "0/0.milk\tgood 1.milk\t17\n0/1.milk\tofficial unique.milk\t3\n");
    write(directory + "/preset-genres/genres/chill.idx", "official unique.milk\t3\n");
    write(directory + "/preset-genres/genres/normal.idx", "good 1.milk\t17\n");
    write(directory + "/preset-genres/genres/intense.idx", "good 1.milk\t17\n");
    auto await = [&library](uint64_t request) {
      for (int i = 0; i < 1000 && library.OfficialPackStatus(request) == 0; ++i)
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
    };
    auto customRequest = library.RequestCustomPack(custom);
    for (int i = 0; i < 1000 && library.CustomPackPending(); ++i)
      std::this_thread::sleep_for(std::chrono::milliseconds(5));
    CHECK(library.CustomPackStatus(customRequest) == 2);
    int customCount = library.CategoryCount("custom");
    // Facet pool survives an official commit: re-intersected with the new bundled names.
    CHECK(library.SetPool({"good 1.milk", "official unique.milk", "absent-in-official.milk"}) == 1);
    CHECK(library.SetCategory("facets"));
    auto request = library.RequestOfficialPack(directory, false); await(request);
    CHECK(library.OfficialPackStatus(request) == 1);
    CHECK(library.CommitOfficialPack(request));
    CHECK(library.OfficialPackStatus(request) == 2);
    CHECK(library.Category() == "facets" && library.CategoryCount("facets") == 2);
    library.SetPool({});
    CHECK(library.CategoryCount("facets") == 0);
    CHECK(library.Category() == "all");
    CHECK(library.CategoryCount("all") == 2 + customCount);
    CHECK(library.CategoryCount("custom") == customCount);
    CHECK(library.CategoryCount("chill") == 1 && library.Weight("good 1.milk") == 17);
    auto captured = library.ResolvePreset("good 1.milk");
    auto warmCaptured = g_prewarmReader("good 1.milk");
    CHECK(captured.data == "official first");
    CHECK(captured.texturePaths.size() == 1 && captured.texturePaths[0] == directory + "/textures");
    CHECK(library.OfficialPackInUse(directory));
    CHECK(LoadPreset("good 1.milk", false));
    CHECK(library.SetCategory("custom"));
    auto customCaptured = library.ResolvePreset(library.Next());
    CHECK(customCaptured.texturePaths.size() == 2 && customCaptured.texturePaths[1] == directory + "/textures");
    // An explicit prepare must not overwrite a category/skip mutation.
    auto stale = library.RequestOfficialPack("", false); await(stale);
    library.MarkSkipped("good 1.milk", "official stale snapshot control");
    CHECK(!library.CommitOfficialPack(stale)); library.DiscardOfficialPack(stale);
    auto rejected = library.RequestOfficialPack(root + "/missing-official", false); await(rejected);
    CHECK(library.OfficialPackStatus(rejected) == -1 && library.CategoryCount("custom") == customCount);
    // A custom publication between official prepare and commit must not be lost.
    auto old = library.RequestOfficialPack("", false); await(old);
    auto removeCustom = library.RequestCustomPack("");
    for (int i = 0; i < 1000 && library.CustomPackPending(); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(5));
    CHECK(library.CustomPackStatus(removeCustom) == 2);
    CHECK(!library.CommitOfficialPack(old)); library.DiscardOfficialPack(old);
    auto remove = library.RequestOfficialPack("", false); await(remove);
    CHECK(library.CommitOfficialPack(remove));
    CHECK(library.CategoryCount("all") == 12); // retained two skipped names in bundled inventory
    CHECK(library.OfficialPackInUse(directory)); // captured render/custom fallback generations pin it
    captured = {}; customCaptured = {};
    CHECK(library.OfficialPackInUse(directory)); // actual renderer must also pin its source
    CHECK(LoadPreset("good 2.milk", true));
    warmCaptured = {};
    CHECK(library.OfficialPackInUse(directory)); // outgoing instance still owns its images
    CHECK(LoadPreset("good 2.milk", false));
    for (int i = 0; i < 1000 && library.OfficialPackInUse(directory); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(5));
    CHECK(!library.OfficialPackInUse(directory));
    // Reject corrupt authored/storage identities and index weights without changing live state.
    for (const char* index : {"../evil.milk\tname.milk\t0\n", "0/0.milk\tname.milk\t-1\n", "0/0.milk\tname.milk\t3\n0/1.milk\tname.milk\t3\n"}) {
      write(directory + "/official-presets.idx", index);
      auto invalid = library.RequestOfficialPack(directory, false); await(invalid);
      CHECK(library.OfficialPackStatus(invalid) == -1 && library.CategoryCount("custom") == 0);
    }
    write(directory + "/official-presets.idx", "0/0.milk\tgood 1.milk\t17\n0/1.milk\tofficial unique.milk\t3\n");
    // File validation precedes native indexing on cold startup. Keep the requested mood
    // pending even when every starter in that mood has already been skipped.
    write(directory + "/preset-genres/genres/intense.idx", "official unique.milk\t3\n");
    library.MarkSkipped("good 1.milk", "cold mood fixture");
    library.MarkSkipped("good 2.milk", "cold mood fixture");
    library.MarkSkipped("good 3.milk", "cold mood fixture");
    Java_nl_neerdael_projectm_core_ProjectMJNI_setOfficialPresetRestorePending(nullptr,nullptr,true);
    {
      std::lock_guard<std::mutex> lock(g_inputs.categoryMutex);
      g_inputs.requestedCategory="intense";++g_inputs.categoryRequestedSerial;
    }
    g_inputs.categoryDirty=true;
    HandleCommands();
    CHECK(g_inputs.categoryDirty.load());
    CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_isMusicCategoryPending(nullptr,nullptr));
    auto delayedRestore=library.RequestOfficialPack(directory);await(delayedRestore);
    CHECK(library.OfficialPackStatus(delayedRestore)==2);
    HandleCommands();CHECK(g_inputs.categoryDirty.load());
    Java_nl_neerdael_projectm_core_ProjectMJNI_setOfficialPresetRestorePending(nullptr,nullptr,false);
    HandleCommands();
    CHECK(library.Category()=="intense" && library.CategoryCount("intense")==1);
    CHECK(!Java_nl_neerdael_projectm_core_ProjectMJNI_isMusicCategoryPending(nullptr,nullptr));
    auto delayedRemove=library.RequestOfficialPack("",false);await(delayedRemove);
    CHECK(library.CommitOfficialPack(delayedRemove));
    library.ResetSkipped();library.MarkSkipped("good 1.milk","restore prior fixture");
    library.MarkSkipped("preskipped.milk","restore prior fixture");library.SetCategory("all");
    // The two independent cold-restore requests converge on a coherent joined catalog.
    auto restoreOfficial = library.RequestOfficialPack(directory);
    auto restoreCustom = library.RequestCustomPack(custom);
    for (int i = 0; i < 1000 && (library.OfficialPackPending() || library.CustomPackPending()); ++i)
      std::this_thread::sleep_for(std::chrono::milliseconds(5));
    CHECK(library.OfficialPackStatus(restoreOfficial) == 2 && library.CustomPackStatus(restoreCustom) == 2);
    CHECK(library.CategoryCount("all") == 3 && library.CategoryCount("custom") == 2);
    auto superseded = library.RequestOfficialPack(directory, false);
    auto currentRequest = library.RequestOfficialPack("", false); await(currentRequest);
    CHECK(library.OfficialPackStatus(superseded) == -1);
    CHECK(library.CommitOfficialPack(currentRequest));
    auto clearCustom = library.RequestCustomPack("");
    for (int i = 0; i < 1000 && library.CustomPackPending(); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(5));
    CHECK(library.CustomPackStatus(clearCustom) == 2);
    library.ResetSkipped(); library.MarkSkipped("preskipped.milk", "restore fixture");
    // Return the GL/category fixture to bundled All before later context-loss controls.
    { std::lock_guard<std::mutex> lock(g_inputs.categoryMutex);
      g_inputs.requestedCategory="all";++g_inputs.categoryRequestedSerial; }
    g_inputs.categoryDirty=true;HandleCommands();
    CHECK(LoadPreset("good 2.milk",false));
  }
}
static void frame() { Java_nl_neerdael_projectm_core_ProjectMJNI_onDrawFrame(nullptr, nullptr); }
// A switch (remote-control command, or a switch request made between frames) after a direct
// frame waits for one stored frame (patch 0016).
static void switchFrame() { bool waits = g_lastFrameDirect; frame(); if (waits) frame(); }
static void feedAudio(uint8_t amp) { std::lock_guard<std::mutex> l(g_inputs.pcmMutex); for (int i = 0; i < 1024; ++i) g_inputs.pcm.push_back(128 + ((i & 1) ? amp : -amp)); g_inputs.audioLevel = amp / 128.f; g_inputs.audioLevelTime = NowSeconds(); }
static std::string current() { std::lock_guard<std::mutex> l(g_published.mutex); return g_published.currentPreset; }

// Exercise the Java renderer handoff through its real JNI lifecycle. Plain StatsListener
// renderers never require/acknowledge a budget and must retain their own settings.
static void checkManagedToLegacyRendererHandoff() {
  for (int legacyWidth : {2560, 3840}) {
    printf("managed release -> plain renderer (%s surface size)\n", legacyWidth == 3840 ? "same" : "different");
    Java_nl_neerdael_projectm_core_ProjectMJNI_onSurfaceCreated(nullptr, nullptr);
    const jlong managedGeneration = Java_nl_neerdael_projectm_core_ProjectMJNI_requireRenderBudget(nullptr, nullptr);
    Java_nl_neerdael_projectm_core_ProjectMJNI_configureRenderBudget(nullptr, nullptr, 3840, 2160, 2, 7, managedGeneration);
    Java_nl_neerdael_projectm_core_ProjectMJNI_onSurfaceChanged(nullptr, nullptr, 3840, 2160);
    Java_nl_neerdael_projectm_core_ProjectMJNI_setAutoChange(nullptr, nullptr, false);
    Java_nl_neerdael_projectm_core_ProjectMJNI_setBlankDetection(nullptr, nullptr, false);
    g_engine.current = "handoff fixture"; // Avoid involving asynchronous preset indexing.
    const jlong beforeManagedFrame = Java_nl_neerdael_projectm_core_ProjectMJNI_getRenderedFrameSerial(nullptr, nullptr);
    frame();
    CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_getRenderedFrameSerial(nullptr, nullptr) > beforeManagedFrame);
    CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_getCompletedRenderBudgetGeneration(nullptr, nullptr) == managedGeneration);
    CHECK(g_feedbackDetailAlpha == 1.f && g_appliedSoftCutSeconds == 7);

    Java_nl_neerdael_projectm_core_ProjectMJNI_release(nullptr, nullptr);
    Java_nl_neerdael_projectm_core_ProjectMJNI_setNativeTrails(nullptr, nullptr, 0);
    Java_nl_neerdael_projectm_core_ProjectMJNI_setSoftCutDuration(nullptr, nullptr, 1);
    Java_nl_neerdael_projectm_core_ProjectMJNI_onSurfaceCreated(nullptr, nullptr);
    // A delayed old managed UI callback must not reattach its request to the new owner.
    Java_nl_neerdael_projectm_core_ProjectMJNI_configureRenderBudget(nullptr, nullptr, 3840, 2160, 2, 7, managedGeneration);
    Java_nl_neerdael_projectm_core_ProjectMJNI_onSurfaceChanged(nullptr, nullptr, legacyWidth, legacyWidth == 3840 ? 2160 : 1440);
    g_engine.current = "handoff fixture";
    const jlong beforeLegacyFrame = Java_nl_neerdael_projectm_core_ProjectMJNI_getRenderedFrameSerial(nullptr, nullptr);
    frame();
    CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_getRenderedFrameSerial(nullptr, nullptr) > beforeLegacyFrame);
    CHECK(g_feedbackDetailAlpha == 0.f && g_appliedSoftCutSeconds == 1);
    CHECK(g_locked); // Cleanup must not reset unrelated persisted engine inputs.
    const auto legacyBudget = RenderBudgetSnapshot();
    CHECK(!legacyBudget.managed && !legacyBudget.awaitingReview);
    CHECK(legacyBudget.width == 0 && legacyBudget.height == 0);
    CHECK(legacyBudget.generation > managedGeneration);
    CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_getCompletedRenderBudgetGeneration(nullptr, nullptr) == -1);
    Java_nl_neerdael_projectm_core_ProjectMJNI_release(nullptr, nullptr);
  }
}

int main(int argc, char** argv) {
  setvbuf(stdout, nullptr, _IONBF, 0);
  if (argc == 2 && std::string(argv[1]) == "--budget-handoff") {
    checkManagedToLegacyRendererHandoff();
    printf("MANAGED/LEGACY HANDOFF TESTS PASSED\n");
    return 0;
  }
  std::string root = argv[1], skip = root + "/skip.txt", texdir = root + "/extracted_textures";
  static AAssetManager am{root};
  g_library.Start(&am, skip, texdir);
  for (int i = 0; i < 200 && !g_library.Ready(); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(5));

  printf("indexing from presets.idx\n");
  CHECK(g_library.Ready());
  CHECK(g_library.ActiveCount() == 13);   // 14 .milk entries (incl. .MILK and a CRLF line), others ignored, 1 pre-skipped

  printf("preset weights from presets.idx\n");
  CHECK(g_library.Weight("good 3.milk") == 40 && g_library.Weight("good 2.milk") == 2);
  CHECK(g_library.Weight("good 1.milk") == 0 && g_library.Weight("good 4.milk") == 0);
  CHECK(g_library.Weight("crlf.milk") == 7);  // CRLF line

  printf("music category limits every library selection path\n");
  CHECK(g_library.SetCategory("intense"));
  CHECK(g_library.Category() == "intense" && g_library.CategoryCount("intense") == 3);
  for (int i = 0; i < 30; ++i) {
    std::string pick = g_library.Next();
    CHECK(pick == "good 1.milk" || pick == "good 2.milk" || pick == "good 3.milk");
    g_library.RecordShown(pick);
    std::string random = g_library.Random(pick);
    CHECK(random == "good 1.milk" || random == "good 2.milk" || random == "good 3.milk");
  }
  auto generation = g_library.CategoryGeneration();
  CHECK(g_library.SetCategory("chill"));
  CHECK(g_library.CategoryGeneration() > generation);
  CHECK(g_library.Previous().empty() && g_library.PeekPrevious().empty());
  CHECK(g_library.PeekRandom() == "good 4.milk" || g_library.PeekRandom() == "good 5.milk");
  printf("the prepared random preset is never the one on screen\n");
  g_library.RecordShown("good 4.milk");
  CHECK(g_library.PeekRandom() == "good 5.milk");
  g_library.RecordShown("good 5.milk");  // Next or Previous landed on the prepared random preset
  CHECK(g_library.PeekRandom() == "good 4.milk");
  // A curated group reduced to one eligible member still selects that member.
  g_library.MarkSkipped("good 5.milk", "single-member control");
  g_library.RecordShown("good 4.milk");
  CHECK(g_library.CategoryCount("chill") == 1);
  CHECK(g_library.PeekRandom() == "good 4.milk" && g_library.PeekRandom() == "good 4.milk");
  CHECK(g_library.Random("good 4.milk") == "good 4.milk");
  g_library.ResetSkipped();
  g_library.MarkSkipped("preskipped.milk", "fixture initial skip");
  CHECK(!g_library.SetCategory("dance") && g_library.Category() == "all");
  CHECK(!g_library.SetCategory("unknown") && g_library.Category() == "all");
  CHECK(g_library.SetCategory("all"));
  CHECK(g_library.ActiveCount() == 13 && g_library.Weight("good 3.milk") == 40);

  printf("facet pool plays through the facets category\n");
  CHECK(g_library.SetPool({"good 1.milk", "good 1.milk", "missing.milk", "custom/x.milk"}) == 1);
  CHECK(g_library.CategoryCount("facets") == 1);
  CHECK(g_library.SetCategory("facets"));
  CHECK(g_library.Category() == "facets");
  for (int i = 0; i < 5; ++i) CHECK(g_library.Random("") == "good 1.milk");
  g_library.MarkSkipped("good 1.milk", "test");
  CHECK(g_library.CategoryCount("facets") == 0);
  CHECK(!g_library.Next().empty());
  CHECK(g_library.Category() == "all");
  g_library.ResetSkipped();
  g_library.MarkSkipped("preskipped.milk", "fixture initial skip");
  CHECK(g_library.SetPool({}) == 0);
  CHECK(!g_library.SetCategory("facets"));
  CHECK(g_library.Category() == "all");

  printf("custom packs join All but never join scored categories\n");
  std::string pack = root + "/pack-generation-one";
  mkdir(pack.c_str(), 0700);
  mkdir((pack + "/0").c_str(), 0700);
  { FILE* f = fopen((pack + "/0/0.milk").c_str(), "w"); fputs("custom first", f); fclose(f); }
  { FILE* f = fopen((pack + "/0/1.milk").c_str(), "w"); fputs("custom second", f); fclose(f); }
  { FILE* f = fopen((pack + "/presets.idx").c_str(), "w");
    fprintf(f, "0/0.milk\t%s.milk\n0/1.milk\tother/good 1.milk\n", std::string(1000, 'x').c_str()); fclose(f); }
  auto installPack = [](const std::string& directory) {
    g_library.RequestCustomPack(directory);
    for (int i = 0; i < 1000 && g_library.CustomPackPending(); ++i)
      std::this_thread::sleep_for(std::chrono::milliseconds(5));
    CHECK(!g_library.CustomPackPending());
  };
  installPack(pack);
  CHECK(g_library.CategoryCount("all") == 15 && g_library.CategoryCount("custom") == 2);
  CHECK(g_library.CategoryCount("chill") == 2 && g_library.CategoryCount("intense") == 3);
  CHECK(g_library.SetCategory("custom"));
  std::string first = g_library.Next();
  CHECK(first.find("custom/pack-generation-one/") == 0);
  CHECK(g_library.Load(first) == "custom first" || g_library.Load(first) == "custom second");
  g_library.RecordShown(first);
  std::string second = g_library.Random(first);
  CHECK(first != second && g_library.Contains(second));
  g_library.RecordShown(second);
  CHECK(g_library.Previous() == first);
  std::string longName = "custom/pack-generation-one/" + std::string(1000, 'x') + ".milk";
  g_library.MarkSkipped(longName, "custom skip identity");
  CHECK(g_library.CategoryCount("custom") == 1 && g_library.CategoryCount("intense") == 3);
  printf("facet pool requested before the index is ready survives BuildIndex\n");
  { PresetLibrary& early = *new PresetLibrary();
    CHECK(early.SetPool({"good 2.milk", "good 3.milk", "missing.milk"}) == 0);  // empty bundled inventory
    early.Start(&am, skip, "");
    for (int i = 0; i < 1000 && !early.Ready(); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(5));
    CHECK(early.Ready());
    CHECK(early.CategoryCount("facets") == 2);
    CHECK(early.SetCategory("facets") && early.Category() == "facets"); }
  // Long nested/display names must preserve their skip identity after a process restart.
  PresetLibrary& restartedPack = *new PresetLibrary();
  restartedPack.Start(&am, skip, "");
  for (int i = 0; i < 1000 && !restartedPack.Ready(); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(5));
  restartedPack.RequestCustomPack(pack);
  for (int i = 0; i < 1000 && restartedPack.CustomPackPending(); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(5));
  CHECK(!restartedPack.CustomPackPending() && restartedPack.CategoryCount("custom") == 1);
  // Rejected and canceled native preparations must never replace the live catalog.
  auto rejected = g_library.RequestCustomPack(root + "/missing-pack", false);
  for (int i = 0; i < 1000 && g_library.CustomPackPending(); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(5));
  CHECK(g_library.CustomPackStatus(rejected) == -1 && g_library.CategoryCount("custom") == 1);
  auto staged = g_library.RequestCustomPack(pack, false);
  for (int i = 0; i < 1000 && g_library.CustomPackPending(); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(5));
  CHECK(g_library.CustomPackStatus(staged) == 1 && g_library.CategoryCount("custom") == 1);
  g_library.DiscardCustomPack(staged);
  CHECK(!g_library.CommitCustomPack(staged) && g_library.CategoryCount("custom") == 1);
  staged = g_library.RequestCustomPack(pack, false);
  for (int i = 0; i < 1000 && g_library.CustomPackPending(); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(5));
  CHECK(g_library.CommitCustomPack(staged) && g_library.CustomPackStatus(staged) == 2);
  CHECK(g_library.Category() == "custom" && g_library.CategoryCount("all") == 14);
  installPack("");
  CHECK(g_library.Category() == "all" && g_library.CategoryCount("custom") == 0);
  CHECK(!g_library.Contains(first) && g_library.Read(first).empty());
  CHECK(g_library.ActiveCount() == 13);
  g_library.ResetSkipped();
  g_library.MarkSkipped("preskipped.milk", "fixture initial skip");

  printf("a facet pool change during a staged (bundled-only) import keeps the import and no stale facet order\n");
  CHECK(g_library.SetPool({"good 1.milk"}) == 1);
  CHECK(g_library.SetCategory("facets") && g_library.Category() == "facets");
  staged = g_library.RequestCustomPack(pack, false);  // new directory, not applied: bundled-only prepare
  for (int i = 0; i < 1000 && g_library.CustomPackPending(); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(5));
  CHECK(g_library.CustomPackStatus(staged) == 1);
  CHECK(g_library.SetPool({"good 2.milk", "good 3.milk"}) == 2);  // pool P2 while the pack is staged
  CHECK(g_library.Category() == "facets");
  for (int i = 0; i < 10; ++i) { std::string pick = g_library.Random(""); CHECK(pick == "good 2.milk" || pick == "good 3.milk"); }
  CHECK(g_library.CommitCustomPack(staged));  // the staged import is not invalidated by the pool change
  CHECK(g_library.Category() == "custom");    // a staged commit selects Custom; it never keeps a facet order
  CHECK(g_library.CategoryCount("facets") == 2);
  for (int i = 0; i < 10; ++i) {
    std::string next = g_library.Next(); g_library.RecordShown(next);
    CHECK(next.find("custom/pack-generation-one/") == 0);
    std::string random = g_library.Random(next);
    CHECK(random.find("custom/pack-generation-one/") == 0);
  }
  CHECK(g_library.SetCategory("facets"));     // re-selecting facets draws from the current pool P2
  for (int i = 0; i < 10; ++i) {
    std::string next = g_library.Next(); g_library.RecordShown(next);
    CHECK(next == "good 2.milk" || next == "good 3.milk");
    std::string random = g_library.Random(next);
    CHECK(random == "good 2.milk" || random == "good 3.milk");
  }
  installPack("");
  CHECK(g_library.SetPool({}) == 0);
  CHECK(g_library.SetCategory("all") && g_library.CategoryCount("custom") == 0 && g_library.ActiveCount() == 13);
  g_library.ResetSkipped();
  g_library.MarkSkipped("preskipped.milk", "fixture initial skip");

  printf("indexing falls back to listing the folder without presets.idx\n");
  { std::string root2 = argv[2]; static AAssetManager am2{root2}; PresetLibrary& other = *new PresetLibrary();
    other.Start(&am2, root2 + "/skip.txt", "");  // never destroyed, like the app's library
    for (int i = 0; i < 200 && !other.Ready(); ++i) std::this_thread::sleep_for(std::chrono::milliseconds(5));
    CHECK(other.Ready() && other.ActiveCount() == 3);
    CHECK(other.CategoryCount("normal") == 0);  // malformed weight must not load
    CHECK(!other.SetCategory("normal") && other.Category() == "all"); }
  CHECK(g_library.SkippedCount() == 1);

  printf("texture pack extracted before the index is ready\n");
  { FILE* f = fopen((texdir + "/worms.jpg").c_str(), "rb"); CHECK(f != nullptr); if (f) { fseek(f, 0, SEEK_END); CHECK(ftell(f) == 9); fclose(f); } }
  { FILE* f = fopen((texdir + "/clouds.jpg").c_str(), "rb"); CHECK(f != nullptr); if (f) fclose(f); }

  printf("first frame loads a preset (hard cut, no wait)\n");
  Java_nl_neerdael_projectm_core_ProjectMJNI_onSurfaceCreated(nullptr, nullptr);
  printf("lines are quads, 1 px at MilkDrop's 1024x768\n");
  CHECK(g_lineReferenceWidth == 1024);
  CHECK(g_lineReferenceHeight == 768);
  Java_nl_neerdael_projectm_core_ProjectMJNI_onSurfaceChanged(nullptr, nullptr, 1280, 720);
  frame();
  CHECK(!current().empty());
  CHECK(current() != "preskipped.milk");
  CHECK(g_texturePathCalls.size() == 1 && g_texturePathCalls[0] == texdir);
  CHECK(g_loadsAtTextureCall == 0);  // search path set before the first preset loaded
  CHECK(!g_locked);

  printf("texture lookup belongs to each preset, including All and replacement generations\n");
  auto loadTextureFixture = [](const std::string& name, bool smooth) {
    // Like the real switch path, store a frame before loading after direct presentation.
    projectm_opengl_set_direct_output(g_engine.pm, false);
    projectm_opengl_render_frame(g_engine.pm);
    g_engine.lastFrameDirect = false;
    return LoadPreset(name, smooth);
  };
  installPack(pack);
  CHECK(g_library.SetCategory("all"));
  CHECK(loadTextureFixture(second, false));
  CHECK(IsCustomPresetPackInUse(pack));
  CHECK(g_textureSearchPaths.back() == std::vector<std::string>({pack + "/textures", texdir}));
  const auto warm = g_prewarmReader(second);
  CHECK(warm.data == "custom first" || warm.data == "custom second");
  CHECK(warm.texturePaths == g_textureSearchPaths.back());
  const auto samePackCalls = g_textureSearchPaths.size();
  CHECK(loadTextureFixture(second, false));
  CHECK(g_textureSearchPaths.size() == samePackCalls);
  CHECK(loadTextureFixture("good 1.milk", true));
  CHECK(IsCustomPresetPackInUse(pack)); // Outgoing preset can still lazily read its images.
  CHECK(g_textureSearchPaths.back() == std::vector<std::string>({texdir}));
  CHECK(g_prewarmReader("good 1.milk").texturePaths == g_textureSearchPaths.back());
  CHECK(loadTextureFixture(second, false));
  Java_nl_neerdael_projectm_core_ProjectMJNI_onSurfaceCreated(nullptr, nullptr);
  Java_nl_neerdael_projectm_core_ProjectMJNI_onSurfaceChanged(nullptr, nullptr, 1280, 720);
  frame();
  CHECK(current() == second);
  CHECK(g_textureSearchPaths.back() == std::vector<std::string>({pack + "/textures", texdir}));
  const std::string replacement = root + "/pack-generation-two";
  mkdir(replacement.c_str(), 0700);
  mkdir((replacement + "/0").c_str(), 0700);
  { FILE* f = fopen((replacement + "/0/0.milk").c_str(), "w"); fputs("replacement data", f); fclose(f); }
  { FILE* f = fopen((replacement + "/presets.idx").c_str(), "w"); fputs("0/0.milk\treplacement.milk\n", f); fclose(f); }
  installPack(replacement);
  const std::string replaced = "custom/pack-generation-two/replacement.milk";
  CHECK(g_prewarmReader(second).data.empty());
  CHECK(warm.texturePaths == std::vector<std::string>({pack + "/textures", texdir}));
  static std::string loadingDirectory;
  loadingDirectory = replacement;
  g_loadObserver = [] { CHECK(IsCustomPresetPackInUse(loadingDirectory)); };
  CHECK(loadTextureFixture(replaced, true));
  g_loadObserver = nullptr;
  CHECK(IsCustomPresetPackInUse(pack) && IsCustomPresetPackInUse(replacement));
  g_fakeTransitioning = false;
  frame(); // The actual engine reports the outgoing instance has been released.
  CHECK(!IsCustomPresetPackInUse(pack) && IsCustomPresetPackInUse(replacement));
  CHECK(g_textureSearchPaths.back() == std::vector<std::string>({replacement + "/textures", texdir}));
  CHECK(g_prewarmReader(replaced).data == "replacement data");
  CHECK(g_prewarmReader(replaced).texturePaths == g_textureSearchPaths.back());
  installPack("");
  CHECK(g_prewarmReader(second).data.empty());
  CHECK(!loadTextureFixture(second, false));
  CHECK(loadTextureFixture("good 1.milk", false));
  CHECK(!IsCustomPresetPackInUse(pack) && !IsCustomPresetPackInUse(replacement));
  g_prewarmActive = second;
  CHECK(IsCustomPresetPackInUse(pack)); // A retired reader leases its generation before resolving.
  g_prewarmActive.clear();
  ++g_inputs.categoryRequestedSerial;
  CHECK(IsCustomPresetPackInUse(pack)); // Retain until the GL category handoff is acknowledged.
  g_inputs.categoryAppliedSerial = g_inputs.categoryRequestedSerial.load();
  CHECK(!IsCustomPresetPackInUse(pack));
  CHECK(g_textureSearchPaths.back() == std::vector<std::string>({texdir}));
  g_library.ResetSkipped();
  g_library.MarkSkipped("preskipped.milk", "fixture initial skip");
  CheckOfficialPack(g_library, root, pack);
  // Later lifecycle checks count the initial path application plus one context recreation.
  g_texturePathCalls.assign(1, texdir);
  if (argc == 4 && std::string(argv[3]) == "--texture-routing") {
    installPack(replacement);
    CHECK(loadTextureFixture(replaced, false));
    CHECK(IsCustomPresetPackInUse(replacement));
    Java_nl_neerdael_projectm_core_ProjectMJNI_release(nullptr, nullptr);
    CHECK(!IsCustomPresetPackInUse(replacement)); // A saved resume name owns no files after release.
    printf("CUSTOM PACK TEXTURE ROUTING TESTS PASSED\n");
    return 0;
  }

  printf("music category stays pending until its first preset is published\n");
  auto requestCategory = [](const std::string& category) {
    std::lock_guard<std::mutex> lock(g_inputs.categoryMutex);
    g_inputs.requestedCategory = category;
    ++g_inputs.categoryRequestedSerial;
    g_inputs.categoryDirty = true;
  };
  std::string category = (current() == "good 1.milk" || current() == "good 2.milk" || current() == "good 3.milk")
                          ? "chill" : "intense";
  g_loadObserver = [] { CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_isMusicCategoryPending(nullptr, nullptr)); };
  requestCategory(category);
  switchFrame();
  CHECK(!Java_nl_neerdael_projectm_core_ProjectMJNI_isMusicCategoryPending(nullptr, nullptr));
  CHECK(g_library.Contains(current()));
  // Startup/context restoration must apply the same completion ordering.
  g_engine.current.clear();
  g_engine.lastFrameDirect = false;
  g_lastFrameDirect = false;  // a new context has no previously rendered direct frame
  requestCategory(category == "intense" ? "chill" : "intense");
  frame();
  CHECK(!Java_nl_neerdael_projectm_core_ProjectMJNI_isMusicCategoryPending(nullptr, nullptr));
  CHECK(g_library.Contains(current()));
  g_loadObserver = nullptr;
  requestCategory("all");
  switchFrame();

  printf("category retries bounded load failures before acknowledging completion\n");
  requestCategory("chill");
  switchFrame();
  CHECK(current() == "good 4.milk" || current() == "good 5.milk");
  g_failNextLoads = 4;
  requestCategory("normal");
  switchFrame();
  CHECK(g_library.CategoryCount("normal") == 1);
  CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_isMusicCategoryPending(nullptr, nullptr));
  for (int i = 0; i < 10 && Java_nl_neerdael_projectm_core_ProjectMJNI_isMusicCategoryPending(nullptr, nullptr); ++i) frame();
  CHECK(g_library.Category() == "normal" && g_library.Contains(current()));
  CHECK(!Java_nl_neerdael_projectm_core_ProjectMJNI_isMusicCategoryPending(nullptr, nullptr));
  g_library.ResetSkipped();
  g_library.MarkSkipped("preskipped.milk", "fixture initial skip");
  requestCategory("all");
  switchFrame();

  printf("retained category changes prepare the next selection around the preset on screen\n");
  requestCategory("chill");  // two good presets; switching to All retains either one
  switchFrame();
  for (int i = 0; i < 20; ++i) {
    for (const char* category : {"all", "chill"}) {
      std::string kept = current();
      requestCategory(category);
      switchFrame();
      const auto prepared = g_prewarmLists.back();
      CHECK(current() == kept && prepared.size() == 3);
      CHECK(prepared[0] == g_library.PeekNext() && prepared[1] == g_library.PeekRandom());
      CHECK(prepared[1] != kept && prepared[2].empty());
    }
    std::string prepared = g_prewarmLists.back()[1];
    Java_nl_neerdael_projectm_core_ProjectMJNI_randomPreset(nullptr, nullptr, true); switchFrame();
    CHECK(current() == prepared);
  }

  printf("a preset that leaves out uncompilable code is shown, logged and not skipped\n");
  { int skippedBefore = g_library.SkippedCount(); size_t logsBefore = g_logLines.size();
    g_warnNextLoads = 1;
    Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
    CHECK(g_warnNextLoads == 0 && g_library.SkippedCount() == skippedBefore);
    std::string expected = "Preset code left out (" + current() + "): Could not compile per-pixel code: syntax error (line 2, column 5)";
    bool logged = false;
    for (size_t i = logsBefore; i < g_logLines.size(); ++i) logged = logged || g_logLines[i] == expected;
    CHECK(logged); }

  printf("Next and Previous landing on the prepared random preset refresh its preparation\n");
  std::string prepared = g_prewarmLists.back()[1];
  Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
  CHECK(current() == prepared && g_prewarmLists.back()[1] != current());
  prepared = g_prewarmLists.back()[1];
  Java_nl_neerdael_projectm_core_ProjectMJNI_randomPreset(nullptr, nullptr, true); switchFrame();
  CHECK(current() == prepared);
  prepared = g_prewarmLists.back()[1];
  Java_nl_neerdael_projectm_core_ProjectMJNI_previousPreset(nullptr, nullptr, true); switchFrame();
  CHECK(current() == prepared && g_prewarmLists.back()[1] != current());
  prepared = g_prewarmLists.back()[1];
  Java_nl_neerdael_projectm_core_ProjectMJNI_randomPreset(nullptr, nullptr, true); switchFrame();
  CHECK(current() == prepared);
  requestCategory("all");
  switchFrame();

  printf("settings from any thread\n");
  Java_nl_neerdael_projectm_core_ProjectMJNI_setAutoChange(nullptr, nullptr, false); frame();
  CHECK(g_locked);
  Java_nl_neerdael_projectm_core_ProjectMJNI_setAutoChange(nullptr, nullptr, true); switchFrame();

  printf("commands\n");
  std::string a = current();
  Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
  std::string b = current(); CHECK(b != a);
  Java_nl_neerdael_projectm_core_ProjectMJNI_randomPreset(nullptr, nullptr, true); switchFrame();
  std::string c = current(); CHECK(c != b);
  Java_nl_neerdael_projectm_core_ProjectMJNI_previousPreset(nullptr, nullptr, true); switchFrame();
  CHECK(current() == b);
  Java_nl_neerdael_projectm_core_ProjectMJNI_previousPreset(nullptr, nullptr, true); switchFrame();
  CHECK(current() == a);

  printf("projectM-requested auto switch (smooth), and forced hard cut before a resize\n");
  // A switch shows up as a successful load: after a reshuffle the same preset may legally come next.
  size_t loads = g_loaded.size(); g_reqCb(false, nullptr); switchFrame();
  CHECK(g_loaded.size() == loads + 1);
  CHECK(g_lastSmooth);
  Java_nl_neerdael_projectm_core_ProjectMJNI_setForceHardCut(nullptr, nullptr, true);
  loads = g_loaded.size(); g_reqCb(false, nullptr); switchFrame();
  CHECK(g_loaded.size() == loads + 1 && !g_lastSmooth);
  g_reqCb(false, nullptr); switchFrame();
  CHECK(g_lastSmooth);  // flag is one-shot

  printf("mesh size only re-applied when it changes\n");
  int meshCalls = g_meshCalls;
  Java_nl_neerdael_projectm_core_ProjectMJNI_setSoftCutDuration(nullptr, nullptr, 5); frame();
  CHECK(g_meshCalls == meshCalls);
  Java_nl_neerdael_projectm_core_ProjectMJNI_setMeshSize(nullptr, nullptr, 64, 48); frame();
  CHECK(g_meshCalls == meshCalls + 1);

  printf("broken presets are skipped and persisted, playback continues\n");
  for (int i = 0; i < 40; ++i) { Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame(); }
  CHECK(g_library.SkippedCount() == 3);    // pre-skipped + 2 broken
  CHECK(current().find("broken") == std::string::npos);
  { FILE* f = fopen(skip.c_str(), "r"); char line[256]; int n = 0; while (fgets(line, sizeof line, f)) ++n; fclose(f); CHECK(n == 3); }

  printf("next never shows the preset on screen again, also across reshuffles\n");
  { std::string before = current(); int repeats = 0;
    for (int i = 0; i < 200; ++i) {  // ~18 passes through the shuffled order
      Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
      if (current() == before) ++repeats;
      before = current();
    }
    CHECK(repeats == 0); }

  printf("audio is fed on the GL thread, capped to projectM's buffer\n");
  g_pcmFed = 0; feedAudio(60); frame(); CHECK(g_pcmFed == 576);

  printf("blank-preset skipping is off by default: a black preset with music stays\n");
  g_pixel = 5; int skippedAtStart = g_library.SkippedCount();
  Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
  std::string unproven = current();
  for (int i = 0; i < 400; ++i) { feedAudio(60); frame(); std::this_thread::sleep_for(std::chrono::milliseconds(20)); }
  CHECK(current() == unproven && g_library.SkippedCount() == skippedAtStart);
  Java_nl_neerdael_projectm_core_ProjectMJNI_setBlankDetection(nullptr, nullptr, true);

  printf("dark preset during silence is NOT skipped\n");
  g_pixel = 0; int skippedBefore = g_library.SkippedCount();
  Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
  std::string dark = current();
  g_inputs.audioLevel = 0.f;
  for (int i = 0; i < 400; ++i) { frame(); std::this_thread::sleep_for(std::chrono::milliseconds(20)); }  // 8s
  CHECK(g_library.SkippedCount() == skippedBefore && current() == dark);

  printf("visible preset with music is NOT skipped\n");
  g_pixel = 200;
  Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
  std::string bright = current();
  for (int i = 0; i < 400; ++i) { feedAudio(60); frame(); std::this_thread::sleep_for(std::chrono::milliseconds(20)); }
  CHECK(g_library.SkippedCount() == skippedBefore && current() == bright);

  printf("black preset with music is replaced at once, but only skipped for good the 2nd time\n");
  g_pixel = 5;
  Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
  std::string black = current();
  for (int i = 0; i < 400 && current() == black; ++i) { feedAudio(60); frame(); std::this_thread::sleep_for(std::chrono::milliseconds(20)); }
  CHECK(current() != black);
  CHECK(g_library.SkippedCount() == skippedBefore);  // first strike: moved on, not listed
  { FILE* f = fopen((skip + ".blank").c_str(), "r"); CHECK(f != nullptr); char line[256] = {0}; CHECK(fgets(line, sizeof line, f) != nullptr); fclose(f);
    line[strcspn(line, "\r\n")] = 0; CHECK(black == line); }  // strike persisted
  Java_nl_neerdael_projectm_core_ProjectMJNI_previousPreset(nullptr, nullptr, true); switchFrame();
  CHECK(current() == black);  // shown again
  for (int i = 0; i < 400 && current() == black; ++i) { feedAudio(60); frame(); std::this_thread::sleep_for(std::chrono::milliseconds(20)); }
  CHECK(current() != black);
  CHECK(g_library.SkippedCount() == skippedBefore + 1);  // second strike: skipped

  printf("skip current preset (too slow) and blank-detection toggle\n");
  g_pixel = 200; int beforeSkip = g_library.SkippedCount(); std::string slow = current();
  Java_nl_neerdael_projectm_core_ProjectMJNI_skipCurrentPreset(nullptr, nullptr); switchFrame();
  CHECK(current() != slow && g_library.SkippedCount() == beforeSkip + 1);
  Java_nl_neerdael_projectm_core_ProjectMJNI_setBlankDetection(nullptr, nullptr, false);
  g_pixel = 5; Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
  std::string dim = current();
  for (int i = 0; i < 400; ++i) { feedAudio(60); frame(); std::this_thread::sleep_for(std::chrono::milliseconds(20)); }
  CHECK(current() == dim && g_library.SkippedCount() == beforeSkip + 1);
  Java_nl_neerdael_projectm_core_ProjectMJNI_setBlankDetection(nullptr, nullptr, true);

  printf("everything black (rendering fault): after 3 black presets in a row nothing more is struck\n");
  g_pixel = 200;  // a visible preset resets the run of black ones
  Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
  for (int i = 0; i < 200; ++i) { feedAudio(60); frame(); std::this_thread::sleep_for(std::chrono::milliseconds(20)); }
  g_pixel = 5; int skippedBeforeRun = g_library.SkippedCount();
  Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
  int changes = 0; std::string onScreen = current();
  for (int i = 0; i < 2000 && changes < 4; ++i) {
    feedAudio(60); frame(); std::this_thread::sleep_for(std::chrono::milliseconds(20));
    if (current() != onScreen) { ++changes; onScreen = current(); }
  }
  CHECK(changes == 3);  // three black presets moved on, the fourth stays
  CHECK(g_library.SkippedCount() <= skippedBeforeRun + 3);

  printf("reset skip list\n");
  Java_nl_neerdael_projectm_core_ProjectMJNI_resetSkippedPresets(nullptr, nullptr);
  CHECK(g_library.SkippedCount() == 0 && g_library.ActiveCount() == 14);
  { FILE* f = fopen((skip + ".blank").c_str(), "r"); CHECK(f != nullptr); CHECK(fgetc(f) == EOF); fclose(f); }  // strikes cleared

  printf("context loss: new instance resumes the same preset, textures re-applied\n");
  g_pixel = 200; std::string shown = current();
  g_lineReferenceWidth = g_lineReferenceHeight = 0;
  Java_nl_neerdael_projectm_core_ProjectMJNI_onSurfaceCreated(nullptr, nullptr);
  Java_nl_neerdael_projectm_core_ProjectMJNI_onSurfaceChanged(nullptr, nullptr, 1280, 720); frame();
  CHECK(current() == shown);
  CHECK(g_texturePathCalls.size() == 2);
  CHECK(g_lineReferenceWidth == 1024 && g_lineReferenceHeight == 768);  // set on the new instance too

  printf("black detection reads the window framebuffer, not projectM's\n");
  CHECK(g_readFbo == 7);  // the previous read binding is restored after sampling
  CHECK(g_packBuffer == 0 && g_mapped > 0);  // pixel pack buffer unbound again; results were collected
  CHECK(g_fences <= 1);                      // at most one read in flight, fences are deleted

  auto settle = [](int ms) { for (int i = 0; i < ms / 2; ++i) { frame(); std::this_thread::sleep_for(std::chrono::milliseconds(2)); } };
  Java_nl_neerdael_projectm_core_ProjectMJNI_setSoftCutDuration(nullptr, nullptr, 5); frame();

  printf("lightweight: outgoing frame captured, projectM hard-cuts, overlay fades for min(transition, 3 s)\n");
  Java_nl_neerdael_projectm_core_ProjectMJNI_setTransitionMode(nullptr, nullptr, 1, false);
  CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_isLightweightTransition(nullptr, nullptr));
  int captures = g_captures, starts = g_fadeStarts; loads = g_loaded.size();
  g_requestInRender = true; frame();          // request fires during this frame's render
  CHECK(g_captures == captures + 1 && g_loaded.size() == loads);  // no switch yet
  frame();                                    // next frame switches
  CHECK(g_loaded.size() == loads + 1 && !g_lastSmooth);
  CHECK(g_fadeStarts == starts + 1 && g_fadeSeconds == 3.0 && g_engine.fade.Active());
  int draws = g_fadeDraws; frame(); CHECK(g_fadeDraws == draws + 1);

  printf("a remote-control switch ends the fade immediately\n");
  Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
  CHECK(!g_engine.fade.Active());

  printf("beat-triggered hard cuts and forced hard cuts are never faded\n");
  captures = g_captures; starts = g_fadeStarts;
  g_reqCb(true, nullptr); switchFrame(); frame();
  Java_nl_neerdael_projectm_core_ProjectMJNI_setForceHardCut(nullptr, nullptr, true);
  g_requestInRender = true; frame(); frame();
  CHECK(g_captures == captures && g_fadeStarts == starts && !g_lastSmooth);

  printf("capture failure falls back to projectM's classic transition\n");
  g_captureOk = false; loads = g_loaded.size();
  g_requestInRender = true; frame(); frame();
  CHECK(g_loaded.size() == loads + 1 && g_lastSmooth && !g_engine.fade.Active());
  g_captureOk = true;

  printf("classic mode: projectM soft cut, no capture\n");
  Java_nl_neerdael_projectm_core_ProjectMJNI_setTransitionMode(nullptr, nullptr, 2, true);
  CHECK(!Java_nl_neerdael_projectm_core_ProjectMJNI_isLightweightTransition(nullptr, nullptr));
  captures = g_captures; loads = g_loaded.size();
  g_requestInRender = true; frame(); frame();
  CHECK(g_captures == captures && g_loaded.size() == loads + 1 && g_lastSmooth);

  printf("classic mode blends at the full render size\n");
  CHECK(g_windowW == 1280 && g_windowH == 720);

  // Waits until the running transition has ended and the render size is back to full.
  auto finishTransition = [&](int before) {
    for (int i = 0; i < 1500 && Java_nl_neerdael_projectm_core_ProjectMJNI_getTransitionCounter(nullptr, nullptr) == before; ++i) frame();
    settle(400); };
  // Starts an automatic blend; returns the transition counter before it.
  auto startBlend = [&]() {
    int before = Java_nl_neerdael_projectm_core_ProjectMJNI_getTransitionCounter(nullptr, nullptr);
    g_requestInRender = true; frame(); frame();
    return before; };

  printf("auto: blends render at 75%% into the off-screen target, stretched onto the surface\n");
  Java_nl_neerdael_projectm_core_ProjectMJNI_setTransitionMode(nullptr, nullptr, 0, false);
  Java_nl_neerdael_projectm_core_ProjectMJNI_setSoftCutDuration(nullptr, nullptr, 1);
  g_renderSleepMs = 1; g_renderSleepMsSmooth = 0;
  Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();  // hard cut: full size
  settle(1500);
  CHECK(!Java_nl_neerdael_projectm_core_ProjectMJNI_isLightweightTransition(nullptr, nullptr));
  CHECK(g_windowW == 1280 && g_windowH == 720);
  int fboFrames = g_fboFrames, blits = g_blits;
  int transitions = startBlend();
  CHECK(g_lastSmooth && g_windowW == 960 && g_windowH == 540);
  CHECK(g_fboFrames > fboFrames && g_blits > blits);
  CHECK(g_blitSrcW == 960 && g_blitSrcH == 540 && g_blitDstW == 1280 && g_blitDstH == 720);
  finishTransition(transitions);
  CHECK(g_windowW == 1280 && g_windowH == 720);  // back to full size after the blend
  CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_getBlendScalePercent(nullptr, nullptr) == 75);
  fboFrames = g_fboFrames; frame();
  CHECK(g_fboFrames == fboFrames);  // full size renders straight to the surface

  printf("auto: a blend far slower than before is lowered at once, and stays lower\n");
  settle(1500);
  g_renderSleepMsSmooth = 15;
  transitions = startBlend();
  CHECK(g_windowW == 960);
  for (int i = 0; i < 200 && g_windowW == 960; ++i) frame();
  CHECK(g_windowW == 768 && g_windowH == 432);  // 60%, during the same blend
  finishTransition(transitions);
  CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_getBlendScalePercent(nullptr, nullptr) == 60);
  Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();  // fast frames before it
  settle(1500);
  transitions = startBlend();
  CHECK(g_windowW == 768);  // the next blend starts at the lower size
  finishTransition(transitions);
  CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_getBlendScalePercent(nullptr, nullptr) == 50);
  g_renderSleepMs = g_renderSleepMsSmooth = 0;

  printf("auto: blends with frames to spare raise the resolution again (low-end devices start at 60%%)\n");
  Java_nl_neerdael_projectm_core_ProjectMJNI_setTransitionMode(nullptr, nullptr, 0, true);
  g_renderSleepMs = g_renderSleepMsSmooth = 2;
  settle(1500);
  transitions = startBlend();
  CHECK(g_windowW == 768);
  finishTransition(transitions);
  for (int i = 0; i < 2; ++i) { settle(1500); finishTransition(startBlend()); }
  CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_getBlendScalePercent(nullptr, nullptr) == 75);
  CHECK(!Java_nl_neerdael_projectm_core_ProjectMJNI_isLightweightTransition(nullptr, nullptr));
  CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_getLastTransitionFps(nullptr, nullptr) > 0.f);
  g_renderSleepMs = g_renderSleepMsSmooth = 0;

  // A wall-clock busy spin cannot guarantee CPU share when the host thread is descheduled.
  // Feed measured wall/CPU samples to the real policy instead; render routing is covered above.
  {
    const double loadStart = g_engine.lastLoadStart, loadEnd = g_engine.lastLoadEnd, loadMs = g_engine.lastLoadMs;
    const double lastFrameAt = g_engine.lastFrameAt;
    const float lastFps = g_engine.lastFps;
    const int blendLevel = g_engine.blendLevel, fastBlends = g_engine.fastBlends;
    const bool halfRateOutgoing = g_engine.halfRateOutgoing;
    bool tooSlow[kBlendLevels];
    std::copy(std::begin(g_engine.blendLevelTooSlow), std::end(g_engine.blendLevelTooSlow), tooSlow);
    const int scalePercent = g_published.blendScalePercent.load(), counter = g_published.transitionCounter.load();
    const float transitionFps = g_published.lastTransitionFps.load();
    const uint32_t outgoingDivisor = g_outgoingDivisor;

    auto sampledBlend = [&](double frameCpuSeconds, bool cpuBound) {
      constexpr double start = 100.0, frameSeconds = 0.016;
      g_engine.lastLoadStart = g_engine.lastLoadEnd = start;
      g_engine.lastLoadMs = 0;
      g_engine.lastFps = 250.f;
      g_engine.lastFrameAt = start;
      g_engine.blendLevel = kDefaultBlendLevel;
      g_engine.fastBlends = 0;
      g_engine.halfRateOutgoing = false;
      std::fill(std::begin(g_engine.blendLevelTooSlow), std::end(g_engine.blendLevelTooSlow), false);
      projectm_opengl_set_outgoing_preset_frame_divisor(g_engine.pm, 1);
      BeginTransition(1.0, false);
      g_engine.transitionScaled = true;
      g_engine.transitionScale = kBlendScales[g_engine.blendLevel];
      const int before = g_published.transitionCounter.load();
      // Include all 63 frames through 1.008 s, rather than jumping past the end without CPU samples.
      for (int sample = 1; sample <= 63; ++sample) {
        TrackTransition(start + sample * frameSeconds, frameCpuSeconds);
        ApplyRenderScale(g_engine.transitionScale);
        if (sample == 40) {  // 0.640 s: after early adaptation, still inside the one-second blend
          CHECK(g_engine.inTransition);
          CHECK(g_windowW == (cpuBound ? 960u : 768u));
          CHECK(g_windowH == (cpuBound ? 540u : 432u));
          CHECK(g_engine.transitionStepped == !cpuBound);
          CHECK(g_outgoingDivisor == (cpuBound ? 2u : 1u));
        }
      }
      CHECK(!g_engine.inTransition && g_engine.transitionFrames == 63);
      CHECK(g_published.transitionCounter.load() == before + 1);
      CHECK(g_engine.transitionStepped == !cpuBound);
      CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_getBlendScalePercent(nullptr, nullptr) == (cpuBound ? 100 : 60));
    };

    printf("auto: sampled CPU-bound blend keeps its resolution and halves outgoing frames\n");
    sampledBlend(0.015, true);
    printf("auto: equally slow sampled low-CPU blend lowers resolution instead\n");
    sampledBlend(0.0001, false);

    // Return to real timestamps and full-size routing before subsequent render/detector tests.
    g_engine.detector.Disarm();
    g_engine.lastLoadStart = loadStart; g_engine.lastLoadEnd = loadEnd; g_engine.lastLoadMs = loadMs;
    g_engine.lastFrameAt = lastFrameAt; g_engine.lastFps = lastFps;
    g_engine.transitionStart = g_engine.transitionLoadEnd = g_engine.transitionEnd = 0;
    g_engine.transitionCpuSeconds = g_engine.transitionWorstMs = 0;
    g_engine.transitionFrames = g_engine.transitionSlowFrames = 0;
    g_engine.transitionScaled = g_engine.transitionStepped = false;
    g_engine.transitionScale = 1.f; g_engine.scaledUntil = 0;
    g_engine.blendLevel = blendLevel; g_engine.fastBlends = fastBlends;
    g_engine.halfRateOutgoing = halfRateOutgoing;
    std::copy(std::begin(tooSlow), std::end(tooSlow), g_engine.blendLevelTooSlow);
    g_published.blendScalePercent = scalePercent; g_published.transitionCounter = counter;
    g_published.lastTransitionFps = transitionFps;
    projectm_opengl_set_outgoing_preset_frame_divisor(g_engine.pm, outgoingDivisor);
    ApplyRenderScale(1.f);
    CHECK(g_windowW == 1280 && g_windowH == 720);
  }

  printf("the next preset's shaders are compiled in the background\n");
  CHECK(g_prewarmStarts >= 1 && g_prewarmReader("good 1.milk").texturePaths == std::vector<std::string>({texdir}));
  CHECK(!g_prewarmRequests.empty() && g_prewarmRequests.back() == g_library.PeekNext());

  printf("random and previous presets are prepared too: Right picks the prepared random preset\n");
  // The skip list was reset above, and the random pick is seeded per run: it can be a broken
  // preset, which Right skips on the way to another one (tested at the start). Skip them first and
  // switch once, so the prepared random preset is one that loads.
  g_library.MarkSkipped("broken1.milk", "test"); g_library.MarkSkipped("broken2.milk", "test");
  Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
  { std::vector<std::string> list = g_prewarmLists.back();
    CHECK(list.size() == 3 && list[1] == g_library.PeekRandom() && list[2] == g_library.PeekPrevious());
    std::string before = current(), prepared = list[1];
    Java_nl_neerdael_projectm_core_ProjectMJNI_randomPreset(nullptr, nullptr, true); switchFrame();
    CHECK(current() == prepared && current() != before);
    CHECK(g_library.PeekPrevious() == before);  // Left would go back to it: prepared as well
    CHECK(g_prewarmLists.back()[1] == g_library.PeekRandom() && g_prewarmLists.back()[1] != prepared); }

  printf("troubleshooting switches: Background compile and Shader binary cache, with the trail file\n");
  {
    char path[] = "/tmp/projectm-trail-XXXXXX";
    int created = mkstemp(path);
    CHECK(created >= 0);
    close(created);
    projectmtv::OpenTrail(path, "abc123");
    auto trail = [&path]() { std::ifstream in(path); std::stringstream text; text << in.rdbuf(); return text.str(); };
    const std::string pid = "pid=" + std::to_string(getpid()) + " ";
    int stops = g_prewarmStops, starts = g_prewarmStarts;
    Java_nl_neerdael_projectm_core_ProjectMJNI_setBackgroundCompile(nullptr, nullptr, false);
    Java_nl_neerdael_projectm_core_ProjectMJNI_setShaderBinaryCache(nullptr, nullptr, false);
    CHECK(g_programCacheEnabled);  // never applied on the calling (UI) thread
    frame();
    CHECK(!g_programCacheEnabled);
    CHECK(g_prewarmStops == stops + 1 && !g_engine.prewarmerStarted && g_prewarmStarts == starts);
    size_t requests = g_prewarmLists.size();
    Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
    CHECK(g_prewarmLists.size() == requests);  // nothing is prepared while it is off
    std::string text = trail();
    printf("%s", text.c_str());
    CHECK(text.size() == 2 * projectmtv::kTrailLineBytes);  // two fixed-size lines
    CHECK(text.rfind("render " + pid, 0) == 0);
    CHECK(text.find(" session=abc123 cache=") != std::string::npos);
    CHECK(text.find("loaded '" + current() + "' (cut) in ") != std::string::npos);
    CHECK(text.find("prewarm " + pid) == projectmtv::kTrailLineBytes);
    CHECK(text.find("background compile off") != std::string::npos);
    // Every line carries the switch states of this process.
    CHECK(text.find("render " + pid) == 0 && text.find(" cache=off compile=off loaded '") != std::string::npos);
    CHECK(text.find(" cache=off compile=off background compile off") != std::string::npos);
    Java_nl_neerdael_projectm_core_ProjectMJNI_setBackgroundCompile(nullptr, nullptr, true);
    Java_nl_neerdael_projectm_core_ProjectMJNI_setShaderBinaryCache(nullptr, nullptr, true);
    frame();
    CHECK(g_programCacheEnabled);
    CHECK(g_prewarmStarts == starts + 1 && g_engine.prewarmerStarted);
    CHECK(g_prewarmLists.size() == requests + 1);  // prepares the upcoming presets right away
    text = trail();  // the render thread records the change on its next frame, with the new states
    CHECK(text.substr(0, projectmtv::kTrailLineBytes).find(
              " cache=on compile=on troubleshooting switches changed while showing '" + current() + "'") != std::string::npos);
    // A long preset name is cut to the line, which stays fixed-size and newline-terminated.
    projectmtv::WriteTrail(projectmtv::kTrailRender, "loading '%s'", std::string(1000, 'x').c_str());
    text = trail();
    CHECK(text.size() == 2 * projectmtv::kTrailLineBytes && text[projectmtv::kTrailLineBytes - 1] == '\n');
    close(projectmtv::TrailFd().exchange(-1));
    unlink(path);
  }

  printf("output measurements: flat and still are logged, never skipped\n");
  {
    auto outputLine = [](const std::string& preset) {
      for (auto it = g_logLines.rbegin(); it != g_logLines.rend(); ++it)
        if (it->rfind("OUTPUT preset='" + preset + "'", 0) == 0) return *it;
      return std::string(); };
    g_pixel = 230; g_noise = 3;  // near-white with faint, unchanging texture
    Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
    std::string white = current();
    int skipped = g_library.SkippedCount();  // after the switch: it may skip a broken preset on the way
    for (int i = 0; i < 400; ++i) { feedAudio(60); frame(); std::this_thread::sleep_for(std::chrono::milliseconds(20)); }
    CHECK(current() == white && g_library.SkippedCount() == skipped);
    g_pixel = 60; g_noise = 120;  // varied picture (luma range > 12) that does not move
    Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
    std::string frozen = current();
    skipped = g_library.SkippedCount();
    std::string whiteLine = outputLine(white);
    printf("    %s\n", whiteLine.c_str());
    CHECK(whiteLine.find("flat=") != std::string::npos && whiteLine.find("flat=0/") == std::string::npos);
    CHECK(whiteLine.find("skipped=no") != std::string::npos);
    for (int i = 0; i < 400; ++i) { feedAudio(60); frame(); std::this_thread::sleep_for(std::chrono::milliseconds(20)); }
    CHECK(current() == frozen && g_library.SkippedCount() == skipped);
    g_noise = 0; g_pixel = 200;
    Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
    std::string frozenLine = outputLine(frozen);
    printf("    %s\n", frozenLine.c_str());
    CHECK(frozenLine.find("flat=0/") != std::string::npos && frozenLine.find("still=0/") == std::string::npos);
    CHECK(frozenLine.find("change_pct_avg=0.0") != std::string::npos);
  }

  printf("LOAD lines carry size, weight, shader size/loops and the memory taken\n");
  {
    Java_nl_neerdael_projectm_core_ProjectMJNI_nextPreset(nullptr, nullptr, true); switchFrame();
    std::string load;
    for (auto it = g_logLines.rbegin(); it != g_logLines.rend() && load.empty(); ++it)
      if (it->rfind("LOAD preset=", 0) == 0) load = *it;
    printf("    %s\n", load.c_str());
    CHECK(load.find(" size=1280x720 weight_mb=") != std::string::npos);
    CHECK(load.find(" shader_kb=") != std::string::npos && load.find(" loops=") != std::string::npos);
    CHECK(load.find(" avail_drop_mb=") != std::string::npos && load.find(" rss_growth_mb=") != std::string::npos);
    size_t bytes = 0; int loops = 0;
    ShaderStats("warp_1=`for (int i=0;i<3;i++) x+=1; // for(\ncomp_1=`y = tex2D(a,b); for(;;){}\nper_frame_1=for(\n",
                bytes, loops);
    CHECK(loops == 2 && bytes > 40 && bytes < 90);  // comments and non-shader lines ignored
    ShaderStats("warp_1=/*\r\nwarp_2=for(;;) {}\r\nwarp_3=*/\r\n", bytes, loops);
    CHECK(loops == 0 && bytes == 0);  // a loop inside a block comment spanning lines
    ShaderStats("warp_1=`a;\r\nwarpx=for(\ncomp_2=`for\ncomp_3=(;;)\n", bytes, loops);
    CHECK(loops == 1 && bytes == std::string("a;\nfor\n(;;)").size());  // same rules as gen-preset-index.py
  }

  printf("audio level getter\n");
  feedAudio(60);
  CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_getAudioLevel(nullptr, nullptr) > 0.4f);
  g_inputs.audioLevelTime = NowSeconds() - 5;
  CHECK(Java_nl_neerdael_projectm_core_ProjectMJNI_getAudioLevel(nullptr, nullptr) == 0.f);
  CHECK(g_loadsAfterDirectFrame == 0);  // every switch started from a stored frame
  checkManagedToLegacyRendererHandoff();
  printf("ALL TESTS PASSED\n");
  return 0;
}
