package com.example.projectm.visualizer;

import java.io.*;
import java.util.*;
import java.util.zip.*;
import java.util.concurrent.*;

/** ZIP staging and an atomic active-pack pointer. Call only from a background worker. */
final class CustomPresetPack {
    static final Object STORE_LOCK = new Object();
    static final long MAX_ZIP_BYTES = 2L * 1024 * 1024 * 1024;
    private static final long MAX_PRESET_BYTES = 8L * 1024 * 1024;
    private static final long MAX_TEXTURE_BYTES = 64L * 1024 * 1024;
    private static final long MAX_EXPANDED_BYTES = 4L * 1024 * 1024 * 1024;
    // Bound directory scanning and disk use; texture decoding/GPU limits remain native.
    private static final int MAX_TEXTURES = 5000;
    // Keep in sync with projectM's Renderer/TextureManager.hpp.
    private static final Set<String> TEXTURE_EXTENSIONS = new HashSet<>(Arrays.asList(
            ".jpg", ".jpeg", ".png", ".tga", ".bmp", ".dib", ".dds"));
    interface Cancellation { boolean canceled(); }
    interface Progress { void updated(int presets); }
    interface IndexStatus { int status(long request); }
    interface DirectoryUse { boolean inUse(File directory); }
    private static final Map<File, FutureTask<Void>> CLEANUPS = new HashMap<>();
    private static final Set<File> PENDING_CLEANUPS = new HashSet<>();
    private static final ExecutorService CLEANUP_WORKER = Executors.newSingleThreadExecutor(task -> {
        Thread thread = new Thread(task, "CustomPresetCleanup");
        thread.setDaemon(true);
        return thread;
    });

    static final class Pack {
        final File directory;
        final int count;
        final int textureCount;
        Pack(File directory, int count) { this(directory, count, 0); }
        Pack(File directory, int count, int textureCount) {
            this.directory = directory;
            this.count = count;
            this.textureCount = textureCount;
        }
    }

    static Pack prepare(File root, InputStream input, Cancellation cancellation, Progress progress) throws IOException {
        if (!root.isDirectory() && !root.mkdirs()) throw new IOException("Cannot create pack storage");
        File archive = new File(root, "incoming.zip");
        byte[] buffer = new byte[32768];
        try {
            try (FileOutputStream out = new FileOutputStream(archive)) {
                long length = 0; int n;
                while ((n = input.read(buffer)) != -1) {
                    checkCanceled(cancellation); length += n;
                    if (length > MAX_ZIP_BYTES) throw new IOException("ZIP exceeds 2 GiB");
                    out.write(buffer, 0, n);
                }
            }
            return prepare(root, archive, cancellation, progress);
        } finally { archive.delete(); }
    }

