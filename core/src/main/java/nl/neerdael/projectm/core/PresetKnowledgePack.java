package nl.neerdael.projectm.core;

import android.content.res.AssetManager;
import java.io.BufferedInputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import java.util.zip.CRC32;
import java.util.zip.Inflater;
import java.util.zip.InflaterInputStream;
import java.util.zip.ZipException;

/**
 * Reader for a preset knowledge pack (preset-knowledge-pack-v1): source-only recipes for a preset
 * collection, specified in tools/milk-analyzer/export-contract/knowledge-pack/FORMAT.md and checked
 * against the shared golden vectors there. The pack is plain gzip, JSON and SHA-256; no Android
 * types are used outside load(), so the same reader serves the app, Milkbeat and JVM tools.
 *
 * The core is streamed in passes over a re-openable source: the file hash is verified first, then
 * every line is hash-checked, strictly decoded, parsed and reduced to its {@link Preset} view.
 * Nothing is published until the whole pack has passed; only then does a {@link RecipeVisitor}
 * receive each full recipe, once. Memory follows the views, not the recipes.
 */
public final class PresetKnowledgePack {
    public static final String POLICY = "preset-knowledge-pack-v1";
    public static final String RECIPE_POLICY = "preset-visual-recipe-v1";
    public static final String MANIFEST = "manifest.json";
    public static final String CORE = "core.jsonl.gz";

    /** A pack that breaks one of the FORMAT.md reader rules; {@link #rule} names it. */
    public static final class InvalidPackException extends IOException {
        public final String rule;
        InvalidPackException(String rule, String detail) { super(rule + ": " + detail); this.rule = rule; }
    }

    /** Receives each parsed recipe once, in manifest order, after the whole pack has been verified. */
    public interface RecipeVisitor { void visit(Preset preset, Map<String, Object> recipe); }

    public static final class Effect {
        public final String name, stage;
        /** The effect row's other fields (parameters such as sectors, taps or mirrored). */
        public final Map<String, Object> parameters;
        Effect(String name, String stage, Map<String, Object> parameters) { this.name = name; this.stage = stage; this.parameters = parameters; }
    }

    public static final class Reaction {
        public final String band, target, kind, response;
        Reaction(String band, String target, String kind, String response) { this.band = band; this.target = target; this.kind = kind; this.response = response; }
    }

    /** A calibrated source estimate: value and 10th-90th percentile interval (either may be null). */
    public static final class Estimate {
        public final Double value;
        public final double[] interval;
        Estimate(Double value, double[] interval) { this.value = value; this.interval = interval; }
    }

    /** The reader view of one recipe (FORMAT.md, "Reader view"). */
    public static final class Preset {
        public final String name, sha256;
        public final List<Effect> effects;
        public final List<Reaction> reactivity;
        public final Estimate meanLuminance, meanAbsFrameDifference;
        public final Double activity;
        public final List<String> activityBands, facetOptions, energyTags;
        /** Facet values by name, sorted by name. */
        public final Map<String, Double> facetValues;

