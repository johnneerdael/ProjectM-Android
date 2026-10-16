package nl.neerdael.projectm.core;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import xcrash.Errno;
import xcrash.XCrash;

import static org.junit.Assert.*;

public class NativeCrashInitializationTest {
    @Rule public TemporaryFolder temporary = new TemporaryFolder();

    @Test public void failedPriorInitializationDoesNotBecomeCaptureReady() {
        String first = NativeCrashReports.initializeCapture(null, temporary.getRoot());
        assertTrue(first, first.contains("unavailable"));
        // The bundled library reports OK after even a failed initialization.
        assertEquals(Errno.OK, XCrash.init(null));
        String repeated = NativeCrashReports.initializeCapture(null, temporary.getRoot());
        assertTrue(repeated, repeated.contains("already initialized"));
        assertFalse(repeated, repeated.contains("capture ready"));
    }
}
