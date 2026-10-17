package com.example.projectm.visualizer;

/** Prefer the app-specific notification access view, then fall back for TV/OEM settings apps. */
final class TrackAccessNavigation {
    static final String DETAIL = "android.settings.NOTIFICATION_LISTENER_DETAIL_SETTINGS";
    static final String LIST = "android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS";
    static final String TV_PATH = "Settings › Device Preferences › Apps › Special app access › Notification access";
    static final String PHONE_PATH = "Settings › Apps › Special app access › Notification access";
    interface Launcher { boolean launch(String action); }

    /** Phones list Apps at the top level of Settings; Android TV nests it under Device Preferences. */
    static String settingsPath(boolean touchscreen) {
        return touchscreen ? PHONE_PATH : TV_PATH;
    }

    static boolean open(int apiLevel, Launcher launcher) {
        if (apiLevel >= 30 && launcher.launch(DETAIL)) return true;
        if (launcher.launch(LIST)) return true;
        if (launcher.launch("android.settings.APPLICATION_SETTINGS")) return true;
        return launcher.launch("android.settings.SETTINGS");
    }
}
