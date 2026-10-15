package com.example.projectm.visualizer;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class UpdaterTest {
    @Test
    public void defaultEnabledStillHonorsExplicitOff() throws Exception {
        java.lang.reflect.Method method = null;
        try { method = Updater.class.getDeclaredMethod("enabledPreference", android.content.SharedPreferences.class); }
        catch (NoSuchMethodException missing) { }
        org.junit.Assert.assertNotNull("explicit GitHub update preference policy missing", method);
        for (Boolean stored : new Boolean[]{null, Boolean.FALSE, Boolean.TRUE}) {
            android.content.SharedPreferences preferences = (android.content.SharedPreferences) java.lang.reflect.Proxy.newProxyInstance(
                    getClass().getClassLoader(), new Class<?>[]{android.content.SharedPreferences.class},
                    (proxy, called, args) -> called.getName().equals("getBoolean") ? stored == null ? args[1] : stored : null);
            org.junit.Assert.assertEquals(stored == null || stored, method.invoke(null, preferences));
        }
    }
    @Test
    public void updatesStayOnTheInstalledPlatform() {
        assertEquals(BuildConfig.TOUCHSCREEN ? "projectM-Android-2.3.40.apk" : "projectM-TV-2.3.40.apk",
                Updater.apkName("2.3.40"));
    }

    @Test
    public void versionFromTheLatestReleaseRedirect() {
        assertEquals("1.9.18", Updater.versionFromTagUrl("https://github.com/johnneerdael/ProjectM-TV/releases/tag/v1.9.18"));
        assertEquals("2.0", Updater.versionFromTagUrl("https://github.com/johnneerdael/ProjectM-TV/releases/tag/v2.0/"));
        assertNull(Updater.versionFromTagUrl("https://github.com/johnneerdael/ProjectM-TV/releases"));
        assertNull(Updater.versionFromTagUrl("https://github.com/johnneerdael/ProjectM-TV/releases/tag/nightly"));
        assertNull(Updater.versionFromTagUrl("https://github.com/johnneerdael/ProjectM-TV/releases/tag/v1.9.18-beta"));
    }

    @Test
    public void followsOnlyARenamedRepositorysLatestRelease() {
        assertEquals("https://github.com/per-young/ProjectM-Android/releases/latest",
                Updater.latestUrlOfRenamedRepo("https://github.com/per-young/ProjectM-Android/releases/latest"));
        assertNull(Updater.latestUrlOfRenamedRepo("https://github.com/johnneerdael/ProjectM-Android/releases/latest"));
        assertNull(Updater.latestUrlOfRenamedRepo("https://github.com/someone-else/ProjectM-Android/releases/latest"));
        assertNull(Updater.latestUrlOfRenamedRepo("http://github.com/johnneerdael/ProjectM-Android/releases/latest"));
        assertNull(Updater.latestUrlOfRenamedRepo("https://github.com/johnneerdael/ProjectM-Android/releases"));
        assertNull(Updater.latestUrlOfRenamedRepo("https://example.com/johnneerdael/ProjectM-Android/releases/latest"));
        assertNull(Updater.latestUrlOfRenamedRepo(null));
    }

    @Test
    public void versionsCompareNumerically() {
        assertTrue(Updater.compareVersions("1.9.10", "1.9.9") > 0);
        assertTrue(Updater.compareVersions("1.10", "1.9.18") > 0);
        assertTrue(Updater.compareVersions("1.9.18", "1.9.19") < 0);
        assertEquals(0, Updater.compareVersions("1.9", "1.9.0"));
        assertEquals(0, Updater.compareVersions("1.9.19-ci.42", "1.9.19"));
    }

    @Test
    public void totalSizeFromAResumedDownload() {
        assertEquals(41518462L, Updater.totalFromContentRange("bytes 1000-41518461/41518462"));
        assertEquals(-1L, Updater.totalFromContentRange("bytes 1000-41518461/*"));
        assertEquals(-1L, Updater.totalFromContentRange(null));
    }

    @Test
    public void ciSuffixIsIgnored() {
        assertEquals("1.9.19", Updater.stripSuffix("1.9.19-ci.42"));
        assertEquals("1.9.19", Updater.stripSuffix("1.9.19"));
    }

    @Test
    public void checksAreDueEverySixHours() {
        long hour = 60 * 60 * 1000L, checkedAt = 1_000_000_000_000L;
        assertEquals(6 * hour, Updater.untilNextCheck(checkedAt, checkedAt));
        assertEquals(hour, Updater.untilNextCheck(checkedAt, checkedAt + 5 * hour));
        assertEquals(0, Updater.untilNextCheck(checkedAt, checkedAt + 6 * hour));
        assertEquals(0, Updater.untilNextCheck(0, checkedAt));             // never checked
        assertEquals(0, Updater.untilNextCheck(checkedAt, checkedAt - 1)); // clock went back
    }
}
