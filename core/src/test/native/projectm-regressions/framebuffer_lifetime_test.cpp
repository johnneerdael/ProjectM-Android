// Real GLAD hooks observe engine operations, not a simulated PowerVR crash. The
// driver invariant comes from Chromium/Skia's Imagination deletion workaround.
#include "gl_context.hpp"
#include <ProjectM.hpp>
#include <Renderer/FramebufferDeletion.hpp>
#include <Renderer/Texture.hpp>
#include <projectM-4/render_opengl.h>

#include <algorithm>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace {
void Require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
struct Binding {
    GLuint current{};
    GLuint previous{~0u};
    GLuint previousComplete{~0u};
    void Bind(GLuint id, bool wasComplete) {
        if (current == id) return; // Redundant binds need not update driver history.
        previous = current;
        if (wasComplete) previousComplete = current;
        current = id;
    }
    bool References(GLuint id) const {
        return current == id || previous == id || previousComplete == id;
    }
    void Forget(GLuint id) {
        if (current == id) current = 0;
        if (previous == id) previous = ~0u;
        if (previousComplete == id) previousComplete = ~0u;
    }
};
Binding readBinding, drawBinding;
PFNGLBINDFRAMEBUFFERPROC realBind;
PFNGLDELETEFRAMEBUFFERSPROC realDelete;
PFNGLGENFRAMEBUFFERSPROC realGen;
PFNGLGENRENDERBUFFERSPROC realGenRenderbuffers;
PFNGLGETSTRINGPROC realGetString;
PFNGLDELETETEXTURESPROC realDeleteTextures;
int textureDeletes{};
int unsafeDeletes{}, deleted{}, binds{}, renderbufferGenerations{}, vendorQueries{};
bool powerVR{}, enforce{};
GLuint observedGuard{};
std::map<GLuint, bool> liveFramebuffers;
const char* phase = "initialization";

