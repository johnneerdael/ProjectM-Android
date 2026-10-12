package com.example.projectm.visualizer;

import java.text.NumberFormat;
import java.util.*;
import nl.neerdael.projectm.core.PresetFacets;

/** Mood panel state: facet selection, collection choice, persistence and engine pool. No views. */
final class MoodFacetsController {
    interface Prefs { String get(String key, String fallback); void put(String key, String value); }
    interface Engine { void setPresetPool(String[] names); void setMusicCategory(String id); int customCount(); }
    interface SkipList { Set<String> names(); }

    static final String PREF_FACETS = "mood_facets", PREF_COLLECTION = "mood_collection", PREF_CATEGORY = "music_category";
    private static final int FEW = 20;

    private final PresetFacets facets;
    private final Prefs prefs;
    private final Engine engine;
    private final SkipList skips;
    private final LinkedHashSet<String> selected = new LinkedHashSet<>();
    private String collection;

    MoodFacetsController(PresetFacets facets, Prefs prefs, Engine engine, SkipList skips) {
        this.facets = facets; this.prefs = prefs; this.engine = engine; this.skips = skips;
        collection = "custom".equals(prefs.get(PREF_COLLECTION, "bundled")) ? "custom" : "bundled";
        String stored = prefs.get(PREF_FACETS, "");
        if (facets != null && !stored.isEmpty())
            selected.addAll(facets.select(Arrays.asList(stored.split(",")), Collections.<String>emptySet()).selected());
    }

    boolean facetsAvailable() { return facets != null; }
    Set<String> selected() { return Collections.unmodifiableSet(selected); }
    String collection() { return collection; }

    PresetFacets.Selection selection() {
        return facets == null ? null : facets.select(selected, skips.names());
    }

    void toggle(String optionId) {
        if (facets == null || "custom".equals(collection)) return;
        PresetFacets.Selection current = selection();
        if (!selected.remove(optionId)) {
            if (current.isDimmed(optionId) || current.countIfToggled(optionId) == 0) return;
            selected.add(optionId);
        }
        apply();
    }

    void clearAll() { selected.clear(); apply(); }

    void setCollection(String id) {
        collection = "custom".equals(id) && engine.customCount() > 0 ? "custom" : "bundled";
        apply();
    }

    void apply() {
        prefs.put(PREF_FACETS, String.join(",", selected));
        prefs.put(PREF_COLLECTION, collection);
        String category;
        if ("custom".equals(collection)) category = "custom";
        else if (facets != null && !selected.isEmpty()) {
            engine.setPresetPool(selection().presetNames());
            category = "facets";
        } else category = "all";
        prefs.put(PREF_CATEGORY, category);
        engine.setMusicCategory(category);
    }

    String header() {
        if ("custom".equals(collection)) return "Custom pack";
        if (facets == null || selected.isEmpty()) return facets == null ? "All presets" : "All presets in your mix";
        int size = selection().poolSize();
        String text = NumberFormat.getIntegerInstance(Locale.US).format(size) + " presets in your mix";
        return size < FEW ? text + " · few presets: some repetition" : text;
    }
}
