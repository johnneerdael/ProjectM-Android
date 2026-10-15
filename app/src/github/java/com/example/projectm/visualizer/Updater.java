package com.example.projectm.visualizer;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.Process;
import android.os.SystemClock;
import android.util.Log;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.DateFormat;
import java.util.Arrays;
import java.util.Date;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Auto-update from the GitHub releases (Settings › Advanced › Auto-update, on by default). While
 * it is off, the app opens no network connection. While it is on, the app checks whether a newer
 * release exists at every launch and every 6 hours while it stays in the foreground, downloads its
 * APK in the background, checks that it is this app, newer and signed with the same key, and then
 * offers to install it. Installing always goes through Android's installer, which asks the user to
 * confirm (and, the first time, to allow installs from this app). Apps installed by an F-Droid
 * client are updated by F-Droid instead.
 */
final class Updater {
    interface Listener { void onUpdateReady(String version); }

    private static final String TAG = "ProjectMTV";
    static final String REPO = "https://github.com/per-young/ProjectM-Android";
    static final String APK_MIME = "application/vnd.android.package-archive";
    private static final String PREF_ENABLED = "auto_update";
    private static final String PREF_CHECKED_AT = "update_checked_at";
    private static final long CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000L;
    private static final long CHECK_DELAY_MS = 10000;  // after launch: startup work goes first
    private static final int TIMEOUT_MS = 30000;
    private static final int DOWNLOAD_ATTEMPTS = 5;       // per check; the part downloaded is kept
    private static final long RETRY_DELAY_MS = 5000;      // times the attempt number
    // adb shell setprop debug.projectmtv.update_from 1.9.17: act as if that version were installed
    // (and accept a download with the installed version code), to test updating end to end.
    private static final String TEST_PROPERTY = "debug.projectmtv.update_from";
    private static final String[] FDROID_CLIENTS = {
            "org.fdroid.fdroid", "org.fdroid.basic", "org.fdroid.fdroid.privileged",
            "com.looker.droidify", "com.machiav3lli.fdroid"};
    private static final Pattern APK_NAME = Pattern.compile(Pattern.quote(BuildConfig.APK_PREFIX) + "([0-9][0-9.]*)\\.apk");

    private static Updater instance;

    private final Context context;
    private final SharedPreferences prefs;
    private final boolean viaFDroid;
    private final Handler worker;
    private volatile Handler main;
    private volatile Listener listener;
    private volatile String status;
    private volatile String readyVersion;
    private volatile boolean resumed;
    private volatile boolean launchCheckDue;  // every launch checks once, however recent the last check

    /**
     * One per process, so an activity that is being destroyed and its successor never download into
     * the same folder at once. The activity attaches its listener with {@link #attach}.
     */
    static synchronized Updater get(Context context, SharedPreferences prefs) {
        if (instance == null) instance = new Updater(context.getApplicationContext(), prefs);
        return instance;
    }

    private Updater(Context context, SharedPreferences prefs) {
        this.context = context;
        this.prefs = prefs;
        viaFDroid = installedByFDroid(context);
        status = viaFDroid ? "via F-Droid" : isEnabled() ? "waiting" : "off";
        HandlerThread thread = new HandlerThread("Updater", Process.THREAD_PRIORITY_BACKGROUND);
        thread.start();
        worker = new Handler(thread.getLooper());
    }

    /** {@code listener} hears about a ready update on {@code main}'s thread. */
    void attach(Handler main, Listener listener) {
        this.main = main;
        this.listener = listener;
        launchCheckDue = true;
    }

    /** The activity is gone: no more callbacks to it, and no check is started for it. */
    void detach(Listener listener) {
        if (this.listener != listener) return;
        this.listener = null;
        worker.removeCallbacks(dueCheck);
    }

    boolean isViaFDroid() { return viaFDroid; }

    boolean isEnabled() { return !viaFDroid && enabledPreference(prefs); }
    static boolean enabledPreference(SharedPreferences prefs) { return prefs.getBoolean(PREF_ENABLED, true); }

    /** The version downloaded and ready to install, or null. */
    String readyVersion() { return readyVersion; }

