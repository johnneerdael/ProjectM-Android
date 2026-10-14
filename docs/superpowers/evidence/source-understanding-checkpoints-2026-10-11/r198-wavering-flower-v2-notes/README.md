# r198 Stahlregen - Wavering Flower: textured frame copy read as a light-grey fill

Round-4 wording triage: the v1 reading said "grey-white, mid-bright"; the real preset is near black (ruler
luma 0.023–0.054). The frozen prediction was right (0.036).

Cause, in two parts, both general:

1. `shape_0` is textured (texture role `previous_main`): it copies the previous frame, and its colour 0.9 is
   a tint on that copy. The reader took it as a fill. The recipe now labels a textured shape's
   `colour_over_time` as a tint, and SKILL says the tint never brightens a dark copy.
2. `feedback_equilibrium._shape_terms` skipped textured shapes only through a `parameters.textured` flag.
   This preset has no such flag; its texture shows as `material.texture.role`. So the disc counted as a 0.9
   emitter over a third of the screen and the closed-form steady state read white. Now fixed.

Closed-form gate (200 group-measure descriptions against native-ruler luma, frames 60–149): Spearman
0.317 → 0.375, mean error 0.2645 → 0.2413. Total error removed 6.46, added 1.83; 8 presets worse by more
than 0.1. Those are presets where the copy recursion really does sustain brightness.

Follow-ups: model a frame copy as extra feedback gain over its area. Refit the calibrated display model,
whose descriptors include equilibrium columns.

The v2 reading (`llm-look-description-v2.txt`) treats the disc as a recursive copy. It still says
mid-bright, from the calibrated estimate (0.33, interval 0.14–0.57), which predates this fix.
