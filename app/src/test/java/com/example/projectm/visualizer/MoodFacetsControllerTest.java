package com.example.projectm.visualizer;

import static org.junit.Assert.*;
import java.io.IOException;
import java.io.StringReader;
import java.text.NumberFormat;
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
    private int allCount = 9606;
    private boolean customPending = false;
    private PresetFacets facets;

    @Before public void setUp() throws IOException { facets = PresetFacets.parse(new StringReader(TABLE)); }

    private MoodFacetsController controller(PresetFacets table) { return controller(table, false); }

    private static String n(int value) { return NumberFormat.getIntegerInstance().format(value); }

    private MoodFacetsController controller(PresetFacets table, boolean outdatedDownload) {
        return new MoodFacetsController(table,
                new MoodFacetsController.Prefs() {
                    public String get(String k, String f) { return store.containsKey(k) ? store.get(k) : f; }
                    public void put(String k, String v) { store.put(k, v); }
                },
                new MoodFacetsController.Engine() {
                    public void setPresetPool(String[] names) { calls.add("pool:" + (names == null ? "null" : String.join(",", names))); }
                    public void setMusicCategory(String id) { calls.add("category:" + id); }
                    public int count(String category) { return "custom".equals(category) ? customCount : "all".equals(category) ? allCount : -1; }
                    public boolean customPending() { return customPending; }
                },
                () -> skipped, outdatedDownload);
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
        assertEquals(n(9606) + " presets in your mix", c.header());
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
        assertEquals(n(9606) + " presets in your mix", c.header());
    }

    @Test public void missingTableKeepsTheStoredSelection() {
        store.put("mood_facets", "chill");
        MoodFacetsController c = controller(null);
        c.apply();
        assertEquals("chill", store.get("mood_facets"));
        assertEquals("all", store.get("music_category"));
    }

    @Test public void customCollectionWithoutPackFallsBackToBundled() {
        store.put("mood_collection", "custom");
        store.put("mood_facets", "chill");
        MoodFacetsController c = controller(facets);
        c.apply();
        assertEquals("bundled", c.collection());
        assertEquals("bundled", store.get("mood_collection"));
        assertEquals("category:facets", calls.get(calls.size() - 1));
        c.toggle("no_strobe");
        assertEquals("chill,no_strobe", store.get("mood_facets"));
    }

    @Test public void pendingCustomRestoreKeepsCustom() {
        customPending = true;
        store.put("mood_collection", "custom");
        MoodFacetsController c = controller(facets);
        c.apply();
        assertEquals("custom", c.collection());
        assertEquals("category:custom", calls.get(calls.size() - 1));
    }

    @Test public void customPackThatDisappearsReturnsToBundled() {
        customCount = 3;
        store.put("mood_facets", "chill");
        MoodFacetsController c = controller(facets);
        c.setCollection("custom");
        customCount = 0;
        assertTrue(c.revalidateCollection());
        assertEquals("bundled", c.collection());
        assertEquals("category:facets", calls.get(calls.size() - 1));
        assertFalse(c.revalidateCollection());
    }

    @Test public void fullySkippedSelectionPlaysAllAndRecoversAfterReset() {
        skipped.addAll(Arrays.asList("a.milk", "c.milk"));
        store.put("mood_facets", "chill");
        MoodFacetsController c = controller(facets);
        assertEquals("No presets match your mix; playing All", c.header());
        c.apply();
        assertEquals("category:all", calls.get(calls.size() - 1));
        assertEquals("chill", store.get("mood_facets"));
        skipped.clear();
        calls.clear();
        c.apply();
        assertEquals(Arrays.asList("pool:a.milk,c.milk", "category:facets"), calls);
        assertEquals("2 presets in your mix · few presets: some repetition", c.header());
    }

    @Test public void headerCountsUseTheDefaultLocaleAndTheEngineCounts() {
        Locale previous = Locale.getDefault();
        try {
            Locale.setDefault(Locale.GERMANY);
            MoodFacetsController c = controller(facets);
            assertEquals("9.606 presets in your mix", c.header());
        } finally {
            Locale.setDefault(previous);
        }
    }

    @Test public void headerFallsBackWithoutAnEngineCount() {
        allCount = 0;  // the index is still being built
        assertEquals("All presets in your mix", controller(facets).header());
    }

    @Test public void customHeaderShowsTheCustomPackCount() {
        customCount = 1234;
        MoodFacetsController c = controller(facets);
        c.setCollection("custom");
        assertEquals("Custom pack: " + n(1234) + " presets", c.header());
    }

    @Test public void outdatedOfficialDownloadExplainsHowToGetMoods() {
        MoodFacetsController c = controller(null, true);
        assertTrue(c.outdatedDownload());
        assertEquals(MoodFacetsController.OUTDATED_DOWNLOAD, c.header());
        assertTrue(c.header().contains("Settings › Advanced › Cream of the Crop"));
        assertFalse(controller(null, false).outdatedDownload());
    }

    @Test public void clearAllDoesNothingWhileCustomPlays() {
        customCount = 3;
        store.put("mood_facets", "chill");
        MoodFacetsController c = controller(facets);
        c.setCollection("custom");
        calls.clear();
        c.clearAll();
        assertTrue(calls.isEmpty());
        assertEquals("chill", store.get("mood_facets"));
        assertEquals(Collections.singleton("chill"), c.selected());
        assertFalse(c.canClear());
        c.setCollection("bundled");
        assertTrue(c.canClear());
    }

    @Test public void deselectingCanEmptyTheMixAndPlaysAll() {
        MoodFacetsController c = controller(facets);
        c.toggle("chill");
        c.toggle("intense");
        c.toggle("no_strobe");  // (chill OR intense) AND no_strobe = a.milk
        assertEquals(1, c.selection().poolSize());
        c.toggle("chill");      // intense AND no_strobe: nothing
        assertTrue(c.exhausted());
        assertEquals("No presets match your mix; playing All", c.header());
        assertEquals("category:all", calls.get(calls.size() - 1));
    }
}
