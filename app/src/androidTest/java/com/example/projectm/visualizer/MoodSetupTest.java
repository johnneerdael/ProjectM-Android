package com.example.projectm.visualizer;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.text.NumberFormat;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import nl.neerdael.projectm.core.PresetFacets;
import nl.neerdael.projectm.core.ProjectMCore;
import nl.neerdael.projectm.core.ProjectMJNI;

/** Mood panel journey with the real menu, D-pad, persistence and legacy migration in the isolated APK. */
final class MoodSetupTest {
    private static void check(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
    }

    private static void onUi(Instrumentation test, Runnable action) {
        Throwable[] failure = new Throwable[1];
        test.runOnMainSync(() -> {
            try { action.run(); }
            catch (Throwable error) { failure[0] = error; }
        });
        if (failure[0] != null) throw new AssertionError("UI assertion failed", failure[0]);
    }

    private static Object field(Activity activity, String name) {
        try {
            Field field = MainActivity.class.getDeclaredField(name);
            field.setAccessible(true);
            return field.get(activity);
        } catch (ReflectiveOperationException error) {
            throw new AssertionError(error);
        }
    }

    @SuppressWarnings("unchecked")
    private static List<FacetRow> facetRows(Activity activity) {
        return (List<FacetRow>) field(activity, "facetRows");
    }

    private static String header(Instrumentation test, Activity activity) {
        String[] text = new String[1];
        onUi(test, () -> text[0] = ((TextView) activity.findViewById(R.id.mood_header)).getText().toString());
        return text[0];
    }

    private static Set<String> skipped(Instrumentation test) throws Exception {
        File file = ProjectMCore.skipListFile(test.getTargetContext());
        if (!file.isFile()) return Collections.emptySet();
        Set<String> names = new HashSet<>();
        try (BufferedReader in = new BufferedReader(new InputStreamReader(new FileInputStream(file), StandardCharsets.UTF_8))) {
            for (String line; (line = in.readLine()) != null; ) if (!line.isEmpty()) names.add(line);
        }
        return names;
    }

    private static String expectedHeader(int size) {
        String text = NumberFormat.getIntegerInstance(Locale.US).format(size) + " presets in your mix";
        return size < 20 ? text + " · few presets: some repetition" : text;
    }

    private static void awaitCategory(String expected) {
        long deadline = SystemClock.elapsedRealtime() + 20000;
        while (SystemClock.elapsedRealtime() < deadline) {
            if (!ProjectMJNI.isMusicCategoryPending() && expected.equals(ProjectMJNI.getMusicCategory())
                    && !ProjectMJNI.getCurrentPresetName().isEmpty()) return;
            SystemClock.sleep(50);
        }
        throw new AssertionError("category not applied: " + expected + ", actual=" + ProjectMJNI.getMusicCategory()
                + ", pending=" + ProjectMJNI.isMusicCategoryPending());
    }

