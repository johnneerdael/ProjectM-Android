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