        /** Throws {@link WrongType} when a view field has the wrong JSON type (FORMAT.md rule 7). */
        Preset(Map<String, Object> recipe) {
            Map<String, Object> preset = object(recipe.get("preset"), "preset");
            name = text(preset.get("name"), "preset.name");
            sha256 = text(preset.get("sha256"), "preset.sha256");
            Map<String, Object> intent = object(recipe.get("intent"), "intent");
            List<Effect> e = new ArrayList<>();
            for (Map<String, Object> row : rows(intent.get("effects"), "intent.effects")) {
                Map<String, Object> fields = new LinkedHashMap<>(row);
                String effect = text(fields.remove("effect"), "intent.effects[].effect");
                String stage = optionalText(fields.remove("stage"), "intent.effects[].stage");
                e.add(new Effect(effect, stage, Collections.unmodifiableMap(fields)));
            }
            effects = Collections.unmodifiableList(e);
            List<Reaction> r = new ArrayList<>();
            for (Map<String, Object> m : rows(intent.get("reactivity"), "intent.reactivity"))
                r.add(new Reaction(optionalText(m.get("band"), "reactivity.band"), optionalText(m.get("target"), "reactivity.target"),
                        optionalText(m.get("kind"), "reactivity.kind"), optionalText(m.get("response"), "reactivity.response")));
            reactivity = Collections.unmodifiableList(r);
            Map<String, Object> estimate = object(recipe.get("display_estimate"), "display_estimate");
            Map<String, Object> statistics = object(estimate.get("statistics"), "display_estimate.statistics");
            meanLuminance = estimate(statistics.get("mean_luminance"), "mean_luminance");
            meanAbsFrameDifference = estimate(statistics.get("mean_abs_frame_difference"), "mean_abs_frame_difference");
            Map<String, Object> activityRow = object(estimate.get("activity"), "display_estimate.activity");
            activity = number(activityRow.get("activity"), "display_estimate.activity.activity");
            activityBands = texts(activityRow.get("bands"), "display_estimate.activity.bands");
            Map<String, Object> facets = object(recipe.get("facets"), "facets");
            facetOptions = texts(facets.get("options"), "facets.options");
            Map<String, Double> values = new TreeMap<>();
            for (Map.Entry<String, Object> v : object(facets.get("values"), "facets.values").entrySet())
                values.put(v.getKey(), number(object(v.getValue(), "facets.values").get("value"), "facets.values." + v.getKey()));
            facetValues = Collections.unmodifiableMap(values);
            energyTags = texts(object(intent.get("energy"), "intent.energy").get("tags"), "intent.energy.tags");
        }
    }

    /** Re-openable core bytes: the reader makes separate passes for hashing, views and visiting. */
    private interface Source { InputStream open() throws IOException; }

    private final Map<String, Object> manifest;
    private final List<String> names;
    private final Map<String, Preset> byName = new HashMap<>();
    private final Map<String, Preset> bySha256 = new HashMap<>();

    private PresetKnowledgePack(Map<String, Object> manifest, List<Preset> presets) {
        this.manifest = manifest;
        List<String> ordered = new ArrayList<>();
        for (Preset p : presets) { ordered.add(p.name); byName.put(p.name, p); bySha256.put(p.sha256, p); }
        this.names = Collections.unmodifiableList(ordered);
    }

    public static PresetKnowledgePack read(File directory) throws IOException { return read(directory, null); }

    /** Reads manifest.json and core.jsonl.gz from a directory; the core file is read once per pass. */
    public static PresetKnowledgePack read(File directory, RecipeVisitor visitor) throws IOException {
        byte[] manifest;
        try (InputStream in = new FileInputStream(new File(directory, MANIFEST))) { manifest = bytes(in); }
        final File core = new File(directory, CORE);
        return read(manifest, () -> new FileInputStream(core), visitor);
    }

    /**
     * Reads a pack from its manifest and core streams. The compressed core is held in memory for the
     * passes; use {@link #read(File, RecipeVisitor)} or {@link #load} to stream from storage instead.
     */
    public static PresetKnowledgePack read(InputStream manifestStream, InputStream coreStream, RecipeVisitor visitor) throws IOException {
        byte[] manifest = bytes(manifestStream);
        final byte[] core = bytes(coreStream);
        return read(manifest, () -> new ByteArrayInputStream(core), visitor);
    }

    /** A pack bundled under assets/{directory}, or null when it is missing or invalid. */
    public static PresetKnowledgePack load(final AssetManager assets, final String directory) {
        try (InputStream in = assets.open(directory + "/" + MANIFEST)) {
            return read(bytes(in), () -> assets.open(directory + "/" + CORE), null);
        } catch (IOException missingOrInvalid) {
            return null;
        }
    }

