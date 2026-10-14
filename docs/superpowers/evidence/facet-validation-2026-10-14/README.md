# Mood facets from static predictions: validation, 2026-10-14 (partial)

Question: do facet statistics measured from our static predictions select
moods better than the calibrated source model? The static prediction is the
illustrator driven only by source facts (no engine). For each preset of the
200-preset group selection (seed 20261013) the frozen snapshot `e2ee84a3`
exports and describes the preset, predicts 300 frames with the checkpoint
audio, and measures them with the engine ruler's own `measure()` (frames
60–299, 480×270). The engine ruler labels (`native-ruler-2026-10-12`) are used
only to validate. Baseline: the calibrated model's out-of-fold predictions
(`oof-r12v3`) for the same presets.

Partial: 106 of 200 presets finished (the pass is still running).

| Spearman vs engine ruler (n=106) | Static prediction | Calibrated model |
|---|---|---|
| mean_luminance | 0.948 | 0.738 |
| mean_abs_frame_difference | 0.939 | 0.635 |
| mean_flow_screen_widths_per_s | 0.925 | 0.638 |
| global_brightness_jumps_per_10s | 0.902 | 0.617 |
| mean_saturation | 0.951 | 0.662 |
| warm_cool | 0.881 (n=101) | 0.647 |

| Facet group agreement | Static, direct | Static, remap | Calibrated, direct | Calibrated, remap | Target |
|---|---|---|---|---|---|
| energy | 0.853 | 0.833 | 0.485 | 0.505 | 0.77 |
| brightness | 0.902 | 0.873 | 0.574 | 0.624 | 0.73 |
| colour | 0.863 | 0.843 | 0.594 | 0.614 | — |
| movement | 0.843 | 0.833 | 0.614 | 0.614 | 0.84 |
| comfort | 0.922 | 0.902 | 0.752 | 0.752 | — |
| mean | 0.877 | 0.857 | 0.604 | 0.622 | — |

"Direct" applies the facet thresholds to the predicted values; "remap" maps
them through a monotone rank mapping fitted on other folds (a global
calibration, never a per-preset correction).

Caveats:

- Partial sample with a likely bias: presets that finish first are the
  faster, often simpler ones. The rest of the 200 must confirm the numbers.
- The snapshot predates the `pow`, channel-mixing composite, exact-display and
  motion-vector/border fixes; a re-run at the current code is planned.
- Measured memberships compare against the current bundle
  (`attributes.tsv`, ruler-based), so this is agreement with the engine ruler,
  not with human judgement.
- Cost: these predictions take seconds to minutes per preset. The owner's
  budget for the facet-producing analysis is 1 s per preset (validation may
  take longer), so a cheaper facet path (fewer frames, lower resolution) has
  to be measured against this accuracy before the facets can switch.

## Cheaper settings lose the accuracy

Same presets, snapshot `7d1c84e3`, frames upscaled to 480×270 before the
ruler `measure()` (`facet_cheap.py`; n ≈ 45, timings under heavy machine load):

| Setting | Median seconds | Spearman range (6 statistics) | Full 480×270, 300 frames |
|---|---|---|---|
| 96×54, 300 frames | 19.4 | 0.69–0.86 | 0.86–0.98 |
| 96×54, 120 frames | 8.4 | 0.66–0.79 | |
| 64×36, 90 frames | 3.9 | 0.57–0.67 | |

Lines, dots and borders are drawn in pixels, so their screen share changes
with resolution; low-resolution statistics are not the full-resolution ones.

Decision (owner, 2026-10-14): facets are precomputed offline, once per
bundled preset, from full-resolution static predictions; nothing runs on the
device, and speed work continues in parallel.

## Held-out set (seed 20261014)

Same method on 200 presets the analysis was never tuned on
(`selection-heldout-20261014.json`: random draw, excluding the 285 presets of
earlier selections and checkpoints), frozen snapshot `7501b10b`. 194
presets finished with an engine reference. The table compares with the
calibrated model's out-of-fold predictions on the same presets.

