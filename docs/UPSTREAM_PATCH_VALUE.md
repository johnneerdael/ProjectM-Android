# Earlier projectM patch comparison checkpoint

This page preserves the earlier 16-patch comparison checkpoint against upstream
projectM 4.2 development. Its images and source identities remain frozen. The
[current 37-patch catalog](https://johnneerdael.github.io/ProjectM-Android/engine/patches/)
includes the later audit repairs, measured benefits and isolated real-preset
close-ups. Older patch history remains in the evidence archive.

## Single-page comparison overview

Images use a GPU-accelerated Android TV emulator with matched preset, textures,
audio, time and seed. Zooms enlarge the same pixels without changing brightness.
A middle column, where present, removes one patch to isolate its effect. Generated
controls are labeled; a rejected render is an error panel, not a black screenshot.

Earlier images use our 13-patch snapshot `654815d8`; 0014 uses the recorded 14-patch
snapshot `41ec3fc1`. The image-comparison checkpoint stays frozen at main `120547f3`, including0015; main’s later0016 is documented from its separate performance evidence. Earlier captures retain their original snapshot identities;Reference lines and0003,0011 and0015 now have locked15-patch comparisons.
The upstream renderer matches master `e98fca85`; capture adjustments and source
identities are recorded in the [evidence record](superpowers/evidence/current-patch-proof/README.md).

## 0001 — TV rendering and preset compatibility

This consolidated patch contains several changes. The examples below cover
line scaling, equation loading and resource handling separately.

### Lines at 4K

![Upstream, our classic-line control and our reference-scaled lines](superpowers/evidence/current-patch-proof/components/locked15-lines/comparison-4k.png)

In **Geiss — 3D — Shockwaves**, upstream's thin loops fade into the background at 4K.
Our classic-line control also stays thin. Enabling reference-scaled lines
keeps the loops broader and more visible; the close-up shows the stroke difference.

Fixed one-pixel lines shrink relative to the picture as resolution increases.
Our optional quad renderer scales their width from a chosen reference size.
This addresses the scaling requested in [upstream #682](https://github.com/projectM-visualizer/projectm/issues/682).
It uses miter joins and flat ends; rounded joins/caps are not implemented.
[Line evidence](superpowers/evidence/current-patch-proof/components/locked15-lines/README.md).

### Presets that fail to load

![Upstream rejects161.milk; our library renders it](superpowers/evidence/current-patch-proof/0001-equations.png)

Upstream rejects **161.milk** before producing a frame. Our library accepts its
legacy split equation records and renders the preset. The reader retries those
records using MilkDrop-compatible joining rules; genuinely rejected code remains
reported. The left panel is the load error, not rendered output.

### Shader cleanup and texture initialization

![Healthy library frames with measured shader-object counts](superpowers/evidence/current-patch-proof/components/shader-lifetime/comparison.png)

After 16 intentionally rejected fragment compilations, upstream leaves 16 vertex
shaders alive; ours leaves none. The vertex shader succeeded before the fragment
failed, so the patch deletes that unattached object before rethrowing the error.
The normal preset pictures show rendering still works; the counters show the fix.
[Shader evidence](superpowers/evidence/current-patch-proof/components/shader-lifetime/README.md).

![Actual attachment pixels and storage-allocation counts](superpowers/evidence/current-patch-proof/components/texture-history/comparison.png)

The lower panels test first-read texture contents. A shared allocator deliberately
fills new storage green: upstream leaves it there, while ours clears fresh and
reused attachments to transparent black. This is a labeled diagnostic, not a
naturally green artist preset. With pooling enabled, ours reuses one allocation
instead of making two. Pooling retains storage and is off by default.
[Texture evidence](superpowers/evidence/current-patch-proof/components/texture-history/README.md).

Batching, caches, pass reductions and Native-trails replay also remain in 0001.
Their deeper optimization/lifecycle comparisons are deferred to a follow-up.
[Patch source](../tools/projectm-patches/0001-tv-rendering-and-preset-compatibility.patch).

## 0002 — HLSL compatibility and finite float round trips

![Upstream fallback versus the authored Madness Portal shader](superpowers/evidence/current-patch-proof/human-review/0002.png)

**Flexi — madness portal** becomes a plain red disc in upstream. Ours runs the
artist's yellow/blue composite with its fine circular detail. The shader declares
a local variable named `sample`; the old parser treats it as a reserved word,
rejects the shader and uses a fallback. The contextual-identifier fix allows it.
[Single-patch control](superpowers/evidence/current-patch-proof/0002-clear-original.png).

### Array layout

![Global array layout restores the authored Quicksand filter](superpowers/evidence/current-patch-proof/components/arrays-quicksand/comparison.png)

In **ORB — Quicksand Lab**, upstream uses the brighter cyan fallback. Our library
runs the authored five-tap filter, producing dimmer regions and stronger edges.
The shader fills five `float4` elements from 20 scalar values; the translator must
group those values into vectors and initialize the array correctly.
[Original-preset evidence](superpowers/evidence/current-patch-proof/components/arrays-quicksand/README.md).

![Local-array diagnostic: fallback versus authored gradient](superpowers/evidence/current-patch-proof/components/arrays-local/comparison.png)

This generated local-array control shows the same issue inside a function:
a red fallback becomes the intended gradient. It tests local layout separately
from Quicksand's global array.

### Writes to shader inputs

![A partial uniform-bank write preserves the other components](superpowers/evidence/current-patch-proof/components/uniform-bank/comparison.png)

The generated control writes `q18` but still needs incoming `q19=0.8`.
Upstream loses the green component; ours preserves it. The writable copy now
starts from the whole incoming uniform bank instead of uninitialized storage.

![Shared time writes change the original Martin preset's star pattern](superpowers/evidence/current-patch-proof/components/uniform-time-helper/comparison.png)

In **Martin — QBikal — Surface Turbulence**, the shader scales `time` before star
helpers read it. Our initialized copy is shared with those helpers, restoring the
authored star/ray arrangement. The preset itself is unchanged.
[Uniform evidence](superpowers/evidence/current-patch-proof/components/uniform-time-helper/README.md).

0002 also preserves float32 constants when emitting GLSL and supports the retained
macro/postfix and implicit-input rules.
[Patch source](../tools/projectm-patches/0002-hlsl-compatibility-and-float-roundtrip.patch).

## 0003 — Evaluator random state and lone-dot numbers

![Upstream rejection and the corrected original Stahlregen preset](superpowers/evidence/current-patch-proof/components/locked15-lone-dot/upstream-current.png)

**Stahlregen — funky Blur** uses a lone `.` in its zoom equation. Upstream rejects
it; a tolerant loader without 0003 omits that code and produces a different pattern.
Ours reads the dot as zero, matching the equation language's intended behavior.

The patch also gives each evaluator thread its own random state, preventing
background preparation from advancing the foreground stream. That part is checked
with thread/stream controls, rather than inferred from this picture.
[Evidence](superpowers/evidence/current-patch-proof/reproduction-validation.json) ·
[Patch source](../tools/projectm-patches/0003-evaluator-thread-local-rand-and-lone-dot.patch).
[Locked15 image/failure receipts](superpowers/evidence/current-patch-proof/components/locked15-lone-dot/README.md)
and [complete evaluator control](superpowers/evidence/current-patch-proof/components/locked15-evaluator/README.md).

## 0004 — Main-textured shape sampler ownership

![Upstream and our library rendering widest swing](superpowers/evidence/current-patch-proof/0004-sampler.png)

In **widest swing**, look at the large yellow/blue textured shape toward the top
left. Its feedback sampling changes when a sampler left on texture unit zero
interferes with the shape. Ours explicitly owns repeat/linear sampling for each
main-textured fill, including replayed geometry.
[Single-patch comparison](superpowers/evidence/current-patch-proof/0004-sampler-isolated.png) ·
[Patch source](../tools/projectm-patches/0004-textured-shape-sampler.patch).

## 0005 — Safe blur intervals

![Upstream and corrected embossed Julia-fractal shading](superpowers/evidence/current-patch-proof/human-review/0005.png)

In **Flexi — a julia fractal for hexcollie embossed (Jelly)**, our image has different
relief and highlights around the same fractal. The zoom makes the changed shading
visible around the dark central shape.

The authored blur bounds become a narrow/inverted interval after clamping.
A typo moved both repaired bounds downward, collapsing the interval and allowing
division by zero. Ours moves the upper bound upward and keeps blur storage and
decoding consistent; the artist's shader stays unchanged.
[Single-patch comparison](superpowers/evidence/current-patch-proof/0005-clear-original.png) ·
[Patch source](../tools/projectm-patches/0005-blur-range-interval.patch).

## 0006 — Signed unit-exponent zoom

![Upstream and our library rendering negative-zoom feedback](superpowers/evidence/current-patch-proof/0006-zoom.png)

**Hexcollie — This is where we begin stripped** develops a different green center
and feedback structure. It uses negative zoom with exponent one. Sending that to
GLSL `pow` is undefined even though the intended result is simply the signed base.
Ours preserves that signed base and the reflected transform. Patch0015 carries this case into its broader CPU-power path.
[Single-patch comparison](superpowers/evidence/current-patch-proof/0006-zoom-isolated.png) ·
[Patch source](../tools/projectm-patches/0006-fixed-warp-signed-unit-zoom.patch).

## 0007 — Evaluated built-in waveform controls

![Original Hexcollie wormhole waveform comparison](superpowers/evidence/current-patch-proof/human-review/0007.png)

The **Hexcollie — now entering the wormhole2** preset sets one initial wave mode,
then changes it through `wave_mode=q8%7`. The old renderer kept drawing the initial
mode. Ours follows the evaluated mode, changing the wave geometry and the feedback
it leaves behind. The matching zoom shows the changed structure.
[Upstream/current frames](superpowers/evidence/current-patch-proof/0007-wormhole.png) ·
[Patch source](../tools/projectm-patches/0007-live-builtin-wave-controls.patch).

## 0008 — Evaluated legacy display controls

![Generated equation-driven invert control](superpowers/evidence/current-patch-proof/0008-display-invert.png)

This generated control turns inversion on through an equation. Upstream keeps
the orange shape on black; ours changes to the inverted blue shape on white.
The renderer now consumes evaluated gamma, echo and filter flags each frame,
including filters that start disabled. Custom composite shaders keep their own
presentation rules.
[Patch source](../tools/projectm-patches/0008-live-legacy-display-controls.patch).

## 0009 — User-texture premultiplication bytes

![Upstream and our texture-byte compatibility result](superpowers/evidence/current-patch-proof/human-review/0009.png)

In **Suksma — chemosynthetic nosferatu — rand tritex**, compare the colored
contours in the zoom. Small texture-upload byte differences grow through feedback.
Our loader preserves the released SOIL2 premultiplication/rounding bytes, including
opaque-channel rounding. This is a texture compatibility choice, not a general
brightness boost.
[Byte and frame evidence](superpowers/evidence/current-patch-proof/visibility-figures.json) ·
[Patch source](../tools/projectm-patches/0009-user-texture-premultiplication.patch).

## 0010 — Per-preset texture search-path ownership

![SOL retains its orange emblem while the host switches to LUNA](superpowers/evidence/current-patch-proof/0010-aurora-ownership.png)

This is an **enhancement for hosts switching custom packs**. Both generated packs
contain `aurora_ownership_core.png`, but in separate texture directories: SOL's
image is orange and LUNA's is blue. At frame 20 the host changes directories before
loading LUNA. Upstream replaces SOL's emblem; ours keeps SOL's image until the
preset retires, including during a fade/reset.

Upstream uses the current global texture lookup. Ours retains the lookup that
belonged to each preset when it loaded. Ordinary Cream of the Crop switching uses
one shared directory and does not trigger this case. It is not a MilkDrop bug.
[Pack sequence and evidence](superpowers/evidence/current-patch-proof/aurora-ownership/README.md) ·
[Patch source](../tools/projectm-patches/0010-preset-texture-search-path-ownership.patch).

## 0011 — CPU warp rotation trigonometry

![Upstream collapses the coordinate field; our library preserves rotation](superpowers/evidence/current-patch-proof/components/locked15-rotation/comparison.png)

The **EoS/Phat/PeterP/Sentinel/Aware** witness uses `rot=10000000`. This labeled
coordinate-color control uses the same angle: upstream collapses the field to one
color, while ours preserves the rotation. GPU sine/cosine lost the transform on
the tested driver; ours computes both on the CPU after float conversion.

The [original preset image](superpowers/evidence/current-patch-proof/0011-rotation.png)
is dark and upstream also rejects an equation, so it is kept as supporting evidence.
The clear control above is generated, not the original artwork.
[Locked-source verification](superpowers/evidence/current-patch-proof/components/locked15-rotation/README.md) ·
[Patch source](../tools/projectm-patches/0011-cpu-warp-rotation-trig.patch).

## 0012 — Custom-shape pixel centres

![Upstream and corrected Green Machine shape coverage](superpowers/evidence/current-patch-proof/human-review/0012.png)

In **Amandio C — the green machine … btbam covers sepultura**, pink/brown wedges
become a green/yellow curved structure. Tiny custom shapes seed a gradient-driven
feedback shader, so a small coverage error grows into a large pattern difference.

D3D9 and GLES sample different pixel-center grids. Ours translates each shape draw
by half a destination pixel, preserving the authored position, radius and colors.
The [isolated comparison](superpowers/evidence/current-patch-proof/0012-visible-original.png)
separates this correction from other changes in the full library.
[Patch source](../tools/projectm-patches/0012-shape-pixel-centers.patch).

## 0013 — Custom-composite texel centres

![Upstream and our Toxic Water Diffusion contours](superpowers/evidence/current-patch-proof/human-review/0013.png)

In **DemonLD — Toxic water diffusion**, compare the green/cyan contour rims and
their neighboring colors in the zoom. An extra half-texel offset made GLES read
between texels and blend colors that the shader expected to sample at their centers.
Its nonlinear color operations amplify that unwanted averaging.

Ours removes the redundant offset. The [single-patch comparison](superpowers/evidence/current-patch-proof/0013-visible-original.png)
shows the contour change without other patch effects; the [impulse control](superpowers/evidence/current-patch-proof/0013-composite-impulse-zoom.png)
shows one bright texel staying intact instead of spreading across four.
[Patch source](../tools/projectm-patches/0013-composite-texel-centers.patch).

## 0014 — Legacy tint and mode-1 waveform

![Upstream, current-minus-0014 and our corrected Hurricane](superpowers/evidence/current-patch-proof/components/legacy14-hurricane/comparison.png)

In **Geiss — Hurricane**, upstream and current-minus-0014 add a green cast despite
`fShader=0`. Ours respects the disabled tint, giving cooler, nearly neutral trails.
The patch also restores mode 1's alpha multiplier and open spiral, removing the
extra line that connected its ends.

The [constant-color controls](superpowers/evidence/current-patch-proof/components/legacy14-hue/README.md)
check disabled, half and full tint separately. The [spiral close-up](superpowers/evidence/current-patch-proof/components/legacy14-mode1/README.md)
isolates the waveform change from tint.
[Current-source evidence](superpowers/evidence/current-patch-proof/components/legacy14-hurricane/README.md) ·
[Patch source](../tools/projectm-patches/0014-legacy-tint-and-mode1-waveform.patch).

## 0015 — Negative warp powers on the CPU

![Upstream collapses defined negative-power coordinates; our library preserves them](superpowers/evidence/current-patch-proof/components/locked15-power/comparison.png)

This generated control uses negative zoom with finite integer nested powers.
Upstream collapses the coordinate field; ours preserves its gradient. GLSL `pow`
is undefined for negative bases even when the CPU expression has a valid answer.
The patch evaluates that expression on the CPU after float conversion and reuses
its result when drawing the prepared mesh. Positive zoom is unchanged.

The original **Great Tulip Majesty** still enters fractional negative-power domains
and its recorded frames remain unchanged. It must not be presented as fixed.
[Locked-source comparison and checks](superpowers/evidence/current-patch-proof/components/locked15-power/README.md) ·
[Patch source](../tools/projectm-patches/0015-warp-negative-zoom-cpu-power.patch).

## 0016 — Mesh initialization caching

Upstream rebuilt the warp and final-composite grids every frame because it never
saved the viewport size used by its cache check. This patch saves the size and
rebuilds/uploads static mesh data only when the viewport or grid changes.

On the AM6, **Royal — Mashup (102)** at1080p/30fps used11.8% less process CPU in two
40-second runs per side, with silence. GPU time and4K were not measured. Existing
host controls check reused versus fresh mesh data; no on-device image comparison
was run. This later main optimization is included without expanding the frozen
15-patch capture checkpoint.
[Performance evidence](superpowers/evidence/mesh-init-cache/README.md) ·
[Patch source](../tools/projectm-patches/0016-cache-mesh-init-per-viewport.patch).

## Supporting evidence and remaining work

[Full-resolution images, inputs and verification](superpowers/evidence/current-patch-proof/README.md)
retain repeated-frame checks, source/binary identities and failed attempts.
The [original PR input map](superpowers/evidence/current-patch-proof/original-evidence-inputs/README.md)
provides the preset names and activation profiles used to guide remaining captures.
The [detailed working assessment](superpowers/evidence/current-patch-proof/expanded-assessment.md)
keeps the component inventory and technical notes out of this review page.

The15 patch sections now have matched comparison evidence. Deeper optimization/lifecycle checks are deferred by agreement; final review and CI remain required before publication.
The upstream capture admits GLES 3.0; our image workers disable the emulator's broken
program-binary export. No original Windows/MilkDrop GPU screenshot was produced.

## Current MilkDrop audit candidate

The candidate series retains released patches0001–0016 and audit repairs0017–0028 unchanged, then adds five independently revertible authored-fidelity fixes:

| Patch | Finding | Behavior |
|---|---|---|
| 0029 | I19 | Restore original line-wave sample budgets, capped by the reference-equivalent width, with a two-point floor. |
| 0030 | I22 | Submit authored discrete custom dots without interpolated midpoints; preserve a single-dot NaN sample input. |
| 0031 | I20 | Restore circle angular spacing and explicit closure before shared smoothing. |
| 0032 | I24 | Capture evaluated outline thickness per shape instance for authored and Native replay; preserve saved style outside the defined int32 truncation domain. |
| 0033 | I16 | Publish the actual previous completed warp field while vectors are hidden, preserving real fragment discard/output writes and per-preset ownership. |

The user accepts necessary authored work instead of the historical zero-added-cost gate for these five. I24 uses the small per-instance repair rather than experimental grouped geometry; I16 uses the actual warp producer rather than a synthetic UV-only shortcut. Earlier CPU warp trig, negative power, cached mesh uploads, prepared replay, float values, textures and Native/reference policies remain intact. No new API, dependency, asset or version change is introduced.

The candidate repairs18 audit IDs. Ten retained policies and five other deferred proposals remain as recorded in the immutable [historical audit](superpowers/evidence/milkdrop-audit-repairs/README.md). Its original patch numbers, zero-cost decisions and captures are not relabelled as new acceptance.

[Current qualification](superpowers/evidence/authored-fidelity-followup/README.md) binds the baseline28 and candidate33 source/artifact identities. Source checks pass329 host,63 normal and sanitizer renderer controls,137 JVM and60 capture/helper tests plus24 subtests. Both ARM core-release/debug-APK builds pass. The focused Native run completed76 jobs across19 presets/fixtures;608 selected final-output RGB captures verify and repeat exactly within each role. This is source-derived GLES qualification, not Windows/D3D pixel equivalence, whole-corpus certification or measured physical-TV headroom. Active-canvas lifecycle passes four repeated jobs/120 boundary captures. Isolated combined cost verifies84 jobs/672 selected captures, with a largest overall added time of+.343ms and variable cycle deltas. Final PR review/CI remain open.

## Retained diagnostic API 0035

Patch0035 adds `projectm_opengl_set_program_cache_enabled` for the process-wide program binary cache from patch0001. Disabled, programs compile from source in their own context without the retrievable hint, export or `glProgramBinary` load; disabling waits for binary calls already under way on other threads; enabled again, the cache starts empty. The former **Advanced › Shader binary cache** setting was retired after it did not resolve the reported PowerVR GE9215 crashes. The app uses its normal enabled default; the core compatibility API remains. Not proposed upstream: the cache itself is TV-only.

## Measured benefit of 0019 / I31

I31 is a rendering-cost repair with unchanged checked images. A native Apple M4 Pro 3840×2160 comparison of the 34-patch engine against its exact 0019 ablation confirms three gamma draws become two at loaded gamma 2.0009999275. In the Standard profile, GPU elapsed time falls 2.307→1.847 ms (−19.9%) and completed-frame time 2.704→2.241 ms (−17.1%). All eight paired ABBA/BAAB blocks favor the patch; the gamma 2.0 inactive control has no resolved GPU/completed-frame effect. Three selected RGB frames match across roles and repeats within each of the Classic and Standard profiles.

This supports retaining 0019 on measured benefit, superseding the earlier inconclusive timing status. It establishes neither universal app FPS gains nor physical-TV performance; gain size depends on workload and hardware bottlenecks. The [isolated proof](superpowers/evidence/i31-benefit/README.md) retains 80 timed runs/28,800 measured frames, source/harness identities, controls, intervals and replay instructions.

## PowerVR framebuffer-copy compatibility 0038

A source-bound ProjectM 2.3.55 Fire TV report identifies a driver `glBlitFramebuffer` crash in feedback resizing. Patch0038 replaces PowerVR resize, Native-trails recombination and scaled-presentation blits with cached textured draws. It also isolates colour-zero routing, completes mixed-attachment resizing before copying, restores touched state and forgets resources safely after context loss. Other GPUs keep blits with explicit read-source detachment before texture retirement. Primary image formats already match; the separate motion-vector attachment keeps its data format.

The [focused evidence](superpowers/evidence/powervr-blit-crash/README.md) binds the released ARM instruction bytes to the resize caller and records host GL and Android/GLES controls. Synthetic 512×288 RGBA copies match exactly, 4K scaling differs by at most one channel step, and nearest Native-trails copying is exact. This is a compatibility repair with no measured speedup or affected-Fire-TV success claim. [Patch source](../tools/projectm-patches/0038-powervr-framebuffer-draw-copy.patch) and [comparison images](user-guide/engine/patches.md#0038-powervr-framebuffer-copies).
