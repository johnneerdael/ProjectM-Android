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

## 4530206b (per-frame side count, motion-vector colour)

Same 200 presets, seed and frames (199 compared; `compare-44e4-4530.log`).

| Metric | 44e4 | 4530 |
|---|---|---|
| Luma error mean / median | 0.0653 / 0.0157 | 0.0606 / 0.0154 |
| Colour map error mean / median | 0.0861 / 0.0451 | 0.0827 / 0.0429 |
| Map correlation median | 0.815 | 0.821 |
| Luma within 0.05 | 69.8% | 71.4% |

Paired 44e4 → 4530: luma error 11 better / 4 worse, colour map error
10 / 5, map correlation 8 / 7.

## 908dea3b (r90–r94 fixes), corrected snapshot

The first 908d pass used `git archive` snapshots without the `core` symlink
(no bundled assets); its losses were measurement artifacts. Re-run with the
link (`report-4530-908dc.json`):

| Metric | 4530 | 908d |
|---|---|---|
| Luma error mean / median | 0.0568 / 0.0152 | 0.0538 / 0.0150 |
| Colour map error mean / median | 0.0790 / 0.0419 | 0.0753 / 0.0416 |
| Map correlation median / mean | 0.822 / 0.672 | 0.825 / 0.686 |
| Luma within 0.05 | 72.1% | 71.6% |

Paired: map correlation 49 better / 26 worse, luma error 45 / 36. The
largest losses are random-draw variance ("fed - glowing 5", "rce-ordinary":
0.007–0.168 across stepper seeds alone) and one exposed gap ("EoS+Phat -
I_v2_Shape_v3": the clamp rule is right, a separate over-retention remains).
Presets with per-frame `rand()` redraws should be measured over several seeds.

## 7d1c84e3 (r95–r104 fixes)

Same 200 presets against the corrected 908d baseline (`report-908dc-7d1c84e3.json`):

| Metric | 908d | 7d1c |
|---|---|---|
| Luma error mean / median | 0.0542 / 0.0150 | 0.0530 / 0.0149 |
| Colour map error mean | 0.0757 | 0.0747 |
| Map correlation median | 0.825 | 0.829 |
| Luma within 0.05 | 71.3% | 73.3% |

Most presets are unchanged; three suksma presets gain strongly (for example
0.346 → 0.099). One large loss: "Rovastar & Illusion - Further Basic
Electronica 2 + cope" (0.000 → 0.299; engine solid white). Its warp computes
`frac(pow(ret, 2*sand))*2`; the old evaluator refused `pow` and fell back to a
gain model that happened to give white. Emulator probes (`pow-probes/`) show
the engine returns exactly 1 for `pow(1, y)` with runtime inputs and ≈0.9996
for `pow(0.999, y)`, matching our rule. Our canvas reaches exactly 1, `frac`
resets it to 0.45 and it cycles (brightened 0.70); the engine's stays white,
most likely because its warp-mesh UVs leave sampled values a hair below 1.
A numerical knife-edge, open; the pow rule itself is confirmed.
