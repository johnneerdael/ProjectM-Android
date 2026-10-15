package nl.neerdael.projectm.core;

import android.content.res.AssetManager;
import android.util.Log;

/**
 * Bindings to the native engine (native-lib.cpp).
 *
 * The surface/frame/release methods must be called on the GL thread. All other methods are
 * thread-safe: they only record a request that the GL thread applies on its next frame.
 */
public final class ProjectMJNI {
    private static final String TAG = "ProjectMJNI";

    static {
        try {
            System.loadLibrary("projectmtv");
        } catch (UnsatisfiedLinkError e) {
            Log.e(TAG, "Failed to load projectmtv library", e);
        }
    }

    /**
     * projectM's blend, rendered below the render resolution (75% to start) and adapted to keep
     * the frame rate: lower when a blend drops frames, higher when blends have frames to spare.
     */
    public static final int TRANSITION_AUTO = 0;
    /** projectM hard-cuts; the last frame of the old preset fades out on top (cheap). */
    public static final int TRANSITION_LIGHTWEIGHT = 1;
    /** projectM's own blend at the full render resolution: both presets render for the whole transition. */
    public static final int TRANSITION_CLASSIC = 2;

    private ProjectMJNI() {}

    /**
     * Starts background work: copies the bundled texture pack to {@code textureDir} (projectM only
     * loads textures from real folders) and indexes the presets. Safe to call repeatedly.
     */
    public static native void init(AssetManager assets, String skipListPath, String textureDir);

    // GL thread only
    public static native void onSurfaceCreated();
    public static native void onSurfaceChanged(int width, int height);
    public static native void onDrawFrame();
    public static native void release();

    // Any thread
    /** Raw Visualizer waveform: 8-bit unsigned mono PCM. */
    public static native void addWaveform(byte[] waveform, int length);
    public static native void nextPreset(boolean hardCut);
    public static native void previousPreset(boolean hardCut);
    public static native void randomPreset(boolean hardCut);
    /** Native authored feedback: -1 off, 0 Standard (core default), 1 Medium, 2 High.
     * The core activates this above 1330p; automatic quality selects the surface size. A negative value keeps the legacy path.
     */
    public static native void setNativeTrails(int level);
    /** Coherent managed-view allocation settings; applies only after the requested surface size is acknowledged. */
    public static native void configureRenderBudget(int width, int height, int trails, int transitionSeconds, long generation);
    /** Hold managed rendering until a fresh configuration is published, for context recreation. */
    public static native long requireRenderBudget();
    /** Context generation that has rendered an actual preset under its approved budget. */
    public static native long getCompletedRenderBudgetGeneration();
    /** Monotonic completed preset-frame serial; budget-guarded calls do not advance it. */
    public static native long getRenderedFrameSerial();
    /** Last rendered state, including actual canvas size or the diffusion fallback. */
    public static native String getNativeTrailsStatus();
    public static native void setPresetDuration(int seconds);
    /** Preset collection: all (default), chill, normal, intense or an installed custom pack. */
    public static native void setMusicCategory(String genreId);
    public static native String getMusicCategory();
    public static native int getCategoryPresetCount(String genreId);
    public static native boolean isMusicCategoryPending();