| Spearman vs engine ruler (n=194) | Static prediction | Calibrated model |
|---|---|---|
| mean_luminance | 0.823 | 0.682 |
| mean_abs_frame_difference | 0.891 | 0.753 |
| mean_flow_screen_widths_per_s | 0.887 | 0.723 |
| global_brightness_jumps_per_10s | 0.909 | 0.799 |
| mean_saturation | 0.877 | 0.721 |
| warm_cool | 0.828 (n=186) | 0.652 |

| Facet group agreement | Static, direct | Static, remap | Calibrated, direct | Target |
|---|---|---|---|---|
| energy | 0.807 | 0.807 | 0.508 | 0.77 |
| brightness | 0.807 | 0.840 | 0.572 | 0.73 |
| colour | 0.749 | 0.749 | 0.540 | — |
| movement | 0.834 | 0.824 | 0.615 | 0.84 |
| comfort | 0.920 | 0.920 | 0.818 | — |
| mean | 0.823 | 0.828 | 0.611 | — |

The held-out numbers are lower than the tuned set's partial numbers and are
the ones to quote. Energy and brightness meet their targets; movement is
0.006 short.

**No strobe** (a preset is predicted safe when it has fewer than one
predicted global brightness jump per 10 s). 99 presets are predicted safe;
**8 are false negatives**, where the engine flashes 1–13 times per 10 s.
7 are false positives. This is the safety bar. The false negatives and what
they exposed:

| Preset | Engine jumps / 10 s | Cause found | Status |
|---|---|---|---|
| Rovastar - Tripmaker (Space Trip Mix) | 13 | Beat-switched textured shapes (`additive = q1`). The blend was read from the header, and the inlined beat test saw end-of-frame state. The constant black inner border on a per-frame band was not drawn. | Fixed (a73317a9, f79a6e9b). Now 4 predicted jumps (frames 95, 157, 158, 245), so it is excluded from No strobe. Still brighter than the engine (grey 0.91 vs 0.69). |
| EoS - matrix cube F | 5 | Per-point q/t variables carried across frames, and the display used the midpoint of a loose static gamma range [0, 8] (4× too bright) instead of the frame's `gamma = 1 + beatdrop*.28`. | Fixed (84de1738, a8a70a3a). Jumps at frames 147, 212, 245, 278 against the engine's 147, 180, 212, 245, 278; mean grey 0.913 vs 0.917. |
| martin - city lights v2 | 4 | The composite failed on projectm-eval `&&` and on an inlined per-frame `loop()`, so the prediction was near black. | Fixed (a73317a9). Now 6 predicted jumps, so it is excluded. Brighter than the engine (0.31 vs 0.18). |
| out of the paradigm nz bulbuless | 1 (peak 0.085) | Its summary predated the per-point q/t restart: the custom waves drew nothing and the canvas stayed black. The composite on the engine's canvas matches the engine frame by frame. | Fixed by re-export (84de1738 and later). Now 4 predicted jumps, so it is excluded (grey 0.76 vs 0.63). |
| ougiel - floutest biohazmat, shifter - orthoganal light CC beta6 | 1–2 (peaks 0.086–0.111) | Prediction peaks below the 0.08 jump (0.049–0.066) with similar brightness. | Open. The peak statistic gives a headroom rule. |
| only glimpses of the reality… | 2 (peak 0.095) | The composite colours the image through `sampler_rand00`, a random library texture scrolled over time. Whether it flashes depends on the texture drawn at load. The unseeded stand-in is smooth (peak 0.006). | Open: No strobe needs every candidate texture checked, or must treat a random texture as uncertain. |
| suksma - chernobyl pie… morriband flame goate | 1 (ruler) | A fresh native render has no jump (peak 0.067). The prediction peaks at 0.071. A threshold case. | Covered by a headroom rule |

`flash_pass.py` runs `facet_precompute.random_flash`, the per-frame
`rand_frame` tail probe, on the held-out presets with r13 summaries (100 of
200). 17 of them read `rand_frame` in an exported shader program. The 8 with
a positive flash probability already flash at the probed frame, and their
static jump counts agree with the engine. No calm preset carried a hidden
random-draw flash in this sample.
