package com.example.projectm.visualizer;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;

/** Optional microphone input for TV. Android routes an attached USB microphone through MIC. */
final class TvAudioInput {
    private static final String PREF = "tv_audio_input";
    private final Activity activity;
    private final SharedPreferences prefs;
    private final Runnable changed;
    private PhonePcmCapture microphone;
    private boolean resumed;
    private boolean automaticPlayback;
    private String status = "Tap to start";

    TvAudioInput(Activity activity, SharedPreferences prefs, Runnable changed) {
        this.activity = activity;
        this.prefs = prefs;
        this.changed = changed;
    }

    private String mode() { return prefs.getString(PREF, "playback"); }
    boolean automatic() { return "automatic".equals(mode()); }
    boolean microphoneSelected() { return "microphone".equals(mode()); }
    boolean usingMicrophone() { return microphoneSelected() || (automatic() && !automaticPlayback); }

    String label() {
        if (automatic()) return "Automatic · " + (automaticPlayback ? "TV playback" : microphoneLabel());
        return microphoneSelected() ? microphoneLabel() : "TV playback";
    }

    private String microphoneLabel() { return "Microphone · " + (microphone == null ? status : microphone.status()); }

    void choose() {
        new AlertDialog.Builder(activity, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle("Audio input")
                .setSingleChoiceItems(new String[]{"TV playback", "Microphone (USB or built-in)", "Automatic"},
                        automatic() ? 2 : microphoneSelected() ? 1 : 0, (dialog, index) -> {
                            dialog.dismiss();
                            select(index == 0 ? "playback" : index == 1 ? "microphone" : "automatic");
                        })
                .setNegativeButton("Cancel", null).show();
    }

    private void select(String mode) {
        stop();
        automaticPlayback = false;
        prefs.edit().putString(PREF, mode).apply();
        if (!"playback".equals(mode) && activity.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            activity.requestPermissions(new String[]{android.Manifest.permission.RECORD_AUDIO}, 1);
            status = "Permission needed";
            changed.run();
            return;
        }
        if (!"playback".equals(mode)) start();
        changed.run();
    }

    void permissionGranted() { if (resumed && usingMicrophone()) start(); }

    void resume() { resumed = true; if (usingMicrophone()) start(); }

    void usePlayback() {
        automaticPlayback = true;
        stop();
    }

    void useMicrophone() {
        automaticPlayback = false;
        if (resumed && !microphoneSelected() && !automatic()) return;
        start();
    }

    void pause() { resumed = false; stop(); automaticPlayback = false; }

    private void start() {
        if (!resumed || microphone != null) return;
        microphone = PhonePcmCapture.microphone();
        status = "Starting";
    }

    private void stop() {
        if (microphone != null) { microphone.stop(); microphone = null; }
        status = "Tap to start";
    }
}
