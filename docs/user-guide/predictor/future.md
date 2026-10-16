# The road ahead: a dataset for generating visuals

The Mood table is the first product of the static analysis. For each of the 9,606 bundled presets the analysis now holds a machine-readable account of *what the preset draws, how it moves, which colours it settles on and how it reacts to music*, derived from the source alone and checked against real renders. Together these accounts form a dataset, and this page describes what it could be used for next. **Nothing on this page is built yet.** It records a direction; none of it is a feature.

## What the dataset contains

Per preset, the research branch can produce (sizes from a typical checkpoint preset):

| Layer | Size | What it holds |
|---|---|---|
| The `.milk` source | 5-50 KB | The preset text itself (CC0, see [Third-party notices](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/THIRD_PARTY.md)) |
| Understanding summary (`description.json`) | ~700 KB | Every static fact in 12 groups (identity, context, construction, colour, geometry, shape state, motion, flashing, audio, feedback, mood, uncertainty), each with its evidence and limits |
| Recipe (`recipe.json`) | ~180 KB | An engine-neutral summary: render structure (feedback, layers, composite, mechanisms, audio bindings, random redraws, mirrors, random textures), intent (named effects such as trails, radial rays, tiling, kaleidoscope folds, and a music-reactivity map), display estimates with intervals |
| Core recipe | ~44 KB | The recipe without bulky program graphs: what an [SDK](sdk.md) reader receives |
| Static estimates and moods | ~100 bytes | Brightness, saturation, coloured share, warm/cool, flow, frame difference, brightness jumps, activity; mood options, palette and main colour (the shipped [Mood table](mood-table.md)) |
| Checkpoint evidence (about 400 presets) | ~1 MB | A frozen [prediction image](prediction-images.md), a plain-language look description written before capture, an emulator render, a 10 s clip and a measured agreement record |

Two example effects from a core recipe:

```json
{"effect": "trails", "half_life_s": 0.133, "decay_per_frame": 0.385, "faint_residue": false}
{"effect": "radial_rays", "screen_share": 1.0, "centre_xy": [0.5, 0.5], "centre_moves": false}
```

Every label is **grounded**: it says what the preset looks like, it is derived from the mathematics the engine will run, and it has been compared with what the engine actually draws ([accuracy](accuracy.md), [gallery](gallery.md)).

## Training a MilkDrop model

### What exists today: MilkDropLM

