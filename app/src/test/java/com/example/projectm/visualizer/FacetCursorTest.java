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

    @Test public void tapOnDimmedChipKeepsCursor() {
        boolean[] selectable = {true, false, true};
        assertEquals(0, FacetCursor.afterTap(0, 1, selectable, true));
    }

    @Test public void tapOnSelectableChipMovesCursor() {
        boolean[] selectable = {true, false, true};
        assertEquals(2, FacetCursor.afterTap(0, 2, selectable, true));
    }

    @Test public void tapWhileDisabledNeverMovesOntoNonSelectableChip() {
        boolean[] selectable = {true, false, true};
        assertEquals(0, FacetCursor.afterTap(0, 1, selectable, false));
        assertEquals(0, FacetCursor.afterTap(0, 7, selectable, false));
    }

    @Test public void rowDescriptionNamesTitleAndFocusedChip() {
        assertEquals("Energy: Chill, selected, 12 presets",
                FacetCursor.rowDescription("Energy", "Chill, selected, 12 presets", true));
        assertEquals("Energy: Chill, selected, 12 presets, unavailable",
                FacetCursor.rowDescription("Energy", "Chill, selected, 12 presets", false));
        assertEquals("Energy", FacetCursor.rowDescription("Energy", null, true));
        assertEquals("Energy, unavailable", FacetCursor.rowDescription("Energy", null, false));
    }
}
