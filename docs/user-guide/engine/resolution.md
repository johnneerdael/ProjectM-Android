# Rendering MilkDrop at 4K

MilkDrop presets were written on Windows PCs between about 2001 and 2013, mostly at about 1024×768. Many of their quantities are measured in *pixels* rather than as fractions of the picture: a waveform is a 1-pixel line, a blur level is a quarter of the canvas blurred by a few texels, and a warp shader that steps by `texsize.zw` moves the image one texel per frame. Render the same preset at 3840×2160 and each of those quantities shrinks to a fraction of what the author saw. That is the cause of the familiar "projectM looks dark and thin at 4K" problem.

ProjectM TV Engine treats resolution as a fidelity problem. It renders at the TV's native panel size while keeping each preset's *authored scale*. The sections below describe each mechanism, its measurements and what it does not fix.

!!! note "Upstream context"
    This is the work described by projectM issue [#682 *Improve line rendering on higher resolutions*](https://github.com/projectM-visualizer/projectm/issues/682). ProjectM TV Engine addresses its resolution-scaling part: reference-scaled quad lines plus the related blur, fade, sample-count and `texsize` rules that line width alone cannot fix. The round joins and caps the issue suggests are not implemented. The behaviour stays opt-in in the C API, so upstream-compatible callers that leave the reference size at 0 get byte-identical GL-line output.

## The problem, measured

| Quantity in MilkDrop | Why it breaks at 4K | Symptom |
|---|---|---|
| Waveforms, custom waves, shape outlines and motion vectors drawn as **1 px GL lines** | At 3840×2160 a 1 px line covers less than a third of the share of the picture it covered at 1024×768 (it would need 3.25 px) | Line-driven feedback presets darken or go almost black |
| **Blur levels** made at ¼, ⅛ and 1/16 of the canvas, blurred by a few of their own texels | The blur radius is a fixed share of the picture only at one size; at 3840×2160 blur1 was **3.75× narrower** than at 1024×768 | Glow and smear presets look sharper and darker |
| **Line-waveform point count**: MilkDrop caps line waveforms at a third of its canvas width in points (`milkdropfs.cpp:3008`) | The cap rises with the render width, so a large render draws far more points than the author saw | `$$$ Royal - Mashup (103)` was **2.3× as bright** at 1080p (0.50 mean luma against 0.22) |
| **`texsize`** in preset shaders (5,284 of the 9,606 bundled presets step by `texsize.zw` texels; 4,428 convert UV to pixels with `texsize.xy`) | A warp that advects by `grad*texsize.zw*6` moves the picture **3.25× slower** at 2160p | `Acid Mandala v1c` stayed small and desaturated (saturation 0.46 against 0.80) |
| **Bilinear feedback re-sampling**, about a sixth of a texel² of smoothing per frame | At 2160p the smoothing is about 10× smaller in picture units | Low-diffusion presets settle into a different visual regime |

## Quad lines: resolution-independent strokes

projectM, like MilkDrop, draws lines with GL lines: 1 px wide, with thick lines drawn several times at an offset. ProjectM TV Engine adds `projectm_opengl_set_line_reference_size(W_ref, H_ref)`. When a reference size is set, lines are drawn as instanced quads, one instance per segment, with miter joins.

!!! note "Which reference size the app uses"
    The Android core uses MilkDrop's 1024×768 reference at render sizes up to 1330p. Above 1330p with Native trails on (the default), it uses 1280×720, matching the authored feedback canvas: at 3840×2160 lines are 3 px wide and `texsize` and the blur chain use 1280×720. The worked numbers on this page use the 1024×768 reference.

- Lines are 1 px wide at the reference size and wider above it by the square root of the area ratio: `max(1, sqrt(W·H / (W_ref·H_ref)))`. A line then covers the same share of the picture at any size and aspect ratio. With the 1024×768 reference that is 1.62 px at 1920×1080 and 3.25 px at 3840×2160.
- At or below the reference area nothing changes, and lines stay MilkDrop's 1 px lines at full brightness. In testing, thinner lines faded by their width made feedback presets go dark below 1080p (`$$$ Royal - Mashup (191)` was black at 480p); keeping 1 px lines avoids that low-resolution darkening.
- Thick lines use MilkDrop's four-pass scheme: the thin line is drawn four times, offset by (0,0), (+x,0), (+x,+y) and (0,+y), with the offsets scaled like the width. projectM uses one pixel for the main wave and half a pixel for custom waves and shape outlines, while MilkDrop 2 uses one canvas pixel for all three (`milkdropfs.cpp:2455, 2738`). That difference remains.
- Edges are hard. An anti-aliased edge exists (`projectm_opengl_set_line_antialiasing`) but is off. In testing a soft edge made a feedback preset 14% darker, because presets that feed their own lines back expect MilkDrop's hard pixels.
- At the reference size a thin quad line lights the same pixels as MilkDrop's 1 px line, apart from a few at sharp turns. On GLES the quads are moved by 1/64 px so that pixel ties follow Mali's GL lines. This was verified on a Mali-G52; Tegra was not verified.
- Dots (GL points) use whole-pixel sizes, with alpha faded by the difference in area.
- If the driver rejects the line shaders, the engine falls back to GL lines.

Waveforms also use miter joins, although #682 suggests round joins. Round joins would blend each joint twice, which changes the brightness of additive and feedback presets.

### Quantities that follow the reference

Line width alone does not restore the authored look. Above the reference area, the following MilkDrop quantities are computed as if the canvas were the reference size.

- Waveform point count: the line-waveform point rule uses the reference-equivalent width, render width ÷ line scale, which is 1182 px at both 1920×1080 and 3840×2160 with the 1024×768 reference. At the historical 160-point checkpoint, `$$$ Royal - Mashup (103)` measured 0.21 mean luma at 1080p and 0.23 at 2160p, against 0.22 at 1024×768. The separate I19 proposal restores MilkDrop’s *cap* at width ÷ 3 while keeping the reference-equivalent width: 341 raw mode-4 points for a 1024-wide authored canvas and 426 with the active Native 1280-wide canvas. It remains outside the shipping series pending matched authored/resolution comparisons; brightness relative to the previous 4K output alone is not enough to decide fidelity.
- Spiro and hash wave fade: MilkDrop 2 multiplies the alpha of wave modes 2 and 5 by 0.07, 0.09, 0.11 or 0.13 for canvas widths of exactly 256, 512, 1024 or 2048, and mode 3 *replaces* the alpha with a size-dependent constant times `treb²` (`milkdropfs.cpp:2955–2990, 3070`). ProjectM TV preserves mode 3’s replacement and the mode-adjusted volume multiplication (patch 0016) and retains projectM’s size buckets in `Waveform::MaximizeColors`. Above the reference area, ProjectM TV feeds that function the reference size instead of the render size.
- Blur chain: blur levels are built from a source with the reference's area (1182×665 at both 1080p and 2160p). The first pass reads the previous frame through its mipmaps at log2 of the scale, so every source pixel still counts. Presets without blur are unaffected. On the Ugoos AM6 this made blur-heavy presets cheaper at 2160p: `fat cancer tour meant t nz+` rose from 7.34 to 9.12 fps (+24%).

### Virtual `texsize`

Above the reference area, preset code sees a canvas of the reference's area at the render's aspect ratio, `ShaderCanvasSize()`. This covers `texsize` (`_c7`), `texsize_main`, `mip_x/y/avg` (`_c12`) and the per-frame and per-pixel `pixelsx`/`pixelsy`. In MilkDrop, `texsize` was the internal canvas the preset was tuned on, so steps written in texels keep their authored size in picture units. Real textures, their sampling and `texsize_<name>` for user images are unchanged. Without a reference size, or at or below its area, frames are byte-identical to the unmodified path.

### Why 1024×768

Eighteen line-heavy presets (feedback showcases and the presets with the largest before/after differences) were rendered with identical audio, clock and seeds. Their mean brightness was compared with GL lines at 1182×665, which is 16:9 with the area of 1024×768 and the fairer ground truth for a 16:9 TV.

| Comparison | Quad lines + reference rules | Plain GL lines |
|---|---|---|
| Median brightness ratio at 1920×1080 | **1.01** | 0.91 |
| Median brightness ratio at 3840×2160 | **1.04** | 0.76 |
| Presets within 10% at 1080p / 2160p | **17 / 14 of 18** | 4 / 4 of 18 |
| Brightness change between 1080p and 2160p (median) | **2.4%** | 15% |

An earlier and wider sample, measured with a 1920×1080 reference, took every 40th bundled preset (175 comparable presets, 168 drawing visible lines). It gave a median brightness deviation of 0.01% from GL lines at 1080p, with no preset more than 10% different. Between 1080p and 1440p, brightness changes by a median 2.0% with quad lines against 4.3% with GL lines.

Aspect ratio alone changes many feedback presets considerably. Going from 1024×768 to 1182×665 with GL lines makes `Goody's Trichromatic Mind Games` 1.35× as bright and `suksma - bleuneycombinatoriccitensor` 0.11× as bright. No uniform can undo that, because the composition itself is different.

### Cost on a TV GPU

On a Ugoos AM6 (Mali-G52, Android 9) the line shaders compile without errors. Measured against GL lines with the current 1024×768 reference (music playing, alternating 60 s runs):

- `Flexi - alien complex 03` (many outlined shapes) is 2.0% slower at 1080p (44.6 against 43.7 fps, GPU-bound).
- At 2160p, `$$$ Royal - Mashup (191)` is 0.9% slower and `$$$ Royal - Mashup (103)` 3.9% slower.

An earlier run with a 1920×1080 reference, where lines stay 1 px at 1080p, measured the first preset within noise and 2 px motion vectors at 2160p up to 1.85% slower.

## Native trails: authored feedback, native geometry

Feedback presets accumulate their image frame after frame. The authored scale matters most in that accumulation, and re-sampling at 4K diverges most there too. Native trails separates the feedback from the new geometry:

- The feedback canvas L runs at an authored size. Above 1330p the Android core uses a 1280×720 line reference and an integer scale `S = round(sqrt(W·H / (1280·720)))`. At 3840×2160, S = 3 and L is 1280×720. At 2560×1440, S = 2. Compatible canvases need S ≥ 2 and both dimensions divisible by S.
- New geometry (this frame's waves and shapes) and the composite are drawn at native resolution. The same evaluated geometry is presented twice: into the authored feedback, and sharply at native size. Equations and RNG are not evaluated a second time, so the level you choose does not change a preset's state.
- **Standard** (the default) skips the native warp. **Medium** and **High** add a centred, headroom-limited native detail band with gain caps of 0.5 and 1. Both levels run the same additional passes, so they differ in detail and not in cost. Gain is limited near black and white, and the shader preserves each block's reconstructed mean before 8-bit quantization, so signed detail cannot add brightness through clipping.
- Each preset owns its resources, including during a transition.
- At render sizes of 1330p or below, with an incompatible integer canvas, or on a driver shader or resource failure, the engine falls back to the legacy path: an average-preserving variance filter `(scale²−1)/6`, capped at 1.9, applied to eligible bilinear warp reads. **Advanced › Diagnostics** shows the active canvas or the fallback reason.

Native trails is an Android-core default. The projectM C API leaves it off, so compatibility tests and other hosts get upstream behaviour unless they opt in.

## What this does not fix

- Chaotic presets can diverge from tiny input differences. Compare them with the same audio and timing.
- Aspect ratio is part of the composition. A 4:3 preset on a 16:9 TV is a different picture.
- `suksma - penattrition - geiss crossfire shaders` keeps MilkDrop's minimum motion-vector length in pixels. Scaling it fixed that preset but made another worse, so the value stays as MilkDrop has it, except while diffusion compensation is active.
- `$$$ Royal - Mashup (191)` is a one-texel neighbour-difference recurrence seeded by the wave. No uniform makes it resolution-independent.
- Host and emulator measurements do not establish performance or shader compatibility on every physical TV GPU.

Source and full measurement notes: [`docs/ARCHITECTURE.md`](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/ARCHITECTURE.md#5-architecture) (Lines, Virtual texsize, Native trails) and the [Native trails design](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/specs/2026-10-05-native-trails.md).
