// Exercise the real JNI render-size and presentation paths with the engine-test fakes.
#define main engine_harness_main
#include "engine_test.cpp"
#undef main

int main() {
    g_engine.scaledFbo = 77;
    ReleaseScaledTarget(true);
    assert(g_guardDeleteCalls == 1 && g_engine.scaledFbo == 0);
    g_engine.scaledFbo = 77;
    ReleaseScaledTarget(false);
    assert(g_guardDeleteCalls == 1 && g_engine.scaledFbo == 0); // Lost-context names make no driver calls.
    g_engine.pm = projectm_create();
    g_engine.width = 3840;
    g_engine.height = 2160;
    ApplySettings();
    assert(g_feedbackDetailAlpha == 0.f && g_lineReferenceWidth == 1280 && g_lineReferenceHeight == 720);
    Java_nl_neerdael_projectm_core_ProjectMJNI_setNativeTrails(nullptr, nullptr, 2);
    ApplySettings();
    assert(g_feedbackDetailAlpha == 1.f && g_lineReferenceWidth == 1280 && g_lineReferenceHeight == 720);
    Java_nl_neerdael_projectm_core_ProjectMJNI_setNativeTrails(nullptr, nullptr, 1);
    ApplySettings(); assert(g_feedbackDetailAlpha == 0.5f);
    Java_nl_neerdael_projectm_core_ProjectMJNI_setNativeTrails(nullptr, nullptr, 0);
    ApplySettings(); assert(g_feedbackDetailAlpha == 0.f);
    Java_nl_neerdael_projectm_core_ProjectMJNI_setNativeTrails(nullptr, nullptr, -1);
    ApplySettings(); assert(g_feedbackDetailAlpha == -1.f && g_lineReferenceWidth == 1024);
    ApplyRenderScale(1.f);
    assert(g_windowW == 3840 && g_windowH == 2160);
    RenderPresetFrame();
    assert(g_blits == 0);
    ApplyRenderScale(0.5f);
    g_framebufferStatus = 0;
    RenderPresetFrame();
    assert(g_windowW == 3840 && g_windowH == 2160);
    g_framebufferStatus = GL_FRAMEBUFFER_COMPLETE;
    ApplyRenderScale(0.5f);
    assert(g_windowW == 1920 && g_windowH == 1080);
    RenderPresetFrame();
    const int ordinaryBlits = g_blits;
    assert(ordinaryBlits > 0 && g_textureCopies == 0);
    g_needsFramebufferCopy = true;
    RenderPresetFrame();
    assert(g_blits == ordinaryBlits && g_textureCopies == 1);
    assert(g_copiedTexture == g_engine.scaledTexture && g_copyWidth == 3840 && g_copyHeight == 2160);
    g_needsFramebufferCopy = false;
    g_engine.width = 1920;
    g_engine.height = 1080;
    Java_nl_neerdael_projectm_core_ProjectMJNI_setNativeTrails(nullptr, nullptr, 2);
    ApplySettings(); assert(g_feedbackDetailAlpha == -1.f && g_lineReferenceWidth == 1024);
    ApplyRenderScale(1.f);
    assert(g_windowW == 1920 && g_windowH == 1080);
    // Hold an old 4K surface while UI approves smaller dimensions for higher-cost settings.
    g_engine.width = 3840; g_engine.height = 2160;
    Java_nl_neerdael_projectm_core_ProjectMJNI_setNativeTrails(nullptr, nullptr, 0);
    Java_nl_neerdael_projectm_core_ProjectMJNI_setSoftCutDuration(nullptr, nullptr, 0);
    ApplySettings(); assert(g_feedbackDetailAlpha == 0.f && g_appliedSoftCutSeconds == 0);
    Java_nl_neerdael_projectm_core_ProjectMJNI_configureRenderBudget(nullptr, nullptr, 1920, 1080, 2, 7, 0);
    assert(!ApplySettings());
    g_engine.current = "budget fixture";
    g_inputs.autoChange = false;
    const jlong serial = Java_nl_neerdael_projectm_core_ProjectMJNI_getRenderedFrameSerial(nullptr, nullptr);
    Java_nl_neerdael_projectm_core_ProjectMJNI_onDrawFrame(nullptr, nullptr);
    assert(Java_nl_neerdael_projectm_core_ProjectMJNI_getRenderedFrameSerial(nullptr, nullptr) == serial);
    assert(g_feedbackDetailAlpha == 0.f && g_appliedSoftCutSeconds == 0);
    g_engine.width = 1920; g_engine.height = 1080;
    assert(ApplySettings());
    assert(g_feedbackDetailAlpha == -1.f && g_appliedSoftCutSeconds == 7);
    // Lost context must wait for a fresh budget even if the old size matches.
    const jlong epoch = Java_nl_neerdael_projectm_core_ProjectMJNI_requireRenderBudget(nullptr, nullptr);
    assert(!ApplySettings());
    Java_nl_neerdael_projectm_core_ProjectMJNI_configureRenderBudget(nullptr, nullptr, 1920, 1080, 2, 7, 0);
    assert(!ApplySettings()); // A stale queued UI request must not acknowledge a new context.
    Java_nl_neerdael_projectm_core_ProjectMJNI_configureRenderBudget(nullptr, nullptr, 1920, 1080, 2, 7, epoch);
    assert(ApplySettings());
    Java_nl_neerdael_projectm_core_ProjectMJNI_onDrawFrame(nullptr, nullptr);
    assert(Java_nl_neerdael_projectm_core_ProjectMJNI_getRenderedFrameSerial(nullptr, nullptr) == serial + 1);
    assert(Java_nl_neerdael_projectm_core_ProjectMJNI_getCompletedRenderBudgetGeneration(nullptr, nullptr) == epoch);
    projectm_destroy(g_engine.pm);
    g_engine.pm = nullptr;
    puts("Render policy JNI sizing/presentation checks passed");
}
