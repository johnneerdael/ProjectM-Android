# r164: line rasterization at pixel boundaries (emulator probes, 2026-10-14)

Probe presets have one white custom wave, decay 0, no echo, and render at 480x270 on emulator-5610.
They are in `build/line-edge-probe-2026-10-14/presets`. Rows and columns are counted top-down in the
captured image.

| Line | Lit (thin) | Lit (thick) |
|---|---|---|
| x = 0 (window 0.0) | none | column 0 |
| x = 0.5 (window 240.0) | column 239 | columns 239, 240 |
| x = 0.501 (240.48) | column 240 | |
| x = 1 (480.0) | column 479 | |
| y = 0.5 (top-down 135.0) | row 135 | row 135 |
| y = 0.501 | row 134 | |
| y = 0.5 - 0.1/480 (135.1) | row 135 | row 135 |
| y = 0.5 + 0.1/480 (134.9) | row 134 | rows 134, 135 |
| y = 0, 1, 0.998, 269/270 | none (custom-wave y is scaled by 1/aspect, so these are off screen) | |

The rule these give:

- `to_pixels` returns window coordinates (pixel edges on integers). The line path must not add half a pixel.
- On an exact boundary a line goes to column `ceil(x) - 1` and top-down row `floor(y)`.
- Thick passes add `1/viewportX` to NDC x and y. The vertex is `y_ndc = (1 - 2y)*invAspectY`, so +y NDC
  moves half a pixel right and 270/960 px *down* in the captured image.

The illustrator drew r164's x=0 line in column 0, and the stretch about cx=0 then smeared it into bright
stripes. The engine draws nothing and stays black. v3 prediction (`prediction-v3.png`) is black.

## Corpus gate (200-preset group measure, analyzer 80c0fb5a against the line fix)

Mean luma error 0.0366 → 0.0354; within 0.05 81.9% → 82.9%; RGB error 0.0419 → 0.0405; map correlation
0.719 → 0.724; series correlation 0.809 → 0.811. Paired: colour-map error 34 better / 13 worse, luma 24 / 24.
Largest gain: EoS+Phat I_v2 Shape v3, luma error 0.223 → 0.015. No regression.
