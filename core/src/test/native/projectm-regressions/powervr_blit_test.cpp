#include "gl_context.hpp"
#include <Renderer/Framebuffer.hpp>
#include <Renderer/FramebufferDeletion.hpp>
#include <Renderer/Shader.hpp>
#include <MilkdropPreset/FeedbackDetail.hpp>
#include <projectM-4/projectM.h>
#include <projectM-4/render_opengl.h>

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <vector>

#define STB_IMAGE_WRITE_STATIC
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include <stb_image/stb_image_write.h>

namespace {
void Require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
bool powerVR{};
int blits{}, programs{}, unrelatedDetachments{};
PFNGLGETSTRINGPROC realGetString;
PFNGLBLITFRAMEBUFFERPROC realBlit;
PFNGLCREATEPROGRAMPROC realCreateProgram;
PFNGLDELETETEXTURESPROC realDeleteTextures;
GLuint GLAD_API_PTR CreateProgram() { ++programs; return realCreateProgram(); }
void GLAD_API_PTR DeleteTextures(GLsizei count, const GLuint* ids) {
    GLint draw{}, before{}, after{};
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &draw);
    if (draw) glGetFramebufferAttachmentParameteriv(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME, &before);
    realDeleteTextures(count, ids);
    if (draw) glGetFramebufferAttachmentParameteriv(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME, &after);
    if (before && before != after && std::find(ids, ids + count, static_cast<GLuint>(before)) == ids + count)
        ++unrelatedDetachments;
}
const GLubyte* GLAD_API_PTR GetString(GLenum name) {
    if (name == GL_VENDOR) return reinterpret_cast<const GLubyte*>(powerVR ? "Imagination Technologies" : "Other vendor");
    if (name == GL_RENDERER) return reinterpret_cast<const GLubyte*>(powerVR ? "PowerVR Rogue GE9215" : "Other renderer");
    return realGetString(name);
}
void GLAD_API_PTR Blit(GLint a, GLint b, GLint c, GLint d, GLint e, GLint f, GLint g, GLint h,
                        GLbitfield mask, GLenum filter) {
    ++blits;
    realBlit(a, b, c, d, e, f, g, h, mask, filter);
}
struct Hooks {
    Hooks() {
        realGetString = glad_glGetString;
        realBlit = glad_glBlitFramebuffer;
        realCreateProgram = glad_glCreateProgram;
        realDeleteTextures = glad_glDeleteTextures;
        glad_glGetString = GetString;
        glad_glBlitFramebuffer = Blit;
        glad_glCreateProgram = CreateProgram;
        glad_glDeleteTextures = DeleteTextures;
    }
    ~Hooks() {
        glad_glGetString = realGetString;
        glad_glBlitFramebuffer = realBlit;
        glad_glCreateProgram = realCreateProgram;
        glad_glDeleteTextures = realDeleteTextures;
    }
};
std::vector<unsigned char> Resize(bool usePowerVR, int sourceWidth = 7, int sourceHeight = 5,
                                  int targetWidth = 13, int targetHeight = 11) {
    powerVR = usePowerVR;
    blits = 0;
    libprojectM::Renderer::ForgetFramebufferDeletion();
    libprojectM::Renderer::InitializeFramebufferDeletion();
    libprojectM::Renderer::Framebuffer framebuffer;
    framebuffer.CreateColorAttachment(0, 0);
    framebuffer.SetSize(sourceWidth, sourceHeight);
    std::vector<unsigned char> original(sourceWidth * sourceHeight * 4);
    for (size_t i = 0; i < original.size(); ++i) original[i] = static_cast<unsigned char>((i * 71 + i / 9) % 256);
    glBindTexture(GL_TEXTURE_2D, framebuffer.GetColorAttachmentTexture(0, 0)->TextureID());
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, sourceWidth, sourceHeight, GL_RGBA, GL_UNSIGNED_BYTE, original.data());
    glBindTexture(GL_TEXTURE_2D, 0);
    framebuffer.SetSize(targetWidth, targetHeight);
    GLint red{}, alpha{}, object{}, kind{};
    framebuffer.BindDraw(0);
    glGetFramebufferAttachmentParameteriv(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME, &object);
    glGetFramebufferAttachmentParameteriv(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE, &kind);
    glGetFramebufferAttachmentParameteriv(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_FRAMEBUFFER_ATTACHMENT_RED_SIZE, &red);
    glGetFramebufferAttachmentParameteriv(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_FRAMEBUFFER_ATTACHMENT_ALPHA_SIZE, &alpha);
    Require(object == static_cast<GLint>(framebuffer.GetColorAttachmentTexture(0, 0)->TextureID()) &&
            kind == GL_TEXTURE && red == 8 && alpha == 8 &&
            glCheckFramebufferStatus(GL_DRAW_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE,
            "resize lost or changed the destination colour attachment");
    framebuffer.BindRead(0);
    glReadBuffer(GL_COLOR_ATTACHMENT0);
    std::vector<unsigned char> result(targetWidth * targetHeight * 4);
    glReadPixels(0, 0, targetWidth, targetHeight, GL_RGBA, GL_UNSIGNED_BYTE, result.data());
    Require(glGetError() == GL_NO_ERROR, "resize generated a GL error");
    if (usePowerVR) Require(blits == 0, "PowerVR resize still calls glBlitFramebuffer");
    else Require(blits > 0, "ordinary GPU no longer uses the existing blit path");
    if (usePowerVR) {
        const int cachedPrograms = programs;
        framebuffer.SetSize(9, 7);
        Require(programs == cachedPrograms && blits == 0, "resize recompiles the copy shader or reintroduces a blit");
    }
    return result;
}

