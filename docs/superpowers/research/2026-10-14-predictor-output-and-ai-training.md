# Predictor output and its use as AI training data (2026-10-14)

This note describes what the source-only predictor writes for each MilkDrop preset, how accurate it is
today, and how that output could train or check a model that generates presets, such as
[MilkDropLM](https://huggingface.co/InferenceIllusionist/MilkDropLM-32b-v0.3). It records findings and an
assessment. Nothing here has been built yet.

## What the predictor writes per preset

Everything below comes from reading the `.milk` file. Frames are rendered only to validate the
mathematics, never to produce a fact. File sizes are from checkpoint r163.

| File | Size | Contents |
|---|---|---|
| `description.json` | ~700 KB | Full static facts in 12 groups: identity, context, construction, colour, geometry, shape_state, motion, flashing, audio, feedback, mood, uncertainty. Each fact names its evidence and states its limits. |
| `recipe.json` | ~180 KB | An engine-neutral summary: `render` (feedback, layers, composite, mechanisms, audio_bindings, random_redraws, mirrors, random_textures), `intent` (effect list and music-reactivity map), `mood`, `display_estimate`, `facets`, `limitations`. |
| `recipe-core-source-only.json` | ~44 KB | The recipe without facets and bulky program graphs. This is what an LLM reader receives. |
| `prediction.png` / `prediction.json` | ~75 KB | A frozen frame-by-frame prediction image (150 steps from the preset's own maths under declared reference audio), with hashes and stated limitations. |
| `llm-look-description-v1.txt` | ~2 KB | A plain-language description written by an SDK reader (Sonnet) that sees only `SKILL.md` and the core recipe. |

Corpus-wide, for all 9,606 bundled presets:

- **Engine-ruler measurements** for mean luminance, saturation, warm/cool, optical-flow speed, frame
  difference and global brightness jumps per 10 s. They come from the pinned, patched engine at 480×270
  with checkpoint audio (`build/preset-corpus/native-ruler-2026-10-12`).
- **Mood facets** (`core/src/main/assets/preset-attributes/attributes.tsv`): multi-select options per
  preset, such as energy (chill/normal/intense), brightness (dark/balanced/bright), colour (monochrome,
  pastel, vivid, warm, cool), movement and "no strobe", plus the underlying numbers.
- **Calibrated estimates** (`display_estimate`): gradient-boosted trees over 8,141 static descriptor
  columns. Each estimate has an out-of-fold interval; luminance Spearman is 0.646.

Example effects from the r163 core recipe:

```json
{"effect": "trails", "half_life_s": 0.133, "decay_per_frame": 0.385, "faint_residue": false}
{"effect": "radial_rays", "screen_share": 1.0, "centre_xy": [0.5, 0.5], "centre_moves": false,
 "condition": "the warp reads one source point per ray through the centre: every frame becomes rays converging on it ..."}
```

Checkpoint evidence lives in `docs/superpowers/evidence/source-understanding-checkpoints-2026-10-11/rN-*/`.
For each checkpoint it holds the selection, frozen prediction, SDK text, comparison image, measured
agreement and misses. The emulator screenshot and a 10 s clip are in `~/Downloads/ProjectM-TV-checkpoints-2026-10-11/`.

## Accuracy today

These are frozen predictions against emulator captures, averaged over frames 60–149. For the last five
checkpoints (r160–r164), accuracy is 100% minus the absolute error, except motion, which uses relative
error.

| | Brightness | Saturation | Motion amount | Layout correlation |
|---|---|---|---|---|
| As frozen | 88% | 90% | 87% | 63% |
| With the r164 line-edge fix | 97% | 96% | 87% | 63% |

Over r129–r156, 93% of predictions were within 0.05 luma, and the median layout correlation was 0.92.
Layout correlation is low for chaotic presets, where the structure is right but filaments or rays fall
elsewhere.

How often the plain-language description is right first time: 2 of the last 5. The misses in r161
(lens motion) and r162 (radial rays) led to general analyzer fixes, and the re-read descriptions now
match. The remaining weak spot is closed-form brightness: in r160 the reader called a preset "bright"
when its real luma was 0.17.

## Training uses

| Use | Inputs | Target or signal | Status of the data |
|---|---|---|---|
| **Description → preset** (instruction tuning) | Plain-language look description or facet selection | Preset text | Descriptions exist only for checkpoints; facets and ruler stats exist for all 9,606 |
| **Preset → look** (understanding) | Preset text | Core recipe and ruler stats | Available for the corpus. The recipe is mathematical, not a labelled guess |
| **Structured conditioning** | Facets, ruler stats, `intent` effects (rays, trails, tiling, kaleidoscope, ...) | Preset text | More specific than family labels such as "Fractal" or "Waveform" |
| **Automatic checker** | A generated preset | Static analysis (target ≤ 1 s) and an engine render: does the measured look match the request? | Analyzer and ruler exist. This enables rejection sampling or RL rewards |
| **Safety filter** | A generated preset | Flash rate and "No strobe" facet | Ruler jump counts exist; the facet is engine-measured for bundled presets |

The checker is probably the most valuable piece. A generator improves fastest when every output can be
scored on whether it looks like what was asked, and the predictor plus the ruler can do that cheaply.

## Caveats

- **Label quality.** Ruler measurements are reliable ground truth. Plain-language descriptions can carry
  closed-form brightness errors. Anchor training labels on ruler numbers and verified structure facts,
  and treat the prose as secondary.
- **Cost of prose at scale.** The SDK reader uses about 135k tokens per preset. Describing the whole
  corpus that way would cost on the order of a billion tokens. A template generated from the core recipe,
  or a smaller model reading a trimmed recipe, would be needed.
- **Engine specificity.** Labels describe projectM-TV (patched projectM 4.1.7) on GLES. Some boundary
  behaviour is implementation-dependent; for example, lines exactly on pixel edges are measured on the
  SwiftShader emulator.
- **Corpus overlap.** MilkDropLM was trained on about 10,000 curated presets. Overlap with the bundled
  Cream of the Crop set is likely, since both draw on the same public packs. Hold-out sets must be chosen
  with that in mind. 561 of the 9,606 bundled presets are "Isosceles edits" (5.8%).
- **Licensing.** The bundled presets and textures are CC0 (`LICENSES/CC0-1.0.txt`). MilkDropLM is Apache-2.0.

## A possible export, not built

One JSON line per preset:

```json
{"preset": "<name>.milk", "sha256": "...", "source": "<preset text>",
 "recipe_core": {...}, "ruler": {"mean_luminance": 0.54, "mean_saturation": 0.98, "...": "..."},
 "facets": ["normal", "bright", "vivid", "warm", "drifting", "no_strobe"],
 "description": "<optional plain-language text>", "evidence": {"checkpoint": "r163", "capture": "..."}}
```

Building it needs a decision on description generation (template or model) and a hold-out policy.
