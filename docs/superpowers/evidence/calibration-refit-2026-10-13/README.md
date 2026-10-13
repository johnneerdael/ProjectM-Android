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

## r12 corpus with descriptor v3

The r12 corpus was exported from the frozen 44e4fa2f snapshot (new mechanisms
since r11, deterministic random draws, random-texture stand-ins); same fit and
descriptor v3 (`model-r12v3`, `facets-r12v3.txt`).

| Target (out-of-fold Spearman) | r11 + v3 | r12 + v3 |
|---|---|---|
| mean_luminance | 0.664 | 0.665 |
| mean_abs_frame_difference | 0.716 | 0.718 |
| mean_flow_screen_widths_per_s | 0.684 | 0.687 |
| global_brightness_jumps_per_10s | 0.771 | 0.771 |
| mean_saturation | 0.645 | 0.645 |
| warm_cool | 0.602 | 0.603 |

| Facet group agreement | r11 + v3 | r12 + v3 |
|---|---|---|
| energy | 0.536 | 0.539 |
| brightness | 0.599 | 0.599 |
| colour | 0.503 | 0.506 |
| movement | 0.637 | 0.637 |
| comfort | 0.816 | 0.816 |
| mean | 0.6182 | 0.6194 |

The per-preset understanding gains between r11 and r12 (group measure map
correlation 0.757 → 0.815) barely move the calibrated ranks: the descriptor
reads summary statistics of the source facts, and those changed little.

## How much rank correlation do the facet targets need?

A diagnostic of the metric itself (not a feature): synthetic predictions are
the engine-ruler values plus Gaussian noise of σ·sd, scored with the same
`facet_agreement` (no remap).

| Noise σ | Spearman (luma, frame difference, jumps) | energy | brightness | colour | movement | comfort | mean |
|---|---|---|---|---|---|---|---|
| 0.3 | 0.94, 0.94, 0.90 | 0.753 | 0.828 | 0.813 | 0.854 | 0.929 | 0.835 |
| 0.5 | 0.86, 0.87, 0.86 | 0.683 | 0.734 | 0.678 | 0.762 | 0.859 | 0.743 |
| 0.75 | 0.76, 0.77, 0.78 | 0.610 | 0.639 | 0.541 | 0.669 | 0.798 | 0.651 |
| 1.0 | 0.67, 0.68, 0.70 | 0.550 | 0.572 | 0.449 | 0.594 | 0.753 | 0.584 |

The current source-only estimates (Spearman 0.66–0.77) sit between σ 0.75
and 1.0, consistent with the measured mean agreement of 0.618. The targets
need roughly:

- Brightness 0.73: Spearman about 0.86;
- Energy 0.77 and Movement 0.84: Spearman about 0.94.

That is a gain of about 0.2 in rank correlation. The descriptor v3 refit
gained about 0.01, so the targets are not reachable by incremental
descriptor additions alone.
