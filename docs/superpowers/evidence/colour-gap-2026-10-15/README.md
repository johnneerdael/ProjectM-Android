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

## Step 5: model r15 shipped (2026-10-15)

The r15 refit regenerated all 9,606 descriptors with the deterministic stepper and the `recipe:*` probe columns, then
refit every target (`fit-report-r15.json`; same exclusions, 5-fold OOF). Against the latest previous fit for each
target:

| OOF Spearman | before | r15 |
|---|---|---|
| mean_luminance | 0.675 | 0.696 |
| mean_saturation | 0.670 | 0.703 |
| coloured_share | 0.654 | 0.682 |
| warm_cool | 0.627 | 0.657 |
| mean_abs_frame_difference | 0.719 | 0.729 |
| hue shares (8) | 0.44–0.61 | 0.51–0.65 (each +0.05 to +0.07) |
| no_strobe ROC AUC | 0.918 | 0.921 |

Leading calibrated hue over all 8,048 coloured ruler presets (coloured share > 0.2), out of fold: ruler top-2 69.2% →
72.1%, top-1 50.1% → 53.9%.

Facet decisions (`facet_scoreboard2.py`, the real decision path), r14h → r15 precision / recall:

| option | r14h | r15 |
|---|---|---|
| dark | 83% / 38% | 81% / 44% |
| balanced | 70% / 36% | 71% / 42% |
| bright | 70% / 59% | 73% / 62% |
| warm | 78% / 54% | 82% / 59% |
| cool | 74% / 45% | 76% / 47% |
| vivid | 78% / 71% | 79% / 73% |
| pastel | 34% / 41% | 33% / 47% |
| still | 83% / 36% | 82% / 39% |
| intense | 74% / 71% | 75% / 72% |
| no_strobe | 98% / 15% (p ≥ 0.9) | 98% / 13% (p ≥ 0.93) |

No strobe gate (`nostrobe_gate_check.py`): at the old thresholds (p ≥ 0.9, jumps < 0.05) r15 admits 729 presets
including one strobing preset (loin bowel … how to impress dullard4, 44 jumps / 10 s, p = 0.906). The next
strobing preset scores 0.886. r14 had a 0.039 margin (0.9 over 0.861), so the threshold moves to 0.93: 599 admitted,
0 strobing, 4 pulses out of fold. That preset's flicker comes from a fully opaque additive wave re-placed by `rand()`
every frame. Corpus-wide, an unconditional per-frame `rand()` on wave geometry shows no strobe lift (visible waves:
17.5% strobing vs 25% without), so it is logged as a one-off rather than turned into a rule.

Palette weight re-check with r15 OOF (`OOF=oof-r15.json palette_weight_ab.py [checkpoints]`), leading hue in ruler
top-2:

| calibrated weight | 200 group (162 coloured) | held-out checkpoints (178) |
|---|---|---|
| 6 | 72.2% | 61.2% |
| 24 (shipped) | 77.8% | 67.4% |
| calibrated only | 80.2% | 66.3% |

Pooled, 24 and calibrated-only are within noise (72.4% vs 72.9%), so the shipped weight stays at 24.

A dedicated strobing classifier (≥ 10 jumps, same trees and folds; `nostrobe_veto_ab.py`) as a second veto does not
raise No strobe recall. Its strobing AUC is 0.930 vs 0.913 for the calm classifier. The largest zero-strobing
admissions out of fold: calm + jumps 758 (0.92 / 0.1, at a grid edge with no margin), calm + veto 688, all three
754. The shipped gate (0.93 / 0.05, 599) keeps its margin; recall is limited by the descriptors, not the rule.

Why calm presets are doubted (`nostrobe_doubt_scan.py`; calm = 0 jumps, doubted p < 0.5 vs trusted p ≥ 0.9). The facts
over-represented in doubted calm presets are: the composite reading mid/treb, q-bridged audio routes, and the
random-palette template (`mqNN = if(above(chng,cthr), rand(n), mqNN)`). They occur at similar rates among strobing
presets (21–30% vs 16–26%), so the doubt is legitimate. The template alone covers 1,478 presets (53% strobing,
26% calm), almost all with the same redraw timing (`chng = sin(time*.5)`, `cthr = .9999`), so its period cannot
separate them. Raising recall needs the magnitude of audio → displayed-brightness gain through the composite,
which the descriptors hold only as route presence.

A prototype audio-response probe (`audio_response_corpus.py`, all 9,606 presets, about 0.6 CPU-s each) evaluates
warp and composite on a flat mid-grey canvas under neutral, transient (bands 2 over averages 1, which fires
above(bass, bass_att) beat detectors) and quiet audio. It also records the change in audio-sensitive frame controls.
Added to the No strobe classifier (`audio_response_ab.py`), AUC stays at 0.922, and admissions before the first /
second / third strobing preset go 723 / 776 / 887 → 771 / 786 / 888: noise level. It is not adopted. Fixed-band
probes do not separate calm from strobing better than the existing route facts.

## Step 6: missed light sources in the feedback equilibrium (2026-10-15)

Checkpoint r257 (Tag – Cradle of Life) is black in the ruler (0.00–0.03) and in the real clip (0.021). Its
equilibrium is correctly 0: both shapes are textured canvas copies, and the custom waves are sparse 3D points at
alpha 0.07. Yet calibrated luminance is 0.43. The model does not trust an equilibrium of 0, and rightly so: of 1,715
presets with equilibrium luma < 0.01, only 48% are dark.

`equilibrium_missing_sources.py` compares equilibrium-black presets that are bright in the ruler (> 0.3, 391) with
dark ones (< 0.05, 495). The facts over-represented in the bright group name the light the equilibrium does not model:

- shape outlines (`border_r/g/b`: 21% vs 7%; border material jump bounds 25% vs 10%). The engine draws the outline
  (border_a > 0.0001) untextured in the border colour, even when the fill samples the canvas. `_shape_terms` skipped
  textured shapes entirely, outline included;
- per-frame shader randomness and noise injection (`_c4`, which is `rand_frame`: 18% vs 3%; `rand_frame` 27% vs 11%;
  `texsize_noise_lq` 20% vs 8%). This is not modelled yet.

The outline is now an equilibrium element (`feedback_equilibrium._outline_term`). Corners sit at
`x + rad·cos·aspectY, y + rad·sin` in NDC (projectM `CustomShape`), so the polygon's on-screen circumradius is rad·H/2
px. The line is 1 px wide, or 2 px for a thick outline (four offset passes), and only the on-screen part of the
perimeter counts. Test: `test_shape_outline_adds_light_even_when_the_fill_is_textured`.

Corpus gate (`outline_gate.py`, current code vs the r15 cached equilibrium, Spearman with ruler luminance): local
0.3525 → 0.3607, spread 0.3279 → 0.3349. 28 presets leave the equilibrium-black group; their ruler mean is 0.473, and
71% are above 0.2. The calibration picks this up at the next refit.