    /** One line for the diagnostics. */
    String statusLabel() { return status; }

    /**
     * At every resume: announces a downloaded update right away (no network needed; e.g. after
     * Android restarted the app because the user allowed installs from it), and checks GitHub at
     * launch or when the interval has passed. While resumed, the checks repeat every interval.
     */
    void onResume() {
        resumed = true;
        if (!isEnabled()) return;
        worker.post(announceDownloaded);
        schedule(CHECK_DELAY_MS);
    }

    /** In the background: no checks until the next resume. */
    void onPause() {
        resumed = false;
        worker.removeCallbacks(dueCheck);
    }

    private final Runnable announceDownloaded = () -> {
        if (!isEnabled()) return;
        String ready = cleanUp(installedVersion(testVersion()));
        if (ready != null) announce(ready);
    };

    void setEnabled(boolean enabled) {
        if (viaFDroid) return;
        prefs.edit().putBoolean(PREF_ENABLED, enabled).apply();
        worker.removeCallbacks(dueCheck);
        if (enabled) {
            status = "waiting";
            worker.post(() -> check(true));  // switched on: look right away
        } else {
            readyVersion = null;
            status = "off";
            worker.post(() -> {  // after a running check, which stops by itself
                deleteAll(updatesDir());
                deleteAll(downloadDir());
                readyVersion = null;
                status = "off";
            });
        }
    }

    /**
     * Hands the downloaded APK to Android's installer, which asks to confirm. Returns false when
     * nothing is ready or no installer can be opened.
     */
    boolean install(Activity activity) {
        String version = readyVersion;
        if (version == null) return false;
        File apk = new File(updatesDir(), apkName(version));
        if (!apk.isFile()) return false;
        Uri uri;
        if (Build.VERSION.SDK_INT >= 24) {
            uri = UpdateFileProvider.uriFor(context, apk.getName());
        } else {
            // Android 5-6: the installer only reads files, so this one (and its folder) must be readable.
            apk.setReadable(true, false);
            apk.getParentFile().setExecutable(true, false);
            uri = Uri.fromFile(apk);
        }
        @SuppressWarnings("deprecation")  // ACTION_VIEW might open another app on some TVs
        Intent intent = new Intent(Intent.ACTION_INSTALL_PACKAGE)
                .setDataAndType(uri, APK_MIME)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try {
            activity.startActivity(intent);
            Log.i(TAG, "Update: installer opened for " + version);
            return true;
        } catch (ActivityNotFoundException | SecurityException e) {
            Log.w(TAG, "Update: no installer (" + e + ")");
            return false;
        }
    }

    private final Runnable dueCheck = () -> {
        if (resumed) check(false);
    };

    private void schedule(long delayMs) {
        worker.removeCallbacks(dueCheck);
        worker.postDelayed(dueCheck, Math.max(delayMs, CHECK_DELAY_MS));
    }

    /** The next check while resumed, also after a failed one. */
    private void scheduleNext(long delayMs) {
        if (resumed && isEnabled()) schedule(delayMs);
    }

    /** On the worker thread. */
    private void check(boolean force) {
        if (!isEnabled()) return;
        String test = testVersion();
        String installed = installedVersion(test);
        String ready = cleanUp(installed);
        if (ready != null) announce(ready);
        long checkedAt = prefs.getLong(PREF_CHECKED_AT, 0);
        long now = System.currentTimeMillis();
        long wait = untilNextCheck(checkedAt, now);
        if (!force && !launchCheckDue && wait > 0) {
            if (ready == null) status = "up to date, checked " + time(checkedAt);
            scheduleNext(wait);
            return;
        }
        launchCheckDue = false;
        status = "checking";
        try {
            String latest = latestVersion(installed);
            if (!isEnabled()) return;  // switched off while asking
            String current = ready != null ? ready : installed;
            if (compareVersions(latest, current) <= 0) {
                // Only a completed check counts: a failure is retried at the next launch or interval.
                prefs.edit().putLong(PREF_CHECKED_AT, now).apply();
                status = ready != null ? ready + " ready to install" : "up to date, checked " + time(now);
                Log.i(TAG, "Update: latest release is " + latest + ", installed " + installed);
                return;
            }
            Log.i(TAG, "Update: " + latest + " available (installed " + installed + "), downloading");
            File apk = download(latest, installed, test != null);
            if (apk == null) return;  // switched off meanwhile
            deleteAll(updatesDir());  // an older download
            File target = new File(updatesDir(), apk.getName());
            if (!updatesDir().mkdirs() && !updatesDir().isDirectory() || !apk.renameTo(target)) {
                throw new IOException("cannot store the download");
            }
            prefs.edit().putLong(PREF_CHECKED_AT, now).apply();
            announce(latest);
        } catch (IOException | RuntimeException e) {
            status = "check failed (" + e.getMessage() + "), trying again later";
            Log.w(TAG, "Update: " + e);
        } finally {
            scheduleNext(CHECK_INTERVAL_MS);
        }
    }

