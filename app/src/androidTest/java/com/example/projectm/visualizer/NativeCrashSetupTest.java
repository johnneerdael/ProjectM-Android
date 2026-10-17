package com.example.projectm.visualizer;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.os.SystemClock;

import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.Method;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import nl.neerdael.projectm.core.NativeCrashReports;

/** Two-process journey: capture deliberately terminates the test app; report runs after restart. */
final class NativeCrashSetupTest {
    static void run(Instrumentation test, boolean capture) {
        Bundle result = new Bundle();
        try {
            test.waitForIdleSync(); // Application.onCreate runs after Instrumentation.onCreate.
            if (capture) {
                if (!"Native crash capture ready".equals(NativeCrashReports.status()))
                    throw new AssertionError(NativeCrashReports.status());
                File ready = new File(test.getTargetContext().getExternalCacheDir(), "native-crash-capture.ready");
                try (FileOutputStream output = new FileOutputStream(ready)) {
                    output.write(NativeCrashReports.status().getBytes(StandardCharsets.UTF_8));
                }
                // A fatal native signal exercises capture without relying on a compiler retaining
                // an intentional null dereference (undefined behavior can be optimized away).
                android.system.Os.kill(android.os.Process.myPid(), android.system.OsConstants.SIGSEGV);
                SystemClock.sleep(10000);
                throw new AssertionError("native fault did not terminate the process");
            }
            List<NativeCrashReports.Report> reports = NativeCrashReports.recent(test.getTargetContext());
            if (reports.isEmpty()) throw new AssertionError("no saved native crash after restart");
            String details = reports.get(0).details;
            if (!details.contains("SIGSEGV") || !details.contains("libc.so") || !details.contains("#00"))
                throw new AssertionError("native signal/module/backtrace missing: " + details);
            Intent intent = new Intent(test.getTargetContext(), MainActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            Activity activity = test.startActivitySync(intent);
            Method show = MainActivity.class.getDeclaredMethod("showExitReport", List.class);
            show.setAccessible(true);
            Field dialogField = MainActivity.class.getDeclaredField("exitReportDialog");
            dialogField.setAccessible(true);
            test.runOnMainSync(() -> {
                try { show.invoke(activity, ExitDiagnostics.recentExits(test.getTargetContext())); }
                catch (Exception error) { throw new AssertionError(error); }
            });
            AtomicReference<String> displayed = new AtomicReference<>("");
            long deadline = SystemClock.elapsedRealtime() + 10000;
            while (SystemClock.elapsedRealtime() < deadline) {
                test.runOnMainSync(() -> {
                    try {
                        android.app.AlertDialog dialog = (android.app.AlertDialog) dialogField.get(activity);
                        android.widget.TextView message = dialog.findViewById(android.R.id.message);
                        if (message != null) displayed.set(message.getText().toString());
                    } catch (Exception error) { throw new AssertionError(error); }
                });
                if (displayed.get().contains("libc.so")) break;
                SystemClock.sleep(100);
            }
            if (!displayed.get().contains("Saved native crash") || !displayed.get().contains("#00"))
                throw new AssertionError("saved crash did not reach the UI: " + displayed.get());
            test.waitForIdleSync();
            SystemClock.sleep(500); // Dialog's window animation must finish before its capture.
            test.runOnMainSync(() -> {
                try {
                    android.app.AlertDialog dialog = (android.app.AlertDialog) dialogField.get(activity);
                    android.graphics.Rect bounds = new android.graphics.Rect();
                    android.view.View close = dialog.getButton(android.app.AlertDialog.BUTTON_NEGATIVE);
                    if (!close.getGlobalVisibleRect(bounds) || bounds.bottom >
                            test.getTargetContext().getResources().getDisplayMetrics().heightPixels)
                        throw new AssertionError("report action buttons are clipped");
                } catch (Exception error) { throw new AssertionError(error); }
            });
            Bitmap screenshot = test.getUiAutomation().takeScreenshot();
            if (screenshot == null) throw new AssertionError("crash report screenshot unavailable");
            try (FileOutputStream output = new FileOutputStream(new File(
                    test.getTargetContext().getExternalCacheDir(), "native-crash-report.png"))) {
                screenshot.compress(Bitmap.CompressFormat.PNG, 100, output);
            } finally { screenshot.recycle(); }
            result.putString("native_crash", "saved after process death and displayed signal/module/relative PCs");
            test.finish(Activity.RESULT_OK, result);
        } catch (Throwable error) {
            result.putString("error", error.toString());
            test.finish(Activity.RESULT_CANCELED, result);
        }
    }
}
