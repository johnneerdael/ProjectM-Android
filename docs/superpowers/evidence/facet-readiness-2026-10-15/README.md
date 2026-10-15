# Static facet readiness scoreboard (2026-10-15)

Static calibrated estimates (r13 model, out of fold, 9,516 presets) and engine-ruler values go through the same facet rule. Precision: of the presets admitted statically, the share that truly belong. Recall: the share of true members admitted.

## r13 estimates (shipped)

| facet | option | agreement | precision | recall | admitted |
|---|---|---|---|---|---|
| brightness | dark | 77% | 82% | 19% | 598 |
| brightness | balanced | 59% | 53% | 85% | 6914 |
| brightness | bright | 81% | 70% | 54% | 2094 |
| colour | pastel | 100% | 0% | 0% | 0 |
| colour | vivid | 75% | 77% | 72% | 4618 |
| colour | warm | 84% | 77% | 52% | 1592 |
| colour | cool | 86% | 75% | 38% | 854 |
| movement | still | 83% | 82% | 24% | 581 |
| movement | drifting | 64% | 59% | 90% | 7264 |
| movement | fast | 80% | 76% | 47% | 1761 |
| comfort | no_strobe | 79% | 87% | 70% | 4027 |

## With cross-fitted quantile mapping (not shipped)

| facet | option | agreement | precision | recall | admitted |
|---|---|---|---|---|---|
| brightness | dark | 79% | 61% | 61% | 2611 |
| brightness | balanced | 63% | 59% | 59% | 4285 |
| brightness | bright | 80% | 65% | 65% | 2710 |
| colour | pastel | 100% | 0% | 0% | 0 |
| colour | vivid | 75% | 76% | 76% | 4950 |
| colour | warm | 83% | 66% | 66% | 2378 |
| colour | cool | 84% | 57% | 56% | 1688 |
| movement | still | 82% | 58% | 58% | 2021 |
| movement | drifting | 65% | 65% | 65% | 4750 |
| movement | fast | 80% | 66% | 66% | 2835 |
| comfort | no_strobe | 82% | 82% | 83% | 5015 |

## Reading

- The estimates shrink toward the middle. Extremes are admitted precisely but rarely: dark 82% precision at 19%
  recall, still 82% at 24%, cool 75% at 38%. The middle buckets are over-admitted (balanced 53% precision).
- Quantile mapping restores the spread (dark recall 61%) at the cost of precision (61%), with agreement
  changing by only ±1–4 points. For "No strobe" it makes things worse (precision 87% → 82%). Not shipped:
  for mood selection, "when I pick Dark I get dark" matters more than pool size.
- Pastel cannot occur in this table because its rule also needs the monochrome option, which uses
  `coloured_share`, a measure the calibration does not estimate yet.
- To improve: better static features, not remapping. Next steps: calibrated `coloured_share`, hue shares
  (refit running), and per-frame state analysis for jumps.

## Residual gap scans (static OOF errors, r13h model)

These scans look at the worst 10% of presets by absolute error and list the static facts over-represented
among them (lift).

- **Brightness:** active motion-vector grids (lift 1.59), textured-material channel domains, strong warp zoom
  ranges. Per-frame-sized motion-vector grids were dropped from the closed form; they now count from their
  control ranges (`7c7f5ea7`). The effect is negligible until vector length comes from the motion field.
- **Brightness jumps:** a shape-state family (variables `mx`, `my`, `t_abs`, `k2`; 589 presets, median 65 jumps
  per 10 s) dominates the magnitude errors. The model already ranks them as heavy flickerers (median estimate
  58), so this is not a No strobe safety issue.
- **Flow:** bass-driven zoom patterns (lift 1.8–1.9) and zoom ranges. Derived span columns (max − min) gave a
  flow Spearman of 0.6949 → 0.6957. Not shipped.

## After shipping per-option classifiers and the combined No strobe gate (r14 model, `8401582f`)

Options are evaluated independently here. In the real facet output an admitted option also drops conflicting siblings.

| facet | option | agreement | precision | recall | admitted |
|---|---|---|---|---|---|
| brightness | dark | 81% | 83% | 38% | 1189 |
| brightness | balanced | 59% | 53% | 85% | 6910 |
| brightness | bright | 81% | 70% | 60% | 2313 |
| colour | monochrome | 92% | 90% | 27% | 296 |
| colour | pastel | 90% | 34% | 41% | 825 |
| colour | vivid | 75% | 77% | 72% | 4602 |
| colour | warm | 84% | 78% | 54% | 1660 |
| colour | cool | 87% | 74% | 45% | 1024 |
| movement | still | 85% | 83% | 37% | 898 |
| movement | drifting | 64% | 59% | 90% | 7208 |
| movement | fast | 80% | 76% | 49% | 1803 |
| comfort | no_strobe | 56% | 98% | 15% | 769 |
| energy | chill | 76% | 84% | 38% | 1508 |
| energy | normal | 65% | 60% | 87% | 6948 |
| energy | intense | 83% | 74% | 69% | 2679 |

The Energy rows use the facet activity score from the calibrated flow, frame difference and jumps, before any
Energy classifiers; Chill and Intense classifiers are being fitted next. No strobe is now 98% precise, with zero
strobing presets admitted out of fold.

## Middle-bucket classifiers (model r14h, 2026-10-15)

The middle options are what the regression rule leaves over: regression toward the mean puts many dark, bright,
still and fast presets in the middle. Direct classifiers for balanced, drifting and normal are now thresholded at a
70% precision floor (`FACET_PRECISION_FLOOR` in `fit_display_calibration.py`). This puts them level with the
weakest extreme options. When two conflicting siblings both pass their thresholds, the one further above its own
threshold stays (`_apply_option_probabilities`).

`facet_scoreboard2.py` scores the shipped decision path out of fold. It applies value rules on calibrated estimates,
then option classifiers with thresholds and conflict resolution, then the No strobe gate, and compares the result
with ruler memberships.

| option | r14g precision / recall / admitted | r14h precision / recall / admitted |
|---|---|---|
| balanced | 58% / 77% / 5655 | **70% / 36% / 2204** |
| drifting | 61% / 88% / 6798 | **70% / 57% / 3856** |
| normal | 60% / 87% / 6948 | **70% / 65% / 4470** |
| dark | 83% / 38% / 1187 | 83% / 38% / 1178 |
| bright | 70% / 60% / 2313 | 70% / 59% / 2270 |
| still | 83% / 37% / 898 | 83% / 36% / 879 |
| fast | 76% / 49% / 1803 | 78% / 46% / 1654 |

Classifier AUCs: balanced 0.717, drifting 0.734, normal 0.754. Each middle pool still holds 2,200 to 4,500 presets.
Presets whose evidence is not strong enough now get no option in that group, instead of a coin-flip middle option.
Pastel (34% precision) is still the weakest option.
