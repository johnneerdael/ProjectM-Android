package nl.neerdael.projectm.core;

import android.content.Context;

import java.io.File;

/**
 * Entry point for apps that embed the engine: call {@link #init(Context)} once at startup, show a
 * {@link VisualizerView} rendered by a {@link VisualizerRenderer}, and feed audio and settings
 * through {@link ProjectMJNI}.
 */
public final class ProjectMCore {
    private static final String SKIP_LIST_FILE = "skipped_presets.txt";
    private static final String TEXTURE_DIR = "textures";

    private static volatile MemoryProvider memoryProvider = () -> null;
    private static boolean memoryProviderInitialized;

    private ProjectMCore() {}

    static MemoryProvider memoryProvider() { return memoryProvider; }

    private static synchronized void initMemoryProvider(Context app) {
        if (!memoryProviderInitialized) {
            memoryProvider = new AndroidMemoryProvider(app);
            memoryProviderInitialized = true;
        }
    }

    /**
     * Starts the engine's background work: presets are indexed straight from the APK assets, and
     * the texture pack (~4 MB) is copied to app storage once. Both finish on a native thread
     * before the first preset loads. Call from {@code Application.onCreate}; safe to call again.
     *
     * The engine keeps the asset manager for the life of the process, so it is taken from the
     * application context whatever context is passed.
     */
    public static void init(Context context) {
        Context app = context.getApplicationContext();
        NativeCrashReports.install(app);
        initMemoryProvider(app);
        ProjectMJNI.init(app.getAssets(), skipListFile(app).getAbsolutePath(),
                new File(app.getFilesDir(), TEXTURE_DIR).getAbsolutePath());
    }

    /** The engine's list of presets that stayed black; delete it before {@link #init} to reset it. */
    public static File skipListFile(Context context) {
        return new File(context.getFilesDir(), SKIP_LIST_FILE);
    }
}