    private static PresetKnowledgePack read(byte[] manifestBytes, Source core, RecipeVisitor visitor) throws IOException {
        try {
            return verifiedRead(manifestBytes, core, visitor);
        } catch (WrongType wrong) {
            throw new InvalidPackException("json", "manifest or core structure: " + wrong.getMessage());
        }
    }

    private static PresetKnowledgePack verifiedRead(byte[] manifestBytes, Source core, RecipeVisitor visitor) throws IOException {
        Map<String, Object> manifest = object(json(decode(manifestBytes, manifestBytes.length, MANIFEST), MANIFEST), MANIFEST);
        if (!POLICY.equals(manifest.get("policy"))) throw new InvalidPackException("pack policy", String.valueOf(manifest.get("policy")));
        if (!RECIPE_POLICY.equals(manifest.get("recipe_policy")))
            throw new InvalidPackException("recipe policy", String.valueOf(manifest.get("recipe_policy")));
        // Pass 1: the stored core bytes, before anything is decompressed.
        MessageDigest fileDigest = digest();
        try (InputStream in = core.open()) {
            byte[] buffer = new byte[1 << 16];
            for (int n; (n = in.read(buffer)) > 0; ) fileDigest.update(buffer, 0, n);
        }
        if (!hex(fileDigest.digest()).equals(object(manifest.get("core"), "core").get("sha256")))
            throw new InvalidPackException("core file hash", "core file bytes differ from manifest core.sha256");
        Object presetList = manifest.get("presets");
        if (!(presetList instanceof List)) throw new InvalidPackException("manifest structure", "presets must be an array");
        for (Object entry : (List<?>) presetList)
            if (!(entry instanceof Map)) throw new InvalidPackException("manifest structure", "presets must be an array of objects");
        List<Map<String, Object>> entries = rows(presetList, "presets");
        // Pass 2: every line verified and reduced to its view; nothing is published yet.
        final List<Preset> presets = new ArrayList<>(entries.size());
        lines(core, entries, (index, entry, recipe) -> {
            Preset preset;
            try {
                preset = new Preset(recipe);
            } catch (WrongType wrong) {
                throw new InvalidPackException("recipe types", entry.get("name") + ": " + wrong.getMessage());
            }
            if (!Objects.equals(preset.name, entry.get("name")) || !Objects.equals(preset.sha256, entry.get("sha256")))
                throw new InvalidPackException("recipe identity", String.valueOf(entry.get("name")));
            presets.add(preset);
        });
        // Pass 3, only after the whole pack has passed: hand each full recipe to the visitor once.
        if (visitor != null) lines(core, entries, (index, entry, recipe) -> visitor.visit(presets.get(index), recipe));
        return new PresetKnowledgePack(Collections.unmodifiableMap(manifest), presets);
    }

    private interface LineHandler { void handle(int index, Map<String, Object> entry, Map<String, Object> recipe) throws IOException; }

    /** Streams the decompressed core, checking count, line hashes, UTF-8 and recipe policy. */
    private static void lines(Source core, List<Map<String, Object>> entries, LineHandler handler) throws IOException {
        Line line = new Line();
        int index = 0;
        try (InputStream in = new BufferedInputStream(new GzipMember(core.open()), 1 << 16)) {
            while (line.next(in)) {
                if (!line.terminated) throw new InvalidPackException("line ending", "the last core line has no terminating LF");
                if (line.length > 0 && line.bytes[line.length - 1] == '\r')
                    throw new InvalidPackException("line ending", "core lines end in CR LF, not LF");
                if (line.length == 0) continue;
                if (index >= entries.size()) throw new InvalidPackException("preset count", "more core lines than manifest presets");
                Map<String, Object> entry = entries.get(index);
                String name = String.valueOf(entry.get("name"));
                MessageDigest lineDigest = digest();
                lineDigest.update(line.bytes, 0, line.length);
                if (!hex(lineDigest.digest()).equals(entry.get("core_line_sha256"))) throw new InvalidPackException("core line hash", name);
                Map<String, Object> recipe = object(json(decode(line.bytes, line.length, name), name), name);
                if (!RECIPE_POLICY.equals(recipe.get("policy"))) throw new InvalidPackException("recipe policy", name + ": " + recipe.get("policy"));
                handler.handle(index++, entry, recipe);
            }
        }
        if (index != entries.size()) throw new InvalidPackException("preset count", "manifest lists " + entries.size() + ", core holds " + index);
    }

