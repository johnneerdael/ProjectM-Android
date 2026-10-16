package nl.neerdael.projectm.core;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.List;

import static org.junit.Assert.*;

public class NativeCrashReportsTest {
    @Rule public TemporaryFolder temporary = new TemporaryFolder();

    private static final String CRASH =
            "*** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***\n"
            + "Tombstone maker: 'xCrash 3.1.0'\nCrash type: 'native'\n"
            + "Crash time: '2026-10-16T22:00:00.000+0200'\nApp version: '2.3.51'\n"
            + "ABI: 'arm'\npid: 4321, tid: 4322, name: GLThread  >>> nl.neerdael.projectmtv <<<\n"
            + "signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0\n\n"
            + "backtrace:\n    #00 pc 00001234 /vendor/lib/egl/libGLESv2_mtk.so\n"
            + "    #01 pc 00005678 /data/app/lib/arm/libprojectmtv.so\n\n"
            + "build id:\n    /data/app/lib/arm/libprojectmtv.so (BuildId: abc123)\n\n"
            + "stack:\n    PRIVATE_RAW_STACK\n\nmemory near r0:\n    PRIVATE_MEMORY\n\n";

    private File write(String name, String text, long modified) throws Exception {
        File file = new File(temporary.getRoot(), name);
        Files.write(file.toPath(), text.getBytes(StandardCharsets.UTF_8));
        assertTrue(file.setLastModified(modified));
        return file;
    }

    @Test public void readsRealTombstoneFieldsWithoutDisplayingRawMemory() throws Exception {
        write("tombstone_1.native.xcrash", CRASH, 1000);
        List<NativeCrashReports.Report> reports = NativeCrashReports.readDirectory(temporary.getRoot());
        assertEquals(1, reports.size());
        String text = reports.get(0).details;
        assertTrue(text, text.contains("SIGSEGV"));
        assertTrue(text, text.contains("libGLESv2_mtk.so"));
        assertTrue(text, text.contains("libprojectmtv.so"));
        assertTrue(text, text.contains("00001234"));
        assertTrue(text, text.contains("abc123"));
        assertFalse(text, text.contains("PRIVATE_RAW_STACK"));
        assertFalse(text, text.contains("PRIVATE_MEMORY"));
    }

    @Test public void newestReportsAreBoundedAndUnrelatedFilesAreIgnored() throws Exception {
        for (int i = 1; i <= 7; ++i) write("tombstone_" + i + ".native.xcrash", CRASH, i * 1000);
        write("other.native.xcrash", CRASH, 99999);
        write("tombstone_8.java.xcrash", CRASH, 99999);
        List<NativeCrashReports.Report> reports = NativeCrashReports.readDirectory(temporary.getRoot());
        assertEquals(5, reports.size());
        assertEquals("tombstone_7.native.xcrash", reports.get(0).fileName);
        assertEquals("tombstone_3.native.xcrash", reports.get(4).fileName);
    }

    @Test public void emptyOrTruncatedCaptureIsNotPresentedAsACompleteStack() throws Exception {
        write("tombstone_empty.native.xcrash", "\0\0\0", 1000);
        write("tombstone_partial.native.xcrash", CRASH.substring(0, CRASH.indexOf("backtrace:")), 2000);
        List<NativeCrashReports.Report> reports = NativeCrashReports.readDirectory(temporary.getRoot());
        assertEquals(1, reports.size());
        assertTrue(reports.get(0).details, reports.get(0).details.contains("No native backtrace was captured"));
    }

    @Test public void deletingReportsPreservesOtherAppFiles() throws Exception {
        File report = write("tombstone_1.native.xcrash", CRASH, 1000);
        File unrelated = write("engine_trail.txt", "retain this", 1000);
        assertEquals(1, NativeCrashReports.clearDirectory(temporary.getRoot()));
        assertFalse(report.exists());
        assertTrue(unrelated.exists());
    }

    @Test public void oversizedBacktraceCannotOverfillTheViewerOrClipboard() throws Exception {
        StringBuilder large = new StringBuilder(CRASH.substring(0, CRASH.indexOf("backtrace:")));
        large.append("backtrace:\n");
        for (int i = 0; i < 8000; ++i) large.append("    #02 pc 00001234 /vendor/lib/egl/libGLESv2_mtk.so\n");
        write("tombstone_large.native.xcrash", large.toString(), 1000);
        String details = NativeCrashReports.readDirectory(temporary.getRoot()).get(0).details;
        assertTrue(details.length() < 34000);
        assertTrue(details, details.contains("truncated for display"));
        assertTrue(details, details.contains("SIGSEGV"));
    }
}
