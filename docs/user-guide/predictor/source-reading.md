# Reading a preset: from `.milk` text to facts

Everything the predictor knows about a preset starts with its source file. This page follows one file through the reading stages up to the *understanding summary*, a structured record of thousands of facts that every later stage works from.

!!! info "Nothing is rendered here"
    Reading a preset parses it and analyses the parsed program. It does not run the preset, execute its shaders or draw a frame. Each record carries `uses_rendered_images`, `uses_shader_execution` and `uses_equation_execution` flags, all `false`.

## What is in a `.milk` file

A MilkDrop preset (see [Anatomy of a .milk file](../authoring/milk-format.md)) mixes four kinds of content:

- Settings: about 150 named values such as `fDecay` (how much of the previous frame survives), `zoom`, `rot`, `warp`, wave and border colours, echo and gamma.
- Equations in EEL, MilkDrop's expression language, split into several blocks: `per_frame_init` (once at load), `per_frame` (every frame), `per_pixel` (every mesh vertex), plus per-frame and per-point code for each custom shape and wave.
- Shaders: an HLSL *warp* shader that redraws the previous frame, and a *composite* shader that turns the internal canvas into the picture you see.
- Drawn elements: up to four custom waves, four custom shapes, the built-in waveform, borders and motion vectors.

The [frame, step by step](../authoring/execution.md) page explains how the engine runs those parts every frame. The predictor has to understand all of them, and how they feed each other through the feedback loop.

## Stage 1: the native reader

A small native program, `milk-native-reader`, parses the source. It is built from the same parsing code as the engine (`CORE_2331`/`CORE_2334` builds), because MilkDrop's syntax is forgiving in ways a hand-written parser gets wrong: stray semicolons inside parentheses, a lone `.` meaning 0, numbered equation lines joined in MilkDrop's order, and `//` and `\\` comments (see [Equations](../authoring/equations.md)). With the engine's own parser, the predictor sees exactly what the engine would run.

The reader runs on a frozen copy of the file with a 30-second timeout. It returns:

- `values`: every setting, looked up case-insensitively as the engine does;
- `sections`: each equation block as an EEL syntax tree, and each shader body as typed intermediate code;
- `parser_inputs.engine`: which engine build parsed it. The export refuses to continue on an unexpected engine build.

The preset bytes, the reader binary and the analysis modules are hashed before and after the analysis, so a record can always be traced to the exact inputs that produced it.

## Stage 2: families, mechanisms and the visual description

`effect_families.analyze_families` works through the parsed preset in phases:

| Phase | What it examines |
|---|---|
| `equations` | Per-frame and per-pixel equations: which settings they drive, what ranges values can take, which audio bands feed them |
| `drawing` | Waves, shapes, borders, motion vectors: their geometry, colour formulas, alpha, additive or blended drawing, instance counts |
| `warp_` | The warp shader: how it samples the previous frame, blurs, mixes channels, advects by the image's own gradients |
| `comp_` | The composite shader: how the canvas becomes the displayed picture, mirrors, tunnels, colour maps, noise |
| `pipeline` | Which parts actually contribute: a shader that never runs (missing version keys), a wave with alpha below the draw gate, a shape off screen |

The analysis recognises mechanisms, which are named mathematical constructions with parameters. Examples are `radial_feedback_transform` (zoom/rotate toward a centre), `blur_difference_feedback` (fine-minus-coarse blur, which grows patterns), `gradient_driven_advection` (fluid or reaction-diffusion-like flow), `gradient_relief` (embossed edges), `angular_mirror_fold` (kaleidoscope), `polar_radial_sampling` (tunnel), `point_cloud_primitive` (dots) and `nonlinear_feedback_map` (fractal-like maps). A preset typically combines several.

Work is bounded at 250,000 field visits and 256 normalised terms per expression. When a budget runs out, the affected fact becomes an explicit *unknown* instead of a truncated value.

### Closed-form graphs

Alongside the facts, the reader exports closed-form graphs. Each relevant program becomes a serialised dataflow graph `{root, nodes}` with EEL semantics exactly as projectm-eval implements them: integer conversion is floor, division by a near-zero denominator returns 0, and `rand` draws from one process-wide stream. The exported graphs include:

- the warp and composite shaders' RGB output programs (up to 6,000 nodes each);
- the per-frame state and output recurrence, so `q` variables and per-frame controls can be stepped as numbers;
- custom-wave point programs and shape instance recurrences;
- per-pixel mesh terms (zoom, rotation, translation, stretch, warp per vertex).

With these graphs, later stages can *evaluate* a control at a given time, or a shader on a given input, without running the preset as a whole.

## Stage 3: the understanding summary

`preset_understanding.summarize_preset` (policy `preset-understanding-v1`, standard library only) regroups the record into twelve fact groups. Each fact keeps the exact JSON pointer of its evidence.

| Group | Examples of facts |
|---|---|
| `identity` | Preset name and SHA-256, parser and engine identity, declared context |
| `context` | Viewport, feedback frame rate, mesh size, main texture size, audio scenario |
| `construction` | Family codes and mechanisms with parameters |
| `colour` | Source palettes, element colour formulas and their ranges, texture colour transfer, composite colour |
| `geometry` | Shape sizes, positions, side counts, instance counts, custom-wave curves and their projections |
| `shape_state` | Per-frame shape state recurrences and their bounds |
| `motion` | Per-pixel warp field structure, sampling offsets, lookup speeds |
| `flashing` | Sites that can switch brightness on audio thresholds, random redraws, beat-driven toggles |
| `audio` | Audio routes: which band (bass, mid, treble, their smoothed versions, waveform) drives which target, continuous or thresholded |
| `feedback` | Feedback envelope and transfer, colour sensitivity, the native warp recipe, radial zoom, displacement, borders, decay orbit, flat-field state |
| `mood` | The approximate feature vector from earlier research (kept for reference, not used by the Mood table) |
| `uncertainty` | Every unknown, with its reason |

The summary for one preset is typically 0.5 to 0.8 MB of JSON. Everything else takes it as input: the [closed-form maths](feedback-maths.md), the [calibration](mood-table.md), the [recipe](json-output.md) and the [prediction image](prediction-images.md).

## What the reader cannot know

Some things are not in the source:

- The music. Audio inputs are known as *routes* (bass drives this shape's opacity through a threshold), not as values. Estimates assume average audio levels (bands near 1).
- Random choices. `rand` in equations, `rand_preset` per load, random library textures (`sampler_rand00`…) and noise textures are drawn at run time. The analysis knows the distribution, not the draw.
- Unbounded or unresolvable terms. `while` loops, memory written by other code paths, or values that grow without bound are recorded as unknown.

These limits are why the mood stage relies on a calibration model over the facts, and why some presets get no option in a group.

## How long it takes

Parsing and analysis take seconds per preset on a laptop. The whole-corpus run used a 180-second timeout per preset and finished all 9,606 presets. The summaries are computed once, offline, and stored, and the mood stage re-reads them instead of parsing the presets again.