std::vector<unsigned char> Pattern(int width, int height) {
    std::vector<unsigned char> pixels(width * height * 4);
    for (size_t i = 0; i < pixels.size(); ++i) pixels[i] = static_cast<unsigned char>((i * 71 + i / 9) % 256);
    return pixels;
}
void Upload(GLuint texture, int width, int height, const std::vector<unsigned char>& pixels) {
    glBindTexture(GL_TEXTURE_2D, texture);
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
    glBindTexture(GL_TEXTURE_2D, 0);
}
std::vector<unsigned char> Read(libprojectM::Renderer::Framebuffer& target, int width, int height) {
    target.BindRead(0);
    glReadBuffer(GL_COLOR_ATTACHMENT0);
    std::vector<unsigned char> pixels(width * height * 4);
    glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
    return pixels;
}
void MixedResize(bool usePowerVR) {
    powerVR = usePowerVR;
    libprojectM::Renderer::ForgetFramebufferDeletion();
    libprojectM::Renderer::InitializeFramebufferDeletion();
    libprojectM::Renderer::Framebuffer target;
    target.CreateColorAttachment(0, 0);
    target.CreateColorAttachment(0, 1, GL_RG16UI, GL_RG_INTEGER, GL_UNSIGNED_SHORT);
    target.SetSize(4, 3);
    std::vector<unsigned char> solid(4 * 3 * 4, 127);
    Upload(target.GetColorAttachmentTexture(0, 0)->TextureID(), 4, 3, solid);
    target.SetSize(12, 9);
    const auto pixels = Read(target, 12, 9);
    Require(std::all_of(pixels.begin(), pixels.end(), [](unsigned char x) { return x == 127; }),
            "mixed-attachment growth clipped or corrupted the primary image");
    target.BindDraw(0);
    GLint route{};
    glGetIntegerv(GL_DRAW_BUFFER1, &route);
    Require(route == GL_COLOR_ATTACHMENT1, "resize did not restore auxiliary draw routing");
    glReadBuffer(GL_COLOR_ATTACHMENT1);
    std::vector<GLuint> auxiliary(12 * 9 * 4, 99);
    glReadPixels(0, 0, 12, 9, GL_RGBA_INTEGER, GL_UNSIGNED_INT, auxiliary.data());
    Require(glGetError() == GL_NO_ERROR, "integer-attachment readback generated a GL error");
    for (size_t i = 0; i < auxiliary.size(); i += 4)
        Require(auxiliary[i] == 0 && auxiliary[i + 1] == 0,
                "primary colour copy wrote into the integer UV attachment");
}

