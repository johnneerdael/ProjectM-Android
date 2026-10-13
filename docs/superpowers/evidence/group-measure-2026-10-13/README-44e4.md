# Group measure: 44e4fa2f (deterministic baseline)

The first group measure with deterministic predictions: identical across
`PYTHONHASHSEED` values. It includes per-frame decay, RGBA noise, random
textures as the expected image and the blur, relief and tiling descriptors.
It does not include the later side-count (d24b7c4a) and motion-vector colour
(4530206b) fixes. Same 200 presets, ruler references and frames as before;
199 compared.

| Metric | base 9948b7f4 | c2e1 | 44e4 |
|---|---|---|---|
| Luma error median / mean | 0.0219 / 0.0840 | 0.0159 / 0.0699 | 0.0157 / 0.0653 |
| Colour map error median / mean | 0.0516 / 0.1035 | 0.0453 / 0.0911 | 0.0451 / 0.0861 |
| Frame-difference error median / mean | 0.0059 / 0.0191 | 0.0052 / 0.0170 | 0.0048 / 0.0162 |
| Map correlation median / mean | 0.757 / 0.620 | 0.798 / 0.646 | 0.815 / 0.659 |
| Luma within 0.05 | 64.3% | 69.8% | 69.8% |
| Map correlation above 0.8 | 45.2% | 47.7% | 48.7% |

Paired c2e1 → 44e4: map correlation better on 12 presets and worse on 4,
colour map 11 / 5, frame difference 8 / 5, luma 8 / 7. Paired base → 44e4:
luma 72 / 39, colour map 74 / 36, map correlation 55 / 45. Future
comparisons use 44e4 as the reproducible reference.
