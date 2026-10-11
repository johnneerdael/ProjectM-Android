package com.example.projectm.visualizer;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.content.SharedPreferences;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.accessibility.AccessibilityNodeInfo;
import java.lang.reflect.Field;
import nl.neerdael.projectm.core.ProjectMJNI;

/** Real AudioRecord microphone reads, Android playback consent and capturable phone PCM. */
final class PhoneAudioSetupTest {
    private static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
    private static PhoneAudioInput input(Activity activity) throws Exception {
        Field field = MainActivity.class.getDeclaredField("phoneAudio"); field.setAccessible(true);
        return (PhoneAudioInput) field.get(activity);
    }
    private static android.app.UiAutomation automationForClick;
    private static boolean click(AccessibilityNodeInfo node, String text) {
        if (node == null) return false;
        try {
            if (text.equalsIgnoreCase(node.getText() == null ? "" : node.getText().toString())) {
                android.graphics.Rect bounds = new android.graphics.Rect(); node.getBoundsInScreen(bounds);
                android.app.UiAutomation automation = automationForClick;
                long down = SystemClock.uptimeMillis();
                android.view.MotionEvent press = android.view.MotionEvent.obtain(down, down, android.view.MotionEvent.ACTION_DOWN,
                        bounds.centerX(), bounds.centerY(), 0);
                android.view.MotionEvent release = android.view.MotionEvent.obtain(down, down + 50, android.view.MotionEvent.ACTION_UP,
                        bounds.centerX(), bounds.centerY(), 0);
                press.setSource(android.view.InputDevice.SOURCE_TOUCHSCREEN);
                release.setSource(android.view.InputDevice.SOURCE_TOUCHSCREEN);
                try { return automation.injectInputEvent(press, true) && automation.injectInputEvent(release, true); }
                finally { press.recycle(); release.recycle(); }
            }
            for (int i = 0; i < node.getChildCount(); i++) if (click(node.getChild(i), text)) return true;
            return false;
        } finally { node.recycle(); }
    }
    private static void clickText(Instrumentation test, String text) {
        long until = SystemClock.elapsedRealtime() + 10000;
        automationForClick = test.getUiAutomation();
        while (SystemClock.elapsedRealtime() < until) {
            if (click(automationForClick.getRootInActiveWindow(), text)) { SystemClock.sleep(500); return; }
            SystemClock.sleep(100);
        }
        throw new AssertionError("UI text not clickable: " + text);
    }
    private static void awaitSamples(PhoneAudioInput input) {
        long until = SystemClock.elapsedRealtime() + 10000;
        while (SystemClock.elapsedRealtime() < until) {
            if (input.samples() > 4096) return;
            SystemClock.sleep(100);
        }
        throw new AssertionError("no samples: " + input.label());
    }
    static void run(Instrumentation test) {
        Activity activity = null;
        AudioTrack player = null;
        Thread audio = null;
        java.util.concurrent.atomic.AtomicBoolean playing = new java.util.concurrent.atomic.AtomicBoolean(true);
        Bundle result = new Bundle(); int code = Activity.RESULT_CANCELED;
        try {
            test.getUiAutomation();
            check(BuildConfig.TOUCHSCREEN && android.os.Build.VERSION.SDK_INT >= 29, "needs Android 10+ touch build");
            check(test.getTargetContext().getPackageName().endsWith(".setuptest"), "requires isolated setup APK");
            SharedPreferences prefs = test.getTargetContext().getSharedPreferences("projectm_settings", 0);
            prefs.edit().putBoolean("track_access_explained", true).putBoolean("auto_change_enabled", false)
                    .putString("phone_audio_input", "microphone").commit();
            activity = test.startActivitySync(new Intent(test.getTargetContext(), MainActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
            Activity target = activity;
            PhoneAudioInput input = input(activity);
            awaitSamples(input);
            check(input.label().startsWith("Microphone"), "wrong microphone input");
            test.runOnMainSync(input::choose);
            clickText(test, "Phone playback (Android 10+)");
            clickText(test, "Cancel");
            check(PhonePlaybackService.samples() == 0, "denied consent started capture");
            test.runOnMainSync(input::choose);
            clickText(test, "Phone playback (Android 10+)");
            clickText(test, "Start now");
            awaitSamples(input);
            check(input.label().startsWith("Phone playback"), "wrong playback input");
            player = new AudioTrack.Builder().setAudioAttributes(new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .setAllowedCapturePolicy(AudioAttributes.ALLOW_CAPTURE_BY_ALL).build())
                    .setAudioFormat(new AudioFormat.Builder().setSampleRate(44100).setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                            .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                    .setBufferSizeInBytes(8192).setTransferMode(AudioTrack.MODE_STREAM).build();
            AudioTrack output = player;
            output.play();
            audio = new Thread(() -> {
                short[] pcm = new short[1024]; long offset = 0;
                while (playing.get()) {
                    for (int i = 0; i < pcm.length; i++) pcm[i] = (short) (16000 * Math.sin((offset + i) * 2 * Math.PI * 440 / 44100));
                    int written = output.write(pcm, 0, pcm.length);
                    if (written <= 0) break;
                    offset += written;
                }
            }, "PhonePlaybackTest");
            audio.start();
            long until = SystemClock.elapsedRealtime() + 10000;
            float peak = 0;
            while (SystemClock.elapsedRealtime() < until) {
                peak = Math.max(peak, ProjectMJNI.getAudioLevel());
                if (peak > .1f) break;
                SystemClock.sleep(100);
            }
            check(peak > .1f, "capturable phone audio never reached engine: " + peak);
            test.getUiAutomation().performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_HOME);
            SystemClock.sleep(1500);
            check(PhonePlaybackService.samples() == 0, "playback capture outlived activity pause");
            check(ProjectMJNI.getAudioLevel() == 0, "PCM continued after pause");
            test.getTargetContext().startActivity(new Intent(test.getTargetContext(), MainActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            SystemClock.sleep(500);
            check(PhonePlaybackService.samples() == 0, "resume reused old projection consent");
            test.runOnMainSync(input::choose);
            clickText(test, "Phone playback (Android 10+)");
            clickText(test, "Start now");
            awaitSamples(input);
            test.runOnMainSync(target::finish); activity = null;
            SystemClock.sleep(1500);
            check(PhonePlaybackService.samples() == 0, "restarted capture outlived activity");
            result.putString("phone_audio", "PASS: microphone AudioRecord samples, denied/granted Android playback consent, local 440Hz playback RMS=" + peak + ", Home/pause cleanup, fresh consent on resume and restart cleanup");
            code = Activity.RESULT_OK;
        } catch (Throwable failure) { result.putString("failure", android.util.Log.getStackTraceString(failure)); }
        finally {
            playing.set(false);
            if (player != null) { try { player.stop(); } catch (RuntimeException ignored) {} }
            if (audio != null) { try { audio.join(3000); } catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); } }
            if (player != null) player.release();
            if (activity != null) { Activity target = activity; test.runOnMainSync(target::finish); }
            test.finish(code, result);
        }
    }
}
