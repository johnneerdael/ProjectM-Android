package com.example.projectm.visualizer;

import android.content.Context;
import android.graphics.Paint;
import android.graphics.Rect;
import android.util.AttributeSet;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.ViewGroup;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;

import nl.neerdael.projectm.core.PresetFacets;

/**
 * Settings row for one facet group: a title above a horizontal strip of option chips.
 * D-pad Left/Right move a cursor over the chips (skipping dimmed ones), Center toggles the focused
 * chip, a tap toggles a chip (phone edition). Up/Down are not consumed, so focus keeps moving
 * between rows. The row only renders what {@link #update} hands it and reports toggles.
 */
public class FacetRow extends LinearLayout {
    public interface Listener { void onToggle(String optionId); }

    private final TextView title;
    private final HorizontalScrollView scroller;
    private final LinearLayout chipStrip;
    private final List<TextView> chips = new ArrayList<>();
    private List<PresetFacets.Option> options = Collections.emptyList();
    private Set<String> selected = Collections.emptySet();
    private Map<String, Integer> counts = Collections.emptyMap();
    private Set<String> dimmed = Collections.emptySet();
    private boolean enabled = true;
    private int cursor = -1;
    private Listener listener;

    public FacetRow(Context context) {
        this(context, null);
    }

    public FacetRow(Context context, AttributeSet attrs) {
        super(context, attrs);
        setOrientation(VERTICAL);
        setFocusable(true);
        setClickable(true);
        if (BuildConfig.TOUCHSCREEN) setMinimumHeight(dp(48));
        setBackgroundResource(R.drawable.bg_option_row);
        int h = dp(12), v = dp(9);
        setPadding(h, v, h, v);
        // Chips are touch targets only; D-pad focus stays on the row.
        setDescendantFocusability(FOCUS_BLOCK_DESCENDANTS);

        title = new TextView(context);
        title.setTextColor(getResources().getColor(R.color.text_secondary));
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        title.setSingleLine(true);
        addView(title, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        scroller = new HorizontalScrollView(context);
        scroller.setHorizontalScrollBarEnabled(false);
        scroller.setFocusable(false);
        chipStrip = new LinearLayout(context);
        chipStrip.setOrientation(HORIZONTAL);
        chipStrip.setGravity(Gravity.CENTER_VERTICAL);
        scroller.addView(chipStrip, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LayoutParams sp = new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        sp.topMargin = dp(4);
        addView(scroller, sp);
    }

    /** Sets the group title and its options; call {@link #update} afterwards to show state. */
    public void bind(String titleText, List<PresetFacets.Option> options, Listener listener) {
        title.setText(titleText);
        this.options = options;
        this.listener = listener;
        chips.clear();
        chipStrip.removeAllViews();
        int gap = getResources().getDimensionPixelSize(R.dimen.facet_chip_gap);
        for (int i = 0; i < options.size(); i++) {
            final int index = i;
            TextView chip = new TextView(getContext());
            chip.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
            chip.setSingleLine(true);
            chip.setFocusable(false);
            chip.setOnClickListener(c -> {
                cursor = FacetCursor.afterTap(cursor, index, selectable(), enabled);
                toggle(index);
                render();
            });
            LayoutParams lp = new LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            if (i > 0) lp.leftMargin = gap;
            if (BuildConfig.TOUCHSCREEN) chip.setMinimumHeight(dp(40));
            chip.setGravity(Gravity.CENTER_VERTICAL);
            chipStrip.addView(chip, lp);
            chips.add(chip);
        }
        cursor = FacetCursor.first(selectable(), 0);
        render();
    }

    /** Shows the current selection, per-option preset counts, dimmed options and enabled state. */
    public void update(Set<String> selected, Map<String, Integer> counts, Set<String> dimmed, boolean enabled) {
        this.selected = selected;
        this.counts = counts;
        this.dimmed = dimmed;
        this.enabled = enabled;
        cursor = FacetCursor.first(selectable(), cursor);
        render();
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        boolean[] selectable = selectable();
        switch (keyCode) {
            case KeyEvent.KEYCODE_DPAD_LEFT:
                setCursor(FacetCursor.move(cursor, -1, selectable));
                return true;
            case KeyEvent.KEYCODE_DPAD_RIGHT:
                setCursor(FacetCursor.move(cursor, 1, selectable));
                return true;
            case KeyEvent.KEYCODE_DPAD_CENTER:
            case KeyEvent.KEYCODE_ENTER:
            case KeyEvent.KEYCODE_NUMPAD_ENTER:
                toggle(cursor);
                return true;
            default:
                // Up/Down fall through unconsumed so the panel moves focus between rows.
                return super.onKeyDown(keyCode, event);
        }
    }

    @Override
    protected void onFocusChanged(boolean gainFocus, int direction, Rect previous) {
        super.onFocusChanged(gainFocus, direction, previous);
        render();
    }

    private void toggle(int index) {
        if (!enabled || listener == null || index < 0 || index >= options.size()) return;
        if (!selectable()[index]) return;
        listener.onToggle(options.get(index).id);
    }

    private void setCursor(int next) {
        if (next == cursor) return;
        cursor = next;
        render();
    }

    private boolean[] selectable() {
        boolean[] result = new boolean[options.size()];
        for (int i = 0; i < result.length; i++) {
            String id = options.get(i).id;
            result[i] = selected.contains(id) || !dimmed.contains(id);
        }
        return result;
    }

    private void render() {
        boolean focused = isFocused();
        setAlpha(enabled ? 1f : 0.4f);
        title.setTextColor(getResources().getColor(focused ? R.color.text_primary : R.color.text_secondary));
        boolean[] selectable = selectable();
        String cursorDescription = null;
        for (int i = 0; i < chips.size(); i++) {
            PresetFacets.Option option = options.get(i);
            TextView chip = chips.get(i);
            boolean isSelected = selected.contains(option.id);
            Integer count = counts.get(option.id);
            int n = count == null ? 0 : count;
            chip.setText(option.label + " → " + n);
            CharSequence desc = option.label + ", " + (isSelected ? "selected" : "not selected")
                    + ", " + n + " presets";
            chip.setContentDescription(desc);
            if (i == cursor) cursorDescription = desc.toString();
            int color = isSelected ? R.color.accent : (selectable[i] ? R.color.text_primary : R.color.facet_dimmed);
            chip.setTextColor(getResources().getColor(color));
            int flags = chip.getPaintFlags();
            boolean underline = focused && i == cursor;
            chip.setPaintFlags(underline ? flags | Paint.UNDERLINE_TEXT_FLAG : flags & ~Paint.UNDERLINE_TEXT_FLAG);
            chip.setTypeface(null, isSelected ? android.graphics.Typeface.BOLD : android.graphics.Typeface.NORMAL);
        }
        setContentDescription(FacetCursor.rowDescription(title.getText().toString(), cursorDescription, enabled));
        if (focused && cursor >= 0 && cursor < chips.size()) {
            TextView c = chips.get(cursor);
            scroller.post(() -> scroller.smoothScrollTo(Math.max(0, c.getLeft() - dp(24)), 0));
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
