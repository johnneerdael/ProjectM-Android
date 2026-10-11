package com.example.projectm.visualizer;

import org.junit.Test;
import static org.junit.Assert.*;

/** An F-Droid updater must need neither Android context nor a worker. */
public class UpdaterTest {
    @Test public void noContextOrPreferencesNeededToDisableUpdater() {
        Updater updater = null;
        try { updater = Updater.get(null, null); } catch (RuntimeException absentVariant) { }
        assertNotNull("F-Droid updater must not initialize Android/network state", updater);
        assertTrue(updater.isViaFDroid());
        updater.setEnabled(true);
        assertFalse(updater.isEnabled());
        assertNull(updater.readyVersion());
        assertFalse(updater.install(null));
        updater.onResume();
        updater.onPause();
        assertEquals("Updates via F-Droid", updater.statusLabel());
    }
}
