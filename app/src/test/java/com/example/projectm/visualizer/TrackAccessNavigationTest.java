package com.example.projectm.visualizer;

import org.junit.Test;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import static org.junit.Assert.*;

public class TrackAccessNavigationTest {
    @Test public void supportedPerAppPageStopsFallbacks() {
        List<String> attempts = new ArrayList<>();
        assertTrue(TrackAccessNavigation.open(30, action -> { attempts.add(action); return true; }));
        assertEquals(Arrays.asList("android.settings.NOTIFICATION_LISTENER_DETAIL_SETTINGS"), attempts);
    }
    @Test public void olderTvStartsAtNotificationAccessList() {
        List<String> attempts = new ArrayList<>();
        assertTrue(TrackAccessNavigation.open(28, action -> { attempts.add(action); return true; }));
        assertEquals(Arrays.asList("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS"), attempts);
    }
    @Test public void unavailableActivitiesFallBackInOrder() {
        List<String> attempts = new ArrayList<>();
        assertTrue(TrackAccessNavigation.open(34, action -> {
            attempts.add(action); return "android.settings.APPLICATION_SETTINGS".equals(action);
        }));
        assertEquals(Arrays.asList("android.settings.NOTIFICATION_LISTENER_DETAIL_SETTINGS",
                "android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS", "android.settings.APPLICATION_SETTINGS"), attempts);
    }
    @Test public void reportsNoAvailableSettingsActivity() {
        assertFalse(TrackAccessNavigation.open(28, action -> false));
    }
    @Test public void settingsPathMatchesDeviceType() {
        assertEquals("Settings › Apps › Special app access › Notification access", TrackAccessNavigation.settingsPath(true));
        assertEquals("Settings › Device Preferences › Apps › Special app access › Notification access", TrackAccessNavigation.settingsPath(false));
    }
}
