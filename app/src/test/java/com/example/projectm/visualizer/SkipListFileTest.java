package com.example.projectm.visualizer;

import static org.junit.Assert.*;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public class SkipListFileTest {
    @Rule public TemporaryFolder folder = new TemporaryFolder();

    private static void write(File file, String text, boolean append) throws IOException {
        try (FileOutputStream out = new FileOutputStream(file, append)) { out.write(text.getBytes(StandardCharsets.UTF_8)); }
    }

    @Test public void missingFileHasNoNamesAndNoParse() {
        SkipListFile skips = new SkipListFile(new File(folder.getRoot(), "skipped_presets.txt"));
        assertEquals(Collections.<String>emptySet(), skips.names());
        assertEquals(0, skips.parseCount());
    }

    @Test public void unchangedFileIsParsedOnce() throws IOException {
        File file = folder.newFile("skipped_presets.txt");
        write(file, "a.milk\n\nb.milk\n", false);
        SkipListFile skips = new SkipListFile(file);
        Set<String> expected = new HashSet<>(Arrays.asList("a.milk", "b.milk"));
        for (int i = 0; i < 25; i++) assertEquals(expected, skips.names());
        assertEquals(1, skips.parseCount());
    }

    @Test public void appendedNameIsReadAgain() throws IOException {
        File file = folder.newFile("skipped_presets.txt");
        write(file, "a.milk\n", false);
        SkipListFile skips = new SkipListFile(file);
        assertEquals(Collections.singleton("a.milk"), skips.names());
        write(file, "b.milk\n", true);
        assertEquals(new HashSet<>(Arrays.asList("a.milk", "b.milk")), skips.names());
        assertEquals(2, skips.parseCount());
    }

    @Test public void sameLengthRewriteWithNewTimestampIsReadAgain() throws IOException {
        File file = folder.newFile("skipped_presets.txt");
        write(file, "a.milk\n", false);
        assertTrue(file.setLastModified(1_000_000L));
        SkipListFile skips = new SkipListFile(file);
        assertEquals(Collections.singleton("a.milk"), skips.names());
        write(file, "b.milk\n", false);
        assertTrue(file.setLastModified(2_000_000L));
        assertEquals(Collections.singleton("b.milk"), skips.names());
    }

    @Test public void deletedFileClearsNames() throws IOException {
        File file = folder.newFile("skipped_presets.txt");
        write(file, "a.milk\n", false);
        SkipListFile skips = new SkipListFile(file);
        assertEquals(1, skips.names().size());
        assertTrue(file.delete());
        assertEquals(Collections.<String>emptySet(), skips.names());
    }

    @Test public void namesAreReadOnly() throws IOException {
        File file = folder.newFile("skipped_presets.txt");
        write(file, "a.milk\n", false);
        try {
            new SkipListFile(file).names().add("x.milk");
            fail("cached names must not be mutable");
        } catch (UnsupportedOperationException expected) { }
    }
}