void GLAD_API_PTR Bind(GLenum target, GLuint id) {
    const bool readComplete = readBinding.current &&
        glCheckFramebufferStatus(GL_READ_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE;
    const bool drawComplete = drawBinding.current &&
        glCheckFramebufferStatus(GL_DRAW_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE;
    realBind(target, id);
    ++binds;
    if (target == GL_FRAMEBUFFER || target == GL_READ_FRAMEBUFFER) readBinding.Bind(id, readComplete);
    if (target == GL_FRAMEBUFFER || target == GL_DRAW_FRAMEBUFFER) drawBinding.Bind(id, drawComplete);
}
void GLAD_API_PTR DeleteTextures(GLsizei count, const GLuint* ids) {
    textureDeletes += count;
    realDeleteTextures(count, ids);
}
void GLAD_API_PTR Gen(GLsizei count, GLuint* ids) {
    realGen(count, ids);
    for (GLsizei i = 0; i < count; ++i) liveFramebuffers[ids[i]] = true;
}
void GLAD_API_PTR GenRenderbuffers(GLsizei count, GLuint* ids) {
    realGenRenderbuffers(count, ids);
    renderbufferGenerations += count;
}
void GLAD_API_PTR Delete(GLsizei count, const GLuint* ids) {
    GLint read{}, draw{};
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &read);
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &draw);
    Require(readBinding.current == static_cast<GLuint>(read) &&
            drawBinding.current == static_cast<GLuint>(draw), "watcher missed a framebuffer binding");
    for (GLsizei i = 0; i < count; ++i) {
        if (!ids[i]) continue;
        ++deleted;
        if (readBinding.References(ids[i]) || drawBinding.References(ids[i])) {
            if (++unsafeDeletes <= 3)
                std::cerr << phase << ": unsafe deletion FBO=" << ids[i] << '\n';
        }
        if (enforce) {
            const auto guard = readBinding.previousComplete;
            Require(guard && guard != ~0u && guard == drawBinding.previousComplete,
                    "deletion did not replace both previous complete bindings with one guard");
            Require(liveFramebuffers.count(guard) && guard != ids[i], "guard was deleted or absent");
            Require(!observedGuard || guard == observedGuard, "guard changed within one context");
            observedGuard = guard;
        }
        liveFramebuffers.erase(ids[i]);
    }
    realDelete(count, ids);
    for (GLsizei i = 0; i < count; ++i) { readBinding.Forget(ids[i]); drawBinding.Forget(ids[i]); }
}
const GLubyte* GLAD_API_PTR GetString(GLenum name) {
    if (name == GL_VENDOR) {
        ++vendorQueries;
        return reinterpret_cast<const GLubyte*>(powerVR ? "Imagination Technologies" : "Unrelated GPU Vendor");
    }
    if (name == GL_RENDERER)
        return reinterpret_cast<const GLubyte*>(powerVR ? "PowerVR Rogue GE9215" : "Unrelated Renderer");
    return realGetString(name);
}
struct Hooks {
    Hooks(bool enabled) {
        powerVR = enabled;
        enforce = false;
        readBinding = {}; drawBinding = {};
        unsafeDeletes = deleted = binds = renderbufferGenerations = vendorQueries = 0;
        observedGuard = 0;
        textureDeletes = 0;
        liveFramebuffers.clear();
        realBind = glad_glBindFramebuffer; glad_glBindFramebuffer = Bind;
        realDelete = glad_glDeleteFramebuffers; glad_glDeleteFramebuffers = Delete;
        realGen = glad_glGenFramebuffers; glad_glGenFramebuffers = Gen;
        realGenRenderbuffers = glad_glGenRenderbuffers; glad_glGenRenderbuffers = GenRenderbuffers;
        realGetString = glad_glGetString; glad_glGetString = GetString;
        realDeleteTextures = glad_glDeleteTextures; glad_glDeleteTextures = DeleteTextures;
    }
    ~Hooks() {
        glad_glBindFramebuffer = realBind;
        glad_glDeleteFramebuffers = realDelete;
        glad_glGenFramebuffers = realGen;
        glad_glGenRenderbuffers = realGenRenderbuffers;
        glad_glGetString = realGetString;
        glad_glDeleteTextures = realDeleteTextures;
    }
};
struct Target {
    GLuint framebuffer{}, texture{};
    Target() {
        glGenFramebuffers(1, &framebuffer);
        glGenTextures(1, &texture);
        glBindTexture(GL_TEXTURE_2D, texture);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 64, 32, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
        Require(glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE, "test target incomplete");
    }
    ~Target() {
        projectm_opengl_delete_framebuffers(1, &framebuffer);
        glDeleteTextures(1, &texture);
    }
};
void Load(libprojectM::ProjectM& engine, bool smooth) {
    std::istringstream source("[preset00]\nfDecay=0\nfWaveAlpha=0\nfGammaAdj=1\n"
                              "ob_size=0.5\nob_r=0.2\nob_g=0.4\nob_b=0.8\nob_a=1\n");
    engine.LoadPresetData(source, smooth);
}
void CheckInitializationState() {
    GLContext context;
    Hooks hooks(true);
    projectm_opengl_forget_framebuffer_guard();
    Target read, draw;
    GLuint storage{}, unpack{};
    glGenRenderbuffers(1, &storage);
    glBindRenderbuffer(GL_RENDERBUFFER, storage);
    glGenBuffers(1, &unpack);
    glBindBuffer(GL_PIXEL_UNPACK_BUFFER, unpack);
    glActiveTexture(GL_TEXTURE3);
    glBindTexture(GL_TEXTURE_2D, read.texture);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, read.framebuffer);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, draw.framebuffer);
    const GLenum fields[] = {GL_READ_FRAMEBUFFER_BINDING, GL_DRAW_FRAMEBUFFER_BINDING,
                             GL_RENDERBUFFER_BINDING, GL_ACTIVE_TEXTURE,
                             GL_TEXTURE_BINDING_2D, GL_PIXEL_UNPACK_BUFFER_BINDING};
    GLint before[6]{}, after[6]{};
    for (int i = 0; i < 6; ++i) glGetIntegerv(fields[i], &before[i]);
    libprojectM::Renderer::InitializeFramebufferDeletion();
    for (int i = 0; i < 6; ++i) glGetIntegerv(fields[i], &after[i]);
    Require(std::equal(before, before + 6, after), "guard initialization changed caller GL state");
    Require(renderbufferGenerations == 2, "initialization did not allocate one guard renderbuffer");
    enforce = true;
    glDeleteRenderbuffers(1, &storage);
    glDeleteBuffers(1, &unpack);
    glActiveTexture(GL_TEXTURE0);
    Require(glGetError() == GL_NO_ERROR, "guard initialization generated a GL error");
}
std::vector<unsigned char> Exercise(bool enabled, bool legacyReset = false) {
    GLContext context;
    Hooks hooks(enabled);
    // Context replacement must forget stale names without issuing any GL calls.
    if (legacyReset) Require(projectm_opengl_texture_pool_bytes() > 0, "legacy reset lacked stale pooled textures");
    const int calls = binds + deleted + vendorQueries + renderbufferGenerations + textureDeletes;
    if (legacyReset) projectm_opengl_forget_texture_pool();
    else projectm_opengl_forget_framebuffer_guard();
    Require(calls == binds + deleted + vendorQueries + renderbufferGenerations + textureDeletes,
            "context-loss forget issued GL calls");
    if (legacyReset) Require(projectm_opengl_texture_pool_bytes() == 0, "legacy reset retained stale textures");
    // Stale instance destruction can happen before replacement initialization.
    GLuint stale{};
    glGenFramebuffers(1, &stale);
    const int beforeDelete = binds;
    projectm_opengl_delete_framebuffers(1, &stale);
    Require(binds == beforeDelete && renderbufferGenerations == 0,
            "post-forget deletion initialized a guard in the replacement context");
    std::vector<unsigned char> pixels;
    {
        // Two host FBOs exercise split read/draw preservation and deletion of a
        // bound name. They also stand in for JNI's scaled/snapshot targets.
        Target output, readTarget;
        for (int instance = 0; instance < 2; ++instance) {
            phase = "engine initialization";
            libprojectM::ProjectM engine;
            enforce = enabled;
            Require(renderbufferGenerations == (enabled ? 1 : 0),
                    "guard allocated per instance or on an unaffected vendor");
            glBindFramebuffer(GL_READ_FRAMEBUFFER, readTarget.framebuffer);
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER, output.framebuffer);
            GLuint unrelated{};
            glGenFramebuffers(1, &unrelated);
            const int savedBinds = binds;
            projectm_opengl_delete_framebuffers(1, &unrelated);
            Require(readBinding.current == readTarget.framebuffer && drawBinding.current == output.framebuffer,
                    "deletion changed surviving split bindings");
            Require(enabled || savedBinds == binds, "unaffected vendor performed workaround binds");
            engine.SetWindowSize(32, 32);
            engine.SetSoftCutDuration(0);
            engine.SetPresetLocked(true);
            engine.SetHardCutEnabled(false);
            Load(engine, false);
            engine.SetFrameTime(0);
            engine.RenderFrame(output.framebuffer);
            phase = "preset switch";
            for (int i = 0; i < 12; ++i) {
                Load(engine, (i % 2) != 0);
                engine.SetFrameTime((i + 1) / 30.0);
                engine.RenderFrame(output.framebuffer);
            }
            phase = "resize";
            engine.SetWindowSize(64, 32);
            engine.RenderFrame(output.framebuffer);
            if (!instance) {
                glBindFramebuffer(GL_READ_FRAMEBUFFER, output.framebuffer);
                glReadBuffer(GL_COLOR_ATTACHMENT0);
                pixels.resize(64 * 32 * 4);
                glReadPixels(0, 0, 64, 32, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
            }
            phase = "engine retirement";
        }
        // Deletion must emulate GL's unbind-to-zero for names in the delete list.
        GLuint victim{};
        glGenFramebuffers(1, &victim);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, readTarget.framebuffer);
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, victim);
        projectm_opengl_delete_framebuffers(1, &victim);
        Require(readBinding.current == readTarget.framebuffer && drawBinding.current == 0,
                "deleting a bound name did not preserve the other target");
        Require(glGetError() == GL_NO_ERROR, "framebuffer exercise generated a GL error");
    }
    Require(deleted > 100, "engine switch/resize/retirement deletion paths were not exercised");
    if (enabled) {
        Require(unsafeDeletes == 0, "PowerVR current/previous framebuffer deletion invariant violated");
        Require(observedGuard && liveFramebuffers.size() == 1 && liveFramebuffers.count(observedGuard),
                "context retained more than one framebuffer guard");
    } else {
        Require(unsafeDeletes > 0, "off-vendor witness did not detect unguarded deletion paths");
        Require(liveFramebuffers.empty(), "off-vendor path retained a guard");
    }
    std::cout << (enabled ? "PowerVR" : "unaffected vendor") << ": " << deleted << " deletions, "
              << unsafeDeletes << " unsafe, " << renderbufferGenerations << " guards\n";
    if (enabled && !legacyReset) {
        // Leave a real pooled texture behind in the old context. The existing
        // context-loss hook must drop its name without deleting it in the next.
        projectm_opengl_set_texture_pool_limit(4096);
        {
            libprojectM::Renderer::Texture pooled("reset-control", GL_TEXTURE_2D, 4, 4, 1,
                                                  GL_RGBA8, GL_RGBA, GL_UNSIGNED_BYTE, false);
            pooled.SetPoolable(GL_RGBA8, GL_RGBA, GL_UNSIGNED_BYTE);
        }
        Require(projectm_opengl_texture_pool_bytes() > 0, "could not seed context-loss pool control");
    } else if (legacyReset) {
        projectm_opengl_set_texture_pool_limit(0);
    }
    return pixels;
}
}
int main() {
    try {
        CheckInitializationState();
        const auto baseline = Exercise(false);
        const auto guarded = Exercise(true);
        Require(baseline == guarded, "workaround changed rendered output");
        bool colored = false;
        for (size_t i = 0; i < guarded.size(); i += 4)
            colored |= guarded[i] || guarded[i + 1] || guarded[i + 2];
        Require(colored, "output equivalence control was blank");
        // Another real context on the same thread must build exactly one fresh guard.
        Require(Exercise(true, true) == guarded, "legacy context-loss hook did not reset guard safely");
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "framebuffer-lifetime-regressions: " << error.what() << '\n';
        return 1;
    }
}
