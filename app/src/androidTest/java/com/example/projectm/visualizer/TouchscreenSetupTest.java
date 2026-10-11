package com.example.projectm.visualizer;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.widget.ScrollView;
import java.io.File;
import java.io.FileOutputStream;
import nl.neerdael.projectm.core.ProjectMJNI;

/** Inject actual touch streams into the real activity, including slow drags and cancellation. */
final class TouchscreenSetupTest {
    private static void check(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
    }
    private static void onUi(Instrumentation test, Runnable action) {
        Throwable[] failure = new Throwable[1];
        test.runOnMainSync(() -> {
            try { action.run(); } catch (Throwable error) { failure[0] = error; }
        });
        if (failure[0] != null) throw new AssertionError("UI assertion", failure[0]);
    }
    private static void pointer(Instrumentation test, long down, int action, float x, float y) {
        MotionEvent event = MotionEvent.obtain(down, SystemClock.uptimeMillis(), action, x, y, 0);
        try { test.sendPointerSync(event); } finally { event.recycle(); }
    }
    private static void tap(Instrumentation test, float x, float y) {
        long down = SystemClock.uptimeMillis();
        pointer(test, down, MotionEvent.ACTION_DOWN, x, y);
        SystemClock.sleep(60);
        pointer(test, down, MotionEvent.ACTION_UP, x, y);
        test.waitForIdleSync();
        SystemClock.sleep(300);
    }
    private static void tapView(Instrumentation test, Activity activity, int id) {
        float[] point = new float[2];
        onUi(test, () -> {
            View view = activity.findViewById(id);
            android.graphics.Rect bounds = new android.graphics.Rect();
            check(view.getGlobalVisibleRect(bounds), "control is not visible: " + id);
            point[0] = bounds.centerX(); point[1] = bounds.centerY();
        });
        tap(test, point[0], point[1]);
    }
    private static void swipe(Instrumentation test, float x, float y, float endX, float endY, boolean cancel) {
        long down = SystemClock.uptimeMillis();
        pointer(test, down, MotionEvent.ACTION_DOWN, x, y);
        for (int i = 1; i <= 12; i++) {
            SystemClock.sleep(60); // deliberately slower than a fling
            pointer(test, down, MotionEvent.ACTION_MOVE, x + (endX - x) * i / 12, y + (endY - y) * i / 12);
        }
        pointer(test, down, cancel ? MotionEvent.ACTION_CANCEL : MotionEvent.ACTION_UP, endX, endY);
        test.waitForIdleSync();
        SystemClock.sleep(300);
    }
    private static void multiTouch(Instrumentation test, float x, float y, float delta) {
        long down = SystemClock.uptimeMillis();
        MotionEvent.PointerProperties[] properties = new MotionEvent.PointerProperties[2];
        MotionEvent.PointerCoords[] points = new MotionEvent.PointerCoords[2];
        for (int i = 0; i < 2; i++) {
            properties[i] = new MotionEvent.PointerProperties(); properties[i].id = i;
            properties[i].toolType = MotionEvent.TOOL_TYPE_FINGER;
            points[i] = new MotionEvent.PointerCoords(); points[i].x = x + delta + i * 40;
            points[i].y = y; points[i].pressure = 1; points[i].size = 1;
        }
        for (int action : new int[]{MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE,
                MotionEvent.ACTION_POINTER_DOWN, MotionEvent.ACTION_POINTER_UP, MotionEvent.ACTION_UP}) {
            int count = action == MotionEvent.ACTION_POINTER_DOWN || action == MotionEvent.ACTION_POINTER_UP ? 2 : 1;
            points[0].x = action == MotionEvent.ACTION_DOWN ? x : x + delta;
            int encoded = count == 2 ? action | (1 << MotionEvent.ACTION_POINTER_INDEX_SHIFT) : action;
            MotionEvent event = MotionEvent.obtain(down, SystemClock.uptimeMillis(), encoded, count, properties, points,
                    0, 0, 1, 1, 0, 0, android.view.InputDevice.SOURCE_TOUCHSCREEN, 0);
            try { test.sendPointerSync(event); } finally { event.recycle(); }
            SystemClock.sleep(60);
        }
        SystemClock.sleep(300);
    }