    private static void focusFacetRow(Instrumentation test, Activity activity, int index) {
        FacetRow row = facetRows(activity).get(index);
        for (int i = 0; i < 12; i++) {
            boolean[] focused = new boolean[1];
            onUi(test, () -> focused[0] = row.hasFocus());
            if (focused[0]) return;
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_DPAD_DOWN);
        }
        throw new AssertionError("D-pad did not reach facet row " + index);
    }

    private static Activity launch(Instrumentation test) {
        Intent intent = new Intent(test.getTargetContext(), MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        return test.startActivitySync(intent);
    }

    private static void relaunchPause(Instrumentation test, Activity activity) {
        onUi(test, activity::finish);
        test.waitForIdleSync();
        SystemClock.sleep(1500);  // let the old GL thread release its instance before a new activity
    }

    private static void openMood(Instrumentation test, Activity activity) {
        test.sendKeyDownUpSync(KeyEvent.KEYCODE_MENU);
        SystemClock.sleep(300);
        onUi(test, () -> {
            check(activity.findViewById(R.id.overlay_menu).getVisibility() == View.VISIBLE, "Menu did not open the panel");
            check(activity.findViewById(R.id.row_music_category).requestFocus(), "Preset mood not focusable");
        });
        test.sendKeyDownUpSync(KeyEvent.KEYCODE_DPAD_CENTER);
        SystemClock.sleep(400);
        onUi(test, () -> check(activity.findViewById(R.id.mood_menu).getVisibility() == View.VISIBLE,
                "Preset mood did not open the Mood panel; focus=" + activity.getCurrentFocus()));
    }

    static void run(Instrumentation test) {
        Bundle result = new Bundle();
        Activity activity = null;
        int code = Activity.RESULT_CANCELED;
        try {
            check(test.getTargetContext().getPackageName().endsWith(".setuptest"), "requires isolated setup APK");
            SharedPreferences prefs = test.getTargetContext().getSharedPreferences("projectm_settings", 0);
            // 1. Fresh settings (apart from the switches that keep the journey deterministic). An
            // installed custom pack keeps its generation, or process start would select Custom again.
            String customGeneration = prefs.getString("custom_pack_generation", null);
            prefs.edit().clear().putString("custom_pack_generation", customGeneration).putBoolean("track_access_explained", true).putBoolean("auto_change_enabled", false)
                    .putBoolean("blank_detection_v3", false).putBoolean("skip_slow_presets", false)
                    .putInt("transition_duration", 0).putBoolean("mood_facets_migrated_1", true).commit();
            PresetFacets table = PresetFacets.load(test.getTargetContext().getAssets());
            check(table != null, "bundled preset attributes missing");
            activity = launch(test);
            Activity target = activity;
            awaitCategory("all");
            openMood(test, target);

            // 2. Nothing chosen: every preset plays.
            check("All presets in your mix".equals(header(test, target)), "initial header: " + header(test, target));

            // 3. Energy › Chill with D-pad Center (the cursor starts on the first option).
            focusFacetRow(test, target, 0);
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_DPAD_CENTER);
            int chill = table.select(Collections.singletonList("chill"), skipped(test)).poolSize();
            check(chill > 0, "no Chill presets");
            check(expectedHeader(chill).equals(header(test, target)), "Chill header: " + header(test, target)
                    + ", expected " + expectedHeader(chill));
            check("chill".equals(prefs.getString("mood_facets", "")), "Chill not saved");
            awaitCategory("facets");
            check(ProjectMJNI.getCategoryPresetCount("facets") == chill,
                    "engine pool " + ProjectMJNI.getCategoryPresetCount("facets") + " differs from " + chill);

            // 4. Comfort › No strobe narrows the mix.
            focusFacetRow(test, target, table.groups().size() - 1);
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_DPAD_CENTER);
            int calm = table.select(Arrays.asList("chill", "no_strobe"), skipped(test)).poolSize();
            check(calm > 0 && calm < chill, "No strobe did not narrow the mix: " + calm + " of " + chill);
            check(expectedHeader(calm).equals(header(test, target)), "No strobe header: " + header(test, target));
            check("chill,no_strobe".equals(prefs.getString("mood_facets", "")),
                    "selection not saved: " + prefs.getString("mood_facets", ""));

            // 5. An option without presets is dimmed and cannot be chosen (tap: the D-pad cursor skips it).
            String dimmedId = null;
            int dimmedGroup = -1, dimmedIndex = -1;
            PresetFacets.Selection selection = table.select(Arrays.asList("chill", "no_strobe"), skipped(test));
            for (int g = 0; g < table.groups().size() && dimmedId == null; g++) {
                List<PresetFacets.Option> options = table.groups().get(g).options;
                for (int o = 0; o < options.size(); o++) {
                    if (selection.isDimmed(options.get(o).id)) {
                        dimmedId = options.get(o).id; dimmedGroup = g; dimmedIndex = o;
                        break;
                    }
                }
            }
            check(dimmedId != null, "no dimmed option for Chill + No strobe");
            int group = dimmedGroup, index = dimmedIndex;
            String dimmed = dimmedId;
            onUi(test, () -> {
                MoodFacetsController mood = (MoodFacetsController) field(target, "mood");
                check(mood.selection().isDimmed(dimmed), dimmed + " is not dimmed in the panel");
                ViewGroup scroller = (ViewGroup) facetRows(target).get(group).getChildAt(1);
                ViewGroup strip = (ViewGroup) scroller.getChildAt(0);
                View chip = strip.getChildAt(index);
                check(((TextView) chip).getText().toString().endsWith("→ 0"), "dimmed chip shows a count: "
                        + ((TextView) chip).getText());
                chip.performClick();
            });
            check("chill,no_strobe".equals(prefs.getString("mood_facets", "")),
                    "dimmed " + dimmed + " was toggled: " + prefs.getString("mood_facets", ""));
            check(expectedHeader(calm).equals(header(test, target)), "dimmed tap changed the header");

            SystemClock.sleep(300);
            onUi(test, () -> {
                facetRows(target).get(0).requestFocus();
                target.findViewById(R.id.mood_menu).scrollTo(0, 0);  // show the header too
            });
            SystemClock.sleep(300);
            Bitmap screenshot = test.getUiAutomation().takeScreenshot();
            check(screenshot != null, "Mood screenshot unavailable");
            try (FileOutputStream output = new FileOutputStream(new File(
                    test.getTargetContext().getExternalCacheDir(), "mood.png"))) {
                check(screenshot.compress(Bitmap.CompressFormat.PNG, 100, output), "screenshot write failed");
            } finally { screenshot.recycle(); }

            // 6. Clear all returns to every preset.
            onUi(test, () -> target.findViewById(R.id.row_mood_clear).requestFocus());
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_DPAD_CENTER);
            check("".equals(prefs.getString("mood_facets", "x")), "Clear all left " + prefs.getString("mood_facets", "x"));
            check("All presets in your mix".equals(header(test, target)), "cleared header: " + header(test, target));
            awaitCategory("all");

            // Choose Chill again for the persistence check.
            onUi(test, () -> facetRows(target).get(0).requestFocus());
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_DPAD_CENTER);
            check("chill".equals(prefs.getString("mood_facets", "")), "Chill not saved again");

            // 7. Back returns to the main panel on Preset mood.
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);
            SystemClock.sleep(400);
            onUi(test, () -> {
                check(target.findViewById(R.id.overlay_menu).getVisibility() == View.VISIBLE, "main panel not shown");
                check(target.findViewById(R.id.row_music_category).hasFocus(), "focus not on Preset mood");
                check(target.findViewById(R.id.mood_menu).getVisibility() != View.VISIBLE
                        || target.findViewById(R.id.mood_menu).getAlpha() < 1f, "Mood panel still shown");
            });

            // 8. Ten seconds without input hide the panels.
            SystemClock.sleep(11500);
            onUi(test, () -> {
                check(target.findViewById(R.id.overlay_menu).getVisibility() == View.GONE, "main panel did not hide");
                check(target.findViewById(R.id.mood_menu).getVisibility() == View.GONE, "Mood panel did not hide");
            });

            // 9. A relaunch restores the selection, the pool and the header.
            relaunchPause(test, target);
            activity = launch(test);
            Activity restarted = activity;
            awaitCategory("facets");
            check(ProjectMJNI.getCategoryPresetCount("facets") == chill, "pool not restored after relaunch");
            openMood(test, restarted);
            check(expectedHeader(chill).equals(header(test, restarted)), "restored header: " + header(test, restarted));

            // 10. A legacy Intense mood migrates once to the Energy option.
            prefs.edit().remove("mood_facets_migrated_1").remove("mood_facets").remove("mood_collection")
                    .putString("music_category", "intense").commit();
            ProjectMApplication.migrateMoodSelection(prefs);  // runs at process start in the app
            relaunchPause(test, restarted);
            activity = launch(test);
            Activity migrated = activity;
            check("intense".equals(prefs.getString("mood_facets", "")), "legacy Intense not migrated: "
                    + prefs.getString("mood_facets", ""));
            check(prefs.getBoolean("mood_facets_migrated_1", false), "migration flag missing");
            awaitCategory("facets");
            int intense = table.select(Collections.singletonList("intense"), skipped(test)).poolSize();
            check(ProjectMJNI.getCategoryPresetCount("facets") == intense, "migrated pool differs");
            openMood(test, migrated);
            check(expectedHeader(intense).equals(header(test, migrated)), "migrated header: " + header(test, migrated));

            result.putString("stream", "PASS: Mood panel header, D-pad Chill (" + chill + ") and No strobe (" + calm
                    + "), engine pool, dimmed " + dimmed + " not selectable, Clear all, Back focus, auto-hide, relaunch persistence, legacy Intense migration (" + intense + ")\n");
            code = Activity.RESULT_OK;
        } catch (Throwable failure) {
            result.putString("stream", "FAIL: " + failure + "; cause=" + failure.getCause() + "\n");
        } finally {
            if (activity != null) {
                Activity target = activity;
                onUi(test, target::finish);
            }
        }
        test.finish(code, result);
    }
}