    private void announce(String version) {
        if (!isEnabled()) return;
        readyVersion = version;
        status = version + " ready to install";
        Handler handler = main;
        if (handler == null) return;
        handler.post(() -> {
            Listener current = listener;
            if (current != null && version.equals(readyVersion)) current.onUpdateReady(version);
        });
    }

    /** Version of the newest release: GitHub redirects releases/latest to its tag. */
    private static String latestVersion(String installed) throws IOException {
        String url = REPO + "/releases/latest";
        // A renamed repository first redirects to its new /releases/latest, then to the tag.
        for (int hop = 0; ; hop++) {
            HttpURLConnection connection = open(url, installed);
            try {
                connection.setInstanceFollowRedirects(false);
                connection.setRequestMethod("HEAD");
                int code = connection.getResponseCode();
                String location = connection.getHeaderField("Location");
                String version = location != null ? versionFromTagUrl(location) : null;
                if (code / 100 == 3 && version != null) return version;
                String renamed = code / 100 == 3 && hop < 2 ? latestUrlOfRenamedRepo(location) : null;
                if (renamed == null) throw new IOException("HTTP " + code + " " + location);
                url = renamed;
            } finally {
                connection.disconnect();
            }
        }
    }

    /**
     * Downloads and verifies the release APK; null if switched off meanwhile. TV Wi-Fi often stalls
     * for longer than the read timeout, so the part already downloaded is kept: the next attempt
     * (a few per check, and at the next launch) asks only for the rest.
     */
    private File download(String version, String installed, boolean testing) throws IOException {
        File dir = downloadDir();
        if (!dir.mkdirs() && !dir.isDirectory()) throw new IOException("no download folder");
        File apk = new File(dir, apkName(version));
        File[] others = dir.listFiles();
        if (others != null) for (File file : others) if (!file.equals(apk)) file.delete();
        for (int attempt = 1; ; attempt++) {
            if (!isEnabled()) return null;
            try {
                if (downloadRest(version, installed, apk)) break;
                return null;  // switched off
            } catch (IOException e) {
                if (attempt >= DOWNLOAD_ATTEMPTS) throw e;
                Log.w(TAG, "Update: download interrupted at " + apk.length() / 1024 + " KB (" + e
                        + "), resuming");
                SystemClock.sleep(RETRY_DELAY_MS * attempt);
            }
        }
        String problem = verify(apk, testing);
        if (problem != null) {
            apk.delete();
            throw new IOException("download rejected: " + problem);
        }
        return apk;
    }