    /**
     * Decompresses exactly one gzip member (RFC 1952) and, at its end, checks the CRC-32 and size
     * trailer and that no further member or byte follows. GZIPInputStream would silently accept
     * concatenated members and ignore trailing bytes, which FORMAT.md rejects (rule "gzip").
     */
    private static final class GzipMember extends InflaterInputStream {
        private final CRC32 crc = new CRC32();
        private boolean checked;

        GzipMember(InputStream in) throws IOException {
            super(in, new Inflater(true), 1 << 16);
            CRC32 header = new CRC32();
            if (next(header) != 0x1f || next(header) != 0x8b || next(header) != 8) throw new InvalidPackException("gzip", "not a deflate gzip member");
            int flags = next(header);
            if ((flags & 0xe0) != 0) throw new InvalidPackException("gzip", "bad header flags");
            for (int i = 0; i < 6; i++) next(header);
            if ((flags & 4) != 0) {
                int length = next(header) | (next(header) << 8);
                for (int i = 0; i < length; i++) next(header);
            }
            for (int field : new int[]{8, 16}) if ((flags & field) != 0) while (next(header) != 0) { /* zero-terminated name or comment */ }
            if ((flags & 2) != 0) {
                int expected = (int) (header.getValue() & 0xffff);
                int stored = next(header) | (next(header) << 8);
                if (stored != expected) throw new InvalidPackException("gzip", "header CRC mismatch");
            }
        }

        /** The next header byte, added to the running header CRC; a short header is an invalid pack. */
        private int next(CRC32 header) throws IOException {
            int b = in.read();
            if (b < 0) throw new InvalidPackException("gzip", "short header");
            header.update(b);
            return b;
        }

        @Override
        public int read(byte[] buffer, int offset, int count) throws IOException {
            int n;
            try {
                n = super.read(buffer, offset, count);
            } catch (ZipException | java.io.EOFException corrupt) {
                throw new InvalidPackException("gzip", "corrupt deflate data: " + corrupt.getMessage());
            }
            if (n > 0) crc.update(buffer, offset, n);
            else if (n < 0 && !checked) { checked = true; trailer(); }
            return n;
        }

        private void trailer() throws IOException {
            // Bytes the inflater read past the deflate stream start the trailer.
            int remaining = inf.getRemaining();
            byte[] tail = new byte[8];
            int have = Math.min(remaining, 8);
            System.arraycopy(buf, len - remaining, tail, 0, have);
            if (remaining > 8) throw new InvalidPackException("gzip", "bytes after the gzip member");
            while (have < 8) {
                int b = in.read();
                if (b < 0) throw new InvalidPackException("gzip", "short trailer");
                tail[have++] = (byte) b;
            }
            long storedCrc = (tail[0] & 0xffL) | (tail[1] & 0xffL) << 8 | (tail[2] & 0xffL) << 16 | (tail[3] & 0xffL) << 24;
            long storedSize = (tail[4] & 0xffL) | (tail[5] & 0xffL) << 8 | (tail[6] & 0xffL) << 16 | (tail[7] & 0xffL) << 24;
            if (storedCrc != crc.getValue() || storedSize != (inf.getBytesWritten() & 0xffffffffL))
                throw new InvalidPackException("gzip", "trailer CRC or size mismatch");
            if (in.read() >= 0) throw new InvalidPackException("gzip", "bytes after the gzip member");
        }
    }

    /** One line of the decompressed core, reusing its buffer; terminated is false for a last line without LF. */
    private static final class Line {
        byte[] bytes = new byte[1 << 16];
        int length;
        boolean terminated;

