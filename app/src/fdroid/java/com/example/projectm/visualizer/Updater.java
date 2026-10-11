package com.example.projectm.visualizer;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;

/** F-Droid owns app updates. This implementation creates no workers, requests or installers. */
final class Updater {
    interface Listener { void onUpdateReady(String version); }
    private static final Updater INSTANCE = new Updater();
    private Updater() { }
    static Updater get(Context context, SharedPreferences prefs) { return INSTANCE; }
    void attach(Handler main, Listener listener) { }
    void detach(Listener listener) { }
    boolean isViaFDroid() { return true; }
    boolean isEnabled() { return false; }
    void setEnabled(boolean enabled) { }
    String readyVersion() { return null; }
    String statusLabel() { return "Updates via F-Droid"; }
    void onResume() { }
    void onPause() { }
    boolean install(Activity activity) { return false; }
}