    /** One attempt: appends the rest of the APK to {@code apk}. False if switched off meanwhile. */
    private boolean downloadRest(String version, String installed, File apk) throws IOException {
        long have = apk.length();
        HttpURLConnection connection = open(REPO + "/releases/download/v" + version + "/" + apkName(version),
                installed);
        try {
            if (have > 0) connection.setRequestProperty("Range", "bytes=" + have + "-");
            int code = connection.getResponseCode();
            long total;
            if (code == HttpURLConnection.HTTP_PARTIAL && have > 0) {
                total = totalFromContentRange(connection.getHeaderField("Content-Range"));
            } else if (code == 416 && have > 0) {  // nothing left: the file is complete (or broken)
                return true;
            } else if (code == HttpURLConnection.HTTP_OK) {
                have = 0;  // no resume: start over
                total = parseLong(connection.getHeaderField("Content-Length"));
            } else {
                throw new IOException("HTTP " + code);
            }
            // Room for the download and for Android's copy while installing.
            if (total > 0 && apk.getParentFile().getUsableSpace() < (total - have) + total * 2) {
                throw new IOException("not enough storage");
            }
            long written = have;
            int lastPercent = -1;
            byte[] buffer = new byte[64 * 1024];
            try (InputStream in = connection.getInputStream(); OutputStream out = new FileOutputStream(apk, have > 0)) {
                for (int n; (n = in.read(buffer)) > 0; ) {
                    if (!isEnabled()) return false;
                    out.write(buffer, 0, n);
                    written += n;
                    int percent = total > 0 ? (int) (written * 100 / total) : -1;
                    if (percent != lastPercent) {
                        lastPercent = percent;
                        status = "downloading " + version + (percent >= 0 ? " (" + percent + "%)" : "");
                    }
                }
            }
            if (total > 0 && written != total) throw new IOException("download incomplete");
            return true;
        } finally {
            connection.disconnect();
        }
    }

    /** Null if the APK is this app, newer than the installed one and signed with the same key. */
    @SuppressWarnings("deprecation")  // GET_SIGNATURES: also on Android 5-8; the key does not rotate
    private String verify(File apk, boolean testing) {
        PackageManager pm = context.getPackageManager();
        PackageInfo archive = pm.getPackageArchiveInfo(apk.getPath(), PackageManager.GET_SIGNATURES);
        if (archive == null) return "not an APK";
        if (!context.getPackageName().equals(archive.packageName)) return "another app (" + archive.packageName + ")";
        PackageInfo installed;
        try {
            installed = pm.getPackageInfo(context.getPackageName(), PackageManager.GET_SIGNATURES);
        } catch (PackageManager.NameNotFoundException e) {
            return "own package not found";
        }
        long code = versionCode(archive), installedCode = versionCode(installed);
        if (code < installedCode || code == installedCode && !testing) {
            return "version code " + code + " is not newer than " + installedCode;
        }
        if (archive.signatures == null || archive.signatures.length == 0
                || !Arrays.equals(archive.signatures, installed.signatures)) {
            return "signed with another key";
        }
        return null;
    }

    /**
     * Removes unfinished downloads and downloads that are not newer than the installed version.
     * Returns the version still ready to install, or null.
     */
    private String cleanUp(String installed) {
        File[] partial = downloadDir().listFiles();
        if (partial != null) {
            for (File file : partial) {
                Matcher m = APK_NAME.matcher(file.getName());
                if (!m.matches() || compareVersions(m.group(1), installed) <= 0) file.delete();
            }
        }
        String ready = null;
        File[] files = updatesDir().listFiles();
        if (files == null) return null;
        for (File file : files) {
            Matcher m = APK_NAME.matcher(file.getName());
            if (m.matches() && compareVersions(m.group(1), installed) > 0 && ready == null) {
                ready = m.group(1);
            } else if (!file.delete()) {
                Log.w(TAG, "Update: cannot delete " + file);
            }
        }
        return ready;
    }

    private File updatesDir() { return new File(context.getNoBackupFilesDir(), "updates"); }

    private File downloadDir() { return new File(context.getNoBackupFilesDir(), "update-download"); }

    static File updateFile(Context context, String name) {
        return APK_NAME.matcher(name).matches()
                ? new File(new File(context.getNoBackupFilesDir(), "updates"), name) : null;
    }

    static String apkName(String version) { return BuildConfig.APK_PREFIX + version + ".apk"; }

    private static void deleteAll(File dir) {
        File[] files = dir.listFiles();
        if (files != null) for (File file : files) file.delete();
    }

