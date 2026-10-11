package com.example.projectm.visualizer;

import android.content.Context;
import android.util.AttributeSet;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * TV-style settings row: label on the left, value on the right.
 * D-pad left/right steps through the options, center advances (wrapping). In action mode the
 * row only reacts to center/enter.
 */
public class OptionRow extends LinearLayout {
    public interface Listener { void onChanged(int index); }

    private final TextView label;
    private final TextView value;
    private String[] options = new String[0];
    private int index;
    private boolean wrap;
    private Listener listener;
    private Runnable action;
    private String actionValue = "";

    public OptionRow(Context context, AttributeSet attrs) {
        super(context, attrs);
        setOrientation(HORIZONTAL);
        setGravity(Gravity.CENTER_VERTICAL);
        setFocusable(true);
        setClickable(true);
        if (BuildConfig.TOUCHSCREEN) setMinimumHeight(dp(48));
        setBackgroundResource(R.drawable.bg_option_row);
        int h = dp(12), v = dp(9);
        setPadding(h, v, h, v);

        label = new TextView(context);
        label.setTextColor(getResources().getColor(R.color.text_secondary));
        label.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        label.setSingleLine(true);
        addView(label, new LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f));

        value = new TextView(context);
        value.setTextColor(getResources().getColor(R.color.text_primary));
        value.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        value.setSingleLine(true);
        value.setGravity(Gravity.END);
        addView(value, new LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT));

        setOnClickListener(v1 -> activate());
    }

    /** Option mode: cycles through {@code options}; {@code wrap} lets left/right loop around. */
    public void setup(String title, String[] options, int selected, boolean wrap, Listener listener) {
        label.setText(title);
        this.options = options;
        this.index = Math.max(0, Math.min(selected, options.length - 1));
        this.wrap = wrap;
        this.listener = listener;
        this.action = null;
        this.actionValue = "";  // a later setupAction shows its value again
        render();
    }

    /** Action mode: center/enter runs {@code action}. */
    public void setupAction(String title, String valueText, Runnable action) {
        label.setText(title);
        this.action = action;
        setActionValue(valueText);
    }

    public void setActionValue(String valueText) {
        if (valueText.equals(actionValue) && value.getText().length() > 0) return;
        actionValue = valueText;
        render();
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (action == null) {
            if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT) return step(-1, wrap);
            if (keyCode == KeyEvent.KEYCODE_DPAD_RIGHT) return step(+1, wrap);
        }
        return super.onKeyDown(keyCode, event);
    }

    private void activate() {
        if (action != null) {
            action.run();
        } else {
            step(+1, true);
        }
    }

    private boolean step(int delta, boolean allowWrap) {
        if (options.length == 0) return false;
        int next = index + delta;
        if (allowWrap) {
            next = (next + options.length) % options.length;
        } else {
            next = Math.max(0, Math.min(next, options.length - 1));
        }
        if (next != index) {
            index = next;
            render();
            if (listener != null) listener.onChanged(index);
        }
        return true;  // consume, so focus never jumps sideways out of the row
    }

    @Override
    protected void onFocusChanged(boolean gainFocus, int direction, android.graphics.Rect previous) {
        super.onFocusChanged(gainFocus, direction, previous);
        render();
    }

    private void render() {
        boolean focused = isFocused();
        label.setTextColor(getResources().getColor(focused ? R.color.text_primary : R.color.text_secondary));
        if (action != null) {
            value.setTextColor(getResources().getColor(focused ? R.color.accent : R.color.text_secondary));
            value.setText(actionValue);
            return;
        }
        if (options.length == 0) return;
        String text = options[index];
        if (focused) {
            boolean canLeft = wrap || index > 0;
            boolean canRight = wrap || index < options.length - 1;
            text = (canLeft ? "‹  " : "    ") + text + (canRight ? "  ›" : "    ");
        }
        value.setTextColor(getResources().getColor(focused ? R.color.accent : R.color.text_primary));
        value.setText(text);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