    /** Caller owns the immutable archive; extraction never removes it. */
    static Pack prepare(File root, File archive, Cancellation cancellation, Progress progress) throws IOException {
        if (!root.isDirectory() && !root.mkdirs()) throw new IOException("Cannot create pack storage");
        if (archive.length() > MAX_ZIP_BYTES) throw new IOException("ZIP exceeds 2 GiB");
        File directory = new File(root, UUID.randomUUID().toString());
        boolean success = false;
        byte[] buffer = new byte[32768];
        try {
            checkCanceled(cancellation);
            try (ZipFile zip = new ZipFile(archive)) {
                ArrayList<ZipEntry> presets = new ArrayList<>();
                ArrayList<ZipEntry> textures = new ArrayList<>();
                HashSet<String> names = new HashSet<>();
                HashSet<String> textureNames = new HashSet<>();
                Enumeration<? extends ZipEntry> entries = zip.entries();
                int entryCount = 0;
                long declaredExpanded = 0;
                while (entries.hasMoreElements()) {
                    checkCanceled(cancellation);
                    if (++entryCount > 250000) throw new IOException("ZIP contains too many entries");
                    ZipEntry entry = entries.nextElement();
                    String name = entry.getName();
                    // ZipFile skips unsupported entries without expanding their compressed data.
                    if (entry.isDirectory()) continue;
                    String lowerName = name.toLowerCase(Locale.ROOT);
                    int extensionStart = lowerName.lastIndexOf('.');
                    boolean preset = lowerName.endsWith(".milk");
                    boolean texture = extensionStart >= 0 && TEXTURE_EXTENSIONS.contains(lowerName.substring(extensionStart));
                    if (!preset && !texture) continue;
                    if (preset) {
                        if (!safeName(name) || !names.add(name)) throw new IOException("Invalid or duplicate preset name");
                        presets.add(entry);
                        if (presets.size() > 50000) throw new IOException("A pack may contain up to 50,000 presets");
                        if (entry.getSize() > MAX_PRESET_BYTES) throw new IOException("A preset exceeds 8 MiB");
                    } else {
                        String basename = basename(name);
                        // Native samplers match the lowercase stem, ignoring extension and directories.
                        String stem = basename.substring(0, basename.lastIndexOf('.')).toLowerCase(Locale.ROOT);
                        if (!safeName(name) || stem.isEmpty() || basename.getBytes("UTF-8").length > 255
                                || !textureNames.add(stem))
                            throw new IOException("Invalid or ambiguous texture name; texture basenames must be unique ignoring case and extension");
                        textures.add(entry);
                        if (textures.size() > MAX_TEXTURES) throw new IOException("A pack may contain up to 5,000 textures");
                        if (entry.getSize() > MAX_TEXTURE_BYTES) throw new IOException("A texture exceeds 64 MiB");
                    }
                    if (entry.getSize() < 0 || entry.getCrc() < 0) throw new IOException("Corrupt entry in ZIP");
                    declaredExpanded += entry.getSize();
                    if (declaredExpanded > MAX_EXPANDED_BYTES) throw new IOException("Pack exceeds the 4 GiB expanded limit");
                }
                if (presets.isEmpty()) throw new IOException("No .milk presets found in the ZIP");
                if (!directory.mkdir()) throw new IOException("Cannot create pack directory");
                long expanded = 0;
                try (Writer index = new BufferedWriter(new OutputStreamWriter(
                        new FileOutputStream(new File(directory, "presets.idx")), "UTF-8"))) {
                    for (int i = 0; i < presets.size(); i++) {
                        checkCanceled(cancellation);
                        ZipEntry entry = presets.get(i);
                        // Generated storage names avoid ZIP paths, filename limits and basename collisions.
                        String storage = (i / 1000) + "/" + i + ".milk";
                        File target = new File(directory, storage);
                        File parent = target.getParentFile();
                        if (!parent.isDirectory() && !parent.mkdir()) throw new IOException("Cannot create preset directory");
                        expanded = extract(zip, entry, target, MAX_PRESET_BYTES, expanded, buffer, cancellation);
                        index.write(storage + "\t" + entry.getName() + "\n");
                        if ((i + 1) % 500 == 0 || i + 1 == presets.size()) progress.updated(i + 1);
                    }
                }
                if (!textures.isEmpty()) {
                    File textureDirectory = new File(directory, "textures");
                    if (!textureDirectory.mkdir()) throw new IOException("Cannot create texture directory");
                    for (ZipEntry entry : textures) {
                        checkCanceled(cancellation);
                        // Preserve sampler names, but never extract ZIP directory paths or link metadata.
                        expanded = extract(zip, entry, new File(textureDirectory, basename(entry.getName())),
                                MAX_TEXTURE_BYTES, expanded, buffer, cancellation);
                    }
                }
                checkCanceled(cancellation);
                success = true;
                return new Pack(directory, presets.size(), textures.size());
            }
        } finally {
            if (!success) delete(directory);
        }
    }

    private static boolean safeName(String name) throws UnsupportedEncodingException {
        if (name.startsWith("/") || name.contains("\\") || name.getBytes("UTF-8").length > 1024) return false;
        if (name.length() > 1 && Character.isLetter(name.charAt(0)) && name.charAt(1) == ':') return false;
        for (int i = 0; i < name.length(); i++) if (Character.isISOControl(name.charAt(i))) return false;
        for (String part : name.split("/", -1))
            if (part.isEmpty() || part.equals(".") || part.equals("..")) return false;
        return true;
    }

    private static String basename(String name) { return name.substring(name.lastIndexOf('/') + 1); }

