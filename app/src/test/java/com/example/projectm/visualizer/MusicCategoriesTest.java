package com.example.projectm.visualizer;

import org.junit.Test;
import static org.junit.Assert.*;

public class MusicCategoriesTest {
    @Test public void customIsSelectableOnlyWithAnInstalledPack() {
        assertEquals("custom", MusicCategories.normalize("custom"));
        assertEquals("Custom", MusicCategories.label("custom"));
        assertArrayEquals(new String[]{"all", "custom"},
                MusicCategories.available(id -> "custom".equals(id) ? 50000 : 0));
        assertArrayEquals(new String[]{"all"}, MusicCategories.available(id -> 0));
    }
    @Test public void onlyAvailablePredictiveGroupsAreSelectable() {
        String[] ids = MusicCategories.available(id -> "all".equals(id) ? 14 : "intense".equals(id) ? 3 : 0);
        assertArrayEquals(new String[]{"all", "intense"}, ids);
        assertEquals("Intense", MusicCategories.label("intense"));
    }
    @Test public void unknownPersistenceFallsBackToAll() {
        assertEquals("all", MusicCategories.normalize("nonexistent"));
        assertEquals("all", MusicCategories.normalize(null));
        assertEquals("all", MusicCategories.normalize("ambient"));
        assertEquals("facets", MusicCategories.normalize("facets"));  // the Mood panel's pool
    }
    @Test public void pendingRequestDoesNotBecomeFalseFallback() {
        assertEquals("intense", MusicCategories.appliedSelection("intense", "all", true));
        assertEquals("all", MusicCategories.appliedSelection("intense", "all", false));
        assertEquals("intense", MusicCategories.appliedSelection("intense", "intense", false));
    }
    @Test public void retiredSelectionsReturnToAll() {
        assertEquals("all", MusicCategories.normalize("dance"));
        assertEquals("all", MusicCategories.normalize("pop"));
        assertEquals("Chill", MusicCategories.label("chill"));
        assertEquals("Normal", MusicCategories.label("normal"));
    }
    @Test public void selectedIndexUsesStableIds() {
        assertEquals(1, MusicCategories.selectedIndex(new String[]{"all","intense"}, "intense"));
        assertEquals(0, MusicCategories.selectedIndex(new String[]{"all"}, "intense"));
    }
}
