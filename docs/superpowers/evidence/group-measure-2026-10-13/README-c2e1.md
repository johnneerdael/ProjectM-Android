# Group measure: c2e11470 (RGBA noise; blur, relief and tiling descriptors)

Same 200-preset selection, ruler references and frames as `README-wt2.md`.
The analyzer is the committed tree at c2e11470. Among its changes, only the
RGBA noise textures affect the illustration; the blur, relief, tiling and
time-spread changes are descriptors.

| Metric | wt2 | c2e1 |
|---|---|---|
| Luma error median / mean | 0.0159 / 0.0697 | 0.0159 / 0.0699 |
| Colour map error median / mean | 0.0439 / 0.0914 | 0.0453 / 0.0911 |
| Frame-difference error median / mean | 0.0058 / 0.0165 | 0.0052 / 0.0170 |
| Map correlation median / mean | 0.808 / 0.641 | 0.798 / 0.646 |
| Series correlation median / mean | 0.916 / 0.740 | 0.915 / 0.746 |

Paired wt2 → c2e1: frame difference better on 44 presets and worse on 30;
colour map 43 / 35; luma 41 / 41; map correlation 37 / 39. Overall the
change is neutral to slightly positive. About 80 presets change each way,
far more than for wt2, because RGBA noise redraws the random noise values
for every preset that samples noise. Part of the spread is therefore a
different random draw, not a better or worse model. The checkpoint where
the fourth channel matters (r70) improved from 0.70 to 0.96 time-average
correlation.
