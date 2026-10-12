package com.example.projectm.visualizer;

import java.text.NumberFormat;
import java.util.*;
import nl.neerdael.projectm.core.PresetFacets;

/** Mood panel state: facet selection, collection choice, persistence and engine pool. No views. */
final class MoodFacetsController {
    interface Prefs { String get(String key, String fallback); void put(String key, String value); }
    /** count(category) is the engine's preset count for a category ("all", "custom", "facets"); 0 while unknown. */
    interface Engine { void setPresetPool(String[] names); void setMusicCategory(String id); int count(String category); boolean customPending(); }
    interface SkipList { Set<String> names(); }

    static final String PREF_FACETS = "mood_facets", PREF_COLLECTION = "mood_collection", PREF_CATEGORY = "music_category";
    private static final int FEW = 20;
    /** Header when the installed official collection predates preset attributes (F-Droid). */
    static final String OUTDATED_DOWNLOAD = "Download the full collection again to choose moods (Settings › Advanced › Cream of the Crop)";

    private final PresetFacets facets;
    private final Prefs prefs;
    private final Engine engine;
    private final SkipList skips;
    private final boolean outdatedDownload;
    private final LinkedHashSet<String> selected = new LinkedHashSet<>();
    private String collection;

    /**
     * @param outdatedDownload the facet table is missing because the installed official collection
     *                         was downloaded before collections carried preset attributes
     */
    MoodFacetsController(PresetFacets facets, Prefs prefs, Engine engine, SkipList skips, boolean outdatedDownload) {
        this.facets = facets; this.prefs = prefs; this.engine = engine; this.skips = skips;
        this.outdatedDownload = facets == null && outdatedDownload;
        collection = "custom".equals(prefs.get(PREF_COLLECTION, "bundled")) ? "custom" : "bundled";
        String stored = prefs.get(PREF_FACETS, "");
        if (facets != null && !stored.isEmpty())
            selected.addAll(facets.select(Arrays.asList(stored.split(",")), Collections.<String>emptySet()).selected());
        validateCollection();
    }

    /** A custom collection whose pack is gone, and not being restored, plays the bundled one again. */
    private void validateCollection() {
        if ("custom".equals(collection) && engine.count("custom") <= 0 && !engine.customPending()) collection = "bundled";
    }

    /** Re-checks the custom collection; returns true when it fell back to bundled (and applied that). */
    boolean revalidateCollection() {
        String before = collection;
        validateCollection();
        if (before.equals(collection)) return false;
        apply();
        return true;
    }

    /** A selection that matches no playable preset (all skipped, or no preset fits every group): All plays, the selection stays stored. */
    boolean exhausted() {
        return facets != null && !selected.isEmpty() && "bundled".equals(collection) && selection().poolSize() == 0;
    }

    boolean facetsAvailable() { return facets != null; }
    boolean outdatedDownload() { return outdatedDownload; }
    /** Clear all applies only to the built-in collection; Custom keeps the stored facets untouched. */
    boolean canClear() { return "bundled".equals(collection); }
    Set<String> selected() { return Collections.unmodifiableSet(selected); }
    String collection() { return collection; }

    PresetFacets.Selection selection() {
        return facets == null ? null : facets.select(selected, skips.names());
    }

    void toggle(String optionId) {
        validateCollection();
        if (facets == null || "custom".equals(collection)) return;
        PresetFacets.Selection current = selection();
        if (!selected.remove(optionId)) {
            if (current.isDimmed(optionId) || current.countIfToggled(optionId) == 0) return;
            selected.add(optionId);
        }
        apply();
    }

    /**
     * The "-> N" of an option's chip: the presets left if it were toggled. Removing the only selected
     * option selects the engine's All category (which Custom joins), so that count comes from the engine.
     */
    int optionCount(String optionId) {
        PresetFacets.Selection current = selection();
        if (current == null) return 0;
        if (selected.size() == 1 && selected.contains(optionId)) {
            int all = engine.count("all");
            if (all > 0) return all;
        }
        return current.countIfToggled(optionId);
    }

    void clearAll() {
        validateCollection();
        if (!canClear()) return;
        selected.clear();
        apply();
    }

    void setCollection(String id) {
        collection = "custom".equals(id) && engine.count("custom") > 0 ? "custom" : "bundled";
        apply();
    }

    /** Comma-joined ids; String.join needs API 26 and the app supports API 21. */
    private static String joinIds(Collection<String> ids) {
        StringBuilder out = new StringBuilder();
        for (String id : ids) {
            if (out.length() > 0) out.append(',');
            out.append(id);
        }
        return out.toString();
    }

    private int lastSkipCount = -1;

    /**
     * Call with the engine's skip count while the panel is visible. The first call records the baseline.
     * When the count changed, a selection in the built-in collection sends its pool again (the pool
     * leaves skipped presets out, and may now be exhausted) and true tells the caller to re-render.
     */
    boolean skipsChanged(int skipCount) {
        int before = lastSkipCount;
        lastSkipCount = skipCount;
        if (before < 0 || before == skipCount) return false;
        if (facets != null && !selected.isEmpty() && "bundled".equals(collection)) apply();
        return true;
    }

    void apply() {
        validateCollection();
        // Without a facet table the stored ids cannot be checked: keep them for a later table.
        if (facets != null) prefs.put(PREF_FACETS, joinIds(selected));
        prefs.put(PREF_COLLECTION, collection);
        String category;
        if ("custom".equals(collection)) category = "custom";
        else if (facets != null && !selected.isEmpty() && !exhausted()) {
            engine.setPresetPool(selection().presetNames());
            category = "facets";
        } else category = "all";
        prefs.put(PREF_CATEGORY, category);
        engine.setMusicCategory(category);
    }

    /** The pool size line: always a count when one is known. */
    String header() {
        NumberFormat format = NumberFormat.getIntegerInstance();
        if ("custom".equals(collection)) {
            int custom = engine.count("custom");
            return custom > 0 ? "Custom pack: " + format.format(custom) + " presets" : "Custom pack";
        }
        if (outdatedDownload) return OUTDATED_DOWNLOAD;
        if (facets == null || selected.isEmpty()) {
            int all = engine.count("all");
            return all > 0 ? format.format(all) + " presets in your mix" : "All presets in your mix";
        }
        // Every selected preset is skipped, or deselecting left groups that no preset satisfies together.
        if (exhausted()) return "No presets match your mix; playing All";
        int size = selection().poolSize();
        String text = format.format(size) + " presets in your mix";
        return size < FEW ? text + " · few presets: some repetition" : text;
    }
}