void HostCopyState() {
    powerVR = true;
    libprojectM::Renderer::ForgetFramebufferDeletion();
    projectm_handle instance = projectm_create();
    Require(instance && projectm_opengl_needs_framebuffer_copy_workaround(), "PowerVR host capability missing");
    libprojectM::Renderer::Framebuffer source, output;
    source.CreateColorAttachment(0, 0); source.SetSize(7, 5);
    output.CreateColorAttachment(0, 0);
    output.CreateColorAttachment(0, 1, GL_RG16UI, GL_RG_INTEGER, GL_UNSIGNED_SHORT);
    output.SetSize(7, 5);
    const auto original = Pattern(7, 5);
    Upload(source.GetColorAttachmentTexture(0, 0)->TextureID(), 7, 5, original);
    output.Bind(0);
    GLint drawFramebuffer{};
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &drawFramebuffer);
    libprojectM::Renderer::Shader caller;
#ifdef USE_GLES
    const std::string version = "#version 300 es\n";
#else
    const std::string version = "#version 330\n";
#endif
    caller.CompileProgram(version + "void main(){gl_Position=vec4(0.0,0.0,0.0,1.0);}",
                          version + "precision highp float;out vec4 color;void main(){color=vec4(1.0);}");
    caller.Bind();
    GLint callerProgram{};
    glGetIntegerv(GL_CURRENT_PROGRAM, &callerProgram);
    GLuint vao{}, dummyTexture{}, sampler{};
    glGenVertexArrays(1, &vao); glBindVertexArray(vao);
    glGenTextures(1, &dummyTexture);
    glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, dummyTexture);
    glGenSamplers(1, &sampler); glBindSampler(0, sampler);
    glActiveTexture(GL_TEXTURE5);
    glViewport(3, 5, 19, 17);
    const GLenum capabilities[] = {GL_BLEND, GL_DEPTH_TEST, GL_STENCIL_TEST, GL_CULL_FACE,
        GL_SCISSOR_TEST, GL_DITHER, GL_RASTERIZER_DISCARD, GL_SAMPLE_ALPHA_TO_COVERAGE, GL_SAMPLE_COVERAGE};
    for (auto capability : capabilities) glEnable(capability);
    glScissor(0, 0, 1, 1);
    glColorMask(GL_FALSE, GL_TRUE, GL_FALSE, GL_FALSE);
#ifndef USE_GLES
    glColorMaski(1, GL_FALSE, GL_FALSE, GL_TRUE, GL_FALSE);
#endif
    const int before = blits;
    projectm_opengl_copy_texture_to_framebuffer(instance, source.GetColorAttachmentTexture(0, 0)->TextureID(), 7, 5);
    Require(blits == before, "host C API copy called glBlitFramebuffer");
    GLint actual{}, viewport[4]{};
    glGetIntegerv(GL_CURRENT_PROGRAM, &actual); Require(actual == callerProgram, "caller program changed");
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &actual); Require(actual == drawFramebuffer, "draw framebuffer changed");
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &actual); Require(actual == drawFramebuffer, "read framebuffer changed");
    glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &actual); Require(actual == static_cast<GLint>(vao), "VAO changed");
    glGetIntegerv(GL_ACTIVE_TEXTURE, &actual); Require(actual == GL_TEXTURE5, "active texture changed");
    glGetIntegerv(GL_VIEWPORT, viewport);
    Require(viewport[0] == 3 && viewport[1] == 5 && viewport[2] == 19 && viewport[3] == 17, "viewport changed");
    for (auto capability : capabilities) Require(glIsEnabled(capability), "copy changed a caller enable");
    GLboolean mask[4]{};
    glGetBooleanv(GL_COLOR_WRITEMASK, mask);
    Require(!mask[0] && mask[1] && !mask[2] && !mask[3], "colour mask changed");
