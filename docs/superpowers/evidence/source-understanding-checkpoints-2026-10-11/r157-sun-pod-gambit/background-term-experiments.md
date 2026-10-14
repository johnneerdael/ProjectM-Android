# r157 follow-up: closed-form background term (2026-10-14)

r157's miss came from `feedback_equilibrium`'s background term, `offset/(1-gain)`. The offset is the
clamped screen mean of the warp at black. Zero-mean noise `(noise*2-1)*.01` keeps only its positive half,
which gives +0.0023 per frame. Gain 0.996 then amplifies it to a canvas of about 0.57, while the engine
stays black.

Four general replacements were tried. Each was gated against native-ruler luma (frames 60–149) on the
200 group-measure descriptions (`desc-d7ad1519`). The baseline is analyzer 4d179eea: Spearman 0.317,
mean error 0.2645, 19.0% within 0.05.

| Background term | Spearman | Mean error | Within 0.05 | Changed: better / worse |
|---|---|---|---|---|
| Signed (unclamped) screen mean as offset | 0.277 | 0.2716 | 18.0% | 28 / 33 |
| Per-pixel fixed point `clip(o_p/(1-g_p))` | 0.288 | 0.2672 | 17.5% | 15 / 16 |
| unorm8 round-to-nearest orbit from black | 0.308 | 0.2663 | 17.5% | 20 / 38 |
| unorm8 orbit from white when drawn elements inject energy | 0.298 | 0.2648 | 17.0% | 34 / 36 |

None passes the no-regression gate, so all four were reverted. What they show:

- **Signed mean.** It fixes zero-mean noise. It also erases regions that a warp pushes below zero for real,
  and in those presets the positive regions accumulate brightness (Fvese MV Fun 3: 0.51 → 0.00, real 0.74).
- **Per-pixel fixed point.** It ignores transport. Static per-pixel offsets accumulate where moving content
  would average them out.
- **unorm8 orbits.** The RGBA8 canvas uses round-to-nearest (see `source_feedback_persistence`), so the rest
  state is hysteretic. Rising from black stops at `(o-δ)/(1-g)`; falling from above stops at `(o+δ)/(1-g)`,
  with δ = 0.5/255. The affine `o/(1-g)` is the midpoint of that band. Without the history it is the better
  neutral estimate, and choosing an end by whether elements inject energy does not recover the history.
- **r157 itself.** Its noise changes every frame, so the 8-bit stores are dithered: rounding is linear in
  expectation and neither orbit applies. The right description would be a rectified, dithered AR(1)
  process. That is a property of one noise class, not something to fit to this preset.

Conclusion: the background term does not limit closed-form accuracy (mean error 0.26 against 0.04 for the
stepped prediction). The remaining error comes from drawn coverage, transport of drawn energy and the
composite. Work on the closed form should go there.
