package com.example.projectm.visualizer;

/** Option cursor of a facet row: moves skip options that cannot be selected (dimmed). */
final class FacetCursor {
    private FacetCursor() {}

    static int move(int current, int direction, boolean[] selectable) {
        for (int i = current + direction; i >= 0 && i < selectable.length; i += direction)
            if (selectable[i]) return i;
        return current;
    }

    /** The preferred index if selectable, else the first selectable one, else -1. */
    static int first(boolean[] selectable, int preferred) {
        if (preferred >= 0 && preferred < selectable.length && selectable[preferred]) return preferred;
        for (int i = 0; i < selectable.length; i++) if (selectable[i]) return i;
        return -1;
    }

    /** Cursor after a tap on {@code tapped}: moves only onto a selectable chip, else stays. */
    static int afterTap(int current, int tapped, boolean[] selectable, boolean enabled) {
        if (tapped >= 0 && tapped < selectable.length && selectable[tapped]) return tapped;
        return current;
    }

    /** Accessibility text of the whole row: title, the focused chip's description, disabled state. */
    static String rowDescription(String title, String chipDescription, boolean enabled) {
        String text = chipDescription == null ? title : title + ": " + chipDescription;
        return enabled ? text : text + ", unavailable";
    }
}
