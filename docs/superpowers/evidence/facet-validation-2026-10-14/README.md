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
