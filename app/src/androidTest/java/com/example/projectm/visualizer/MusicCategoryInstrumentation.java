package com.example.projectm.visualizer;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.KeyEvent;
import android.view.View;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.HashSet;
import java.util.Set;
import nl.neerdael.projectm.core.ProjectMJNI;

/** Runtime test using only Android framework APIs; adds no dependencies to the app. */
public final class MusicCategoryInstrumentation extends Instrumentation {
    private boolean liveAudio;
    private String setupCase;
    @Override public void onCreate(Bundle arguments) {
        super.onCreate(arguments);
        liveAudio = arguments != null && "true".equals(arguments.getString("live_audio"));
        setupCase = arguments == null ? null : arguments.getString("setup_case");
        start();
    }
    private void check(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
    }
    private Set<String> members(String category) throws Exception {
        Set<String> names = new HashSet<>();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                getTargetContext().getAssets().open("preset-genres/genres/" + category + ".idx")))) {
            String line;
            while ((line = reader.readLine()) != null) names.add(line.split("\t")[0]);
        }
        return names;
    }
    private void awaitCategory(String expected) {
        long deadline = SystemClock.elapsedRealtime() + 15000;
        while (SystemClock.elapsedRealtime() < deadline) {
            if (!ProjectMJNI.isMusicCategoryPending() && expected.equals(ProjectMJNI.getMusicCategory())
                    && !ProjectMJNI.getCurrentPresetName().isEmpty()) return;
            SystemClock.sleep(50);
        }
        throw new AssertionError("category not applied: " + expected + ", actual=" + ProjectMJNI.getMusicCategory());
    }
    @Override public void onStart() {
        if (setupCase != null) {
            if ("native_crash_capture".equals(setupCase)) NativeCrashSetupTest.run(this, true);
            else if ("native_crash_report".equals(setupCase)) NativeCrashSetupTest.run(this, false);
            else if ("tv_menu".equals(setupCase)) TvMenuSetupTest.run(this);
            else if (setupCase.startsWith("fdroid_")) DistributionSetupTest.run(this, setupCase);
            else if ("phone_audio".equals(setupCase)) PhoneAudioSetupTest.run(this);
            else if ("touchscreen".equals(setupCase)) TouchscreenSetupTest.run(this);
            else if ("custom_pack".equals(setupCase)) CustomPackSetupTest.run(this, false);
            else if ("custom_pack_qr".equals(setupCase)) CustomPackSetupTest.runQr(this);
            else if ("custom_pack_restart".equals(setupCase)) CustomPackSetupTest.run(this, true);
            else if ("resolution_recording".equals(setupCase)) ResolutionSetupTest.record(this);
            else if ("resolution".equals(setupCase)) ResolutionSetupTest.run(this);
            else if ("native_trails".equals(setupCase)) NativeTrailsSetupTest.run(this);
            else if ("mood".equals(setupCase)) MoodSetupTest.run(this);
            else TrackAccessSetupTest.run(this, setupCase);
            return;
        }
        Bundle result = new Bundle();
        Activity activity = null;
        try {
            Intent intent = new Intent(getTargetContext(), MainActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            activity = startActivitySync(intent);
            ProjectMJNI.setAutoChange(false);
            ProjectMJNI.setMusicCategory("all");
            awaitCategory("all");
            Set<String> intense = members("intense");
            check(!intense.isEmpty(), "missing intense members");
            ProjectMJNI.setMusicCategory("intense");
            awaitCategory("intense");
            check(intense.contains(ProjectMJNI.getCurrentPresetName()), "out-of-category initial preset");
            int eligible = ProjectMJNI.getCategoryPresetCount("intense");
            check(eligible > 0 && eligible <= intense.size(), "invalid eligible Intense count");
            check(ProjectMJNI.getPresetCount() == eligible, "active count is not category-specific");
            result.putString("intense_members", "packaged=" + intense.size() + ", eligible=" + eligible);
            if (liveAudio) {
                int audible = 0;
                float peak = 0;
                SystemClock.sleep(4000); // allow capture/session discovery to settle
                String name = ProjectMJNI.getCurrentPresetName();
                for (int i = 0; i < 150; i++) {
                    float level = ProjectMJNI.getAudioLevel();
                    if (level > .001f) audible++;
                    peak = Math.max(peak, level);
                    check(intense.contains(ProjectMJNI.getCurrentPresetName()), "live playback escaped Intense");
                    SystemClock.sleep(100);
                }
                result.putString("live_audio", "preset=" + name + ", audible_samples=" + audible
                        + "/150, peak_rms=" + peak);
                check(audible >= 75, "live music was not received reliably: " + audible + "/150 samples");
            }
            for (int i = 0; i < 5; i++) {
                ProjectMJNI.randomPreset(true);
                SystemClock.sleep(300);
                check(intense.contains(ProjectMJNI.getCurrentPresetName()), "random escaped category");
            }
            for (String mood : new String[]{"chill", "normal"}) {
                Set<String> group = members(mood);
                check(!group.isEmpty(), "missing " + mood + " members");
                ProjectMJNI.setMusicCategory(mood);
                awaitCategory(mood);
                check(group.contains(ProjectMJNI.getCurrentPresetName()), mood + " initial selection escaped");
                check(ProjectMJNI.getPresetCount() == ProjectMJNI.getCategoryPresetCount(mood),
                        mood + " active count differs");
                for (int i = 0; i < 5; i++) {
                    ProjectMJNI.randomPreset(true);
                    SystemClock.sleep(300);
                    check(group.contains(ProjectMJNI.getCurrentPresetName()), mood + " random escaped");
                }
            }
            ProjectMJNI.setMusicCategory("dance");  // retired persisted/core identifier
            awaitCategory("all");
            Activity target = activity;
            runOnMainSync(() -> {
                View row = target.findViewById(R.id.row_music_category);
                check(row != null && row.isFocusable(), "category row unavailable");
            });
            ProjectMJNI.setMusicCategory("not-a-category");
            awaitCategory("all");
            if (liveAudio) {
                getTargetContext().getSharedPreferences("projectm_settings", 0).edit()
                        .putString("music_category", "intense").apply();
                ProjectMJNI.setMusicCategory("intense");
                awaitCategory("intense");
            }
            result.putString("stream", "PASS: category application, active count, random membership, all three groups, focusable row, retired selection fallback\n");
            finish(Activity.RESULT_OK, result);
        } catch (Throwable failure) {
            result.putString("stream", "FAIL: " + failure + "\n");
            finish(Activity.RESULT_CANCELED, result);
        } finally {
            if (activity != null) {
                Activity target = activity;
                runOnMainSync(target::finish);
            }
        }
    }
}
