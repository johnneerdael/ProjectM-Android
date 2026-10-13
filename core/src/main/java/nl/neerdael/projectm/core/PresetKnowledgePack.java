package nl.neerdael.projectm.core;

import android.content.res.AssetManager;
import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import java.util.zip.GZIPInputStream;

/**
 * Reader for a preset knowledge pack (preset-knowledge-pack-v1): source-only recipes for a preset
 * collection, specified in tools/milk-analyzer/export-contract/knowledge-pack/FORMAT.md and checked
 * against the shared golden vectors there. The pack is plain gzip, JSON and SHA-256; no Android
 * types are used outside load(), so the same reader serves the app, Milkbeat and JVM tools.
 *
 * Recipes are streamed: each line is hash-checked, parsed and reduced to its {@link Preset} view,
 * so memory stays proportional to the views, not to the recipes. Callers that need other recipe
 * fields receive each parsed recipe once through a {@link RecipeVisitor}.
 */
public final class PresetKnowledgePack {
    public static final String POLICY = "preset-knowledge-pack-v1";
    public static final String RECIPE_POLICY = "preset-visual-recipe-v1";
    public static final String MANIFEST = "manifest.json";

    /** A pack that breaks one of the FORMAT.md reader rules; {@link #rule} names it. */
    public static final class InvalidPackException extends IOException {
        public final String rule;
        InvalidPackException(String rule, String detail) { super(rule + ": " + detail); this.rule = rule; }
    }

    /** Receives each parsed recipe once, in manifest order, after its line hash is verified. */
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

