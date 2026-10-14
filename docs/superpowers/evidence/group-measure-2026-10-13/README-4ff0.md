# Group measure: noise port and No strobe fixes (2026-10-14)

Same 200-preset selection and native-ruler references as `README-44e4.md`
(frames 60–149, 480×270, checkpoint audio). Frozen snapshots with the `core`
asset link.

## 7d1c84e3 → 48d8e2c8 (exact MilkdropNoise, separate warp/composite rand_frame)

| Metric (mean) | 7d1c84e3 | 48d8e2c8 |
|---|---|---|
| luma error | 0.0530 | 0.0529 |
| colour-map error | 0.0747 | 0.0736 |
| map correlation | 0.684 | 0.692 |
| series correlation | 0.765 | 0.769 |
| luma within 0.05 | 73.3% | 72.3% |

Paired luma: 43 improved, 45 worse. The changes are neutral to slightly
positive. The largest loss (drugsincombat - whirlfire b) feeds unsmoothed
`noise_lq` back into its warp. The texel distribution is unchanged, but the
realisation differs, and the engine draws noise anew at every load.

## 48d8e2c8 → 4ff0daee (beat-switched shapes, EEL && / || and loops, per-point q/t restart, borders, per-frame gamma)

| Metric (mean) | 48d8e2c8 | 4ff0daee |
|---|---|---|
| luma error | 0.0527 | 0.0501 |
| RGB error | 0.0585 | 0.0560 |
| colour-map error | 0.0735 | 0.0712 |
| map correlation | 0.690 | 0.697 |
| series correlation | 0.767 | 0.774 |
| luma within 0.05 | 72.4% | 74.0% |

Paired: luma 15 better and 11 worse; RGB 18 and 9; frame difference 17
and 9. Largest gains: Hexcollie - electronegativity (colour-map error 0.216
→ 0.022), stupid mash5 - men in black 3 (0.195 → 0.044), EoS + Phat -
chasers 14 sentinel (0.103 → 0.010). The largest loss, EoS - dark side of
the moon (0.025 → 0.079), was a regression from the per-frame blend: the
shape state read only by `additive` was not stepped. It is fixed in
4fd25e72 (luma 0.154, engine 0.172, was 0.152).

## 09863b63 → a0466ceb (projectm-eval rand stream layout; site-ordered main-code draws)

3206de13 skips the draws that the other blocks take from projectm-eval's single
stream (wave and shape init at load; per-pixel, shape-instance and wave draws
each frame). a0466ceb draws every always-running main-code rand site once
per block, in statement order, shared by every inlined copy.

| Metric (mean) | 09863b63 | a0466ceb |
|---|---|---|
| luma error | 0.0464 | 0.0405 |
| RGB error | 0.0521 | 0.0461 |
| colour-map error | 0.0682 | 0.0625 |
| map correlation | 0.694 | 0.701 |
| series correlation | 0.780 | 0.802 |
| luma within 0.05 | 76.6% | 81.2% |

Paired: luma 28 better and 21 worse; RGB 33 and 15; colour map 35 and 12.
Largest gains (luma error):

- EoS+Phat - CAT Scan: 0.643 → 0.084.
- phat+EoS - Bass responce: 0.231 → 0.044.
- New Creations … Willie Wonka: 0.113 → 0.026. Its shape_0_init `red=rand(20)` now precedes the main per-frame draws.
- suksma - byT o' the bublee: 0.116 → 0.057. `index4`/`index3` init draws now come in statement order, and the late fade to black appears.

The largest loss, suksma - dotes hostile + demonlord (0.380 → 0.464), was
already a large miss. The ruler goes almost black for frames 15–100, while
the prediction stays bright. It is an open case and is not caused by the
stream order. The other losses are 0.015 or less. The same two presets time
out in both runs.

## Tiny-grid validation (e5cf833b, 2026-10-14): rejected

The facet statistics needed to cost at most 1 s per preset. A 64×36 grid with
the same source maths was tested against the native ruler on the 200-preset
selection, using frames 60–149, cold load only (`tiny_one.py`, `tiny_pass.py`).
The 197 presets measured in all three runs:

| vs ruler | 64×36 | full resolution (a0466ceb) |
|---|---|---|
| luma error (mean) | 0.130 | 0.041 |
| luma within 0.05 | 39.6% | 81.2% |
| saturation error | 0.147 | 0.054 |
| frame difference error | 0.033 | 0.011 |
| Spearman luma / saturation / frame difference | 0.756 / 0.674 / 0.740 | 0.924 / 0.922 / 0.924 |

The misses are flips, not drift: Rovastar voovsnakedmov predicts 0.960 at
64×36, 0.089 at full resolution and 0.097 on the ruler, and suksma purple 9-d
predicts 0.046, 0.887 and 0.888. MilkDrop feedback depends on pixel scale.
Shader offsets are written in texels (`texsize.zw*8`), lines and dots are one
pixel wide, and blur kernels are fixed in pixels, so a grid eight times
smaller is a different system.

The grid also missed the time budget: a 150-frame prediction took a median
3.9 s, a 90th percentile of 78 s and a maximum of 310 s. The cost of
per-instance shapes and per-point waves does not depend on the grid.

## a0466ceb → 90b63b14 (per-frame wave sample counts, compiled stage plans, frame-site shader rand, negative shape radius, kaleidoscope folds, recurrence node budget)

| Metric (mean) | a0466ceb | 90b63b14 |
|---|---|---|
| luma error | 0.0405 | 0.0367 |
| RGB error | 0.0461 | 0.0422 |
| map correlation | 0.701 | 0.717 |
| series correlation | 0.802 | 0.806 |
| luma within 0.05 | 81.2% | 82.2% |

Paired: luma 20 better and 11 worse, RGB 20 and 12, map correlation 20 and 9.

Largest gains:

- suksma dotes hostile + demonlord: 0.464 → 0.016. Its opaque black wave sets its sample count per frame and is now drawn.
- anglican't americouldn't - zhuGan: 0.196 → 0.006.

The largest loss is 0.014 (shifter + Flexi liquid circuitry, 0.048 → 0.062). Failures fell from 2 to 1: Acid Mandala, whose unresolved loop plans used to crash the run, now predicts.

## 90b63b14 → 054df663 (shared reg00–reg99 registers, per-pixel memory reads)

No preset in the 200-preset selection changed: every metric is identical, with 0 better and 0 worse. 186 of the 9606 presets use the registers, and none in the selection depended on them. The fix is neutral here. It repairs r137 (martin + flexi - carpet weaver bipolar 02), which was black and now matches the engine's green/magenta carpet.

## 054df663 → f9042762 (mode 2/5 built-in wave texture-size bucket gain)

Neutral on the selection. Mean luma error went from 0.0364 to 0.0366, and paired luma was 3 better and 3 worse; no preset moved by more than 0.006. Luma within 0.05 fell from 82.4% to 81.9% because one preset crossed the line.