    private static String awaitPreset(String old) {
        long deadline = SystemClock.elapsedRealtime() + 15000;
        while (SystemClock.elapsedRealtime() < deadline) {
            String name = ProjectMJNI.getCurrentPresetName();
            if (!name.isEmpty() && (old == null || !old.equals(name))) return name;
            SystemClock.sleep(50);
        }
        throw new AssertionError("preset never changed from " + old);
    }
    private static void menu(Instrumentation test, Activity activity, int id, boolean visible) {
        onUi(test, () -> check((activity.findViewById(id).getVisibility() == View.VISIBLE) == visible,
                "wrong panel visibility: " + id));
    }
    private static void scrollBottom(Instrumentation test, Activity activity, int id) {
        for (int i = 0; i < 7; i++) {
            int[] p = new int[4];
            onUi(test, () -> {
                View view = activity.findViewById(id);
                int[] xy = new int[2]; view.getLocationOnScreen(xy);
                p[0] = xy[0] + view.getWidth() / 2; p[1] = xy[1]; p[2] = view.getHeight();
            });
            swipe(test, p[0], p[1] + p[2] * .8f, p[0], p[1] + p[2] * .2f, false);
        }
    }
    static void run(Instrumentation test) {
        Activity activity = null;
        Bundle result = new Bundle();
        int code = Activity.RESULT_CANCELED;
        try {
            check(BuildConfig.TOUCHSCREEN, "requires touchscreen build");
            check(test.getTargetContext().getPackageName().endsWith(".setuptest"), "requires isolated setup APK");
            SharedPreferences prefs = test.getTargetContext().getSharedPreferences("projectm_settings", 0);
            prefs.edit().putBoolean("track_access_explained", true).putBoolean("auto_change_enabled", false)
                    .putBoolean("blank_detection_v3", false).putBoolean("skip_slow_presets", false)
                    .putBoolean("auto_update", false).putString("phone_audio_input", "microphone").putInt("transition_duration", 0).commit();
            activity = test.startActivitySync(new Intent(test.getTargetContext(), MainActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
            Activity target = activity;
            String first = awaitPreset(null);
            float[] size = new float[2];
            onUi(test, () -> { View view = target.findViewById(R.id.visualizer_view);
                size[0] = view.getWidth(); size[1] = view.getHeight(); });
            float x = size[0] * .15f, y = size[1] * .5f;
            swipe(test, x, y, size[0] * .65f, y, false);
            String next = awaitPreset(first);
            menu(test, target, R.id.overlay_menu, false);
            swipe(test, size[0] * .65f, y, x, y, false);
            check(awaitPreset(next).equals(first), "left swipe did not return to prior preset");
            swipe(test, x, y, size[0] * .65f, y, true);
            check(ProjectMJNI.getCurrentPresetName().equals(first), "cancelled horizontal swipe changed preset");
            swipe(test, x, y, x, y + size[1] * .25f, false);
            check(ProjectMJNI.getCurrentPresetName().equals(first), "vertical drag switched preset");
            menu(test, target, R.id.overlay_menu, false);
            long down = SystemClock.uptimeMillis();
            pointer(test, down, MotionEvent.ACTION_DOWN, x, y);
            pointer(test, down, MotionEvent.ACTION_CANCEL, x, y);
            menu(test, target, R.id.overlay_menu, false);
            multiTouch(test, x, y, size[0] * .3f);
            check(ProjectMJNI.getCurrentPresetName().equals(first), "multi-touch changed preset");
            menu(test, target, R.id.overlay_menu, false);
            tap(test, x, y);
            menu(test, target, R.id.overlay_menu, true);
            onUi(test, () -> {
                View panel = target.findViewById(R.id.overlay_menu);
                check(panel instanceof ScrollView, "main panel not scrollable");
                android.graphics.Rect visible = new android.graphics.Rect();
                android.view.WindowInsets insets = panel.getRootWindowInsets();
                android.view.ViewGroup.MarginLayoutParams params = (android.view.ViewGroup.MarginLayoutParams) panel.getLayoutParams();
                check(params.getMarginEnd() >= insets.getStableInsetRight(), "menu overlaps phone navigation bar");
                check(panel.getGlobalVisibleRect(visible) && visible.width() == panel.getWidth(),
                        "main panel clipped horizontally: visible=" + visible + " width=" + panel.getWidth()
                                + " translation=" + panel.getTranslationX());
            });
            onUi(test, () -> {
                android.graphics.Rect rect = new android.graphics.Rect();
                target.findViewById(R.id.row_auto_change).getDrawingRect(rect);
                target.findViewById(R.id.row_auto_change).requestRectangleOnScreen(rect, true);
            });
            SystemClock.sleep(300);
            tapView(test, target, R.id.row_auto_change);
            check(prefs.getBoolean("auto_change_enabled", false), "touch row did not cycle");
            tapView(test, target, R.id.row_auto_change);
            check(!prefs.getBoolean("auto_change_enabled", true), "touch row did not persist");
            // A settings scroll must not become a preset swipe or a row activation.
            scrollBottom(test, target, R.id.overlay_menu);
            check(ProjectMJNI.getCurrentPresetName().equals(first), "menu scrolling switched preset");
            check(!prefs.getBoolean("auto_change_enabled", true), "scroll activated option row");
            tapView(test, target, R.id.row_advanced);
            menu(test, target, R.id.advanced_menu, true);
            scrollBottom(test, target, R.id.advanced_menu);
            boolean oldCache = prefs.getBoolean("shader_binary_cache", true);
            tapView(test, target, R.id.row_shader_binary_cache);
            check(prefs.getBoolean("shader_binary_cache", true) != oldCache, "Advanced touch setting not saved");
            tapView(test, target, R.id.advanced_back);
            menu(test, target, R.id.overlay_menu, true);
            tapView(test, target, R.id.row_track_display);
            menu(test, target, R.id.track_menu, true);
            scrollBottom(test, target, R.id.track_menu);
            boolean oldPill = prefs.getBoolean("track_pill", false);
            tapView(test, target, R.id.row_track_pill);
            check(prefs.getBoolean("track_pill", false) != oldPill, "Track touch setting not saved");
            tapView(test, target, R.id.track_back);
            menu(test, target, R.id.overlay_menu, true);
            scrollBottom(test, target, R.id.overlay_menu);
            android.graphics.Bitmap screenshot = test.getUiAutomation().takeScreenshot();
            check(screenshot != null, "screenshot unavailable");
            try (FileOutputStream out = new FileOutputStream(new File(test.getTargetContext().getExternalCacheDir(), "touch-menu.png"))) {
                screenshot.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out);
            } finally { screenshot.recycle(); }
            tapView(test, target, R.id.menu_close);
            menu(test, target, R.id.overlay_menu, false);
            tap(test, x, y); tap(test, x, y);
            menu(test, target, R.id.overlay_menu, false);
            tap(test, x, y);
            int[] panelPoint = new int[2];
            onUi(test, () -> { View panel = target.findViewById(R.id.overlay_menu);
                panel.getLocationOnScreen(panelPoint); panelPoint[0] += 20; panelPoint[1] += 20; });
            long held = SystemClock.uptimeMillis();
            pointer(test, held, MotionEvent.ACTION_DOWN, panelPoint[0], panelPoint[1]);
            SystemClock.sleep(11000);
            menu(test, target, R.id.overlay_menu, true);
            pointer(test, held, MotionEvent.ACTION_UP, panelPoint[0], panelPoint[1]);
            menu(test, target, R.id.overlay_menu, true);
            SystemClock.sleep(11000);
            menu(test, target, R.id.overlay_menu, false);
            // Keep the existing remote contract available in the touchscreen APK too.
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_MENU);
            menu(test, target, R.id.overlay_menu, true);
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);
            SystemClock.sleep(300);
            menu(test, target, R.id.overlay_menu, false);
            result.putString("touchscreen", "PASS: slow right/left, vertical/horizontal cancel, multi-touch suppression, system-bar-safe bounds, tap, persisted main/submenu settings, panel scrolling, hold/release timeout, touch navigation and D-pad");
            code = Activity.RESULT_OK;
        } catch (Throwable failure) {
            result.putString("failure", android.util.Log.getStackTraceString(failure));
        } finally {
            if (activity != null) { Activity target = activity; onUi(test, target::finish); }
            test.finish(code, result);
        }
    }
}
