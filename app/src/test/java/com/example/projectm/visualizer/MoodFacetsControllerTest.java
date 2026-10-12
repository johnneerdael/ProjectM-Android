package com.example.projectm.visualizer;

import static org.junit.Assert.*;
import java.io.IOException;
import java.io.StringReader;
import java.util.*;
import nl.neerdael.projectm.core.PresetFacets;
import org.junit.Before;
import org.junit.Test;

public class MoodFacetsControllerTest {
    private static final String TABLE =
            "#projectm-tv-preset-attributes\t1\n#definition\tx\n#group\tenergy\tEnergy\n#option\tenergy\tchill\tChill\n#option\tenergy\tintense\tIntense\n"
            + "#group\tcomfort\tComfort\n#option\tcomfort\tno_strobe\tNo strobe\n"
            + "#columns\tname\toptions\tluminance\tsaturation\tcoloured_share\twarm_cool\tflow\tframe_difference\tjumps\tactivity\n"
            + "a.milk\tchill,no_strobe\t0\t0\t0\t0\t0\t0\t0\t0\nb.milk\tintense\t0\t0\t0\t0\t0\t0\t0\t0\nc.milk\tchill\t0\t0\t0\t0\t0\t0\t0\t0\n";
    private final Map<String, String> store = new HashMap<>();
    private final List<String> calls = new ArrayList<>();
    private final Set<String> skipped = new HashSet<>();
    private int customCount = 0;
    private PresetFacets facets;

    @Before public void setUp() throws IOException { facets = PresetFacets.parse(new StringReader(TABLE)); }

    private MoodFacetsController controller(PresetFacets table) {
        return new MoodFacetsController(table,
                new MoodFacetsController.Prefs() {
                    public String get(String k, String f) { return store.containsKey(k) ? store.get(k) : f; }
                    public void put(String k, String v) { store.put(k, v); }
                },
                new MoodFacetsController.Engine() {
                    public void setPresetPool(String[] names) { calls.add("pool:" + (names == null ? "null" : String.join(",", names))); }
                    public void setMusicCategory(String id) { calls.add("category:" + id); }
                    public int customCount() { return customCount; }
                },
                () -> skipped);
    }

    @Test public void toggleAppliesPoolThenFacetsCategoryAndPersists() {
        MoodFacetsController c = controller(facets);
        c.toggle("chill");
        assertEquals(Arrays.asList("pool:a.milk,c.milk", "category:facets"), calls);
        assertEquals("chill", store.get("mood_facets"));
        assertEquals("facets", store.get("music_category"));
        assertEquals("2 presets in your mix · few presets: some repetition", c.header());
    }

    @Test public void clearingEverythingRestoresAll() {
        store.put("mood_facets", "chill");
        MoodFacetsController c = controller(facets);
        c.clearAll();
        assertEquals("", store.get("mood_facets"));
        assertTrue(calls.contains("category:all"));
        assertEquals("All presets in your mix", c.header());
    }

    @Test public void dimmedOptionsCannotBeToggledOn() {
        store.put("mood_facets", "no_strobe");
        MoodFacetsController c = controller(facets);
        assertTrue(c.selection().isDimmed("intense"));
        c.toggle("intense");
        assertEquals("no_strobe", store.get("mood_facets"));
    }

    @Test public void unknownStoredIdsAreDroppedAndTheRestKept() {
        store.put("mood_facets", "chill,retired_option");
        MoodFacetsController c = controller(facets);
        assertEquals(Collections.singleton("chill"), c.selected());
        c.apply();
        assertEquals("chill", store.get("mood_facets"));
    }

    @Test public void customCollectionDisablesFacetsAndKeepsThemStored() {
        customCount = 3;
        store.put("mood_facets", "chill");
        MoodFacetsController c = controller(facets);
        c.setCollection("custom");
        assertTrue(calls.contains("category:custom"));
        assertEquals("chill", store.get("mood_facets"));
        c.toggle("intense");  // ignored while custom plays
        assertEquals("chill", store.get("mood_facets"));
        c.setCollection("bundled");
        assertEquals("category:facets", calls.get(calls.size() - 1));
    }

    @Test public void skippedPresetsAreExcludedFromCountsAndPool() {
        skipped.add("a.milk");
        MoodFacetsController c = controller(facets);
        c.toggle("chill");
        assertEquals("pool:c.milk", calls.get(0));
    }

    @Test public void missingTableOffersOnlyTheCollection() {
        MoodFacetsController c = controller(null);
        assertFalse(c.facetsAvailable());
        assertNull(c.selection());
        c.toggle("chill");
        assertTrue(calls.isEmpty());
        assertEquals("All presets", c.header());
    }
}