    private static HttpURLConnection open(String url, String installed) throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setConnectTimeout(TIMEOUT_MS);
        connection.setReadTimeout(TIMEOUT_MS);
        connection.setUseCaches(false);
        connection.setRequestProperty("User-Agent", "ProjectM-TV/" + installed);
        return connection;
    }

    /** The installed version name without a CI suffix (1.9.19-ci.12 → 1.9.19). */
    private String installedVersion(String test) {
        if (test != null) return test;
        try {
            String name = context.getPackageManager().getPackageInfo(context.getPackageName(), 0).versionName;
            return name != null ? stripSuffix(name) : "0";
        } catch (PackageManager.NameNotFoundException e) {
            return "0";
        }
    }

    private static String testVersion() {
        java.lang.Process p = null;
        try {
            p = new ProcessBuilder("getprop", TEST_PROPERTY).redirectErrorStream(true).start();
            p.getOutputStream().close();
            try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream()))) {
                String value = r.readLine();
                return value != null && value.trim().matches("[0-9][0-9.]*") ? value.trim() : null;
            }
        } catch (IOException e) {
            return null;
        } finally {
            if (p != null) p.destroy();
        }
    }

    @SuppressWarnings("deprecation")
    private static long versionCode(PackageInfo info) {
        return Build.VERSION.SDK_INT >= 28 ? info.getLongVersionCode() : info.versionCode;
    }

    @SuppressWarnings("deprecation")
    private static boolean installedByFDroid(Context context) {
        String installer;
        try {
            PackageManager pm = context.getPackageManager();
            installer = Build.VERSION.SDK_INT >= 30
                    ? pm.getInstallSourceInfo(context.getPackageName()).getInstallingPackageName()
                    : pm.getInstallerPackageName(context.getPackageName());
        } catch (PackageManager.NameNotFoundException | IllegalArgumentException e) {
            return false;
        }
        return installer != null && Arrays.asList(FDROID_CLIENTS).contains(installer);
    }

    private static String time(long millis) {
        return DateFormat.getTimeInstance(DateFormat.SHORT).format(new Date(millis));
    }

    private static long parseLong(String value) {
        try {
            return value != null ? Long.parseLong(value.trim()) : -1;
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    // --- pure helpers, unit-tested ---

    /** Milliseconds until the next check is due; 0 if due now, also when the clock went back. */
    static long untilNextCheck(long checkedAt, long now) {
        return checkedAt > now || now - checkedAt >= CHECK_INTERVAL_MS ? 0 : checkedAt + CHECK_INTERVAL_MS - now;
    }

    /** "bytes 100-199/1000" → 1000; -1 if unknown. */
    static long totalFromContentRange(String contentRange) {
        if (contentRange == null) return -1;
        int slash = contentRange.lastIndexOf('/');
        return slash >= 0 ? parseLong(contentRange.substring(slash + 1)) : -1;
    }

    /** "https://github.com/…/releases/tag/v1.9.18" → "1.9.18"; null for anything else. */
    static String versionFromTagUrl(String url) {
        Matcher m = Pattern.compile("/releases/tag/v([0-9]+(?:\\.[0-9]+)*)/?$").matcher(url.trim());
        return m.find() ? m.group(1) : null;
    }

    /** "https://github.com/per-young/<repo>/releases/latest" → itself; null for another owner. */
    static String latestUrlOfRenamedRepo(String location) {
        return location != null
                && location.trim().matches("https://github\\.com/per-young/[A-Za-z0-9._-]+/releases/latest/?")
                ? location.trim() : null;
    }

    static String stripSuffix(String versionName) {
        int dash = versionName.indexOf('-');
        return dash >= 0 ? versionName.substring(0, dash) : versionName;
    }

    /** Compares dotted version numbers numerically: 1.9.10 > 1.9.9, 1.10 > 1.9.18, 1.9 == 1.9.0. */
    static int compareVersions(String a, String b) {
        String[] x = stripSuffix(a).split("\\."), y = stripSuffix(b).split("\\.");
        for (int i = 0; i < Math.max(x.length, y.length); i++) {
            long p = i < x.length ? parseLong(x[i]) : 0, q = i < y.length ? parseLong(y[i]) : 0;
            if (p != q) return p < q ? -1 : 1;
        }
        return 0;
    }
}
