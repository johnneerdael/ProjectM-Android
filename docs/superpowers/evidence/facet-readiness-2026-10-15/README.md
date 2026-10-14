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
