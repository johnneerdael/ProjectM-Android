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

## Correction (same day)

The explanation above, that the RGBA noise redraw caused the spread, was not
checked. Two of the largest losers (`liquid circuitry … pataoblivion`, map
correlation −0.22; `toffee cream`, −0.12) do not sample noise at all. The
real cause was nondeterminism. The recurrence builders popped state names
from a Python set, so the order of state updates, and the `rand()` value each
update received, followed per-process string hashing. The same snapshot gave
`toffee cream` mean luma 0.170, 0.202 and 0.156 in three runs. Every preset
with `rand()` in wave or shape programs therefore drew differently in each
group-measure process. Part of each version-to-version difference measured
so far, gains and losses alike, is that noise rather than the code change.

Fixed in 44e4fa2f (names processed smallest first, state returned sorted).
`predict_one` now gives identical results across `PYTHONHASHSEED` values. A
deterministic group measure of 44e4fa2f is the new baseline for comparisons.

## The four presets that stayed low after the determinism fix

`drop ballast`, `american pie 3`, `Two-Pointed Pulsagon` and `finchman nz`
kept their c2e1 values in the deterministic 44e4 run. All four sample noise
textures and read their fourth channel. Map correlation against the engine
over four noise draws, with RGBA noise and with the old RGB-only noise:

| Preset | RGBA noise | RGB noise | wt2 run | c2e1 run |
|---|---|---|---|---|
| drop ballast | −0.10, −0.20, +0.29, −0.35 | −0.05, +0.07, −0.23, +0.04 | −0.06 | −0.35 |
| Two-Pointed Pulsagon | +0.09, −0.02, +0.09, −0.09 | +0.09, +0.02, −0.02, +0.07 | +0.13 | +0.02 |

For noise-driven presets the score swings by up to ±0.3 with the noise
texture alone, under either implementation. Both version values sit inside
that spread, and the averages over draws barely differ. projectM seeds its
noise textures from the clock at every load, so these layouts are random in
the engine too. This is noise-draw variance, not a regression. A per-preset
comparison of noise-driven presets should average over several draws.
