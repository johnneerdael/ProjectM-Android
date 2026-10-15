# Colour through feedback: static display palette (step 1)

The static gap scan lists colour through feedback as the largest unresolved item: 9,566 of 9,606 summaries
say "feedback/image colour is unresolved". The metric here is static output only, compared with engine-ruler
hues: does the leading hue fall in the ruler's top 2 (presets with coloured share > 0.2)?

| Static answer (one per preset) | 200-preset set, overall correct | Held-out checkpoints r129–r205 |
|---|---|---|
| steady-state hue alone | 36% | 39% |
| `display_palette` v1 (pooled sources) | 51% | — |
| v2 + trail gains + composite flat transfer | 43% (rejected) | — |
| v3 + trail gains only | 48% (rejected) | — |
| **v4 (pooled, weights ordered by measured source reliability)** | **50%** | **44%** |

Coverage goes from 76% to 86% of coloured presets. Source reliability on the 200 set: composite detail 64%,
steady state 64%, shape fills 50%, built-in waves 36%, custom-wave points 38%.

Why v2 failed: the composite flat transfer was measured on grey canvases, so applying it per channel to
coloured input assumes the channels are independent, and composites that swap or mix channels break that.
Next step: measure the composite's response to coloured flat inputs (an R/G/B response matrix per level)
statically, and map element colours through it.

## Step 2: composite colour matrix and warp detail colour

| Variant | 200 set, overall correct (coverage) | Held-out |
|---|---|---|
| v5: element colours through the composite's coloured-probe matrix | 49% (84%) | 44% |
| v6: v5 plus a matrix guard (skipped for edge-based composites) plus warp detail colour as a source | **51% (88%)** | 44% |

`composite.colour_matrix` probes black and (l,0,0), (0,l,0), (0,0,l) at l = 0.3, so channel swaps and mixes
are handled. Edge-based composites barely respond to flat input; their matrix is dominated by the black level,
so it is skipped there (the EoS chasers misses). `feedback.warp_detail_response` is the colour the warp shader
creates from a grey texture.

Pooling plateaus near 50% (44% held out). The remaining misses are colour created by feedback dynamics,
random textures and per-load tints, plus presets whose colour comes from audio-gated routes. Next: the warp's
colour transform as an iterated map (per-channel and cross-channel gains under coloured probes), the second
colour row of the gap table.

Tried and reverted: the hue of a channel-selective warp's gain vector as a source (20% of exported warps keep
only some channels). 200 set 51% (unchanged), held-out 44% → 42%. More sources no longer help; pooling has hit
its ceiling.

## Step 3: calibrated hue weight in the pooled palette (2026-10-15)

When the calibrated hue shares shipped (r13h), they joined the pool with weight 6. That value was never tuned out
of fold. Checkpoint r218 (Magellan's Nebula) shows the failure mode: calibrated green/pink, while steady state,
warp detail, wave and shape all lead blue. The pooled palette led blue; the ruler shows pink/green.

`palette_weight_ab.py` rebuilds recipes, substitutes the out-of-fold calibrated shares (oof-r14g), and re-pools
at several weights. Static only; no frames are stepped. Metric: leading hue in the ruler's top two, on presets
with ruler coloured share above 0.2.

| calibrated weight | 200 group set (162 coloured) | held-out checkpoints (163 coloured) | both (325) |
|---|---|---|---|
| 0 (static sources only) | 51.2% | 42.3% | 46.8% |
| 6 (previous) | 67.9% | 60.1% | 64.0% |
| 12 | 74.1% | 65.0% | 69.5% |
| **24 (shipped)** | 72.8% | 66.9% | **69.8%** |
| calibrated only | 69.8% | 68.7% | 69.2% |

At weight 24 the calibrated lead stands, and static sources mostly break near-ties. The values 12, 24 and
calibrated-only are within noise of each other; 6 is clearly worse. Re-scoring the 14 recent checkpoints whose
stored recipes carry calibrated hue gives 11 → 12 top-2 hits: r213 and r218 are fixed, r225 flips wrong, and
r215 stays wrong.

Checkpoint descriptions come from mixed analyzer versions. Some held-out static sources are therefore older
than the current code, which may understate pooling on that set.

## Step 4: recipe colour probes as calibration columns (2026-10-15)

Rounds 6 and 7 kept showing calibrated brightness misses on presets whose recipe already holds the answer. Checkpoints
r235 and r228 share a composite (detail luma 0.66), but r235's warp darkens detail (warp detail luma 0.016 vs 0.46).
The ruler agrees (0.23 vs 0.62); the calibration ranked them backwards (0.57 vs 0.49). The summary flattening
that feeds the calibration never contained the recipe-level probes.

`recipe_columns_ab.py` (static, same 5-fold CV) adds the warp and composite detail responses, the composite colour
matrix, and the palette pooled from static sources only, to the cached r14 descriptors. The matrix also gives
derived columns: singular-value ratios (rank-1 means every input becomes one chroma) and the saturation reachable
from black plus each unit input column.

| OOF | base | + recipe probes |
|---|---|---|
| mean_saturation Spearman | 0.668 | 0.702 |
| coloured_share | 0.655 | 0.681 |
| mean_luminance | 0.670 | 0.692 |
| leading hue in ruler top-2 | 69.3% | 72.3% |
| monochrome AUC | 0.887 | 0.895 |
| pastel AUC / recall at 70% precision | 0.825 / 2.5% | 0.835 / 9.5% |

These are now `recipe:*` columns of `static_descriptor` v4 (`preset_recipe.probe_columns`). `build_recipe` passes
its render, so the probes are not recomputed.

### Determinism fix found on the way

Regenerating the columns with production code changed values for about 1% of presets (for example a matrix entry
of 0.22 vs −0.02). The stage-control stepper ran the per-frame program until a 3 s wall-clock deadline, so under
machine load it reached fewer frames, and later probe times read stale state. `eel_memory.WorkBudget` replaces the
clock. Each step charges the frame-program node count, and each EEL loop iteration charges its body size. On a
300-preset sample, stepping costs about 0.5M units/s (Spearman 0.88 with seconds). At 2M units, 97% of presets
step to t = 5 s fully; the rest stop at the same point on every machine (`stepping_units.py`). The descriptor
cache is regenerated with the deterministic code for the r15 refit.