        Preset(Map<String, Object> recipe) {
            Map<String, Object> preset = map(recipe.get("preset"));
            name = (String) preset.get("name");
            sha256 = (String) preset.get("sha256");
            Map<String, Object> intent = map(recipe.get("intent"));
            List<Effect> e = new ArrayList<>();
            for (Object row : list(intent.get("effects"))) {
                Map<String, Object> fields = new LinkedHashMap<>(map(row));
                Object effect = fields.remove("effect"), stage = fields.remove("stage");
                e.add(new Effect((String) effect, (String) stage, Collections.unmodifiableMap(fields)));
            }
            effects = Collections.unmodifiableList(e);
            List<Reaction> r = new ArrayList<>();
            for (Object row : list(intent.get("reactivity"))) {
                Map<String, Object> m = map(row);
                r.add(new Reaction((String) m.get("band"), (String) m.get("target"), (String) m.get("kind"), (String) m.get("response")));
            }
            reactivity = Collections.unmodifiableList(r);
            Map<String, Object> estimate = map(recipe.get("display_estimate"));
            Map<String, Object> statistics = map(estimate.get("statistics"));
            meanLuminance = estimate(statistics.get("mean_luminance"));
            meanAbsFrameDifference = estimate(statistics.get("mean_abs_frame_difference"));
            Map<String, Object> activityRow = map(estimate.get("activity"));
            activity = number(activityRow.get("activity"));
            activityBands = strings(activityRow.get("bands"));
            Map<String, Object> facets = map(recipe.get("facets"));
            facetOptions = strings(facets.get("options"));
            Map<String, Double> values = new TreeMap<>();
            for (Map.Entry<String, Object> v : map(facets.get("values")).entrySet()) values.put(v.getKey(), number(map(v.getValue()).get("value")));
            facetValues = Collections.unmodifiableMap(values);
            energyTags = strings(map(intent.get("energy")).get("tags"));
        }
    }

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

    public static PresetKnowledgePack read(File directory) throws IOException {
        try (InputStream manifest = new FileInputStream(new File(directory, MANIFEST));
             InputStream core = new FileInputStream(new File(directory, "core.jsonl.gz"))) {
            return read(manifest, core, null);
        }
    }

    /**
     * Reads a pack from its manifest and core streams (the core file named by the manifest).
     * Applies every FORMAT.md reader rule and throws {@link InvalidPackException} when one fails.
     * The core is streamed: each line is checked against its manifest hash before it is parsed or
     * visited, and the core file hash is checked when the stream ends (a mismatch still rejects
     * the pack after the visitor has seen the line-verified recipes).
     */
    public static PresetKnowledgePack read(InputStream manifestStream, InputStream coreStream, RecipeVisitor visitor) throws IOException {
        Map<String, Object> manifest = map(Json.parse(new String(bytes(manifestStream), StandardCharsets.UTF_8)));
        if (!POLICY.equals(manifest.get("policy"))) throw new InvalidPackException("pack policy", String.valueOf(manifest.get("policy")));
        if (!RECIPE_POLICY.equals(manifest.get("recipe_policy")))
            throw new InvalidPackException("recipe policy", String.valueOf(manifest.get("recipe_policy")));
        List<Object> entries = list(manifest.get("presets"));
        List<Preset> presets = new ArrayList<>(entries.size());
        DigestInputStream digested = new DigestInputStream(coreStream, digest());
        Line line = new Line();
        int index = 0;
        try (InputStream in = new BufferedInputStream(new GZIPInputStream(digested, 1 << 16), 1 << 16)) {
            while (line.next(in)) {
                if (line.length == 0) continue;
                if (index >= entries.size()) throw new InvalidPackException("preset count", "more core lines than manifest presets");
                Map<String, Object> entry = map(entries.get(index++));
                if (!hex(digest().digest(Arrays.copyOf(line.bytes, line.length))).equals(entry.get("core_line_sha256")))
                    throw new InvalidPackException("core line hash", String.valueOf(entry.get("name")));
                Map<String, Object> recipe = map(Json.parse(new String(line.bytes, 0, line.length, StandardCharsets.UTF_8)));
                if (!RECIPE_POLICY.equals(recipe.get("policy")))
                    throw new InvalidPackException("recipe policy", entry.get("name") + ": " + recipe.get("policy"));
                Preset preset = new Preset(recipe);
                if (!Objects.equals(preset.name, entry.get("name")) || !Objects.equals(preset.sha256, entry.get("sha256")))
                    throw new InvalidPackException("recipe identity", String.valueOf(entry.get("name")));
                if (visitor != null) visitor.visit(preset, recipe);
                presets.add(preset);
            }
            byte[] rest = new byte[1 << 12];
            while (digested.read(rest) > 0) { /* hash any bytes after the gzip member */ }
        }
        if (index != entries.size()) throw new InvalidPackException("preset count", "manifest lists " + entries.size() + ", core holds " + index);
        if (!hex(digested.getMessageDigest().digest()).equals(map(manifest.get("core")).get("sha256")))
            throw new InvalidPackException("core file hash", "core file bytes differ from manifest core.sha256");
        return new PresetKnowledgePack(Collections.unmodifiableMap(manifest), presets);
    }

    /** One LF-terminated line of the decompressed core, reusing its buffer. */
    private static final class Line {
        byte[] bytes = new byte[1 << 16];
        int length;

        boolean next(InputStream in) throws IOException {
            length = 0;
            int b;
            while ((b = in.read()) >= 0) {
                if (b == '\n') return true;
                if (length == bytes.length) bytes = Arrays.copyOf(bytes, bytes.length * 2);
                bytes[length++] = (byte) b;
            }
            return length > 0;
        }
    }

    /** A pack bundled under assets/{directory}, or null when it is missing or invalid. */
    public static PresetKnowledgePack load(AssetManager assets, String directory) {
        try (InputStream manifest = assets.open(directory + "/" + MANIFEST);
             InputStream core = assets.open(directory + "/core.jsonl.gz")) {
            return read(manifest, core, null);
        } catch (IOException missingOrInvalid) {
            return null;
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

    @SuppressWarnings("unchecked")
    private static Map<String, Object> map(Object value) {
        return value instanceof Map ? (Map<String, Object>) value : Collections.<String, Object>emptyMap();
    }

    @SuppressWarnings("unchecked")
    private static List<Object> list(Object value) {
        return value instanceof List ? (List<Object>) value : Collections.emptyList();
    }

    private static Double number(Object value) { return value instanceof Number ? ((Number) value).doubleValue() : null; }

    private static List<String> strings(Object value) {
        List<String> out = new ArrayList<>();
        for (Object item : list(value)) if (item instanceof String) out.add((String) item);
        return Collections.unmodifiableList(out);
    }

    private static Estimate estimate(Object value) {
        Map<String, Object> row = map(value);
        List<Object> interval = list(row.get("interval"));
        double[] bounds = interval.size() == 2 && interval.get(0) instanceof Number && interval.get(1) instanceof Number
                ? new double[]{((Number) interval.get(0)).doubleValue(), ((Number) interval.get(1)).doubleValue()} : null;
        return new Estimate(number(row.get("value")), bounds);
    }
}
