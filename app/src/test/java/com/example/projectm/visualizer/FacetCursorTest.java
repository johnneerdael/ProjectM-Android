package com.example.projectm.visualizer;

import static org.junit.Assert.assertEquals;
import org.junit.Test;

public class FacetCursorTest {
    @Test public void skipsDimmedOptionsWithoutWrapping() {
        boolean[] selectable = {true, false, false, true, true};
        assertEquals(3, FacetCursor.move(0, 1, selectable));
        assertEquals(4, FacetCursor.move(3, 1, selectable));
        assertEquals(4, FacetCursor.move(4, 1, selectable));
        assertEquals(0, FacetCursor.move(3, -1, selectable));
        assertEquals(0, FacetCursor.move(0, -1, selectable));
    }

    @Test public void firstSelectableIsUsedWhenTheCurrentOptionBecomesDimmed() {
        boolean[] selectable = {false, false, true};
        assertEquals(2, FacetCursor.first(selectable, 0));
        assertEquals(-1, FacetCursor.first(new boolean[]{false, false}, 0));
    }
}