    /**
     * Mood facet pool: bundled preset names (PresetFacets.Selection.presetNames()) that the
     * "facets" music category plays. Null or empty clears it. Select it with
     * setMusicCategory("facets"); names absent from the bundled library are ignored.
     */
    public static native void setPresetPool(String[] names);
    /** Favorites collection: the requested preset names across the installed bundled and custom catalogs. */
    public static native void setFavorites(String[] names);
    /**
     * Index an immutable host-owned preset directory on the native worker. An empty path removes
     * the pack. presets.idx contains generated relative storage paths, a tab, and display paths.
     * Custom presets join All only. Use setMusicCategory("custom") to select the pack; category
     * application waits for indexing. Preserve directory contents until replacement is applied.
     */
    public static native long setCustomPresetPack(String directory);
    /** True until the worker has processed the latest custom-pack index request. */
    public static native boolean isCustomPresetPackPending();
    /** Stage an index without replacing the live pack. Commit only after status 1 (ready). */
    public static native long prepareCustomPresetPack(String directory);
    /** 0 preparing, 1 ready, 2 applied, -1 rejected or superseded; tied to the returned request ID. */
    public static native int getCustomPresetPackStatus(long request);
    /** Publish prepared metadata and select Custom. False leaves the live catalog unchanged. */
    public static native boolean commitCustomPresetPack(long request);
    /** Cancel a queued/prepared request without changing an already applied pack. */
    public static native void discardCustomPresetPack(long request);
    /** Live rendering/transition or prewarming can still need an immutable generation's images. */
    public static native boolean isCustomPresetPackInUse(String directory);
    /** Official base collection replaces bundled starters, preserving moods and the custom slot. */
    /** Hold startup category application/persistence while the host validates its stored collection.
     * Call before asynchronous validation starts and clear in finally after restore or failure. */
    public static native void setOfficialPresetRestorePending(boolean pending);
    public static native long setOfficialPresetPack(String directory);
    public static native long prepareOfficialPresetPack(String directory);
    /** Same request-scoped 0/1/2/-1 contract as custom-pack status. */
    public static native int getOfficialPresetPackStatus(long request);
    public static native boolean commitOfficialPresetPack(long request);
    public static native void discardOfficialPresetPack(long request);
    public static native boolean isOfficialPresetPackPending();
    /** Includes indexing, rendering, texture lookup and background compilation ownership. */
    public static native boolean isOfficialPresetPackInUse(String directory);
    public static native void setSoftCutDuration(int seconds);
    public static native void setAutoChange(boolean enabled);
    /** projectM's hard cut to the next preset on a loud beat (off: presets only change by blending). */
    public static native void setBeatCuts(boolean enabled);
    /** Memory runs low: pauses compiling upcoming presets in the background for 20 s. */
    public static native void onMemoryPressure();
    /**
     * Compiles the upcoming presets on a background thread with its own EGL context (on, the
     * default), or only on the render thread when they are shown (off: longer stalls at switches).
     * A troubleshooting switch for GPU drivers that fail with a second context; applied on the GL
     * thread.
     */
    public static native void setBackgroundCompile(boolean enabled);
    /**
     * Reuses linked shader programs as binaries across projectM instances and contexts (on, the
     * default), or always compiles them from source (off). A troubleshooting switch for GPU
     * drivers whose program binaries fail when moved between contexts. Applied on the GL thread,
     * which waits there for binary calls already under way; the caller never blocks.
     */
    public static native void setShaderBinaryCache(boolean enabled);
    /**
     * File in which the engine keeps one line per thread about what it was last doing (loading,
     * blending, compiling), overwritten in place, so it survives a crash of the process. Each line
     * reads {@code <thread> pid=<pid> ms=<wall clock ms> session=<session> cache=on|off
     * compile=on|off <message>}, with the Shader binary cache and Background compile states as
     * applied when it was written. {@code session} (letters and digits, up to 23) identifies this
     * process, e.g. matching what the app stores with {@code ActivityManager.setProcessStateSummary}. Read it before calling this.
     */
    public static native void setDiagnosticsFile(String path, String session);
    public static native void setMeshSize(int width, int height);
    /** Adds the current preset to the skip list and moves on (hard cut). */
    public static native void skipCurrentPreset();
    /**
     * Enables skipping of presets that stay black while music plays. Off by default: output is
     * always measured and logged, but only skipped on request.
     */
    public static native void setBlankDetection(boolean enabled);
    /** Transition mode: {@link #TRANSITION_AUTO}, {@link #TRANSITION_LIGHTWEIGHT} or {@link #TRANSITION_CLASSIC}. */
    /** @param lowEndDevice Auto's blends start at a lower resolution. */
    public static native void setTransitionMode(int mode, boolean lowEndDevice);
    /** Resolution of Auto's blends in percent of the render resolution, 0 before the first blend. */
    public static native int getBlendScalePercent();
    /** True when automatic preset switches currently use the lightweight transition. */
    public static native boolean isLightweightTransition();
    /** Makes the next automatic preset switch a hard cut (used before resolution changes). */
    public static native void setForceHardCut(boolean enabled);
    /** Reads an Android system property ("" if unset or not readable). */
    public static native String getSystemProperty(String name);
    public static native String getCurrentPresetName();
    /** Recent audio input level (RMS, 0..1); 0 if no audio arrived in the last second. */
    public static native float getAudioLevel();
    /** Increments every time a new preset is shown. */
    public static native int getPresetChangeCounter();
    public static native int getPresetCount();
    /** Increments when a transition finishes; see {@link #getLastTransitionFps()}. */
    public static native int getTransitionCounter();
    /** Average FPS over the last transition, including the preset-load stall. */
    public static native float getLastTransitionFps();
    public static native int getSkippedCount();
    public static native void resetSkippedPresets();
    /**
     * Upstream numeric version (4.2.0 for the pinned unreleased projectM 4.2 master snapshot).
     * This is not the app/core release version or proof of an upstream release.
     */
    public static native String getVersion();
}
