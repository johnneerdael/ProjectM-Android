# Motion, waves, shapes and blur

The built-in effects are the warp mesh, decay, the classic composite filters, the built-in waveform, custom waves and shapes, and blur. Formulas and line references on this page are from MilkDrop 2's `milkdropfs.cpp`.

## The feedback loop

Each frame, the previous canvas is resampled through the warp mesh into a new canvas and darkened by decay. Blur levels are made, and then shapes, custom waves, the built-in wave, darken-centre and borders are drawn on top. The composite turns that canvas into the displayed picture. The next frame warps the canvas, not the displayed picture, so anything done only in the composite never accumulates.

## The warp formula

Per mesh vertex, after `per_pixel` code (`milkdropfs.cpp:1877–1920`):

```text
zoom2 = pow(zoom, pow(zoomexp, rad*2 - 1))
u = vertex_x * aspect / 2 / zoom2 + 0.5        (v likewise, y flipped)
u = (u - cx) / sx + cx                          stretch (v with cy, sy)
u += warp * 0.0035 * sin(…)                     four animated sine/cosine terms
v += warp * 0.0035 * cos(…)                     (speed: warpanimspeed, size: 1/warpscale)
rotate (u, v) by rot about (cx, cy)             cosf/sinf on the CPU
u -= dx;  v -= dy                               translate
```

