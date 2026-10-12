package com.example.projectm.visualizer;

import java.util.ArrayList;

final class MusicCategories {
    interface Counts { int count(String id); }
    private static final String[] IDS = {"all", "chill", "normal", "intense", "custom"};
    private static final String[] LABELS = {"All", "Chill", "Normal", "Intense", "Custom"};

    static String normalize(String id) {
        if ("facets".equals(id)) return id;  // the Mood panel's facet pool
        for (String candidate : IDS) if (candidate.equals(id)) return id;
        return "all";
    }
    static String label(String id) {
        for (int i = 0; i < IDS.length; i++) if (IDS[i].equals(id)) return LABELS[i];
        return LABELS[0];
    }
    static String[] available(Counts counts) {
        ArrayList<String> ids = new ArrayList<>();
        ids.add("all");
        for (int i = 1; i < IDS.length; i++) if (counts.count(IDS[i]) > 0) ids.add(IDS[i]);
        return ids.toArray(new String[0]);
    }
    static int selectedIndex(String[] ids, String selected) {
        for (int i = 0; i < ids.length; i++) if (ids[i].equals(selected)) return i;
        return 0;
    }
    static String appliedSelection(String requested, String actual, boolean pending) {
        return normalize(pending ? requested : actual);
    }
    private MusicCategories() {}
}
