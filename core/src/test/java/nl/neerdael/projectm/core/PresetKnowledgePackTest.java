package nl.neerdael.projectm.core;

import static org.junit.Assert.*;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import org.junit.Test;

/** Runs the shared golden vectors of tools/milk-analyzer/export-contract/knowledge-pack (FORMAT.md). */
public class PresetKnowledgePackTest {
    private static final File GOLDEN = new File("../tools/milk-analyzer/export-contract/knowledge-pack/golden-v1");

    @SuppressWarnings("unchecked")
    private static Map<String, Object> expected() throws IOException {
        return (Map<String, Object>) Json.parse(new String(Files.readAllBytes(new File(GOLDEN, "expected.json").toPath()), StandardCharsets.UTF_8));
    }

    /** The reader view of FORMAT.md, in the same shape as expected.json. */
    private static Map<String, Object> view(PresetKnowledgePack.Preset p) {
        Map<String, Object> v = new LinkedHashMap<>();
        v.put("name", p.name);
        v.put("sha256", p.sha256);
        List<Object> effects = new ArrayList<>();
        for (PresetKnowledgePack.Effect e : p.effects) effects.add(e.name);
        v.put("effects", effects);
        List<Object> reactivity = new ArrayList<>();
        for (PresetKnowledgePack.Reaction r : p.reactivity) reactivity.add(Arrays.asList(r.band, r.target, r.kind, r.response));
        v.put("reactivity", reactivity);
        v.put("mean_luminance", estimate(p.meanLuminance));
        v.put("mean_abs_frame_difference", estimate(p.meanAbsFrameDifference));
        v.put("activity", p.activity);
        v.put("activity_bands", new ArrayList<Object>(p.activityBands));
        v.put("facet_options", new ArrayList<Object>(p.facetOptions));
        v.put("facet_values", new LinkedHashMap<String, Object>(p.facetValues));
        v.put("energy_tags", new ArrayList<Object>(p.energyTags));
        return v;
    }

    private static Map<String, Object> estimate(PresetKnowledgePack.Estimate e) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("value", e.value);
        m.put("interval", e.interval == null ? null : Arrays.<Object>asList(e.interval[0], e.interval[1]));
        return m;
    }

    private static void assertClose(String where, Object expected, Object actual, double tolerance) {
        if (expected instanceof Number || actual instanceof Number) {
            assertNotNull(where, expected);
            assertNotNull(where, actual);
            assertEquals(where, ((Number) expected).doubleValue(), ((Number) actual).doubleValue(), tolerance);
        } else if (expected instanceof List) {
            List<?> a = (List<?>) expected, b = (List<?>) actual;
            assertEquals(where + " size", a.size(), b.size());
            for (int i = 0; i < a.size(); i++) assertClose(where + "[" + i + "]", a.get(i), b.get(i), tolerance);
        } else if (expected instanceof Map) {
            Map<?, ?> a = (Map<?, ?>) expected, b = (Map<?, ?>) actual;
            assertEquals(where + " keys", new ArrayList<>(a.keySet()), new ArrayList<>(b.keySet()));
            for (Object k : a.keySet()) assertClose(where + "." + k, a.get(k), b.get(k), tolerance);
        } else {
            assertEquals(where, expected, actual);
        }
    }

    @Test
    @SuppressWarnings("unchecked")
    public void acceptedPacksExposeTheExpectedView() throws IOException {
        Map<String, Object> expected = expected();
        double tolerance = ((Number) expected.get("float_tolerance")).doubleValue();
        Map<String, Object> accept = (Map<String, Object>) expected.get("accept");
        assertEquals(new HashSet<>(Arrays.asList("valid", "unknown-fields")), accept.keySet());
        for (Map.Entry<String, Object> pack : accept.entrySet()) {
            PresetKnowledgePack read = PresetKnowledgePack.read(new File(GOLDEN, pack.getKey()));
            List<Object> views = new ArrayList<>();
            for (String name : read.names()) views.add(view(read.byName(name)));
            assertClose(pack.getKey(), pack.getValue(), views, tolerance);
            PresetKnowledgePack.Preset first = read.byName(read.names().get(0));
            assertSame(first, read.bySha256(first.sha256));
        }
    }

    @Test
    @SuppressWarnings("unchecked")
    public void eachBrokenPackIsRejectedForItsRule() throws IOException {
        Map<String, Object> reject = (Map<String, Object>) expected().get("reject");
        assertEquals(9, reject.size());
        for (Map.Entry<String, Object> pack : reject.entrySet()) {
            final List<String> visited = new ArrayList<>();
            try {
                PresetKnowledgePack.read(new File(GOLDEN, pack.getKey()), (preset, recipe) -> visited.add(preset.name));
                fail(pack.getKey() + " was accepted");
            } catch (PresetKnowledgePack.InvalidPackException e) {
                assertEquals(pack.getKey(), pack.getValue(), e.rule);
            }
            // Nothing from a rejected pack is handed out, whichever line breaks the rule.
            assertEquals(pack.getKey(), Collections.emptyList(), visited);
        }
    }

    @Test
    public void rawRecipesAreHandedOverWhileStreamingAndNotRetained() throws IOException {
        File valid = new File(GOLDEN, "valid");
        final List<String> seen = new ArrayList<>();
        PresetKnowledgePack read = PresetKnowledgePack.read(
                new ByteArrayInputStream(Files.readAllBytes(new File(valid, "manifest.json").toPath())),
                new ByteArrayInputStream(Files.readAllBytes(new File(valid, "core.jsonl.gz").toPath())),
                (preset, recipe) -> seen.add(preset.name + ":" + ((Map<?, ?>) recipe.get("intent")).containsKey("effects")));
        assertEquals(read.names().size(), seen.size());
        assertTrue(seen.get(0).endsWith(":true"));
        assertEquals(3, read.size());
    }

    @Test
    public void jsonParserHandlesEscapesNumbersAndNesting() throws IOException {
        Object parsed = Json.parse("{\"a\":[1,-2.5e-3,true,false,null],\"s\":\"q\\\"\\\\\\/\\n\\u00e9\\ud83c\\udfb5\",\"o\":{}}");
        Map<?, ?> m = (Map<?, ?>) parsed;
        assertEquals(Arrays.asList(1.0, -0.0025, true, false, null), m.get("a"));
        assertEquals("q\"\\/\n\u00e9\ud83c\udfb5", m.get("s"));
        assertTrue(((Map<?, ?>) m.get("o")).isEmpty());
        for (String bad : new String[]{"{", "[1,]", "{\"a\" 1}", "01", "\"\\x\"", "[1] 2", "nul"}) {
            try {
                Json.parse(bad);
                fail(bad);
            } catch (IOException expected) {
                // malformed input is reported, never silently accepted
            }
        }
    }
}
