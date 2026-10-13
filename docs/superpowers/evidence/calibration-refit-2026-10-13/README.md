# Display calibration refits, 2026-10-13

Same fit as r11 (`fit_display_calibration.py`, native-ruler labels, the
validation exclusions, out-of-fold predictions), with facet agreement measured
by the `remap` method.

## r11 corpus with descriptor v3 (2b20e5c4)

Descriptor v3 adds composite-transfer columns: the threshold level, the time
spread and the non-finite share.

| Target (out-of-fold Spearman) | r11 | r11 + v3 |
|---|---|---|
| mean_luminance | 0.646 | 0.664 |
| mean_abs_frame_difference | 0.710 | 0.716 |
| mean_flow_screen_widths_per_s | 0.681 | 0.684 |
| global_brightness_jumps_per_10s | 0.765 | 0.771 |
| mean_saturation | 0.638 | 0.645 |
| warm_cool | 0.602 | 0.602 |

| Facet group agreement | r11 | r11 + v3 |
|---|---|---|
| energy | 0.532 | 0.536 |
| brightness | 0.598 | 0.599 |
| colour | 0.502 | 0.503 |
| movement | 0.639 | 0.637 |
| comfort | 0.812 | 0.816 |
| mean | 0.6166 | 0.6182 |

Every target's rank correlation rises a little, but facet agreement stays
flat. The targets (Energy 0.77, Brightness 0.73, Movement 0.84) need much
stronger rank prediction than these descriptor additions give. The r12
corpus (new mechanisms, deterministic random draws) is refitted next.
