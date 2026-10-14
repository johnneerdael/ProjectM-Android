# r162 v2: one source point per ray

The engine samples `c + (p - c)/s` (stretch about (cx, cy)). Here `s = zm*rd`, with `rd` the distance from c,
so the sampled offset `(p - c)/rd` is a unit step along the pixel's own ray. Every pixel on a ray reads the
same source point, and each frame becomes coloured rays converging on c. The v1 recipe had no measure of
this, so the reader described only the central curve.

`preset_recipe.ray_sampling` measures it statically. It evaluates the closed-form backward map (the
illustration's mesh evaluator, per pixel at 96x54), with frame-state inputs drawn arbitrarily in [-3, 3],
and reports the share of pixels with `|d r_src / d r_dst| < 0.15` (the minimum over three draws). It costs
at most 0.11 s per preset and runs only when zoom, sx or sy vary across the screen (a uniform scale gives
1/s everywhere). `intent` emits `radial_rays` when the share is at least 0.5.

| Preset | share | Render |
|---|---|---|
| r162 fat cancer gnothing gnew | 1.00 | capture: spokes converge low on screen |
| r161 whoraeckle curt ain Rod | 0.99 | capture: fan rays |
| 376 (anisotropic rd, warp/composite shaders, echo mirror) | 1.00 | emulator: fans in the lower corners; shaders add mirrored structure |
| Benjam - Fractal Timepiece (`zoom = rad`) | 1.00 | emulator: black for 300 frames (its only wave has alpha 0.001), so nothing to spread |
| r159 / r157 (radial zoom profiles) | 0.04 / 0.00 | no rays |

Group measure (200 presets): 54 evaluated, 4 at or above 0.5. What shows depends on content existing and on
later shaders; the effect's condition text says it smears drawn content.
