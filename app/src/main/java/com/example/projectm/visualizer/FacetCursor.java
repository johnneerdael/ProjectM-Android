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
}
