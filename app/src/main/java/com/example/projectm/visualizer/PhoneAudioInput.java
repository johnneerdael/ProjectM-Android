package com.example.projectm.visualizer;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.widget.Toast;

/** Activity-owned input selection; microphone and playback capture never run together. */
final class PhoneAudioInput {
    static final int CONSENT_REQUEST = 2;
    private static final String PREF = "phone_audio_input";
    private final Activity activity;
    private final SharedPreferences prefs;
    private PhonePcmCapture microphone;
    private Intent consent;
    private boolean resumed;
    private boolean requesting;
    private String message = "Tap to start";

    PhoneAudioInput(Activity activity, SharedPreferences prefs) { this.activity = activity; this.prefs = prefs; }
    private boolean playback() { return "playback".equals(prefs.getString(PREF, "microphone")); }
    private boolean permitted() {
        return Build.VERSION.SDK_INT < 23 || activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
    }
    String label() {
        return playback() ? "Phone playback · " + PhonePlaybackService.status()
                : "Microphone · " + (microphone == null ? message : microphone.status());
    }
    long samples() { return playback() ? PhonePlaybackService.samples() : microphone == null ? 0 : microphone.samples(); }
    void choose() {
        new AlertDialog.Builder(activity, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle("Audio input")
                .setSingleChoiceItems(new String[]{"Microphone", "Phone playback (Android 10+)"}, playback() ? 1 : 0,
                        (dialog, index) -> { dialog.dismiss(); select(index == 1); })
                .setNegativeButton("Cancel", null).show();
    }
    private void select(boolean playback) {
        if (playback && Build.VERSION.SDK_INT < 29) {
            Toast.makeText(activity, "Phone playback capture needs Android 10 or later", Toast.LENGTH_LONG).show(); return;
        }
        stop();
        prefs.edit().putString(PREF, playback ? "playback" : "microphone").apply();
        if (!permitted()) {
            activity.requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 1); return;
        }
        if (playback) requestPlayback(); else resume();
    }
    private void requestPlayback() {
        if (!resumed || requesting || Build.VERSION.SDK_INT < 29) return;
        try {
            requesting = true;
            activity.startActivityForResult(activity.getSystemService(MediaProjectionManager.class).createScreenCaptureIntent(), CONSENT_REQUEST);
        } catch (RuntimeException error) {
            requesting = false;
            Toast.makeText(activity, "Phone playback capture is unavailable", Toast.LENGTH_LONG).show();
        }
    }
    void permissionGranted() {
        if (!resumed) return;
        if (playback()) requestPlayback(); else resume();
    }
    void result(int resultCode, Intent data) {
        requesting = false;
        if (playback() && resultCode == Activity.RESULT_OK && data != null) consent = data;
        else message = "Tap to start";
        if (resumed) resume();
    }
    void resume() {
        resumed = true;
        if (!permitted()) { message = "Permission needed"; return; }
        if (playback()) {
            if (consent == null) return; // every new projection session requires fresh Android consent
            Intent data = consent; consent = null;
            try { activity.startForegroundService(new Intent(activity, PhonePlaybackService.class).putExtra(PhonePlaybackService.TOKEN, data)); }
            catch (RuntimeException error) {
                Toast.makeText(activity, "Phone playback capture could not start", Toast.LENGTH_LONG).show();
            }
        } else if (microphone == null) {
            if (!activity.getPackageManager().hasSystemFeature(PackageManager.FEATURE_MICROPHONE)) {
                message = "Unavailable"; return;
            }
            microphone = PhonePcmCapture.microphone();
        }
    }
    void pause() { resumed = false; stop(); }
    private void stop() {
        if (microphone != null) { microphone.stop(); microphone = null; }
        activity.stopService(new Intent(activity, PhonePlaybackService.class));
        consent = null;
        message = "Tap to start";
    }
}
