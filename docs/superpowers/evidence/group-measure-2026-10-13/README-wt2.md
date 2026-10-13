# Group measure: working-tree snapshot wt2

`wt2` is a copy of the analyzer taken while the per-frame random sites, mesh
terms with stepped frame controls and the legacy-composite video echo were
uncommitted. That code was committed in d584df77. Same 200-preset selection
(seed 20261013), same native ruler references, frames 60–149.

| Metric | base 9948b7f4 | head 9dee0aba | wt2 |
|---|---|---|---|
| Luma error median | 0.0219 | 0.0171 | 0.0159 |
| Luma within 0.05 | 64.3% | 70.9% | 70.4% |
| Colour map error median | 0.0516 | 0.0443 | 0.0439 |
| Map correlation median | 0.757 | 0.794 | 0.808 |
| Map correlation above 0.8 | 45.2% | 46.7% | 48.2% |
| Frame-difference error mean | 0.0191 | 0.0164 | 0.0165 |

Paired head → wt2: luma better on 9 presets and worse on 6, map correlation
better on 9 and worse on 3, frame difference better on 4 and worse on 8. Most
presets do not use the changed paths, so the totals move little. One preset
(Acid Mandala v3) timed out in every version and is not compared.
Reports: `report-head-wt2.json`, `report-base-wt2.json`.
