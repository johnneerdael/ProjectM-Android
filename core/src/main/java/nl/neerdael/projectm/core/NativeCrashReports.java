package nl.neerdael.projectm.core;

import android.content.Context;
import android.util.Log;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

import xcrash.TombstoneParser;
import xcrash.XCrash;

/** Local native crash capture shared by apps embedding the AAR. Reports never upload themselves. */
public final class NativeCrashReports {
    private static final String TAG = "NativeCrashReports";
    private static final String DIRECTORY = "projectm-crashes";
    private static final int MAX_REPORTS = 5;
    private static final int MAX_READ_BYTES = 256 * 1024;
    private static final int MAX_DISPLAY_CHARS = 32 * 1024;
    private static boolean attempted;
    private static volatile String status = "Native crash capture has not started";

    private NativeCrashReports() {}

    /** A bounded presentation of a saved tombstone; raw register/stack memory stays in app storage. */
    public static final class Report {
        public final String fileName;
        public final long timestampMs;
        public final String details;

        private Report(File file, String details) {
            this.fileName = file.getName();
            this.timestampMs = file.lastModified();
            this.details = details;
        }
    }

    /** Called once by ProjectMCore before native engine work. Keeps normal Android crash handling. */
    static synchronized void install(Context context) {
        if (attempted) return;
        attempted = true;
        File directory = directory(context);
        if (!directory.isDirectory() && !directory.mkdirs()) {
            status = "Native crash capture unavailable: cannot create report directory";
            return;
        }
        try {
            status = initializeCapture(context.getApplicationContext(), directory);
        } catch (RuntimeException | LinkageError error) {
            status = "Native crash capture unavailable: " + error.getClass().getSimpleName();
            Log.w(TAG, status, error);
        }
    }

    static String initializeCapture(Context context, File directory) {
        // xCrash returns OK without applying parameters after any earlier init,
        // even a failed one. Its supported loader callback proves this call ran
        // the native initialization path with our parameters rather than skipping it.
        boolean[] configuredHere = {false};
        int result = XCrash.init(context, new XCrash.InitParameters()
                .setLibLoader(name -> {
                    System.loadLibrary(name);
                    configuredHere[0] = true;
                })
                .setLogDir(directory.getAbsolutePath())
                .disableJavaCrashHandler().disableAnrCrashHandler().enableNativeCrashHandler()
                .setNativeRethrow(true).setNativeLogCountMax(MAX_REPORTS)
                .setNativeLogcatSystemLines(0).setNativeLogcatEventsLines(0).setNativeLogcatMainLines(0)
                .setNativeDumpFds(false).setNativeDumpNetwork(false).setNativeDumpMap(false)
                .setNativeDumpAllThreads(false).setNativeDumpElfHash(false));
        if (result != 0) return "Native crash capture unavailable (initialization " + result + ")";
        if (!configuredHere[0] || !directory.getAbsolutePath().equals(XCrash.getLogDir()))
            return "Native crash capture unavailable: xCrash was already initialized by another component";
        return "Native crash capture ready";
    }

    /** Current capture availability, including a failed native-library initialization. */
    public static String status() { return status; }

    /** Read up to five saved native reports, newest first. Call on a background thread. */
    public static List<Report> recent(Context context) {
        return readDirectory(directory(context));
    }

    /** Delete saved native reports only. Call on a background thread after the user selects Clear. */
    public static int clear(Context context) { return clearDirectory(directory(context)); }

    private static File directory(Context context) {
        return new File(context.getApplicationContext().getNoBackupFilesDir(), DIRECTORY);
    }

    private static File[] files(File directory) {
        File[] files = directory.listFiles(file -> file.isFile() && file.getName().startsWith("tombstone_")
                && file.getName().endsWith(".native.xcrash"));
        return files == null ? new File[0] : files;
    }

    static List<Report> readDirectory(File directory) {
        File[] files = files(directory);
        Arrays.sort(files, (left, right) -> {
            int time = Long.compare(right.lastModified(), left.lastModified());
            return time != 0 ? time : left.getName().compareTo(right.getName());
        });
        List<Report> reports = new ArrayList<>();
        for (File file : files) {
            if (reports.size() == MAX_REPORTS) break;
            try {
                byte[] buffer = new byte[4096];
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (FileInputStream input = new FileInputStream(file)) {
                    for (int read; bytes.size() < MAX_READ_BYTES && (read = input.read(buffer, 0,
                            Math.min(buffer.length, MAX_READ_BYTES - bytes.size()))) > 0;) bytes.write(buffer, 0, read);
                }
                String text = new String(bytes.toByteArray(), StandardCharsets.UTF_8);
                int zero = text.indexOf('\0');
                if (zero >= 0) text = text.substring(0, zero);
                if (text.trim().isEmpty()) continue;
                Map<String, String> fields = TombstoneParser.parse(null, text);
                StringBuilder details = new StringBuilder();
                append(details, "Crash time", fields.get(TombstoneParser.keyCrashTime));
                if (text.contains("\nApp version:")) append(details, "App version", fields.get(TombstoneParser.keyAppVersion));
                append(details, "ABI", fields.get(TombstoneParser.keyAbi));
                append(details, "Process", fields.get(TombstoneParser.keyProcessName));
                append(details, "Thread", fields.get(TombstoneParser.keyThreadName));
                append(details, "Signal", fields.get(TombstoneParser.keySignal));
                append(details, "Code", fields.get(TombstoneParser.keyCode));
                append(details, "Fault address", fields.get(TombstoneParser.keyFaultAddr));
                append(details, "Abort message", fields.get(TombstoneParser.keyAbortMessage));
                String backtrace = fields.get(TombstoneParser.keyBacktrace);
                if (backtrace == null || backtrace.trim().isEmpty())
                    details.append("\nNo native backtrace was captured.\n");
                else append(details, "\nNative backtrace", backtrace);
                append(details, "\nBuild IDs", fields.get(TombstoneParser.keyBuildId));
                append(details, "\nCapture error", fields.get(TombstoneParser.keyXCrashError));
                boolean truncated = details.length() > MAX_DISPLAY_CHARS || file.length() > MAX_READ_BYTES;
                if (details.length() > MAX_DISPLAY_CHARS) details.setLength(MAX_DISPLAY_CHARS);
                if (truncated) details.append("\nReport truncated for display.\n");
                reports.add(new Report(file, details.toString()));
            } catch (IOException | RuntimeException error) {
                Log.w(TAG, "Could not read " + file.getName(), error);
                reports.add(new Report(file, "Saved native report could not be read: " + error.getClass().getSimpleName()));
            }
        }
        return reports;
    }

    private static void append(StringBuilder out, String label, String value) {
        if (value != null && !value.trim().isEmpty()) out.append(label).append(": ").append(value.trim()).append('\n');
    }

    static int clearDirectory(File directory) {
        int deleted = 0;
        for (File file : files(directory)) if (file.delete()) ++deleted;
        return deleted;
    }
}
