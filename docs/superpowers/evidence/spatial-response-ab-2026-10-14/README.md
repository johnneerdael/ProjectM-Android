# Warp spatial-response features: A/B against the calibrated display model (rejected)

**Question.** Flat-colour probes cannot see spatial operators: blur, sharpening, pattern growth
(r160). Does the warp's spatial frequency response add information to the calibrated display model?

**Feature.** The exported warp stage is evaluated at 480x270 on a white-noise probe around mid grey:
`out(0.5 + noise) - out(0.5)`. We record the radially binned power ratio in five wavelength bands, the overall
ratio, and the flat output's own texture. It runs on 7,621 presets with an exported warp, at a median 0.39 s
(p90 0.79 s, max 4.4 s).

**Test.** Descriptor rows from corpus-understanding r13 (9,606 summaries), with and without the seven
`spatial:*` columns. Both use identical HistGradientBoosting settings and 5-fold CV against the native ruler,
excluding the validation sets.

| Target | base | + spatial |
|---|---|---|
| mean_luminance | 0.6682 | 0.6682 |
| mean_abs_frame_difference | 0.7154 | 0.7182 |
| mean_flow | 0.6857 | 0.6873 |
| brightness_jumps | 0.7704 | 0.7696 |
| mean_saturation | 0.6621 | 0.6639 |
| warm_cool | 0.6183 | 0.6197 |

**Verdict.** Not shipped. The changes are within fold noise, so the existing 8,175 columns already carry what
the spatial response measures. `ab_spatial.py` reproduces the test.