        boolean next(InputStream in) throws IOException {
            length = 0;
            terminated = false;
            int b;
            while ((b = in.read()) >= 0) {
                if (b == '\n') { terminated = true; return true; }
                if (length == bytes.length) bytes = Arrays.copyOf(bytes, bytes.length * 2);
                bytes[length++] = (byte) b;
            }
            return length > 0;
        }
    }

    public int size() { return names.size(); }
    /** Preset names in manifest order. */
    public List<String> names() { return names; }
    public Preset byName(String name) { return byName.get(name); }
    /** Lookup by the SHA-256 (lowercase hex) of the preset file. */
    public Preset bySha256(String sha256) { return bySha256.get(sha256); }
    /** The parsed manifest (raw JSON values). */
    public Map<String, Object> manifest() { return manifest; }

    private static String decode(byte[] data, int length, String what) throws InvalidPackException {
        try {
            return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(data, 0, length)).toString();
        } catch (CharacterCodingException notUtf8) {
            throw new InvalidPackException("encoding", what + " is not valid UTF-8");
        }
    }

    private static Object json(String text, String what) throws InvalidPackException {
        try {
            return Json.parse(text);
        } catch (IOException malformed) {
            throw new InvalidPackException("json", what + ": " + malformed.getMessage());
        }
    }

    private static byte[] bytes(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[1 << 16];
        for (int n; (n = in.read(buffer)) > 0; ) out.write(buffer, 0, n);
        return out.toByteArray();
    }

    private static MessageDigest digest() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException unavailable) {
            throw new IllegalStateException(unavailable);
        }
    }

    private static String hex(byte[] digest) {
        StringBuilder hex = new StringBuilder(64);
        for (byte b : digest) hex.append(Character.forDigit((b >> 4) & 15, 16)).append(Character.forDigit(b & 15, 16));
        return hex.toString();
    }

    // Typed access to JSON values: a wrong type throws WrongType (FORMAT.md rule 7); missing is empty or null.

    private static final class WrongType extends RuntimeException {
        WrongType(String path) { super(path + " has the wrong JSON type"); }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> object(Object value, String path) {
        if (value == null) return Collections.emptyMap();
        if (!(value instanceof Map)) throw new WrongType(path);
        return (Map<String, Object>) value;
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> rows(Object value, String path) {
        if (value == null) return Collections.emptyList();
        if (!(value instanceof List)) throw new WrongType(path);
        for (Object row : (List<Object>) value) if (!(row instanceof Map)) throw new WrongType(path);
        return (List<Map<String, Object>>) value;
    }

    private static String text(Object value, String path) {
        if (!(value instanceof String)) throw new WrongType(path);
        return (String) value;
    }

    private static String optionalText(Object value, String path) { return value == null ? null : text(value, path); }

    private static Double number(Object value, String path) {
        if (value == null) return null;
        if (!(value instanceof Number)) throw new WrongType(path);
        return ((Number) value).doubleValue();
    }

    private static List<String> texts(Object value, String path) {
        if (value == null) return Collections.emptyList();
        if (!(value instanceof List)) throw new WrongType(path);
        List<String> out = new ArrayList<>();
        for (Object item : (List<?>) value) out.add(text(item, path));
        return Collections.unmodifiableList(out);
    }

    private static Estimate estimate(Object value, String path) {
        Map<String, Object> row = object(value, path);
        Object interval = row.get("interval");
        double[] bounds = null;
        if (interval != null) {
            if (!(interval instanceof List) || ((List<?>) interval).size() != 2) throw new WrongType(path + ".interval");
            List<?> pair = (List<?>) interval;
            if (!(pair.get(0) instanceof Number) || !(pair.get(1) instanceof Number)) throw new WrongType(path + ".interval");
            bounds = new double[]{((Number) pair.get(0)).doubleValue(), ((Number) pair.get(1)).doubleValue()};
        }
        return new Estimate(number(row.get("value"), path + ".value"), bounds);
    }
}
