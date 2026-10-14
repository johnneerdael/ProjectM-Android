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