    private static long extract(ZipFile zip, ZipEntry entry, File target, long limit, long expanded,
                                byte[] buffer, Cancellation cancellation) throws IOException {
        CRC32 crc = new CRC32();
        long size = 0;
        try (InputStream in = zip.getInputStream(entry);
             OutputStream out = new BufferedOutputStream(new FileOutputStream(target))) {
            int n;
            while ((n = in.read(buffer)) != -1) {
                checkCanceled(cancellation);
                size += n;
                expanded += n;
                if (size > limit || expanded > MAX_EXPANDED_BYTES)
                    throw new IOException("Pack exceeds a file size limit or the 4 GiB expanded limit");
                crc.update(buffer, 0, n);
                out.write(buffer, 0, n);
            }
        }
        if (size != entry.getSize() || crc.getValue() != entry.getCrc()) throw new IOException("Corrupt entry in ZIP");
        return expanded;
    }

    private static void checkCanceled(Cancellation cancellation) throws IOException {
        if (cancellation.canceled()) throw new IOException("Upload canceled");
    }

    static void activate(File root, Pack pack) throws IOException {
        File temp = new File(root, "current.tmp");
        try (FileOutputStream out = new FileOutputStream(temp)) {
            out.write(pack.directory.getName().getBytes("UTF-8"));
            out.getFD().sync();
        }
        if (!temp.renameTo(new File(root, "current"))) throw new IOException("Cannot save the active pack");
    }

    static void restore(File root, File previous) throws IOException {
        if (previous != null) activate(root, new Pack(previous, 0));
        else {
            File pointer = new File(root, "current");
            if (pointer.exists() && !pointer.delete()) throw new IOException("Cannot restore the previous pack pointer");
        }
    }

    static void awaitStatus(long request, int expected, IndexStatus index, Cancellation cancellation, long timeoutMs) throws IOException {
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(timeoutMs);
        for (;;) {
            checkCanceled(cancellation);
            if (Thread.currentThread().isInterrupted()) throw new IOException("Upload canceled");
            int status = index.status(request);
            if (status == expected) return;
            if (status < 0 || request == 0) throw new IOException("Cannot index the preset pack; previous pack retained");
            if (System.nanoTime() >= deadline) throw new IOException("Preset indexing took too long; previous pack retained");
            try { Thread.sleep(25); }
            catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                throw new IOException("Upload canceled", interrupted);
            }
        }
    }

    /** Committed storage belongs to the application process, independent of dialog/socket lifetime. */
    static Future<?> scheduleCleanup(File root) {
        return scheduleCleanup(root, directory -> false);
    }

    static Future<?> scheduleCleanup(File root, DirectoryUse use) {
        synchronized (CLEANUPS) {
            FutureTask<Void> existing = CLEANUPS.get(root);
            if (existing != null) return existing;
            FutureTask<Void> job = new FutureTask<>(() -> {
                synchronized (STORE_LOCK) {
                    try {
                        boolean pending = cleanUnused(root, current(root), use);
                        synchronized (CLEANUPS) {
                            if (pending) PENDING_CLEANUPS.add(root);
                            else PENDING_CLEANUPS.remove(root);
                        }
                    } finally { synchronized (CLEANUPS) { CLEANUPS.remove(root); } }
                }
                return null;
            });
            CLEANUPS.put(root, job);
            CLEANUP_WORKER.execute(job);
            return job;
        }
    }

    /** Retry only while the existing foreground status loop is running; no background poll. */
    static void retryPendingCleanups(DirectoryUse use) {
        List<File> roots;
        synchronized (CLEANUPS) { roots = new ArrayList<>(PENDING_CLEANUPS); }
        for (File root : roots) scheduleCleanup(root, use);
    }

    static File current(File root) {
        try (BufferedReader in = new BufferedReader(new InputStreamReader(
                new FileInputStream(new File(root, "current")), "UTF-8"))) {
            String id = in.readLine();
            if (id == null || !id.matches("[a-f0-9-]{36}")) return null;
            File directory = new File(root, id);
            return new File(directory, "presets.idx").isFile() ? directory : null;
        } catch (IOException ignored) { return null; }
    }

    /** Remove retired generations only after native preset and prewarm readers release them. */
    static void cleanUnused(File root, File active) {
        cleanUnused(root, active, directory -> false);
    }

    private static boolean cleanUnused(File root, File active, DirectoryUse use) {
        File[] children = root.listFiles();
        if (children == null) return false;
        boolean pending = false;
        for (File child : children) {
            if (child.isDirectory() && !child.equals(active)) {
                if (use.inUse(child)) pending = true;
                else delete(child);
            }
        }
        return pending;
    }

    static void delete(File file) {
        File[] children = file.listFiles();
        if (children != null) for (File child : children) delete(child);
        file.delete();
    }

    private CustomPresetPack() {}
}
