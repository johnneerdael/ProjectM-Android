package com.example.projectm.visualizer;

import android.app.Application;
import android.util.Log;

import nl.neerdael.projectm.core.ProjectMCore;
import nl.neerdael.projectm.core.ProjectMJNI;

import java.io.File;

public class ProjectMApplication extends Application {
    private static final String TAG = "ProjectMApplication";
    private static final String PREF_SKIP_LIST_RESET = "skip_list_reset_1_9";
    private static final String PREF_FRAME_RATE_RESET = "frame_rate_reset_30";
    private static final String PREF_MOOD_MIGRATED = "mood_facets_migrated_1";
    private volatile long customRestoreRequest;
    long customRestoreRequest() { return customRestoreRequest; }

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "Starting on " + android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL
                + ", Android " + android.os.Build.VERSION.RELEASE);

        // Up to 1.8 texture-based presets rendered without their textures and could be skipped as
        // blank. The textures ship now, so give every preset a new chance once.
        File skipList = ProjectMCore.skipListFile(this);
        android.content.SharedPreferences prefs = getSharedPreferences("projectm_settings", MODE_PRIVATE);
        if (!prefs.getBoolean(PREF_SKIP_LIST_RESET, false)) {
            if (skipList.exists() && !skipList.delete()) Log.w(TAG, "Could not reset " + skipList);
            prefs.edit().putBoolean(PREF_SKIP_LIST_RESET, true).apply();
        }

        // The default frame rate became half the refresh rate (30 fps at 60 Hz), which lets Auto
        // pick a much higher resolution. Move everyone to it once, also those who chose a rate, and
        // let Auto learn its level anew at that rate.
        if (!prefs.getBoolean(PREF_FRAME_RATE_RESET, false)) {
            prefs.edit()
                    .remove("frame_rate_cap")
                    .remove("auto_render_height")
                    .putBoolean(PREF_FRAME_RATE_RESET, true)
                    .apply();
        }

        migrateMoodSelection(prefs);

        // Before the engine starts: keeps what the previous process was doing when it ended.
        ExitDiagnostics.start(this);
        ProjectMCore.init(this);
        OfficialCollection.restore(this);

        File customRoot = new File(getNoBackupFilesDir(), "custom-presets");
        File custom = CustomPresetPack.current(customRoot);
        // Recover the default if a process died after the durable pointer was saved but before
        // the asynchronous preference write. Later user mood choices keep the same generation.
        if (custom != null && !custom.getName().equals(prefs.getString("custom_pack_generation", "")))
            prefs.edit().putString("music_category", "custom").putString("mood_collection", "custom")
                    .putString("custom_pack_generation", custom.getName()).apply();
        long customRequest = custom == null ? 0 : ProjectMJNI.setCustomPresetPack(custom.getAbsolutePath());
        customRestoreRequest = customRequest;

        // Versions up to 1.7 extracted ~130MB of presets on every launch; reclaim that space.
        new Thread(() -> {
            android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);
            deleteRecursively(new File(getCacheDir(), "projectM"));
            deleteRecursively(new File(getFilesDir(), "projectM"));
            try {
                if (customRequest != 0) CustomPresetPack.awaitStatus(customRequest, 2,
                        ProjectMJNI::getCustomPresetPackStatus, () -> false, 30000);
                customRestoreRequest = 0;
                synchronized (CustomPresetPack.STORE_LOCK) {
                    new File(customRoot, "incoming.zip").delete();
                    new File(customRoot, "current.tmp").delete();
                    CustomPresetPack.scheduleCleanup(customRoot);
                }
            } catch (java.io.IOException failedIndex) {
                ProjectMJNI.discardCustomPresetPack(customRequest);
                customRestoreRequest = 0;
                Log.w(TAG, "Custom pack restore did not finish; preserving its files", failedIndex);
            }
        }, "LegacyCleanup").start();
    }

    /**
     * The Chill/Normal/Intense moods became Energy options of the Mood panel, and Custom its
     * collection choice. Carries the previous choice over once (the mood setup case calls it too).
     */
    static void migrateMoodSelection(android.content.SharedPreferences prefs) {
        if (prefs.getBoolean(PREF_MOOD_MIGRATED, false)) return;
        String legacy = prefs.getString("music_category", "all");
        android.content.SharedPreferences.Editor edit = prefs.edit().putBoolean(PREF_MOOD_MIGRATED, true);
        if ("chill".equals(legacy) || "normal".equals(legacy) || "intense".equals(legacy))
            edit.putString("mood_facets", legacy).putString("music_category", "facets");
        else if ("custom".equals(legacy)) edit.putString("mood_collection", "custom");
        edit.apply();
    }

    private static void deleteRecursively(File file) {
        if (!file.exists()) return;
        File[] children = file.listFiles();
        if (children != null) {
            for (File child : children) deleteRecursively(child);
        }
        if (!file.delete()) Log.w(TAG, "Could not delete " + file);
    }
}
