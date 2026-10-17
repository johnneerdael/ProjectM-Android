# Patch catalog

ProjectM TV Engine is projectM at commit `6f6480746` (unreleased 4.2 master) plus 37 ordered patches in [`tools/projectm-patches/`](https://github.com/johnneerdael/ProjectM-TV/tree/main/tools/projectm-patches). They are applied when the native library is built; the upstream source is never edited in place.

Most patches make the engine behave more like MilkDrop 2. projectM is a clean-room reimplementation of MilkDrop on OpenGL, and over the years small differences crept in: in how equation code is accepted, how HLSL becomes GLSL, where Direct3D 9 and OpenGL put pixel centres, and which per-frame variables are actually read. Each entry below names what projectM did differently, what MilkDrop 2 does (citing its released source where we checked it), what the patch changes, and the preset that shows it.

Two patches deliberately go beyond MilkDrop 2. [0010](#0010-each-preset-keeps-its-own-textures) adds correct behaviour for something MilkDrop never supported: presets whose textures live in different folders. [0005](#0005-blur-ranges-that-cannot-collapse) repairs a MilkDrop 2 typo instead of reproducing it.

!!! info "How the images were made"
    The images for 0001 to 0014 come from the [current-patch proof](https://github.com/johnneerdael/ProjectM-TV/pull/55). A preset is rendered by real libprojectM on a GPU-accelerated Android TV emulator: GLES 3.0, frozen audio, seed 12345, a frame/30 clock, frames 0 to 119, each role captured twice with byte-identical results. *Without* means the full series minus only that patch (a single-patch ablation); *with* is the full series at that recorded 14-patch checkpoint. Images are unbrightened and rendered at 512×288 (some at 256×144) with quad lines and Native trails off. They establish cause and effect for that preset on that GPU. They are not Windows reference renders, and they do not certify every preset or every TV.

!!! info "Earlier upstream-master comparisons for the audit repairs"
    The earlier whole-engine pairs in 0017 to 0033 compare unmodified upstream master [`e98fca85`](https://github.com/projectM-visualizer/projectm/commit/e98fca85e57802d27a6d11499642de2a1d5e994e) with ProjectM TV [`8a15996e`](https://github.com/johnneerdael/ProjectM-TV/commit/8a15996e8510533113a44e26feaddc3a7d6e85f5) with all 34 patches. They are new native Apple M4 Pro GPU captures: OpenGL 4.1 over Metal, matching preset bytes, fixed float32 mono audio, seed 12345, 48×32 mesh and 30 Hz clock. Every RGB frame repeats byte for byte within each role, with no reported GL errors. Originals run 480 frames; small supplementary diagnostics and 4K pairs run 240. Each caption gives the actual dimensions and the selected frame.

    Both engines use actual output dimensions, classic lines, antialiasing off and TV feedback detail off. These full-engine pairs include all earlier fixes, so they are neither single-patch ablations nor production Native Standard-trails screenshots. The linked issue controls establish the cause of each repair. The pairs cover 18 retained repair IDs; visible effects and measured performance benefits have separate evidence. Synthetic diagnostics are marked as such, and affected-preset counts are unconfirmed. The gamma repair has no demonstrated visible improvement in its isolated original witness, but its separate native-M4 benchmark demonstrates lower rendering cost. Click any image for the lossless full-resolution frame. Matching zooms crop the original browser image without editing its brightness or pixels. [Capture records and reproduction](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/patch-visual-catalog/README.md) include exact identities and limits. Desktop images do not certify Windows/D3D appearance or TV performance.

!!! info "Close-ups that isolate each correction"
    Sections 0021, 0023, 0028, 0030, 0032 and 0033 lead with close-ups of real presets at native 3840×2160. The left panel disables only the named repair and the right panel enables it. All other patches, preset bytes, frozen audio, seed and clock match. These Apple M4 Pro GPU captures use the Native Standard profile: 1280×720 line/shader reference, antialiasing enabled and feedback detail 0. Each selected RGB frame repeats exactly in two runs, with no reported GL errors. Each caption names the feature to look at; click a close-up for its unchanged full frame.

    The earlier comparisons of upstream master with the complete TV engine are still inside each section. They include several fixes and use a different rendering profile, so their overall brightness cannot identify the effect of an individual repair. [Isolated capture records and reproduction](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/patch-proof-clarity/README.md) distinguish those comparisons. Desktop images establish these witnesses, not physical-TV performance or Windows pixel identity.

## At a glance

| Patch | What it fixes | Witness |
|---|---|---|
| [0001](#0001-tv-rendering-and-preset-compatibility) | MilkDrop's tolerant equation loading; sampler, random-texture and blur-target fixes; resolution independence; TV rendering | `161.milk` |
| [0002](#0002-hlsl-compatibility-and-exact-float-literals) | HLSL that Microsoft's compiler accepted | `Flexi - madness portal.milk` |
| [0003](#0003-evaluator-lone-dot-and-per-thread-random) | NS-EEL's lone `.` number; undisturbed `rand()` | `Stahlregen - funky Blur (lotus mix) …` |
| [0004](#0004-textured-shapes-sample-with-wrap-and-bilinear-filtering) | Wrap/bilinear sampling for textured shapes | `widest swing.milk` |
| [0005](#0005-blur-ranges-that-cannot-collapse) | A usable blur range when min ≈ max | `flexi - a julia fractal for hexcollie embossed (Jelly).milk` |
| [0006](#0006-negative-zoom-mirrors) | Mirroring by negative zoom | `Hexcollie - This is where we begin stripped.milk` |
| [0007](#0007-per-frame-waveform-controls) | Per-frame `wave_mode`, dots, thickness, additive | `Hexcollie - now entering the wormhole2 …` |
| [0008](#0008-per-frame-display-filters) | Per-frame gamma, echo, brighten, darken, solarize, invert | synthetic control |
| [0009](#0009-premultiplied-user-textures) | Released texture bytes after projectM's image-loader change | `suksma - chemosynthetic nosferatu … rand tritex - inv play.milk` |
| [0010](#0010-each-preset-keeps-its-own-textures) | Beyond MilkDrop 2: per-pack texture folders that blend without swapping images | Aurora SOL / LUNA packs |
| [0011](#0011-huge-rotation-values) | CPU sine/cosine for `rot` | `EoS_Phat_PeterP_Sentinel_Aware_6 …` |
| [0012](#0012-tiny-shapes-land-on-the-right-pixels) | Direct3D 9 pixel centres for custom shapes | `amandio c - the green machine 2 … btbam covers sepultura.milk` |
| [0013](#0013-composite-reads-the-exact-feedback-texel) | Exact texel reads in custom composites | `DemonLD_-_Toxic_water_diffusion …` |
| [0014](#0014-legacy-colour-shading-and-mode-1-spirals) | Authored `fShader` tint amount; mode-1 spiral opacity and open shape | `BrainStain- boiling-mix2(redi jedi full carb mix).milk` |
| [0015](#0015-negative-warp-powers-use-milkdrop-cpu-maths) | CPU-defined negative nested powers beyond authored exponent one | synthetic nested-unit, square and cube controls |
| [0016](#0016-cached-static-warp-uploads) | Retain the static mesh until size/aspect/producer changes | `cache controls` |
| [0017](#0017-built-in-wave-opacity) | Original mode alpha and volume amplification | `Happening.milk` |
| [0018](#0018-custom-wave-input-windows) | Centered and separated valid audio windows | `Mig_304 - geiss remix 2.milk` |
| [0019](#0019-gamma-only-pass-count) | Separate original gamma-only epsilon | `suksma - type o negative - world coming down.milk` |
| [0020](#0020-named-eel-constants) | Original double decimal inputs | `audit pi precision.milk · synthetic` |
| [0021](#0021-original-equation-inputs) | Inverse aspect and fresh wave-point inputs | `Crush ice; Carnival` |
| [0022](#0022-negative-odd-echo-orientation) | Signed nonzero horizontal flip | `audit negative echo.milk · synthetic` |
| [0023](#0023-legacy-oscillator-y) | Original physical Y in built-in warp deformation | `Geiss - Mega Swirl 2 (2).milk` |
| [0024](#0024-legacy-mesh-diagonal) | Original physical triangle diagonal | `07.milk` |
| [0025](#0025-legacy-per-pixel-traversal) | Original physical row evaluation order | `audit legacy physical traversal.milk · synthetic` |
| [0026](#0026-legacy-angle-seam) | Original signed-zero negative-X seam | `Liquido.milk` |
| [0027](#0027-wave-colour-clamp) | Clamp local RGB before nonzero brightening | `Geiss - Blur Mix 3.milk` |
| [0028](#0028-border-fan-topology) | Original border strip-fan coverage | `Dbleja - Escape (Red Mix).milk` |
| [0029](#0029-original-line-sample-caps) | Reference-width cap on original line budgets | `$$$ Royal - Mashup (103).milk` |
| [0030](#0030-discrete-custom-dots) | Authored dots without extra interpolated points | `phat + EoS - Bass_responce_Red_Movements_Disorienting nebula3.milk` |
| [0031](#0031-circle-spacing-and-closure) | Original angular spacing and closure before smoothing | `$$$ Royal - Mashup (11).milk` |
| [0032](#0032-live-shape-thickness) | Evaluated style captured per instance and replay | `martin - city lights v2(1).milk` |
| [0033](#0033-latest-previous-motion-field) | Refresh actual warp UV while vectors are hidden | `Seizure Salad` |
| [0034](#0034-gles-motion-field-storage) | Compatible continuous UV on GLES without float render targets | capability, integer storage and decoder controls |
| [0035](#0035-program-cache-switch) | Retained diagnostic API for the shared program binary cache | `program-cache-switch` control |
| [0036](#0036-powervr-framebuffer-retirement) | Protect PowerVR framebuffer retirement during changes/resizing | real-GL binding/lifetime control |
| [0037](#0037-reusable-line-rendering) | Share line geometry, shaders and instanced Mesh drawing in Renderer | Mesh and matched-render controls |

## 0001 — TV rendering and preset compatibility

The largest patch consolidates 27 historical patches from the projectM 4.1.7 era, ported onto 4.2 master's new Mesh and shader-cache ownership.

![Upstream rejects 161.milk; ProjectM TV renders it](../images/patches/0001-equations.jpg)

### Equation code is loaded like MilkDrop

In projectM, a compile error in *any* equation block aborts the whole preset. Upstream 4.2 refuses to load `161.milk` (`[PerFrameContext] Could not compile per-frame code: syntax error`).

MilkDrop 2's `CState::StripLinefeedCharsAndComments` and `CState::RecompileExpressions` (`state.cpp`) join numbered lines, strip comments and *leave out* a block that still fails to compile.

ProjectM TV leaves code that the evaluator accepts untouched. It retries rejected code once in MilkDrop's form: numbered records joined, `//` and `\\` comments removed, and a `;` inside parentheses with no following operand read as a space (as NS-EEL does). A block that still fails is left out:

- failed preset init leaves `q` variables at 0;
- failed wave/shape init leaves `t` variables at 0;
- failed per-frame, per-pixel or per-point code does not run.

Only a *parse* error in the file fails the load. Each omission is logged as `Preset code left out (<preset>): <reason> (line N, column M)`. In the source inventory, 62 bundled presets had raw equation code that projectM rejected.

### Shader samplers and random textures

- `sampler_state` blocks no longer break the shader. projectM stripped them only from a search copy, so `shader_body` was replaced at the wrong offset and the stage fell back to a default shader (51 bundled presets, for example `ORB - Arctic Chill`). The block fields are still ignored, as in projectM: the sampler *name* prefix chooses filtering and wrap.
- Warp texture unit 0 is reserved for the unqualified main sampler, so named point/clamp/wrap aliases keep their requested modes.
- Each random-texture alias from `rand00` to `rand15` gets its requested sampler mode and filename filter (`pc_rand00_red`), and the emitted short alias binds the same texture unit. ProjectM TV also keeps one image per slot for the whole preset load, shared by the warp and composite shaders and kept across shader reloads. MilkDrop 2 does not share them: it chooses separately for each shader (`plugin.cpp:2927`). See [Textures](../authoring/textures.md#random-textures-rand00-to-rand15).

### Rendering state

- Allocating blur textures unbinds the read and draw targets. projectM saved the framebuffer bindings *after* allocation, so when a warp shader sampled blur, the waves and borders drawn next went to framebuffer 0. Witness: `midgitstraights of majillaen - featy sweet.milk`. On Mali the error is silent, because framebuffer 0 is a valid target.
- Fresh feedback starts as transparent black instead of undefined memory.
- A resize keeps history: old colour contents are scaled into the new textures, so a resolution change does not restart every feedback preset.

### Resolution independence and Native trails

0001 also adds quad lines, reference-scaled blur and wave counts, virtual `texsize` and Native trails. These address the resolution-scaling part of projectM issue [#682](https://github.com/projectM-visualizer/projectm/issues/682); the round joins and caps it suggests are not implemented. [Rendering MilkDrop at 4K](resolution.md) explains them.

### TV performance work

The patch also carries program-binary and translated-GLSL caches for background prewarming, batched custom-shape uploads, a texture pool, an outgoing-preset frame divisor for blends, and tile-GPU framebuffer invalidation; see [How a frame reaches your TV](pipeline.md). The historical speedups were measured on the 4.1.7 engine and are not claimed for 4.2.

### GLES 3.0

Unmodified upstream at the pin requires GLES 3.2. 0001 admits GLES 3.0, which most TV boxes provide. Upstream master, as observed at `e98fca85`, has since made the same change.

## 0002 — HLSL compatibility and exact float literals

MilkDrop 2 compiled preset shaders with Microsoft's HLSL compiler. projectM translates them to GLSL, and a translation failure silently replaces the authored shader with a default one, so the preset looks completely different.

![Flexi - madness portal: red disc without 0002, authored yellow/blue composite with it](../images/patches/0002-clear-original.jpg)

`Flexi - madness portal.milk` becomes a plain red disc when its composite cannot translate, because it declares a local variable named `sample`. With 0002 the authored yellow and blue composite renders. Removing only 0002 changes 120 of 120 frames.

| What MilkDrop's compiler accepted | projectM before | ProjectM TV |
|---|---|---|
| Writing to a uniform inside a shader (`q18 = 1;`, `time *= 0.4;`) | Uninitialized local copy per function: other components and other functions read garbage (426 translated shaders) | One global copy per assigned uniform, initialized from the uniform at the start of `main()` |
| Flat array initializers `const float4 samples[5] = {…20 values…}` | Emitted as one `vec4[]` of 20 scalars, rejected by GLSL (56 bundled presets) | Grouped into element constructors; ambiguous layouts fail loudly instead of being guessed |
| A local named `sample`; `#define` macros; `(float2(x,y)).x` | Parse failure or changed precedence (16 bundled witnesses) | Contextual identifiers, token-replacement macros with authored spacing, full postfix parsing |
| Plain uninitialized globals (`float mus;`) | Undefined GLSL globals | External inputs that read 0 (the D3D9 compiler treated them as constants) |
| Float literals such as `4194304.0` | Printed with 6 significant digits (`4.1943e+06` = 4194300) | Exact float32 round trip; nonfinite literals fail the stage instead of becoming an identifier named `inf` |

In an earlier corpus pass over 15,576 authored shaders, historical patches 0030 to 0032 (now split between 0001 and 0002) made 102 more shaders compile and lost none.

## 0003 — Evaluator: lone dot and per-thread random

![Synthetic lone-dot fixture: upstream rejects it, without 0003 the block is dropped, with 0003 it runs](../images/patches/0003-lone-dot-v2.jpg)

NS-EEL accepts a lone `.` as a number (0). projectm-eval requires a digit, so `zoom=zoom+.10*sin(rad+.+15.15)` is a syntax error. Upstream rejects the Stahlregen *funky Blur* presets entirely. With 0001 alone their per-pixel block is dropped; removing only 0003 changes 120 of 120 frames of the unchanged preset. The image uses a synthetic fixture in which the dropped block changes the wave colour, which is easier to see. With 0003 the block runs as on MilkDrop. Seven bundled presets use the construction.

The evaluator's Mersenne Twister state for `rand()` was process-wide. ProjectM TV compiles upcoming presets on a background thread, so that work could advance the live preset's random stream. Each thread now has its own fixed-seed stream; the algorithm is unchanged.

## 0004 — Textured shapes sample with wrap and bilinear filtering

![widest swing.milk with and without 0004](../images/patches/0004-sampler.jpg)

In projectM, a custom shape with `textured=1` bound the main texture but inherited whatever sampler object was left on unit 0 (clamp, or nearest after the first instance).

MilkDrop 2 restores wrap/linear sampler state after the warp shader (`RestoreShaderParams`). On frames where it computes blur levels, the blur passes then set unit 0 back to clamp (`milkdropfs.cpp:1611`), and nothing resets it before `DrawCustomShapes()`. MilkDrop's textured shapes therefore wrap on frames without blur and clamp on frames with blur.

ProjectM TV gives every main-textured fill its own repeat/linear sampler, including geometry replayed for Native trails. That removes projectM's unpredictable nearest/clamp mix, but for presets that use blur it wraps where MilkDrop 2 clamps. Removing only 0004 changes 119 of 120 frames of `widest swing.milk`.

## 0005 — Blur ranges that cannot collapse

![Julia fractal Jelly with a collapsed and a valid blur range](../images/patches/0005-clear-original.jpg)

`blur1_min`…`blur3_max` define the colour range stored in each blur texture. MilkDrop 2's `CPlugin::GetSafeBlurMinMax` (`milkdropfs.cpp` 1551-1583) tries to push a too-narrow interval (`max − min < 0.1`) apart, but a typo sets *both* bounds to `avg − 0.05`, collapsing it. projectM reproduces the collapse, and the decode divides by zero.

ProjectM TV expands the upper bound upward, keeps the clamp-then-expand order, and falls back to a coherent 0 to 1 range for nonfinite or unrepresentable inputs. Where MilkDrop produced a degenerate blur, this deliberately differs from MilkDrop 2. `flexi - a julia fractal for hexcollie embossed (Jelly)` sets blur3 to 0.49-0.52 after blur2 0.78-0.91. Without 0005 it is darker, with altered embossing (frame 59 MAE 38.5). For other witnesses, such as `Cope - The Cloud`, the repair changes nothing visible.

## 0006 — Negative zoom mirrors

![Hexcollie - This is where we begin stripped with and without 0006](../images/patches/0006-zoom.jpg)

MilkDrop 2 computes the zoom on the CPU: `powf(fZoom, powf(fZoomExp, rad*2-1))` (`milkdropfs.cpp` 1877). With `zoomexp = 1`, a negative zoom stays negative and reflects the image through the warp centre. projectM evaluates `pow` in GLSL, which is undefined for a negative base; the witness gets 3,234 NaN UV components per frame. Patch 0006 uses the signed value when the authored exponent is exactly 1. [0015](#0015-negative-warp-powers-use-milkdrop-cpu-maths) extends the CPU calculation to other negative nested powers; fractional-domain appearance remains unresolved.

## 0007 — Per-frame waveform controls

![Hexcollie wormhole2 with and without live wave_mode](../images/patches/0007-wormhole-visible.jpg)

projectM read `wave_mode`, `wave_usedots`, `wave_thick` and `wave_additive` from the preset file only and ignored per-frame changes. MilkDrop 2 reads the evaluated value every frame: `(int)(*var_pf_wave_mode) % NUM_WAVES` (`milkdropfs.cpp` 2852). ProjectM TV consumes the evaluated values and rebuilds the wave when the mode changes. The witness sets `wave_mode=q8%7` per frame; without 0007, 135,296 of 147,456 pixels differ at frame 29.

projectM has 16 waveform modes, MilkDrop 2 has 8. The value wraps modulo 16 here and modulo 8 on MilkDrop 2, so `wave_mode=9` is mode 1 on Windows and projectM's mode 9 here. Negative remainders draw nothing.

## 0008 — Per-frame display filters

![Synthetic equation-only invert control](../images/patches/0008-display-invert.jpg)

`gamma`, `echo_alpha`, `echo_zoom`, `echo_orient`, `brighten`, `darken`, `solarize` and `invert` are per-frame variables in MilkDrop 2 (`milkdropfs.cpp` 527-540). projectM used only the preset file's values and allocated the filters only when the file's default was on, so a preset could never switch one on from code. ProjectM TV reads them every frame, with MilkDrop's order (brighten, darken, solarize, invert), clamps (gamma 0 to 8, echo zoom 0.001 to 1000) and echo orientation modulo 4.

MilkDrop 2 uses the evaluated values for presets without a composite shader (composite version 0). For shader-version presets without `comp_` code it bakes the file values into a generated shader; ProjectM TV uses the evaluated values for every built-in composite. Neither applies these effects with a custom composite shader. The tested original witness (`idiot - Forty Six and 2`) did not activate the difference under the proof audio, so the image shows a synthetic equation-only control.

## 0009 — Premultiplied user textures

![rand tritex preset with and without premultiplication](../images/patches/0009-visible.jpg)

ProjectM TV's releases based on projectM 4.1.7 loaded images with SOIL2 and premultiplied colour by alpha. 4.2 switched to stb_image without premultiplying, so presets that sample transparent textures changed. In feedback presets, even a 1-level byte difference grows: frame 29 of the witness shows a mean 3.66 and a maximum 201 channel difference. ProjectM TV restores the released bytes, `(rgb·alpha + 128) >> 8` per channel. Whether MilkDrop 2's D3DX loader premultiplied is not verified.

## 0010 — Each preset keeps its own textures

![Aurora SOL/LUNA packs: upstream swaps the outgoing emblem; patched keeps it](../images/patches/0010-aurora-ownership.jpg)

Here ProjectM TV Engine deliberately goes beyond MilkDrop 2. MilkDrop read every texture from one folder, so the question of *which* folder a preset's images come from never arose. [Custom packs](../custom-packs.md) raise that question: a pack's presets prefer the pack's own images, with the bundled textures as fallback. Upstream projectM has one global texture search path, and changing it reloads every texture. During a blend from pack A to pack B, a same-named image in the outgoing preset would therefore switch to B's file.

With 0010, each preset keeps the texture paths it was loaded with until it retires. This per-preset lookup contract is an addition for a situation MilkDrop did not support. In the test, two packs created with the predictor tools each use the same image name. Upstream swaps SOL's orange emblem for LUNA's blue at frame 20; ProjectM TV keeps SOL's.

## 0011 — Huge rotation values

![Rotation witness: upstream fails to load; ProjectM TV renders](../images/patches/0011-rotation.jpg)

MilkDrop 2 converts `rot` to float and computes `sinf`/`cosf` on the CPU (`milkdropfs.cpp` 1813, 1905-1906). projectM computes them in the vertex shader. On the observed GLES driver, `sin`/`cos` of ±10,000,000 both returned 0, collapsing the feedback to the rotation centre. ProjectM TV computes them on the CPU after float conversion, valid up to `FLT_MAX`. The witness uses per-pixel `rot=10000000`; upstream additionally fails to load it, because of a shape equation that 0001 handles. Large-argument trig inside your *own* shader code is still driver-dependent.

## 0012 — Tiny shapes land on the right pixels

![Green machine btbam: pink/brown wedges without 0012, green/yellow structure with it](../images/patches/0012-visible-original.jpg)

Direct3D 9 samples integer pixel centres; OpenGL samples half-integers. MilkDrop 2's `DrawCustomShapes` (`milkdropfs.cpp` 2298) places shapes in D3D9 coordinates, so a shape with `rad=.002` at `x=y=.5` covers one pixel under the Direct3D 9 rasterization rules and zero pixels in projectM. Feedback presets that seed their image with many tiny shapes lose them entirely. ProjectM TV shifts shape fills and outlines by half a destination pixel per render target. Equations, radii, colours and UVs are unchanged. In `amandio c - the green machine 2 skin lard bone beacon nz+ btbam covers sepultura.milk`, 34,365 of 36,864 pixels differ by more than 16 at frame 59.

## 0013 — Composite reads the exact feedback texel

![DemonLD Toxic water with and without the composite half-texel bias](../images/patches/0013-visible-original.jpg)

In MilkDrop 2, `plugin.cpp` shifts the composite grid by −½ pixel (the D3D9 convention) and keeps the UVs. projectM's GL mesh is already unbiased, yet it *also* added +½ texel to the UVs, so every `tex2D(sampler_main, uv)` in a custom composite read between four texels. That is a hidden 2×2 blur: a single 255 feedback texel became four pixels of 64. ProjectM TV removes the redundant bias. In `DemonLD_-_Toxic_water_diffusion …` the bugged window was about 18% brighter at frame 59 (mean luma 57.0 against 48.4). The fix removes the blur, which does not always darken a preset.

## 0014 — Legacy colour shading and mode-1 spirals

The patch corrects three differences in the classic (non-shader) rendering path, found while investigating why a preset looked darker than expected (`milkdropfs.cpp` 2927-2946, 3359-3365, 4117-4144):

| Stage | MilkDrop 2 | projectM | ProjectM TV |
|---|---|---|---|
| Legacy hue shading | No tint when `fShader` ≤ 0.001; otherwise the animated corner colours are mixed with white by `fShader` | Always the full animated tint | Respects the authored amount and threshold |
| Mode-1 waveform opacity | Alpha × 1.25, then volume modulation and clamp | Multiplier missing | Multiplier restored before the clamp |
| Mode-1 waveform shape | Open line strip | Closed loop with an extra segment | Open, as in MilkDrop |

The witness, `BrainStain- boiling-mix2(redi jedi full carb mix).milk`, can still look sparse and dark after the fix: its video echo shows only a zoomed crop of the image and its darken filter squares the colours, as authored. The investigation also showed that the source predictor shared these mistaken assumptions, so agreement with the predictor is not proof of MilkDrop behaviour. [Evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/brainstain-dark-output/README.md).

## Fixed upstream, dropped from the series

Rebasing onto 4.2 master retired nine historical patches because upstream had already made the same fix:

| Historical | Fix | Upstream |
|---|---|---|
| 0001 | Plasma transition float overflow | `0227b7a61` (issue #872) |
| 0008 | HLSL float remainder types and operator precedence | PR [#1031](https://github.com/projectM-visualizer/projectm/pull/1031), contributed from this project |
| 0017 | `projectm_pcm_get_max_samples()` returns 576 | PR #1032 |
| 0018 | Parenthesized constructor expressions | PR #948 |
| 0019 | Quadratic number scanning in the HLSL parser | PR #1030 |
| 0020 | projectm-eval 1.0.7: NS-EEL's 0.00001 comparison/division tolerance | evaluator `22fb0cfd` |
| 0021 | Self-referencing shader macro infinite loop | `c1469f0e5` |
| 0022 | Custom waveform out-of-bounds read | in the pin |
| 0027 | Preset exception diagnostics | in the pin |

projectM v4.1.8 (tagged 2026-10-06) backports most of these parser and waveform fixes, but not the plasma transition fix. It also uses a newer evaluator commit (`e8c311e`, a float-scanner fix) that our pin does not include; its visible impact is unverified.

## 0015 — Negative warp powers use MilkDrop CPU maths

![Defined negative nested-unit, square and cube controls before and after](../images/patches/0015-negative-power.png)

MilkDrop 2 computes `powf(zoom, powf(zoomexp, rad*2-1))` on the CPU after float conversion (`milkdropfs.cpp:1877–1938`). A nested integer exponent can have a finite signed or squared/cubed result even when the authored `zoomexp` is not one. On the observed GLES backend, the old GPU branch returns NaN for these defined controls because GLSL does not define any negative-base `pow`. ProjectM TV prepares the negative result on CPU and supplies it through an instance-owned float buffer at attribute 9. Positive zoom keeps its shader path; raw equation values and prepared-mesh replay are unchanged.

These separate proof images use full published v2.3.25 and candidate AARs at 256×144, 48×32 mesh, 30 frozen frames and the same mono PCM/clock/seed on API 34/Apple M4 Pro/GLES3. Named diagnostic copies activate nested exponents 1/2/3 at selected vertices; constant blue 64 verifies their custom warp/composite programs. They are not the 120-frame single-patch ablations described above. Direct UV controls fail before/pass after, and real-mesh controls check values, NaNs, resize and replay. The buffer adds four bytes per vertex and nonunit negative vertices need two CPU powers; performance is unmeasured.

The exact Great Tulip Majesty (txtr wrap) witness has 33 fractional-domain NaNs per frame in both the original CPU expression and the GPU path. Its 30-frame original/repeat AAR replay is byte-identical after this correction. NaN and Inf are retained, with no epsilon or absolute-value substitution. Observations of invalid interpolation and sampling are backend-bound, so the source predictor's unresolved guard is still appropriate. [Source, IEEE bits and capture evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/tulip-negative-zoom-power/README.md).

## 0016 — Cached static warp uploads

Static warp coordinates, radius/angle and topology are uploaded only when their size, aspect or producer changes. Dynamic attributes and equations still update each frame. This preserves the released mesh-cache fix and prepared replay; see the [cache evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/mesh-init-cache/README.md).

## 0017 — Built-in wave opacity

MilkDrop multiplies mode-adjusted alpha by the volume ramp before clamping. Mode 3 replaces its starting alpha with the canvas coefficient times 1.3 × treb²; mode 1 keeps its 1.25 multiplier. A final alpha below .004 skips the draw. Existing Native/reference styles are unchanged. [I17 evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/milkdrop-audit-repairs/I17/README.md).

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I17-4k-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I17-4k-upstream.png" alt="Happening.milk — Before · upstream master" width="3840" height="2160" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I17-4k-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I17-4k-patched.png" alt="Happening.milk — After · ProjectM TV" width="3840" height="2160" loading="lazy"></a></div></div>
<figcaption><strong>Happening.milk</strong> · 3840×2160, frame 239 at 30 Hz.<br>Before, many streaks wash toward white. After, green, pink and blue remain distinct. This full-engine comparison also includes the legacy warp repairs.</figcaption>
</figure>

## 0018 — Custom wave input windows

Valid custom oscilloscope windows are centered in the 480-sample input, and the channels shift in opposite directions by sep/2. Invalid original windows keep the safe prefix fallback, and oversized requests are still resampled. Spectrum inputs and Native prepared replay are unchanged. [I08 evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/milkdrop-audit-repairs/I08/README.md).

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I08-4k-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I08-4k-upstream.png" alt="Mig_304 - geiss remix 2.milk — Before · upstream master" width="3840" height="2160" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I08-4k-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I08-4k-patched.png" alt="Mig_304 - geiss remix 2.milk — After · ProjectM TV" width="3840" height="2160" loading="lazy"></a></div></div>
<div class="patch-panels patch-zooms"><div class="patch-panel"><strong>Before · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I08-4k-upstream.png" style="--crop-ratio:1152/864;--image-width:333.333333333%;--image-left:-116.666666667%;--image-top:-75.000000000%;" aria-label="Open original full-resolution Before · upstream master frame for zoom"><img src="../../images/patches/audit/I08-4k-upstream.png" alt="Matched crop of Mig_304 - geiss remix 2.milk — Before · same zoom" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I08-4k-patched.png" style="--crop-ratio:1152/864;--image-width:333.333333333%;--image-left:-116.666666667%;--image-top:-75.000000000%;" aria-label="Open original full-resolution After · ProjectM TV frame for zoom"><img src="../../images/patches/audit/I08-4k-patched.png" alt="Matched crop of Mig_304 - geiss remix 2.milk — After · same zoom" loading="lazy"></a></div></div>
<figcaption><strong>Mig_304 - geiss remix 2.milk</strong> · 3840×2160, frame 239 at 30 Hz.<br>The centered, separated audio windows change the small blue custom-wave trace. The matched zoom makes its changed geometry easier to inspect. Zoom rectangle: (1344, 648), 1152×864 source pixels; identical crop and nearest-neighbour display, with no brightness adjustment.</figcaption>
</figure>

## 0019 — Gamma-only pass count

Gamma-only output uses MilkDrop's original .001 pass-count epsilon; echo redraws keep .0001. At the admitted boundary, I31 removes a fullscreen gamma draw and the checked image stays the same. Float diffuse precision, live tint and echo policies are unchanged.

The proven benefit is lower rendering cost with unchanged checked images. An isolated 3840×2160 benchmark on the Apple M4 Pro compares the full engine with its exact 0019 ablation. In the Standard profile:

| Measurement | Without I31 | With I31 | Reduction |
|---|---:|---:|---:|
| Gamma draws per frame | 3 | 2 | One fullscreen draw |
| GPU elapsed time | 2.307 ms | 1.847 ms | 19.9% |
| Completed-frame time | 2.704 ms | 2.241 ms | 17.1% |

All eight balanced blocks favor I31. The gamma-2.0 inactive control keeps two draws, and its GPU/completed-frame intervals include zero change. Separate frames 119, 239 and 479 are RGB-identical across roles and repeats in both tested profiles. These are rendering-cost measurements, not app FPS. Gains on a TV depend on its bottlenecks and are unmeasured. [Full benefit proof and replay](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/i31-benefit/README.md) · [Historical I31 evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/milkdrop-audit-repairs/I31/README.md).

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I31-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I31-upstream.png" alt="suksma - type o negative - world coming down.milk — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I31-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I31-patched.png" alt="suksma - type o negative - world coming down.milk — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<figcaption><strong>suksma - type o negative - world coming down.milk</strong> · 1280×720, frame 119 at 30 Hz.<br>This full upstream-master/main pair illustrates near-unchanged appearance and includes other patches. The separate single-patch 4K benchmark above proves a rendering-cost benefit; it does not depend on a visible improvement in this picture.</figcaption>
</figure>

## 0020 — Named EEL constants

Named pi/e/phi decimals enter the double evaluator without intermediate float rounding. The original abbreviated e/phi decimals, later geometry/shader casts and RNG are unchanged. [I09 evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/milkdrop-audit-repairs/I09/README.md).

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I09-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I09-upstream.png" alt="audit pi precision.milk (synthetic) — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I09-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I09-patched.png" alt="audit pi precision.milk (synthetic) — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<figcaption><strong>audit pi precision.milk (synthetic)</strong> · 1280×720, frame 239 at 30 Hz.<br>This diagnostic deliberately amplifies the float-rounding error in $pi. Upstream makes an oversized red border; the double input restores the narrow border requested by the expression.</figcaption>
</figure>

## 0021 — Original equation inputs

Presets keep the spatial scale and custom-wave colour rhythm their equations describe. The repair restores aspect compensation in per-pixel equations and gives custom-wave points their own fresh host clock, even when main equations slow their own time. [I05/I06 evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/milkdrop-audit-repairs/README.md).









<figure class="patch-comparison patch-causal" data-witness="crush">
<div class="patch-panels"><div class="patch-panel"><strong>Only 0021 disabled</strong><a href="../../images/patches/clarity/crush-without-0021.png" aria-label="Open unchanged 4K crush frame, Only 0021 disabled"><img src="../../images/patches/clarity/crush-without-0021-crop.png" alt="crush: Only 0021 disabled, matched close-up" width="1100" height="1050" class="patch-detail" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/crush-full.png" aria-label="Open unchanged 4K crush frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/crush-full-crop.png" alt="crush: ProjectM TV · fix enabled, matched close-up" width="1100" height="1050" class="patch-detail" loading="lazy"></a></div></div>
<figcaption><strong>Flexi - crush ice 38.milk</strong><br>The central glow separates into readable loops on the right. The old input stretches the feedback differently; the fix restores the aspect compensation used by the preset.<br>Native 3840×2160, frame 239; matched 1100×1050 pixel crop at (1600, 600). Click either close-up for its original 4K frame. No exposure or colour adjustment.</figcaption>
<details><summary>See both full 4K frames</summary>
<div class="patch-panels"><div class="patch-panel"><strong>Only 0021 disabled</strong><a href="../../images/patches/clarity/crush-without-0021.png" aria-label="Open unchanged 4K crush frame, Only 0021 disabled"><img src="../../images/patches/clarity/crush-without-0021.png" alt="crush: Only 0021 disabled, full frame" width="3840" height="2160" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/crush-full.png" aria-label="Open unchanged 4K crush frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/crush-full.png" alt="crush: ProjectM TV · fix enabled, full frame" width="3840" height="2160" loading="lazy"></a></div></div>
</details>
</figure>

<figure class="patch-comparison patch-causal" data-witness="carnival">
<div class="patch-panels"><div class="patch-panel"><strong>Only 0021 disabled</strong><a href="../../images/patches/clarity/carnival-without-0021.png" aria-label="Open unchanged 4K carnival frame, Only 0021 disabled"><img src="../../images/patches/clarity/carnival-without-0021-crop.png" alt="carnival: Only 0021 disabled, matched close-up" width="1100" height="1000" class="patch-detail" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/carnival-full.png" aria-label="Open unchanged 4K carnival frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/carnival-full-crop.png" alt="carnival: ProjectM TV · fix enabled, matched close-up" width="1100" height="1000" class="patch-detail" loading="lazy"></a></div></div>
<figcaption><strong>Shreyas - Carnival loavthephysyq.milk</strong><br>Look at the fine coloured pattern across the centre. Custom-wave colours follow their own host clock rather than inheriting the slowed main-equation clock.<br>Native 3840×2160, frame 239; matched 1100×1000 pixel crop at (1250, 650). Click either close-up for its original 4K frame. No exposure or colour adjustment.</figcaption>
<details><summary>See both full 4K frames</summary>
<div class="patch-panels"><div class="patch-panel"><strong>Only 0021 disabled</strong><a href="../../images/patches/clarity/carnival-without-0021.png" aria-label="Open unchanged 4K carnival frame, Only 0021 disabled"><img src="../../images/patches/clarity/carnival-without-0021.png" alt="carnival: Only 0021 disabled, full frame" width="3840" height="2160" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/carnival-full.png" aria-label="Open unchanged 4K carnival frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/carnival-full.png" alt="carnival: ProjectM TV · fix enabled, full frame" width="3840" height="2160" loading="lazy"></a></div></div>
</details>
</figure>

<details class="patch-context"><summary>Earlier upstream-master comparison and diagnostic controls</summary>
<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I05-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I05-upstream.png" alt="163.milk — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I05-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I05-patched.png" alt="163.milk — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<figcaption><strong>163.milk</strong> · 1280×720, frame 300 at 30 Hz.<br>Inverse aspect inputs change the feedback displacement in this original. The separate synthetic drift example below makes the equation-input effect easier to see.</figcaption>
</figure>

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I05-control-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I05-control-upstream.png" alt="audit inverse aspect.milk (synthetic) — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I05-control-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I05-control-patched.png" alt="audit inverse aspect.milk (synthetic) — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<div class="patch-panels patch-zooms"><div class="patch-panel"><strong>Before · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I05-control-upstream.png" style="--crop-ratio:600/300;--image-width:213.333333333%;--image-left:-33.333333333%;--image-top:-75.000000000%;" aria-label="Open original full-resolution Before · upstream master frame for zoom"><img src="../../images/patches/audit/I05-control-upstream.png" alt="Matched crop of audit inverse aspect.milk (synthetic) — Before · same zoom" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I05-control-patched.png" style="--crop-ratio:600/300;--image-width:213.333333333%;--image-left:-33.333333333%;--image-top:-75.000000000%;" aria-label="Open original full-resolution After · ProjectM TV frame for zoom"><img src="../../images/patches/audit/I05-control-patched.png" alt="Matched crop of audit inverse aspect.milk (synthetic) — After · same zoom" loading="lazy"></a></div></div>
<figcaption><strong>audit inverse aspect.milk (synthetic)</strong> · 1280×720, frame 239 at 30 Hz.<br>Synthetic inverse-aspect drift: the same red square is displaced using dx=aspecty/10. Zoom rectangle: (200, 225), 600×300 source pixels; identical crop and nearest-neighbour display, with no brightness adjustment.</figcaption>
</figure>

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I06-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I06-upstream.png" alt="Shreyas - Carnival loavthephysyq.milk — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I06-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I06-patched.png" alt="Shreyas - Carnival loavthephysyq.milk — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<figcaption><strong>Shreyas - Carnival loavthephysyq.milk</strong> · 1280×720, frame 479 at 30 Hz.<br>Fresh host time changes the colour pattern in the custom waves. It does not mean every preset should become brighter or darker.</figcaption>
</figure>

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I06-control-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I06-control-upstream.png" alt="audit fresh wave time.milk (synthetic) — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I06-control-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I06-control-patched.png" alt="audit fresh wave time.milk (synthetic) — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<div class="patch-panels patch-zooms"><div class="patch-panel"><strong>Before · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I06-control-upstream.png" style="--crop-ratio:250/320;--image-width:512.000000000%;--image-left:-90.000000000%;--image-top:-62.500000000%;" aria-label="Open original full-resolution Before · upstream master frame for zoom"><img src="../../images/patches/audit/I06-control-upstream.png" alt="Matched crop of audit fresh wave time.milk (synthetic) — Before · same zoom" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I06-control-patched.png" style="--crop-ratio:250/320;--image-width:512.000000000%;--image-left:-90.000000000%;--image-top:-62.500000000%;" aria-label="Open original full-resolution After · ProjectM TV frame for zoom"><img src="../../images/patches/audit/I06-control-patched.png" alt="Matched crop of audit fresh wave time.milk (synthetic) — After · same zoom" loading="lazy"></a></div></div>
<figcaption><strong>audit fresh wave time.milk (synthetic)</strong> · 1280×720, frame 239 at 30 Hz.<br>Synthetic fresh-time input: main time is slowed to one tenth; wave-point time must still use the host clock. Zoom rectangle: (225, 200), 250×320 source pixels; identical crop and nearest-neighbour display, with no brightness adjustment.</figcaption>
</figure>

</details>

## 0022 — Negative odd echo orientation

Finite negative odd echo orientations flip horizontally using the original signed nonzero-remainder test. Modulo 4, vertical flip, zoom/mix, tint and gamma are unchanged. [I29 evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/milkdrop-audit-repairs/I29/README.md).

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I29-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I29-upstream.png" alt="audit negative echo.milk (synthetic) — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I29-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I29-patched.png" alt="audit negative echo.milk (synthetic) — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<figcaption><strong>audit negative echo.milk (synthetic)</strong> · 1280×720, frame 239 at 30 Hz.<br>Negative odd echo orientation moves the orange square from the left to the right by applying the authored horizontal mirror.</figcaption>
</figure>

## 0023 — Legacy oscillator Y

Legacy feedback curls in the direction described by MilkDrop's original coordinate system. The correction restores that direction in the built-in and fallback warp; custom warp shaders keep their existing coordinates. [I10 evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/milkdrop-audit-repairs/I10/README.md).





<figure class="patch-comparison patch-causal" data-witness="swirl">
<div class="patch-panels"><div class="patch-panel"><strong>Only 0023 disabled</strong><a href="../../images/patches/clarity/swirl-without-0023.png" aria-label="Open unchanged 4K swirl frame, Only 0023 disabled"><img src="../../images/patches/clarity/swirl-without-0023-crop.png" alt="swirl: Only 0023 disabled, matched close-up" width="1200" height="1300" class="patch-detail" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/swirl-full.png" aria-label="Open unchanged 4K swirl frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/swirl-full-crop.png" alt="swirl: ProjectM TV · fix enabled, matched close-up" width="1200" height="1300" class="patch-detail" loading="lazy"></a></div></div>
<figcaption><strong>Geiss - Mega Swirl 2 (2).milk</strong><br>The central spiral builds a denser curl with distinct strands on the right. Restoring the original oscillator direction changes how the existing strokes accumulate; their authored warp strength and draw count stay the same.<br>Native 3840×2160, frame 239; matched 1200×1300 pixel crop at (1200, 500). Click either close-up for its original 4K frame. No exposure or colour adjustment.</figcaption>
<details><summary>See both full 4K frames</summary>
<div class="patch-panels"><div class="patch-panel"><strong>Only 0023 disabled</strong><a href="../../images/patches/clarity/swirl-without-0023.png" aria-label="Open unchanged 4K swirl frame, Only 0023 disabled"><img src="../../images/patches/clarity/swirl-without-0023.png" alt="swirl: Only 0023 disabled, full frame" width="3840" height="2160" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/swirl-full.png" aria-label="Open unchanged 4K swirl frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/swirl-full.png" alt="swirl: ProjectM TV · fix enabled, full frame" width="3840" height="2160" loading="lazy"></a></div></div>
</details>
</figure>

<details class="patch-context"><summary>Earlier upstream-master comparison and diagnostic controls</summary>
<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I10-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I10-upstream.png" alt="BrainStain-fish on.milk — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I10-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I10-patched.png" alt="BrainStain-fish on.milk — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<figcaption><strong>BrainStain-fish on.milk</strong> · 1280×720, frame 150 at 30 Hz.<br>The legacy oscillator uses the original physical Y direction, changing the curved feedback geometry. Custom warp-shader coordinates keep their separate contract.</figcaption>
</figure>

</details>

## 0024 — Legacy mesh diagonal

Legacy warp triangles use the original physical diagonal. Custom topology and same-size static upload caching are unchanged. [I11 evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/milkdrop-audit-repairs/I11/README.md).

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I11-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I11-upstream.png" alt="07.milk — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I11-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I11-patched.png" alt="07.milk — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<figcaption><strong>07.milk</strong> · 1280×720, frame 150 at 30 Hz.<br>The physical triangle diagonal changes interpolation within the legacy warp mesh. The original radial feedback makes that difference accumulate into a different pattern.</figcaption>
</figure>

## 0025 — Legacy per-pixel traversal

Legacy stateful per-pixel equations visit physical rows in the original order. Custom traversal and once-only prepared replay are unchanged. [I12 evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/milkdrop-audit-repairs/I12/README.md).

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I12-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I12-upstream.png" alt="audit legacy physical traversal.milk (synthetic) — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I12-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I12-patched.png" alt="audit legacy physical traversal.milk (synthetic) — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<figcaption><strong>audit legacy physical traversal.milk (synthetic)</strong> · 1280×720, frame 239 at 30 Hz.<br>The equation increments q1 at each mesh point. Restoring physical row order changes its coloured shear; this control makes stateful traversal visible.</figcaption>
</figure>

## 0026 — Legacy angle seam

At the exact negative-X axis, legacy equation angles retain the original signed-zero atan2 seam. Off-axis and custom inputs are unchanged. Independent CPU trig and actual GPU controls verify the consequence. [I13 evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/milkdrop-audit-repairs/I13/README.md).

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I13-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I13-upstream.png" alt="Liquido.milk — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I13-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I13-patched.png" alt="Liquido.milk — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<div class="patch-panels patch-zooms"><div class="patch-panel"><strong>Before · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I13-upstream.png" style="--crop-ratio:640/288;--image-width:200.000000000%;--image-left:0.000000000%;--image-top:-75.000000000%;" aria-label="Open original full-resolution Before · upstream master frame for zoom"><img src="../../images/patches/audit/I13-upstream.png" alt="Matched crop of Liquido.milk — Before · same zoom" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I13-patched.png" style="--crop-ratio:640/288;--image-width:200.000000000%;--image-left:0.000000000%;--image-top:-75.000000000%;" aria-label="Open original full-resolution After · ProjectM TV frame for zoom"><img src="../../images/patches/audit/I13-patched.png" alt="Matched crop of Liquido.milk — After · same zoom" loading="lazy"></a></div></div>
<figcaption><strong>Liquido.milk</strong> · 1280×720, frame 180 at 30 Hz.<br>This original branches on ang at the exact left axis. The original seam value selects the intended branch; feedback then propagates the changed deformation. Zoom rectangle: (0, 216), 640×288 source pixels; identical crop and nearest-neighbour display, with no brightness adjustment.</figcaption>
</figure>

## 0027 — Wave colour clamp

Local built-in wave RGB is clamped before nonzero brightening. Raw equation values and float colour/alpha submission are unchanged. A separate negative-darken activation is outside this repair. [I18 evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/milkdrop-audit-repairs/I18/README.md).

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I18-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I18-upstream.png" alt="Geiss - Blur Mix 3.milk — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I18-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I18-patched.png" alt="Geiss - Blur Mix 3.milk — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<div class="patch-panels patch-zooms"><div class="patch-panel"><strong>Before · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I18-upstream.png" style="--crop-ratio:1024/158;--image-width:125.000000000%;--image-left:-12.500000000%;--image-top:-182.278481013%;" aria-label="Open original full-resolution Before · upstream master frame for zoom"><img src="../../images/patches/audit/I18-upstream.png" alt="Matched crop of Geiss - Blur Mix 3.milk — Before · same zoom" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I18-patched.png" style="--crop-ratio:1024/158;--image-width:125.000000000%;--image-left:-12.500000000%;--image-top:-182.278481013%;" aria-label="Open original full-resolution After · ProjectM TV frame for zoom"><img src="../../images/patches/audit/I18-patched.png" alt="Matched crop of Geiss - Blur Mix 3.milk — After · same zoom" loading="lazy"></a></div></div>
<figcaption><strong>Geiss - Blur Mix 3.milk</strong> · 1280×720, frame 239 at 30 Hz.<br>The brightened built-in waveform uses clamped colour channels before normalization. Inspect the narrow central wave in the matched zoom; the full pair includes the other wave repairs too. Zoom rectangle: (128, 288), 1024×158 source pixels; identical crop and nearest-neighbour display, with no brightness adjustment.</figcaption>
</figure>

## 0028 — Border fan topology

Eight triangle indices restore the original border strip-fan coverage. Current float colour/alpha and Native rendering policies are unchanged. [M02 evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/milkdrop-audit-repairs/M02/README.md).



<figure class="patch-comparison patch-causal" data-witness="escape">
<div class="patch-panels"><div class="patch-panel"><strong>Only 0028 disabled</strong><a href="../../images/patches/clarity/escape-without-0028.png" aria-label="Open unchanged 4K escape frame, Only 0028 disabled"><img src="../../images/patches/clarity/escape-without-0028-crop.png" alt="escape: Only 0028 disabled, matched close-up" width="1100" height="750" class="patch-detail" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/escape-full.png" aria-label="Open unchanged 4K escape frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/escape-full-crop.png" alt="escape: ProjectM TV · fix enabled, matched close-up" width="1100" height="750" class="patch-detail" loading="lazy"></a></div></div>
<figcaption><strong>Dbleja - Escape (Red Mix).milk</strong><br>The crossed border bands now have the original strip-fan coverage. In the left image, one side pinches into a diagonal; the right retains the matching band around the centre. This is an unchanged bundled preset, not a synthetic shape.<br>Native 3840×2160, frame 0; matched 1100×750 pixel crop at (1400, 650). Click either close-up for its original 4K frame. No exposure or colour adjustment.</figcaption>
<details><summary>See both full 4K frames</summary>
<div class="patch-panels"><div class="patch-panel"><strong>Only 0028 disabled</strong><a href="../../images/patches/clarity/escape-without-0028.png" aria-label="Open unchanged 4K escape frame, Only 0028 disabled"><img src="../../images/patches/clarity/escape-without-0028.png" alt="escape: Only 0028 disabled, full frame" width="3840" height="2160" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/escape-full.png" aria-label="Open unchanged 4K escape frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/escape-full.png" alt="escape: ProjectM TV · fix enabled, full frame" width="3840" height="2160" loading="lazy"></a></div></div>
</details>
</figure>

<details class="patch-context"><summary>Earlier upstream-master comparison and diagnostic control</summary>
<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/M02-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/M02-upstream.png" alt="audit border inverted.milk (synthetic) — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/M02-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/M02-patched.png" alt="audit border inverted.milk (synthetic) — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<figcaption><strong>audit border inverted.milk (synthetic)</strong> · 1280×720, frame 239 at 30 Hz.<br>An intentionally oversized, translucent border exposes overlapping coverage. Restored strip-fan indices change that coverage. The neutral colour also reflects earlier patch 0014 honoring fShader=0; it is not caused by the border topology repair.</figcaption>
</figure>

</details>

## 0029 — Original line sample caps

Line modes 4/6/7 use their original raw sample budgets, capped by one third of the reference-equivalent width with a two-point safety floor. Native/reference scaling and extended modes are unchanged. The cap can substantially change feedback brightness, as in Royal 103. Brightness relative to the previous build does not by itself establish authored Windows appearance.

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I19-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I19-upstream.png" alt="$$$ Royal - Mashup (103).milk — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I19-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I19-patched.png" alt="$$$ Royal - Mashup (103).milk — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<figcaption><strong>$$$ Royal - Mashup (103).milk</strong> · 1280×720, frame 239 at 30 Hz.<br>At 1280×720, the original width-dependent cap changes submitted waveform geometry and this witness becomes brighter. That direction is not universal: the uncapped 4K pair below is nearly unchanged.</figcaption>
</figure>

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I19-4k-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I19-4k-upstream.png" alt="$$$ Royal - Mashup (103).milk — Before · upstream master" width="3840" height="2160" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I19-4k-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I19-4k-patched.png" alt="$$$ Royal - Mashup (103).milk — After · ProjectM TV" width="3840" height="2160" loading="lazy"></a></div></div>
<figcaption><strong>$$$ Royal - Mashup (103).milk</strong> · 3840×2160, frame 239 at 30 Hz.<br>The same original at 3840×2160 with actual-width sampling and TV feedback detail off. Both width budgets reach the full raw sample count, so the cap itself is inactive here.</figcaption>
</figure>

## 0030 — Discrete custom dots

The starfield keeps the points the preset actually authored. Dot mode no longer invents extra stars between those points; ordinary continuous lines still use smoothing. The close-up below includes three authored dots, so the removed extras are easy to pick out.





<figure class="patch-comparison patch-causal" data-witness="nebula">
<div class="patch-panels"><div class="patch-panel"><strong>Only 0030 disabled</strong><a href="../../images/patches/clarity/nebula-without-0030.png" aria-label="Open unchanged 4K nebula frame, Only 0030 disabled"><img src="../../images/patches/clarity/nebula-without-0030-crop.png" alt="nebula: Only 0030 disabled, matched close-up" width="128" height="128" class="patch-detail" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/nebula-full.png" aria-label="Open unchanged 4K nebula frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/nebula-full-crop.png" alt="nebula: ProjectM TV · fix enabled, matched close-up" width="128" height="128" class="patch-detail" loading="lazy"></a></div></div>
<figcaption><strong>phat + EoS - Bass_responce_Red_Movements_Disorienting nebula3.milk</strong><br>Three purple/white authored dots remain in both panels. The extra green/grey dots on the left disappear: they were invented by line interpolation. Dot mode now preserves the preset&#x27;s discrete star positions.<br>Native 3840×2160, frame 0; matched 128×128 pixel crop at (2560, 768). Click either close-up for its original 4K frame. No exposure or colour adjustment.</figcaption>
<details><summary>See both full 4K frames</summary>
<div class="patch-panels"><div class="patch-panel"><strong>Only 0030 disabled</strong><a href="../../images/patches/clarity/nebula-without-0030.png" aria-label="Open unchanged 4K nebula frame, Only 0030 disabled"><img src="../../images/patches/clarity/nebula-without-0030.png" alt="nebula: Only 0030 disabled, full frame" width="3840" height="2160" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/nebula-full.png" aria-label="Open unchanged 4K nebula frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/nebula-full.png" alt="nebula: ProjectM TV · fix enabled, full frame" width="3840" height="2160" loading="lazy"></a></div></div>
</details>
</figure>

<details class="patch-context"><summary>Earlier upstream-master comparison and diagnostic controls</summary>
<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I22-4k-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I22-4k-upstream.png" alt="phat + EoS - Bass_responce_Red_Movements_Disorienting nebula3.milk — Before · upstream master" width="3840" height="2160" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I22-4k-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I22-4k-patched.png" alt="phat + EoS - Bass_responce_Red_Movements_Disorienting nebula3.milk — After · ProjectM TV" width="3840" height="2160" loading="lazy"></a></div></div>
<figcaption><strong>phat + EoS - Bass_responce_Red_Movements_Disorienting nebula3.milk</strong> · 3840×2160, frame 239 at 30 Hz.<br>One of this preset’s four enabled custom waves describes 42 stars. Discrete dots retain authored samples instead of inserting line-interpolation dots. A synthetic zoom below isolates an extra dot that disappears.</figcaption>
</figure>

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I22-control-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I22-control-upstream.png" alt="audit followup dot audit dot ring.milk (synthetic) — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I22-control-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I22-control-patched.png" alt="audit followup dot audit dot ring.milk (synthetic) — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<div class="patch-panels patch-zooms"><div class="patch-panel"><strong>Before · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I22-control-upstream.png" style="--crop-ratio:40/40;--image-width:3200.000000000%;--image-left:-425.000000000%;--image-top:-850.000000000%;" aria-label="Open original full-resolution Before · upstream master frame for zoom"><img src="../../images/patches/audit/I22-control-upstream.png" alt="Matched crop of audit followup dot audit dot ring.milk (synthetic) — Before · same zoom" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I22-control-patched.png" style="--crop-ratio:40/40;--image-width:3200.000000000%;--image-left:-425.000000000%;--image-top:-850.000000000%;" aria-label="Open original full-resolution After · ProjectM TV frame for zoom"><img src="../../images/patches/audit/I22-control-patched.png" alt="Matched crop of audit followup dot audit dot ring.milk (synthetic) — After · same zoom" loading="lazy"></a></div></div>
<figcaption><strong>audit followup dot audit dot ring.milk (synthetic)</strong> · 1280×720, frame 239 at 30 Hz.<br>Synthetic 12-sample dot ring. This nearest-neighbour crop surrounds one interpolated dot: it is present upstream and absent after the repair. The original full frames remain available by clicking. Zoom rectangle: (170, 340), 40×40 source pixels; identical crop and nearest-neighbour display, with no brightness adjustment.</figcaption>
</figure>

</details>

## 0031 — Circle spacing and closure

Circles use the original angular spacing and duplicate the first endpoint before shared smoothing. Native styles, equation execution and the TV transition composition are unchanged.

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I20-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I20-upstream.png" alt="$$$ Royal - Mashup (11).milk — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I20-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I20-patched.png" alt="$$$ Royal - Mashup (11).milk — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<figcaption><strong>$$$ Royal - Mashup (11).milk</strong> · 1280×720, frame 119 at 30 Hz.<br>Original circle spacing and exact closure change the accumulating circular feedback. This is the full preset result, not a close-up proof that every changed pixel lies at the closing seam.</figcaption>
</figure>

## 0032 — Live shape thickness

Shape outlines now respond to the thickness set by their per-frame equations. In City lights, four overlay instances gain their requested thick strokes while the other 45 keep their thin outlines.





<figure class="patch-comparison patch-causal" data-witness="city-alt">
<div class="patch-panels"><div class="patch-panel"><strong>Only 0032 disabled</strong><a href="../../images/patches/clarity/city-alt-without-0032.png" aria-label="Open unchanged 4K city-alt frame, Only 0032 disabled"><img src="../../images/patches/clarity/city-alt-without-0032-crop.png" alt="city-alt: Only 0032 disabled, matched close-up" width="64" height="64" class="patch-detail" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/city-alt-full.png" aria-label="Open unchanged 4K city-alt frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/city-alt-full-crop.png" alt="city-alt: ProjectM TV · fix enabled, matched close-up" width="64" height="64" class="patch-detail" loading="lazy"></a></div></div>
<figcaption><strong>martin - city lights v2(1).milk</strong><br>The white corner has a fuller, continuous outline on the right. This preset asks four overlay instances to become thick; previously their live thickness was ignored.<br>Native 3840×2160, frame 0; matched 64×64 pixel crop at (768, 128). Click either close-up for its original 4K frame. No exposure or colour adjustment.</figcaption>
<details><summary>See both full 4K frames</summary>
<div class="patch-panels"><div class="patch-panel"><strong>Only 0032 disabled</strong><a href="../../images/patches/clarity/city-alt-without-0032.png" aria-label="Open unchanged 4K city-alt frame, Only 0032 disabled"><img src="../../images/patches/clarity/city-alt-without-0032.png" alt="city-alt: Only 0032 disabled, full frame" width="3840" height="2160" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/city-alt-full.png" aria-label="Open unchanged 4K city-alt frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/city-alt-full.png" alt="city-alt: ProjectM TV · fix enabled, full frame" width="3840" height="2160" loading="lazy"></a></div></div>
</details>
</figure>

<details class="patch-context"><summary>Earlier upstream-master comparison and diagnostic controls</summary>
<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I24-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I24-upstream.png" alt="martin - city lights v2 c.milk — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I24-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I24-patched.png" alt="martin - city lights v2 c.milk — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<figcaption><strong>martin - city lights v2 c.milk</strong> · 1280×720, frame 239 at 30 Hz.<br>The four overlay shape instances can use their evaluated thick outlines while the other 45 remain thin. This busy original also contains other repaired features; the disjoint-square diagnostic below isolates live thickness.</figcaption>
</figure>

<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I24-control-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I24-control-upstream.png" alt="audit followup audit shape live disjoint-thick.milk (synthetic) — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I24-control-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I24-control-patched.png" alt="audit followup audit shape live disjoint-thick.milk (synthetic) — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<div class="patch-panels patch-zooms"><div class="patch-panel"><strong>Before · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I24-control-upstream.png" style="--crop-ratio:70/70;--image-width:1828.571428571%;--image-left:-392.857142857%;--image-top:-185.714285714%;" aria-label="Open original full-resolution Before · upstream master frame for zoom"><img src="../../images/patches/audit/I24-control-upstream.png" alt="Matched crop of audit followup audit shape live disjoint-thick.milk (synthetic) — Before · same zoom" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I24-control-patched.png" style="--crop-ratio:70/70;--image-width:1828.571428571%;--image-left:-392.857142857%;--image-top:-185.714285714%;" aria-label="Open original full-resolution After · ProjectM TV frame for zoom"><img src="../../images/patches/audit/I24-control-patched.png" alt="Matched crop of audit followup audit shape live disjoint-thick.milk (synthetic) — After · same zoom" loading="lazy"></a></div></div>
<figcaption><strong>audit followup audit shape live disjoint-thick.milk (synthetic)</strong> · 1280×720, frame 239 at 30 Hz.<br>Synthetic disjoint shape instances, with thin saved style and live thick=1. The matched corner crop exposes the evaluated border width. Zoom rectangle: (275, 130), 70×70 source pixels; identical crop and nearest-neighbour display, with no brightness adjustment.</figcaption>
</figure>

</details>

## 0033 — Latest previous motion field

When motion-vector strokes return on a beat, they follow the latest completed distortion. Updating the motion field while the strokes are hidden prevents them from resuming with an older displacement; the correct injection then develops through feedback.

Keeping this history current adds motion-field writes on hidden frames. [Focused source, lifecycle and rendering-cost evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/authored-fidelity-followup/README.md) records the fidelity and cost tradeoff.


<figure class="patch-comparison patch-causal" data-witness="salad">
<div class="patch-panels"><div class="patch-panel"><strong>Only 0033 disabled</strong><a href="../../images/patches/clarity/salad-without-0033.png" aria-label="Open unchanged 4K salad frame, Only 0033 disabled"><img src="../../images/patches/clarity/salad-without-0033-crop.png" alt="salad: Only 0033 disabled, matched close-up" width="1200" height="1200" class="patch-detail" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/salad-full.png" aria-label="Open unchanged 4K salad frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/salad-full-crop.png" alt="salad: ProjectM TV · fix enabled, matched close-up" width="1200" height="1200" class="patch-detail" loading="lazy"></a></div></div>
<figcaption><strong>Hexcollie, Martin, Flexi n AdamFX - Seizure Salad.milk</strong><br>A real beat-gated preset: the returned vectors inject strokes using the latest completed distortion. The coloured rings develop differently instead of continuing from an older hidden-frame motion field. This frame shows the accumulated effect, not a promise of extra sharpness in every preset.<br>Native 3840×2160, frame 209; matched 1200×1200 pixel crop at (1200, 400). Click either close-up for its original 4K frame. No exposure or colour adjustment.</figcaption>
<details><summary>See both full 4K frames</summary>
<div class="patch-panels"><div class="patch-panel"><strong>Only 0033 disabled</strong><a href="../../images/patches/clarity/salad-without-0033.png" aria-label="Open unchanged 4K salad frame, Only 0033 disabled"><img src="../../images/patches/clarity/salad-without-0033.png" alt="salad: Only 0033 disabled, full frame" width="3840" height="2160" loading="lazy"></a></div>
<div class="patch-panel"><strong>ProjectM TV · fix enabled</strong><a href="../../images/patches/clarity/salad-full.png" aria-label="Open unchanged 4K salad frame, ProjectM TV · fix enabled"><img src="../../images/patches/clarity/salad-full.png" alt="salad: ProjectM TV · fix enabled, full frame" width="3840" height="2160" loading="lazy"></a></div></div>
</details>
</figure>

<details class="patch-context"><summary>Earlier upstream-master comparison and diagnostic controls</summary>
<figure class="patch-comparison">
<div class="patch-panels"><div class="patch-panel"><strong>Before · upstream master</strong><a href="../../images/patches/audit/I16-upstream.png" aria-label="Open full-resolution Before · upstream master image"><img src="../../images/patches/audit/I16-upstream.png" alt="audit followup uv default-feedback.milk (synthetic) — Before · upstream master" width="1280" height="720" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · ProjectM TV</strong><a href="../../images/patches/audit/I16-patched.png" aria-label="Open full-resolution After · ProjectM TV image"><img src="../../images/patches/audit/I16-patched.png" alt="audit followup uv default-feedback.milk (synthetic) — After · ProjectM TV" width="1280" height="720" loading="lazy"></a></div></div>
<div class="patch-panels patch-zooms"><div class="patch-panel"><strong>Before · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I16-upstream.png" style="--crop-ratio:320/28;--image-width:400.000000000%;--image-left:-75.000000000%;--image-top:-1242.857142857%;" aria-label="Open original full-resolution Before · upstream master frame for zoom"><img src="../../images/patches/audit/I16-upstream.png" alt="Matched crop of audit followup uv default-feedback.milk (synthetic) — Before · same zoom" loading="lazy"></a></div>
<div class="patch-panel"><strong>After · same zoom</strong><a class="patch-crop" href="../../images/patches/audit/I16-patched.png" style="--crop-ratio:320/28;--image-width:400.000000000%;--image-left:-75.000000000%;--image-top:-1242.857142857%;" aria-label="Open original full-resolution After · ProjectM TV frame for zoom"><img src="../../images/patches/audit/I16-patched.png" alt="Matched crop of audit followup uv default-feedback.milk (synthetic) — After · same zoom" loading="lazy"></a></div></div>
<figcaption><strong>audit followup uv default-feedback.milk (synthetic)</strong> · 1280×720, frame 239 at 30 Hz.<br>The motion field changes while vectors are hidden for one frame. When the red vectors return, they use the latest completed field. The matched zoom shows the changed segment; this is a diagnostic, not a confirmed stock-preset census. Zoom rectangle: (240, 348), 320×28 source pixels; identical crop and nearest-neighbour display, with no brightness adjustment.</figcaption>
</figure>

</details>

## Known remaining differences from MilkDrop 2

- `sampler_state { … }` fields are ignored; the sampler name prefix selects the mode (as in MilkDrop).
- In warp shaders, an unqualified `sampler_main` follows the preset's `wrap` setting; MilkDrop 2 ignores `wrap` there and uses the name prefix, which defaults to wrapping.
- `randNN` images are shared between the warp and composite shaders for a preset load; MilkDrop 2 picks separately per shader.
- Uninitialized shader globals read 0, not whatever a D3D9 constant register held.
- Fractional negative warp powers have nonfinite coordinates and unresolved appearance. Negative-base `pow` inside authored shaders remains undefined in GLSL.
- Nonfinite `rot` is unsupported.
- `wave_mode` wraps at 16 projectM modes, not 8.
- Blur ranges narrower than 0.1 are repaired instead of collapsing.
- Some reference-scale effects remain resolution-dependent at 4K unless Native trails or diffusion compensation is active ([details](resolution.md#what-this-does-not-fix)).
- HLSL translator edge cases: decimal→double→float double rounding and unchecked integer narrowing.
- Textured custom shapes always wrap; MilkDrop 2 clamps them on frames where blur levels are computed.
- Wave modes 2, 3 and 5 use projectM's size buckets instead of MilkDrop's exact-width fade table.
- Thick custom waves and shape outlines are offset by half a pixel; MilkDrop 2 offsets them by one canvas pixel, and its custom-wave dot size also grows on canvases 1024 px and wider.
- `decay` above 1 is clamped to 1; MilkDrop 2 wraps it to nearly black.
- No Windows reference renders exist in this project's evidence, so identical Windows appearance is never claimed.

These differences were found by auditing the [source predictor](../predictor.md) against MilkDrop 2's code; they are candidates for future engine patches.

The full assessment, including upstream contribution notes, is [`docs/UPSTREAM_PATCH_VALUE.md`](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/UPSTREAM_PATCH_VALUE.md).

## 0034 — GLES motion-field storage

Before allocating a float motion map, the engine checks core/extension capability and the actual mixed framebuffer. Contexts without compatible float rendering use required RG16UI storage containing half-float words. Both consumers decode before bilinear interpolation. Primary color, dithering and actual fragment clipping are unchanged, and so are capable RG16F shader paths. The correction adds no per-frame capability query or new render exception.

## 0035 — Program cache switch

This patch adds a TV-only troubleshooting control and does not change rendering. `projectm_opengl_set_program_cache_enabled(false)` makes every shader program compile and link from source in the context that uses it: no binary-retrievable hint, no `glGetProgramBinary` export, no `glProgramBinary` load, and cached entries are dropped. Turning it off waits for binary calls already running on the background compile thread, so none runs afterwards. Enabled again, the cache starts empty. The default stays enabled. The former app setting was removed after it did not resolve the Fire TV crashes; the additive API remains for existing consumers and laboratory controls. The real-GL `program-cache-switch` control checks the hint and the cache counters on GLES; desktop OpenGL builds have no binary cache.

## 0036 — PowerVR framebuffer retirement

Some Imagination/PowerVR drivers can retain a reference to a previously bound complete framebuffer after it has been deleted. Before deleting an engine framebuffer, this patch binds a small, complete guard framebuffer and then framebuffer zero on both read/draw targets, so neither retained reference points at the retiring object. Surviving bindings are restored. One guard is kept until context destruction, and other GPU vendors keep ordinary deletion. Hosts reset its names before retiring a lost-context instance.

The design follows [Chromium/Skia’s corrected workaround](https://skia.googlesource.com/skia/+/02b14267cb023e7ec9fc52618bd12464ceb6afb7). Real-GL tests intercept actual engine changes, resizes and cleanup: the unsafe binding sequence is observed without protection and absent with it, while nonblank pixels match. This qualifies the call sequence on the tested backend, not a confirmed fix for the reported Fire TV crash.

## 0037 — Reusable line rendering

This is an internal architecture change adapted from our [upstream PR #1047](https://github.com/projectM-visualizer/projectm/pull/1047), commit `ba122baa24cd1794c2a413ec8e308c8ab6e9e4fe`. Colored points, padded line batches, the line renderer and its generic shaders belong to `Renderer`. MilkDrop-specific reference sizing, sample/fade rules, dot styles, canvas inputs and thick-line pass offsets stay in `MilkdropPreset`.

Both line strips and motion-vector quads use `Renderer::Mesh` to own and stream their interleaved instance data, set attribute layouts/divisors and byte offsets, and draw a separate vertex/instance count. The existing indexed mesh path is retained. The motion-vector vertex shader stays with preset code because it samples the preset's warp field; it shares Renderer's fragment shader.

The Android port retains shader compilation during preset prewarming, cached uniform locations, per-instance shape styles, prepared Native-trails replay and the packed/floating motion-UV paths. This refactor is intended to preserve rendering rather than change a preset's appearance. Validation and backend limits are recorded in the [refactor evidence](https://github.com/johnneerdael/ProjectM-Android/blob/main/docs/superpowers/evidence/renderer-line-refactor/README.md).