#ifndef USE_GLES
    glGetBooleani_v(GL_COLOR_WRITEMASK, 1, mask);
    Require(!mask[0] && !mask[1] && mask[2] && !mask[3], "auxiliary colour mask changed");
#endif
    glGetIntegerv(GL_DRAW_BUFFER1, &actual); Require(actual == GL_COLOR_ATTACHMENT1, "draw routing changed");
    glActiveTexture(GL_TEXTURE0);
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &actual); Require(actual == static_cast<GLint>(dummyTexture), "texture zero changed");
    glGetIntegerv(GL_SAMPLER_BINDING, &actual); Require(actual == static_cast<GLint>(sampler), "sampler zero changed");
    Require(Read(output, 7, 5) == original, "host copy changed image, orientation or alpha under caller state");
    Require(glGetError() == GL_NO_ERROR, "host copy generated a GL error");
    for (auto capability : capabilities) glDisable(capability);
    glEnable(GL_DITHER); glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
    glBindVertexArray(0); glDeleteVertexArrays(1, &vao);
    glBindSampler(0, 0); glDeleteSamplers(1, &sampler);
    glBindTexture(GL_TEXTURE_2D, 0); glDeleteTextures(1, &dummyTexture);
    libprojectM::Renderer::Shader::Unbind();
#ifdef USE_GLES
    // GLES has a real default pbuffer; test the host presentation destination too.
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    glReadBuffer(GL_BACK);
    projectm_opengl_copy_texture_to_framebuffer(instance, source.GetColorAttachmentTexture(0, 0)->TextureID(), 7, 5);
    glGetIntegerv(GL_DRAW_BUFFER0, &actual);
    Require(actual == GL_BACK, "default framebuffer draw routing changed");
    std::vector<unsigned char> displayed(original.size());
    glReadPixels(0, 0, 7, 5, GL_RGBA, GL_UNSIGNED_BYTE, displayed.data());
    for (size_t i = 0; i < original.size(); ++i)
        if (i % 4 != 3) Require(displayed[i] == original[i], "default presentation changed an RGB pixel");
    Require(glGetError() == GL_NO_ERROR && blits == before, "default presentation used a blit or invalid state");
#endif
    projectm_destroy(instance);
}

std::vector<unsigned char> DetailCopy(bool usePowerVR) {
    powerVR = usePowerVR;
    blits = 0;
    libprojectM::Renderer::ForgetFramebufferDeletion();
    libprojectM::Renderer::InitializeFramebufferDeletion();
    libprojectM::Renderer::Framebuffer source, output;
    source.CreateColorAttachment(0, 0); source.SetSize(16, 12);
    output.CreateColorAttachment(0, 0); output.SetSize(16, 12);
    Upload(source.GetColorAttachmentTexture(0, 0)->TextureID(), 16, 12, Pattern(16, 12));
    libprojectM::MilkdropPreset::FeedbackDetail detail(16, 12, {8, 6, 2}, true);
    detail.Initialize(source.GetColorAttachmentTexture(0, 0));
    detail.Combine(source.GetColorAttachmentTexture(0, 0), 0.5f, output, 0);
    if (usePowerVR) Require(blits == 0, "Native trails still calls glBlitFramebuffer on PowerVR");
    else Require(blits > 0, "ordinary Native trails no longer uses its blit path");
    Require(glGetError() == GL_NO_ERROR, "Native trails copy generated a GL error");
    return Read(output, 16, 12);
}