[MilkDropLM](https://huggingface.co/InferenceIllusionist/MilkDropLM-32b-v0.3) is an open language model that writes MilkDrop presets. According to its model card (checked 2026-10-16), version 0.3 is a fine-tune of Qwen2.5-Coder-32B-Instruct (about 33 billion parameters), trained for two epochs (about 48 hours on one A100) on "a hand curated and highly organized dataset containing 10,000+ best MilkDrop presets". It was made by InferenceIllusionist together with ISOSCELES, the curator behind *Cream of the Crop*, the collection ProjectM TV bundles. A 7-billion-parameter version exists as well. You prompt it with requests such as "Make a milkdrop preset with [x], [y], [z]" or a category from its list (Dancer, Drawing, Fractal and so on). It is Apache-2.0 licensed.

It is an impressive piece of work. Because it comes from the same curator, its training material very likely overlaps with the 9,606 presets analysed here, which is why the two fit together.

### Where a text-only model is limited

The model card is open about the model's status. It marks the model as an alpha release, carries an epilepsy warning ("This model may generate visuals with flashing lights") and describes no formal evaluation; improvements are reported from alpha testers' feedback. Beyond what the card says, any model trained on preset text alone has structural limits, and these are not specific to MilkDropLM:

- It learns what presets are written like, not what they look like. The training pairs are prompts or categories and preset text. Nothing in a `.milk` file says "this is a dark blue tunnel that pulses on the kick": the look only exists after the engine runs the equations, shaders and feedback loop for a few seconds. A text model can produce code that is plausible as MilkDrop and still produce a black screen, a white-out or a look unrelated to the request.
- Category labels are coarse. "Fractal" or "Dancer" says little about brightness, colour, motion speed or flashing. A request like "calm, dark, mostly purple, no strobe" has no direct counterpart in the training labels.
- There is no feedback loop. Nothing in the generation process checks whether the output parses, whether it reacts to audio, whether it flashes, or whether it matches the request. Every output has to be judged by a person watching it.
- Safety rests on a warning with no filter behind it, so flashing output can only be caught by looking at it.

### How the static dataset gets around those limits

| Limitation | What the static analysis adds |
|---|---|
| Learns text, not look | Every training preset can be paired with its grounded look: recipe effects, brightness, colour, motion and flashing estimates, mood options, palette and main colour. A model can learn *preset → look* (understanding) and *look → preset* (generation) from the same corpus |
| Coarse labels | Requests can be expressed in the same vocabulary the analysis produces: "Energy Chill, Brightness Dark, Palette purple, Main colour purple, Movement Drifting, No strobe", or effect-level descriptions such as "trails with a 0.13 s half-life and radial rays from the centre" |
| No feedback loop | The analysis is an **automatic checker**. A generated preset can be analysed in seconds and scored on whether its predicted look matches the request; outputs that miss can be rejected and regenerated (rejection sampling) or used as a reward signal for reinforcement learning. A short emulator render, as used for the [checkpoints](prediction-images.md#how-the-real-render-is-captured), confirms the final candidates |
| Flashing found by eye | The same No strobe classifier that admits presets to **Comfort › No strobe** (probability at least 0.93 plus a low brightness-jump estimate) can reject flashing candidates before anyone sees them |
| Output may not run | The source reader already parses and compiles presets the way projectM does (including MilkDrop's tolerant equation syntax); a candidate that does not compile, or whose equations are left out, is rejected before scoring |

The checker is probably the most valuable piece. A generator improves fastest when every output can be scored automatically on whether it looks like what was asked, and the static analysis can do that without a GPU.

### A possible training export

One JSON line per preset, not built yet:

```json
{"preset": "<name>.milk", "sha256": "...", "source": "<preset text>",
 "recipe_core": {"render": {}, "intent": {}, "display_estimate": {}},
 "moods": ["chill", "dark", "cool", "blue", "main_blue", "drifting", "no_strobe"],
 "description": "<optional plain-language look description>",
 "evidence": {"checkpoint": "r163", "render_sha256": "..."}}
```

Open decisions before building it:

- How to write descriptions at scale. The [SDK](sdk.md) reader that wrote the checkpoint look descriptions uses a large model and many tokens per preset, so describing all 9,606 presets that way is expensive. A template generated from the core recipe, or a smaller model reading a trimmed recipe, would be needed.
- Which presets to hold out. Because MilkDropLM's training material and Cream of the Crop come from the same curator, a fair evaluation needs presets that neither model has seen. About 6% of the bundled presets (561) are "Isosceles edits" of other presets, so near-duplicates must be grouped before splitting.
- How to weight labels. Estimates carry intervals and the options carry measured precision. Training should weight labels by that confidence and prefer structural facts (effects, layers, audio bindings) over prose.
- How engine-specific the facts are. They describe ProjectM TV Engine (based on projectM 4.1.7 with this repository's patches) on OpenGL ES. Some boundary behaviour, such as lines exactly on pixel edges, is implementation-dependent.

## Generating visuals for other frameworks

The recipe is deliberately engine-neutral. It describes a look in terms of feedback with a half-life, warps, mirror folds, drawn layers, palettes and audio routes, without MilkDrop variable names, so it could also be the input for generators that target other visual systems:

- MilkDrop-compatible players such as Butterchurn (WebGL) and NestDrop read `.milk` presets directly; a look-conditioned generator would serve them unchanged.
- Shader-based systems (fragment-shader formats used by VJ software, live-coding environments and shader-sharing sites) can express feedback, warps and folds as a ping-pong buffer plus a fragment shader. The recipe's feedback gain, warp field, composite transfer and palette map onto that structure.
- Node-based tools and game engines (visual programming environments, particle and VFX graphs) can rebuild the recipe's layers: point clouds and waves as particle emitters, shapes as instanced meshes, feedback as a render-to-texture loop, audio bindings as parameter drivers.
- Style transfer between presets: take the motion of one preset and the palette of another, both described in the same vocabulary, and generate a new preset or shader that combines them.

In every case the static analysis can close the loop the same way: describe the requested look in recipe terms, generate, analyse or render the result, and keep what matches.

## What will not change

Moods stay static. The app's moods come from source analysis; renders validate the mathematics and never set a mood ([the rules](../predictor.md#the-rules)). Nothing runs on your TV: all analysis happens offline when the collection is built. The analysis tools, the evidence and the bundled presets are open (LGPL-2.1 for the code, CC0 for presets and textures).
