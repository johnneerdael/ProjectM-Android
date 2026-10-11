package com.example.projectm.visualizer;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.KeyEvent;
import android.view.View;
import nl.neerdael.projectm.core.ProjectMJNI;

/** Default TV APK regression for focus scrolling and lifecycle after sharing touch-capable panels. */
final class TvMenuSetupTest {
    private static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
    private static void onUi(Instrumentation test, Runnable action) {
        Throwable[] failure = new Throwable[1];
        test.runOnMainSync(() -> { try { action.run(); } catch (Throwable error) { failure[0] = error; } });
        if (failure[0] != null) throw new AssertionError("UI assertion", failure[0]);
    }
    private static void focus(Instrumentation test, Activity activity, int id, int direction) {
        for (int i = 0; i < 30; i++) {
            boolean[] focused = new boolean[1];
            onUi(test, () -> focused[0] = activity.findViewById(id).hasFocus());
            if (focused[0]) {
                onUi(test, () -> {
                    View row = activity.findViewById(id);
                    android.graphics.Rect visible = new android.graphics.Rect();
                    check(row.getGlobalVisibleRect(visible) && visible.height() == row.getHeight(), "focused row clipped: " + id);
                });
                return;
            }
            test.sendKeyDownUpSync(direction); SystemClock.sleep(100);
        }
        throw new AssertionError("D-pad did not reach row " + id);
    }
    static void run(Instrumentation test) {
        Bundle result = new Bundle(); Activity activity = null; int code = Activity.RESULT_CANCELED;
        try {
            check(!BuildConfig.TOUCHSCREEN && test.getTargetContext().getPackageName().endsWith(".setuptest"), "requires default TV setup APK");
            SharedPreferences prefs = test.getTargetContext().getSharedPreferences("projectm_settings", 0);
            prefs.edit().putBoolean("track_access_explained", true).putBoolean("auto_change_enabled", false).commit();
            activity = test.startActivitySync(new Intent(test.getTargetContext(), MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            Activity target = activity;
            SystemClock.sleep(1000);
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_MENU); SystemClock.sleep(300);
            onUi(test, () -> check(target.findViewById(R.id.row_audio_input).getVisibility() == View.GONE, "phone input exposed on TV"));
            focus(test, target, R.id.row_advanced, KeyEvent.KEYCODE_DPAD_DOWN);
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_DPAD_CENTER); SystemClock.sleep(300);
            focus(test, target, R.id.row_last_exit, KeyEvent.KEYCODE_DPAD_DOWN);
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_BACK); SystemClock.sleep(300);
            focus(test, target, R.id.row_track_display, KeyEvent.KEYCODE_DPAD_UP);
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_DPAD_CENTER); SystemClock.sleep(300);
            focus(test, target, R.id.row_track_pill, KeyEvent.KEYCODE_DPAD_DOWN);
            boolean before = prefs.getBoolean("track_pill", false);
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_DPAD_RIGHT);
            check(prefs.getBoolean("track_pill", false) != before, "TV D-pad did not persist value");
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_BACK); SystemClock.sleep(300);
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_MENU); SystemClock.sleep(300);
            onUi(test, () -> check(target.findViewById(R.id.overlay_menu).getVisibility() == View.GONE, "Menu did not close"));
            test.sendKeyDownUpSync(KeyEvent.KEYCODE_HOME); SystemClock.sleep(500);
            long frame = ProjectMJNI.getRenderedFrameSerial();
            test.getTargetContext().startActivity(new Intent(test.getTargetContext(), MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            long until = SystemClock.elapsedRealtime() + 10000;
            while (ProjectMJNI.getRenderedFrameSerial() <= frame && SystemClock.elapsedRealtime() < until) SystemClock.sleep(100);
            check(ProjectMJNI.getRenderedFrameSerial() > frame, "renderer did not resume after Home");
            result.putString("tv_menu", "PASS: default TV main/Advanced/Track D-pad focus and scrolling, persisted value, Back/Menu, no phone source row, Home/resume frames");
            code = Activity.RESULT_OK;
        } catch (Throwable failure) { result.putString("failure", android.util.Log.getStackTraceString(failure)); }
        finally { if (activity != null) { Activity target = activity; onUi(test, target::finish); } test.finish(code, result); }
    }
}