void LostContextOwnership() {
    std::unique_ptr<libprojectM::Renderer::Framebuffer> old;
    {
        GLContext oldContext;
        libprojectM::Renderer::ForgetFramebufferDeletion();
        libprojectM::Renderer::Framebuffer source;
        source.CreateColorAttachment(0, 0); source.SetSize(2, 2);
        old = std::make_unique<libprojectM::Renderer::Framebuffer>();
        old->CreateColorAttachment(0, 0); old->SetSize(2, 2);
        old->Bind(0);
        old->CopyTextureToBoundFramebuffer(source.GetColorAttachmentTexture(0, 0)->TextureID(), 2, 2, GL_NEAREST);
    }
    {
        GLContext replacement;
        // Same hook and ordering as the JNI surface-recreation path.
        libprojectM::Renderer::ForgetFramebufferDeletion();
        const GLuint program = glCreateProgram();
        GLuint vao{}, sampler{};
        glGenVertexArrays(1, &vao); glBindVertexArray(vao);
        glGenSamplers(1, &sampler);
        old.reset();
        Require(glIsProgram(program), "stale copy owner deleted a replacement-context program");
        Require(glIsVertexArray(vao), "stale copy owner deleted a replacement-context VAO");
        Require(glIsSampler(sampler), "stale copy owner deleted a replacement-context sampler");
        glDeleteProgram(program);
        glBindVertexArray(0); glDeleteVertexArrays(1, &vao);
        glDeleteSamplers(1, &sampler);
        Require(glGetError() == GL_NO_ERROR, "stale copy cleanup issued invalid GL calls");
    }
}
}

int main(int argc, char** argv) {
    try {
        GLContext context;
        std::cout << "GL " << glGetString(GL_VERSION) << "; renderer " << glGetString(GL_RENDERER) << '\n';
        Hooks hooks;
        const auto ordinary = Resize(false);
        const auto compatible = Resize(true);
        int largestDifference = 0;
        for (size_t i = 0; i < ordinary.size(); ++i)
            largestDifference = std::max(largestDifference, std::abs(int(ordinary[i]) - int(compatible[i])));
        if (largestDifference > 1) {
            int shown = 0;
            for (size_t i = 0; i < ordinary.size() && shown < 12; ++i) {
                if (std::abs(int(ordinary[i]) - int(compatible[i])) <= 1) continue;
                std::cerr << "copy mismatch byte " << i << " blit=" << int(ordinary[i])
                          << " draw=" << int(compatible[i]) << '\n';
                ++shown;
            }
            std::cerr << "largest copy difference " << largestDifference << '\n';
        }
        Require(largestDifference <= 1, "PowerVR copy changed scaling, orientation, colour or alpha");
        {
            const auto ordinary4k = Resize(false, 31, 17, 3840, 2160);
            const auto compatible4k = Resize(true, 31, 17, 3840, 2160);
            for (size_t i = 0; i < ordinary4k.size(); ++i)
                largestDifference = std::max(largestDifference, std::abs(int(ordinary4k[i]) - int(compatible4k[i])));
            Require(largestDifference <= 1, "PowerVR 4K scaling exceeds one channel step");
        }
        MixedResize(false);
        MixedResize(true);
        HostCopyState();
        const auto ordinaryDetail = DetailCopy(false);
        const auto compatibleDetail = DetailCopy(true);
        Require(ordinaryDetail == compatibleDetail, "Native trails copy changed its pixels");
        if (argc > 1) {
            const auto reference = Resize(false, 31, 17, 512, 288);
            const auto draw = Resize(true, 31, 17, 512, 288);
            int proofDifference = 0;
            for (size_t i = 0; i < reference.size(); ++i)
                proofDifference = std::max(proofDifference, std::abs(int(reference[i]) - int(draw[i])));
            Require(proofDifference <= 1, "proof captures exceed the copy precision bound");
            stbi_flip_vertically_on_write(1);
            Require(stbi_write_png((std::string(argv[1]) + "/reference-blit.png").c_str(), 512, 288, 4, reference.data(), 512 * 4), "could not write reference capture");
            Require(stbi_write_png((std::string(argv[1]) + "/powervr-draw.png").c_str(), 512, 288, 4, draw.data(), 512 * 4), "could not write draw capture");
            std::cout << "512x288 RGBA proof maximum channel difference " << proofDifference << '\n';
        }
        Require(unrelatedDetachments == 0, "deleting a copy source detached an unrelated draw image");
        LostContextOwnership();
        libprojectM::Renderer::ForgetFramebufferDeletion();
        std::cout << "PowerVR resize/MRT/host-state/trails/context controls pass; maximum channel difference "
                  << largestDifference << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