- `warp` defaults to 1, so the animated sine warp is on unless you set `warp=0`.
- `zoom` above 1 zooms in, so the picture flows outward. `zoomexp` makes the zoom depend on the distance from the centre.
- Negative zoom uses CPU `powf` in MilkDrop. With `zoomexp=1` the result is the signed zoom; other integer nested exponents give signed odd powers or positive even powers. A negative base with a nonintegral nested exponent has an invalid real-valued power domain. In authored GLSL shader maths, `pow` is undefined for every negative base, including with integer exponents, so avoid relying on it.
- MilkDrop converts `rot` to float and passes it through CPU `sinf`/`cosf`, so any finite value works, even `rot=10000000`. ProjectM TV does the same. Some other GPU-based implementations collapse at huge angles.
- `wrap` chooses whether coordinates outside 0-1 wrap or clamp. MilkDrop applies it only to the fixed-function warp (treating `wrap > 0.5` as on); a warp shader decides with its sampler name instead. projectM treats `> 0.0001` as on and also applies it to an unqualified `sampler_main` in warp shaders ([details](shaders.md#warp-shader-responsibilities)).

### Decay

With the fixed-function warp, `decay` multiplies the warped image (default 0.98). Below about 0.9 trails vanish quickly, and at 1.0 nothing fades and the picture usually saturates. Keep it at or below 1. MilkDrop converts it to an 8-bit colour, so values above 1 wrap around to nearly black (1.02 becomes 4/255), while projectM clamps them to 1. With a warp shader, MilkDrop ignores the per-frame `decay` variable, so write the fade in the shader. projectM clamps decay to at most 1.

## Classic composite filters

These apply only when there is no custom composite shader, in this order (`milkdropfs.cpp:4147–4340`):

| Effect | Variables | Behaviour |
|---|---|---|
| Video echo | `echo_alpha`, `echo_zoom`, `echo_orient` | Blends a zoomed copy of the image over itself. Orientation mod 4: bit 0 flips horizontally, 2 and 3 flip vertically. `echo_zoom` is clamped to 0.001-1000 |
| Gamma | `gamma` (`fGammaAdj`, default 2) | Brightens by redrawing additively, once per whole unit plus a fractional pass; clamped to 0-8 |
| Brighten | `brighten` | Invert, square, invert again: lifts dark areas (MilkDrop's comment calls it a square root, but the formula is 1−(1−x)²) |
| Darken | `darken` | x²: crushes dark areas |
| Solarize | `solarize` | Folds bright values back down |
| Invert | `invert` | 1 − x |

All of these are per-frame variables, so a preset can switch them on and off from code. Upstream projectM only read their file values. ProjectM TV, like MilkDrop, reads them every frame. Darken-centre (`bDarkenCenter`) draws a small dark fan in the middle with centre alpha 3/32.

## The built-in waveform

`wave_mode` selects the shape, `wave_a` (`fWaveAlpha`) its opacity, `wave_scale` its size and `wave_smoothing` its smoothing. `wave_mystery` changes shape-specific parameters, wrapped to −1…1 for modes 0, 1 and 4. `wave_x` and `wave_y` set the position; `wave_r`, `wave_g` and `wave_b` the colour. `wave_usedots`, `wave_thick` and `wave_additive` change the drawing.

MilkDrop 2 has 8 modes: circle, X-Y spiral, spiro, spiro with alpha by volume, derivative line, explosive hash, line, double line. It reads `wave_mode` every frame as `(int)wave_mode % 8` (`milkdropfs.cpp:2852`), so modes can change mid-preset.

!!! note "Portability"
    projectM has 16 modes: MilkDrop's eight, then eight more of its own. It wraps modulo 16, so `wave_mode=9` is mode 1 on MilkDrop 2 and a projectM-only wave here. Stay within 0-7 for presets meant to look the same everywhere. A negative mode draws nothing in ProjectM TV. Of the bundled presets, four use mode 8 and none use higher modes.

The waveform has 480 samples. MilkDrop caps the line modes at a third of the canvas width in points (`milkdropfs.cpp:3008`), and fades modes 2, 3 and 5 by a factor that depends on the canvas width; mode 3 ignores `wave_a` and uses a fixed alpha times `treb²`. With `bMaximizeWaveColor` on (default), the colour is normalized so its brightest channel is full.

## Custom waves

Up to four waves, `wavecode_0` to `wavecode_3`:

| Setting | Effect |
|---|---|
| `samples` | Points to draw, up to 512. MilkDrop 2.25c recomputes the cap after per-frame code, so the 480 waveform limit and the `sep` reduction applied before it are discarded |
| `bSpectrum` | 0: waveform values (−1…1, centred); 1: spectrum (0 and up) |
| `sep` | In waveform mode, the offset between the left and right channel windows |
| `scaling` | Multiplies the values: ×0.15 for spectrum, ×0.004 for waveform, times the preset's wave scale |
| `smoothing` | 0-1: smoothing between neighbouring samples |
| `bUseDots`, `bDrawThick`, `bAdditive` | Dots instead of lines; four offset passes; additive blending |

In per-point code, `sample` runs 0→1 along the wave and `value1`/`value2` are the left/right values. Set `x`, `y`, `r`, `g`, `b`, `a` for each point. Without dots, MilkDrop smooths the line by roughly doubling its points.

!!! tip "Colour values wrap, they do not clamp"
    MilkDrop converts point colours with `(int)(v*255) & 0xFF`, so a value of 1.2 becomes dark, not white. projectM reproduces the wrap. Clamp colours yourself with `min(1, …)`.

## Custom shapes

Up to four shapes, `shapecode_0` to `shapecode_3`:

- `sides` (3-100) gives a regular polygon of radius `rad`, rotated by `ang`, centred on `x`, `y`.
- The fill is a fan from the centre colour (`r g b a`) to the edge colour (`r2 g2 b2 a2`).
- `textured=1` fills it with the previous frame, rotated by `tex_ang` and scaled by `tex_zoom`, with bilinear filtering. In MilkDrop 2 the edges wrap, *except* on frames where blur levels were computed: the blur passes leave the sampler on clamp (`milkdropfs.cpp:1611`) and nothing resets it before the shapes are drawn. projectM always wraps.
- `border_a > 0` draws an outline; `thickOutline` draws it with four passes offset by one canvas pixel.
- `additive=1` blends additively.
- `num_inst` draws the shape that many times per frame. Per-frame code runs for each instance with `instance` = 0, 1, 2 …, and q, t and all shape variables reset per instance.

Tiny shapes are sensitive to pixel centres, because Direct3D 9 samples pixels at integer coordinates and OpenGL at half-integers. A shape with `rad=0.002` at `x=y=0.5` lights one pixel in MilkDrop and none in a plain OpenGL port. Feedback presets that seed their image with many tiny shapes depend on that pixel. ProjectM TV aligns shapes the way Direct3D 9 did. Even so, shapes smaller than a pixel can be sparse, so make important shapes at least a couple of pixels across at 1080p.

## Blur

The blur effect makes three progressively blurrier, smaller copies of the canvas for shaders: blur1 at a quarter of the canvas size, blur2 an eighth, blur3 a sixteenth. They are computed only if a shader uses them.

| Setting | Variable | Default | Meaning |
|---|---|---|---|
| `b1n`, `b2n`, `b3n` | `blur1_min` … | 0 | Lower end of each level's stored range |
| `b1x`, `b2x`, `b3x` | `blur1_max` … | 1 | Upper end |
| `b1ed` | `blur1_edge_darken` | 0.25 | Darkens blur1's edges |

The range lets a level spend its 8 bits on the brightness band you care about. Level 2's range is nested inside level 1's, and level 3's inside level 2's.

When `max − min` is below 0.1, MilkDrop's `GetSafeBlurMinMax` (`milkdropfs.cpp:1551–1583`) is meant to widen the range around its average, but a typo sets both bounds to the same value, so the range collapses and the blur becomes meaningless. ProjectM TV widens the upper bound instead, which means the same preset can look different from MilkDrop. Keep every level's range at least 0.1 wide, and keep levels 2 and 3 inside level 1's range.

Always read blur with `GetBlur1/2/3(uv)`, which undo the range encoding (see [Shaders](shaders.md#blur-levels-must-be-decoded)).

## Motion vectors and borders

- Motion vectors (`mv_x`, `mv_y` grid count; `mv_dx`, `mv_dy` offset; `mv_l` length; `mv_r g b a` colour) draw short lines showing the warp's motion, *before* the warp. They are visible only when `mv_a` > 0.
- Outer and inner borders (`ob_size`, `ob_r g b a`; `ib_size`, `ib_r g b a`) draw frames at the canvas edge every frame. They are drawn into the canvas, so feedback carries them inward. Many tunnel effects are just a border plus zoom.

## Lines, dots and resolution

Waves, outlines and motion vectors are 1-pixel lines in MilkDrop, tuned on screens of roughly 1024×768. Rendered at 4K, the same line covers a much smaller share of the picture, and line-driven feedback presets go dark. ProjectM TV draws lines with a width that keeps their share of the picture, and keeps blur radius and wave sample counts at their authored scale. If you author on a high-resolution screen with another player, check your preset at 720p too: what looks subtle at 4K may be bright at the resolution most presets were designed for. [How this works](../engine/resolution.md).
