package com.example.projectm.visualizer;

import android.util.Log;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

/**
 * The names in the engine's skip list (one per line), parsed again only when the file's timestamp or
 * length changed, so rendering the Mood panel does not rescan an unchanged list. Used on the UI thread.
 */
final class SkipListFile implements MoodFacetsController.SkipList {
    private static final String TAG = "SkipListFile";
    private final File file;
    private Set<String> names = Collections.emptySet();
    private long modified = -1, length = -1;
    private int parses;

    SkipListFile(File file) { this.file = file; }

    @Override public Set<String> names() {
        if (!file.isFile()) {
            names = Collections.emptySet();
            modified = length = -1;
            return names;
        }
        long nowModified = file.lastModified(), nowLength = file.length();
        if (nowModified == modified && nowLength == length) return names;
        Set<String> read = new HashSet<>();
        try (BufferedReader in = new BufferedReader(new InputStreamReader(new FileInputStream(file), StandardCharsets.UTF_8))) {
            for (String line; (line = in.readLine()) != null; ) if (!line.isEmpty()) read.add(line);
        } catch (IOException unreadable) {
            Log.w(TAG, "Skip list unreadable", unreadable);
            // Not cached: the next call tries again.
            return Collections.unmodifiableSet(read);
        }
        parses++;
        modified = nowModified;
        length = nowLength;
        names = Collections.unmodifiableSet(read);
        return names;
    }

    /** Parses performed so far (tests). */
    int parseCount() { return parses; }
}
