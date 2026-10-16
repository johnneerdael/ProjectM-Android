# The JSON output, field by field

The predictor writes several JSON documents per preset. This page explains each one and every field in it, using real values from two presets: **Various – Fire and Brimstone** (a slow, fluid, flame-coloured feedback preset) and **suksma – delicious carnal amorality** (a fast, blue particle storm).

| Document | Policy string | Size per preset | Produced by | Used for |
|---|---|---|---|---|
| Understanding summary | `preset-understanding-v1` | 0.5–0.8 MB | `preset_understanding.py` | Input to everything else ([Reading a preset](source-reading.md)) |
| **Recipe** | `preset-visual-recipe-v1` | 80–250 KB | `preset_recipe.py` | The engine-neutral description; this page's main subject |
| Core recipe | same, graphs removed | 30–60 KB | `knowledge_pack.core_recipe` | What the [SDK](sdk.md) and LLM readers receive |
| **Mood evidence row** | `projectm-tv-static-mood-evidence` | ~400 bytes | `static_evidence_export.py` | The source of the shipped Mood table |
| Mood table line | `attributes.tsv` | ~170 bytes | `attribute_bundle.py --build-static` | Read by the app |
| Prediction record | `sdk-prediction-illustration-v1` | ~3 KB | `prediction_illustration.py` | Describes a [prediction image](prediction-images.md) |
| Self-comparison | `checkpoint-self-comparison-v1` | ~2 KB | checkpoint review | Prediction vs render measurements |

## Conventions used everywhere

Every recipe repeats its conventions in a `conventions` block, so it can be read without this page:

| Key | Meaning |
|---|---|
| `coordinates` | Per-pixel `x`/`y` in [0, 1], measured along the long side of the viewport, `y = 0` at the top. The short axis spans a centred sub-range. |
| `feedback` | Each frame the previous image is resampled through the warp map, multiplied by decay, then layers are drawn on top; the composite displays the result. |
| `warp_map` | `source = 0.5 + (p − 0.5) / zoom^(zoomexp^(2·rad − 1))`, stretched and rotated about `(cx, cy)`, minus `(dx, dy)`. Content therefore moves right for positive `dx` and down for positive `dy`. |
| `time` | Seconds since the preset loaded. Audio inputs `bass`, `mid` and `treb` are about 1 on average; the `_att` variants are smoothed. |
| `expressions` | Serialised graphs `{root, nodes}` with projectm-eval semantics (integer conversion is floor; division by a denominator below 1e-5 gives 0). |
| `fidelity` | An approximate recipe for a similar effect, not a pixel-exact specification. |

Common value shapes:

- **Ranges** are `[low, high]` lists: the values a quantity can take under the recorded premises.
- **Estimates** are objects with `value`, `interval` (10th–90th percentile of out-of-fold errors) and `evidence`.
- **`evidence`** strings are JSON pointers into the understanding summary (`/analysis/visual_description/...`), or a label such as `source-calibrated`, `source-estimate`, `mechanism-estimate`, `assumed` or `unknown`.
- **`null`** means unknown or not applicable; it is never a silent zero.
- `uses_rendered_images: false` appears on every block that could in principle have used a render; it is always false in shipped output.

## The mood evidence

One row per bundled preset in `docs/superpowers/evidence/static-mood-table-2026-10-16/static-evidence.json.gz`. The file's top level:

| Field | Meaning |
|---|---|
| `schema` | `projectm-tv-static-mood-evidence` |
| `version` | `1` |
| `producer.branch` | The research branch the analysis ran on (`feat/predictor-static-output-bounds`) |
| `producer.commit` | The exact research commit |
| `producer.calibration_model_sha256` | SHA-256 of the calibration model used |
| `producer.policy` | `static source analysis only; no ruler or simulation values` |
| `rows` | One object per preset, sorted by name |

Each row (Fire and Brimstone):

```json
{"name": "Various - Fire and Brimstone.milk",
 "sha256": "ddc3d588…cf914",
 "options": ["chill", "bright", "vivid", "warm", "liquid"],
 "palette": ["green", "red", "yellow"],
 "dominant": null,
 "values": {"luminance": 0.4910, "saturation": 0.8042, "coloured_share": 0.8259, "warm_cool": 0.4487,
            "flow": 0.0952, "frame_difference": 0.0342, "jumps": 0.0, "activity": 0.0949}}
```

| Field | Type | Meaning |
|---|---|---|
| `name` | string | The preset file name, as in `presets.idx` |
| `sha256` | string | SHA-256 of the preset file the analysis read. CI fails if the bundled file no longer matches |
| `options` | list | Mood option ids decided by the static analysis, without colour ids: Energy (`chill`, `normal`, `intense`), Brightness (`dark`, `balanced`, `bright`), Colour (`monochrome`, `pastel`, `vivid`, `warm`, `cool`), Movement (`still`, `drifting`, `fast`), Style (`kaleidoscope`, `tunnel`, `liquid`, `geometric`, `particles`, `fractal`), Comfort (`no_strobe`) |
| `palette` | list | Hue families with at least 10% of the static display palette, in order of share. Empty for grey presets |
| `dominant` | string or null | The main colour family, or null when no colour dominates ([rules](colour.md#main-colour)) |
| `values.luminance` | 0–1 | Estimated mean brightness of the picture |
| `values.saturation` | 0–1 | Estimated mean saturation |
| `values.coloured_share` | 0–1 | Estimated fraction of the picture that is coloured rather than grey |
| `values.warm_cool` | −1 to +1, or null | Estimated balance of warm (red, orange, yellow) against cool (cyan, blue, purple) hues; null when there is no colour |
| `values.flow` | screen widths per second | Estimated motion speed |
| `values.frame_difference` | 0–1 | Estimated mean change between consecutive frames |
| `values.jumps` | per 10 s | Estimated whole-screen brightness jumps per 10 seconds |
| `values.activity` | 0–1 | Energy percentile against the frozen activity reference; 0.09 is calmer than 91% of the reference presets |
| `error` | string | Present only if the analysis failed; the preset then gets no options. The shipped export has none |

## The Mood table line

`attributes.tsv` turns each row into one tab-separated line:

```text
Various - Fire and Brimstone.milk	chill,bright,vivid,warm,green,red,yellow,liquid	0.4910	0.8042	0.8259	0.4487	0.0952	0.0342	0.0000	0.0949
```

Columns: `name`, `options` (definition order: Energy, Brightness, Colour, Palette, Main colour, Movement, Style, Comfort; Main colour ids are `main_<family>`), then `luminance`, `saturation`, `coloured_share`, `warm_cool`, `flow`, `frame_difference`, `jumps`, `activity` with four decimals (`-` for unknown). The header lists every group and option (`#group`, `#option`) and the columns (`#columns`); the app builds the Mood panel from the header, so new groups need no code change.

`manifest.json` records `schema`, `version`, `source: static-analysis`, `static_evidence_sha256`, `producer` (copied from the evidence), `definition_sha256`, `presets_idx_sha256`, `attributes_sha256`, `preset_count`, `measured_count` (rows with any value), `analysis_errors` and `option_counts`.

## The recipe

The recipe is the engine-neutral description of one preset. Top level:

| Field | Meaning |
|---|---|
| `policy` | `preset-visual-recipe-v1` |
| `preset` | `name` and `sha256` of the preset |
| `conventions` | The conventions above |
| `description` | A generated prose summary of constructions and colour ingredients (about 3 KB) |
| `render` | How the picture is built: feedback, layers, composite, mechanisms, audio, randomness, mirrors, textures, palette |
| `display_estimate` | Calibrated estimates of what the engine shows, with intervals |
| `facets` | Mood options and values for this preset |
| `intent` | What the preset is *for*: named effects, audio reactivity, palette and energy character |
| `mood` | An older approximate feature vector, kept for reference (not used by the Mood table) |
| `limitations` | What the recipe does not capture |
| `uses_rendered_images` | Always `false` |
| `program` | Only with `--include-program`: the parsed equations and shaders for an exact port |

### `render.feedback`

| Field | Meaning | Fire and Brimstone |
|---|---|---|
| `decay` | The decay applied each frame, when the engine applies it (null with a custom warp shader, which replaces decay) | `null` |
| `stored_level_halving_steps` | Frames for a stored 8-bit level to halve under decay | `null` |
| `stored_level_floor` | The highest stored level that never decays (the faint residue) | `null` |
| `warp_patterns` | Recognised motion patterns of the mesh warp, each with its control, value range and direction (see below) | radial zoom profile |
| `warp_controls` | Per control (`zoom`, `zoomexp`, `rot`, `warp`, `cx`, `cy`, `dx`, `dy`, `sx`, `sy`): `uniform` (same at every vertex), `value_range`, and `terms` (constant, time, audio or per-pixel parts) | zoom constant 0.99853 |
| `shader_advection` | Sample offsets in the warp shader that move content by the image itself: `stage`, `offset_range_uv` (as fractions of the screen), `evidence` | ±0.06 in u and v |
| `ray_sampling` | Set when the warp reads one source point per ray through a centre (every frame becomes converging rays) | `null` |
| `warp_detail_response` | The warp evaluated on grey multi-scale noise: `mean_luma`, `mean_saturation`, `coloured_share`, `hue_shares`, and its `input` (kind, level 0.5, amplitude 0.2, smoothing 1/4/16 px, 480×270, t = 5 s) | luma 0.51, coloured 0.09 |
| `warp_detail_gain` | The warp on dim noise: `gain` above 1 means small structure grows each frame; `flat_out` is the output level for flat input | gain 1.08 |
| `flat_field` | The state a flat canvas settles to under the warp, when known | `null` |
| `warp_transfer` | The warp evaluated on flat colours (see below) | channel-selective |
| `evidence` | Pointers to the summary facts used | |
| `steady_state` | The feedback equilibrium (see below) | yellow |

**`warp_patterns` entries** have a `pattern` name (`radial_zoom_profile`, `uniform_rotation`, `spatially_varying_rotation`, `uniform_translation`, `translation_component`, …), the `control` it comes from and its ranges. For a zoom: `value_range`, `zoomexp_range`, `effective_zoom_range`, `content_motion` ("contracts toward the screen centre" or "expands …"), `percent_per_step_range` (−0.149 to −0.145 for Fire and Brimstone: 0.15% inward per frame; −9.9 to −1.9 for the particle storm) and `audio_inputs` (bands that change it). For a rotation: `value_range_radians_per_step` (±0.315 rad per frame for the particle storm).

**`warp_transfer`** fields:

| Field | Meaning |
|---|---|
| `gain_rgb`, `offset_rgb` | Per-channel gain and offset for uniform content per frame: `[0.994, 0.97, 0.85]` and `[0.006, 0.03, 0.008]` |
| `linear` | Whether output is proportional to input over all probed levels |
| `halving_frames` | Frames for uniform content to halve (null when it does not fade to half) |
| `steady_level_from_full` | The level a full-brightness canvas settles at |
| `channel_selective` | True when channels persist differently; read `per_channel` then |
| `per_channel` | `r`, `g`, `b` each with `gain`, `linear`, `halving_frames`, `steady_level_from_full`. Fire and Brimstone: blue halves in 4.3 frames and settles at 0.053, red and green settle at 1.0 |
| `wrap` | Set when the warp takes a modulo: levels shift by `shift_per_frame` and wrap every `cycle_frames` (continuous colour cycling) |
| `retention_by_level` | For nonlinear transfers: the fraction kept at each level (above 1 means dim levels are lifted) |
| `levels`, `rgb` | The 11 probe levels and the RGB output for each |
| `source` | `exported warp shader evaluated on flat colours` |

**`steady_state`** fields:

| Field | Meaning |
|---|---|
| `canvas_local_rgb` | Equilibrium canvas colour where elements keep drawing |
| `display_local_rgb` | The same through the composite (what you would see there) |
| `display_spread_rgb` | Equilibrium if the drawn energy were spread over the whole screen |
| `hue_family` | The equilibrium's hue family (`yellow` for Fire and Brimstone) |
| `composite_model` | How the composite was applied (`composite_transfer`, legacy controls, …) |
| `substitution_count` | How many unknown element colours were replaced by neutral priors |
| `level_note` | Reminder that the level is a lower bound for bright presets; use `display_estimate` for brightness |
| `source` | `feedback_equilibrium steady state (source facts, no frames stepped)` |

### `render.layers`

One entry per stage or element, in drawing order: `mesh_warp`, `builtin_wave`, `wave_0`…`wave_3`, `shape_0`…`shape_3`, `shader_warp`, `shader_composite`.

| Field | Meaning |
|---|---|
| `id`, `stage` | Layer id and stage (`mesh_warp`, `drawing`, `warp`, `composite`) |
| `mechanisms` | Mechanism names recognised in this layer |
| `evidence` | Pointers to the element facts |
| `constants` | Constant settings: for a shape `sides`, `instances`, `x`, `y`, `rad`, `ang`, inner colour `r g b a`, outer colour `r2 g2 b2 a2`, border colour, `tex_zoom`, `tex_ang`; for the mesh warp `zoom`, `zoomexp`, `rot`, `sx`, `sy`, `warp` |
| `controls` | Per animated control: `control` name, `control_unit`, `curve_kind` (`constant`, `periodic`, `audio`, …), `constant_value`, `nominal_value_range`, `maximum_absolute_control_rate_per_second`, and the `expression` graph |
| `colour` | `mode_code`, `palette_diversity`, `constant_rgb` and `guaranteed_visible` (whether the element is certain to show) |
| `point_cloud` | For custom waves: `points_per_frame` (512), `sample_grid`, `colour_resolved`, `authored_rgba`, `hue_family_shares`, `mean_rgb`, `mean_alpha`, `mean_saturation`, `positions_closed_form`, `position_bounds`, `frame_inputs` (per-frame state the points read) and the per-point `programs` |

### `render.composite`

| Field | Meaning |
|---|---|
| `flat_transfer` | Displayed colour for each of 11 flat canvas `levels`, at three `times` (2, 5, 8 s): `rgb` (mean), `rgb_spread` (movement between times), `time_varying`, `nonfinite_share` (pixels with undefined output), `output_undefined`, `flat_areas_only` (relief composites only show edges) |
| `detail_response` | The composite on grey multi-scale noise: `mean_rgb`, `mean_luma`, `mean_saturation`, `coloured_share`, `hue_shares` and the `coloured_rule` used (saturation ≥ 0.25 and max channel ≥ 0.10) |
| `colour_matrix` | `level` (0.3), `black_rgb` and `columns_rgb`: displayed RGB ≈ `black_rgb + Σ (input_c / level) · columns_rgb[c]`. An identity-like matrix (Fire and Brimstone) passes colours through; off-diagonal entries mean channel mixing |
| `per_load_random` | Composite switches drawn once per load (`rand_preset`), each branch with `probability_true` |
| `hue_shader` | Set when the composite multiplies by projectM's hue shader |

### `render.mechanisms`, `audio_bindings`, `random_redraws`, `mirrors`, `random_textures`

- **`mechanisms`**: every recognised construction with `mechanism`, `stage`, `parameters` and `evidence`. Examples: `builtin_wave_primitive` (`mode`, `dots`), `polygon_shape_primitive`, `custom_wave_primitive`, `point_cloud_primitive`, `radial_feedback_transform`, `blur_difference_feedback`, `gradient_driven_advection`, `image_driven_advection`, `noise_driven_advection`, `gradient_relief`, `angular_mirror_fold`, `cartesian_mirror_fold`, `repeat_tiling`, `polar_radial_sampling`, `nonlinear_feedback_map`, `complex_quadratic_recurrence`.
- **`audio_bindings`**: which element (`layer`) is driven by which `input` (`bass`, `mid`, `treb`, their `_att` variants, `waveform`) into which `target` (`opacity`, `size`, `position`, `colour`, …), with `linear_gain` when it is a simple multiple. The particle storm binds bass and mid to shape opacity.
- **`random_redraws`**: per-frame state redrawn with `rand` when a condition fires: `states`, `feeds` (the `q` values that carry the draws to shaders and elements), `event_times_s` and `period_s` when known, and a `note`. Fire and Brimstone redraws `q2`–`q7` at unknown times: colours that read them are a random draw.
- **`mirrors`**: `operators`, `flip_directions`, `fold` (number of mirror sectors), `symmetry_score` (0 to 1, an upper estimate) and `conditions` explaining why the symmetry is exact or not.
- **`random_textures`**: shader slots that sample a random library texture (`sampler_rand00`…), with the candidate textures.

### `render.display_palette`

| Field | Meaning | Fire and Brimstone |
|---|---|---|
| `hue_shares` | Pooled share per hue family | green 0.36, red 0.28, yellow 0.27, orange 0.05, pink 0.03 |
| `palette` | Families with share ≥ 0.10 | green, red, yellow |
| `dominant_hue` | Main colour, or null | null |
| `monochrome` | True when the Monochrome classifier admits the preset (palette then empty) | false |
| `dominance` | Share of the top family | 0.49 |
| `sources` | Which sources contributed, each with `weight` and `leading` family | calibrated hue (24, green), steady state (1.5, yellow) |
| `random_tint` | True when colours are drawn per load | false |
| `method` | The pooling rule and weights | |

### `display_estimate`

The calibrated estimates ([From estimates to moods](mood-table.md#2-the-calibration-model)).

| Field | Meaning |
|---|---|
| `policy` | `source-calibrated-display-estimate-v1` |
| `statistics` | One entry per target, each `{value, interval, oof_spearman, evidence, label_source}`; classifier targets add `threshold` |
| `activity` | `activity` (0–1 percentile), `activity_interval`, `bands` (Energy options the value falls in), `possible_bands` (options within the interval), `certain_bands`, `remapped` |
| `reference` | The ruler conditions the estimates are calibrated to |
| `note` | "Calibrated from static source facts; intervals are the 10th–90th percentile out-of-fold residuals; not a rendered measurement of this preset" |

The 29 statistics:

| Statistic | Meaning | Fire and Brimstone |
|---|---|---|
| `mean_luminance` | Mean brightness | 0.49 (0.31–0.71) |
| `mean_abs_frame_difference` | Mean change between frames | 0.034 |
| `mean_flow_screen_widths_per_s` | Motion speed | 0.095 |
| `global_brightness_jumps_per_10s` | Whole-screen jumps per 10 s | 0.0 |
| `mean_saturation` | Mean saturation | 0.80 |
| `warm_cool` | Warm/cool balance | 0.45 |
| `coloured_share` | Coloured fraction | 0.83 |
| `hue_share_red` … `hue_share_pink` | Share of each family among coloured pixels | green 0.33, red 0.26, yellow 0.19 |
| `hue_top_share` | Share of the top family (also sets the palette sharpening `sharpening_power`) | 0.49 (power 1.5) |
| `no_strobe_probability` | Probability of fewer than 1 jump per 10 s | 0.926 (just under the 0.93 gate) |
| `facet_<option>_probability` (12) | Probability per option for dark, bright, monochrome, pastel, warm, cool, still, chill, intense, balanced, drifting, normal, each with its `threshold` | warm 0.82 (threshold 0.51), chill 0.59 (0.69) |

Reading the example: Fire and Brimstone's No strobe probability (0.926) falls just short of the 0.93 gate, so it is **not** admitted to No strobe even though its jumps estimate is 0. Its Chill probability (0.59) is below its threshold (0.69), so the Chill classifier on its own would not admit it; Chill in its options comes from the value rule on activity, which the classifier then confirms or overrides according to the decision steps on the [mood page](mood-table.md#option-classifiers).

### `facets`

The mood options for the preset: `policy` (`preset-facets-v1`), `definition_sha256`, `evidence` and `style_evidence` (what the options rest on), `options`, `possible_options` (options whose rule changes inside the interval), `unresolved_options` (options that need an unknown value), `style`, `values` (the eight values, each with its evidence) and `measurement`.

For a bundled preset the recipe tool reports the options of the bundled table; the static export removes the preset's identity before calling it, so the evidence always holds the static decision.

### `intent`

What a person or another engine should rebuild:

| Field | Meaning |
|---|---|
| `effects` | Named effects with parameters (catalogue below) |
| `reactivity` | Per audio route: `band`, `layer`, `target`, `kind` (`brightness`, `shape`, `motion`, `colour`), `smoothed`, `linear_gain`, `response` (`continuous` or `threshold_or_clamped`) |
| `palette` | `warm_cool`, `saturation`, `hue_variety_bins`, `hue_cycle_per_s`, `background_rgb` from source facts |
| `energy` | `intensity` and `smoothness` scores (0–100) and style `tags` from the older mood layer |
| `guidance` | "Rebuild the listed effects at any resolution and frame rate in a modern engine; keep the reactivity map … and the palette/energy character. Exact pixels are not a goal." |

**Effect catalogue**:

| Effect | Parameters | Meaning |
|---|---|---|
| `trails` | `half_life_s`, `decay_per_frame`, `faint_residue` | Feedback persistence. Particle storm: half-life 1.8 s |
| `zoom_flow` | `percent_per_frame`, `direction` | Mesh zoom toward or away from the centre |
| `rotation_flow` | `radians_per_frame` | Mesh rotation |
| `drift` | `axis`, `pixels_per_second` | Translation |
| `radial_streaks` | `direction`, `half_life_frames`, `spiral`, `condition` | Detail smeared along rays by a strong one-way zoom |
| `radial_rays` | `screen_share`, `centre_xy`, `centre_moves`, `condition` | Every frame becomes rays converging on a centre |
| `level_cycling` | shift and cycle | Colours cycle through the whole range (modulo warp) |
| `kaleidoscope`, `mirror`, `mirror_symmetry` | `sectors` | Mirror folds |
| `tiling` | `mirrored` | Repeated tiles |
| `polar_tunnel` | `radial_mapping` (e.g. `reciprocal_radius`) | Tunnel by polar sampling |
| `swirl`, `rotation`, `spatial_rotation`, `angular_warp`, `periodic_wobble` | | Shader-level twists and wobbles |
| `self_advection`, `reaction_diffusion_flow`, `noise_turbulence` | `stage` | Content moved by itself, by its gradients, or by noise |
| `pattern_growth` | `channels`, `fine_levels`, `coarse_levels` | Fine-minus-coarse blur that grows structure |
| `relief` | `directions` | Embossed edges |
| `blur` | taps and radii | Neighbourhood blur |
| `recursive_copies` | `copies`, `scales` | Several scaled copies of the previous frame |
| `fractal_feedback`, `julia_fractal`, `mandelbox_fractal` | `construction` | Fractal constructions |
| `feedback_scale` | `scale` | Shader-level zoom of the feedback |
| `glow_spots`, `stripes` | | Periodic glows and bands |
| `palette_map` | | The composite remaps levels to a palette |
| `echo_double` | | Video echo: a second, scaled copy |
| `frame_copy` | `layer`, `tex_zoom`, `tex_angle_rad`, `condition` | A textured shape that redraws the previous frame |
| `vector_grid` | | Motion vectors |
| `audio_waveform` | `form`, `position`, `colour_cycles` | The built-in waveform (`two_channel_parallel_traces`, `stereo_xy_trace`, …) |
| `custom_waveform` | `points_per_frame`, `hue_family_shares`, `mean_alpha`, `position_bounds` | A custom wave |
| `parametric_curve` | | A custom wave recognised as a circle or spiral |
| `shapes` | `sides`, `instances`, `radius`, `moving` | Custom shapes |
| `random_redraw` | `feeds`, `first_s`, `period_s` | Values redrawn at random |
| `per_load_variant` | branches | A choice made once per load |

### `mood` (reference only)

An earlier research layer: 23 features (`motion.speed_p95_vp_s`, `flash.coherent_transitions_hz`, `palette.effective_hue_bins`, `structure.symmetry`, …), each with `value`, `interval`, `evidence` and `evidence_paths`, plus scores (`intensity`, `smoothness`, `psychedelic`, `warm`, `cold`) and suitability per listening profile (`ambient-v1`, `techno-v1`, `gentle-home-tv-v1`, …). Its own `limitations` say it is built on editable assumptions and not calibrated against viewers. **The Mood table does not use it.**

## Expression graphs

Wherever the recipe carries an `expression` or `programs` entry, it is a dataflow graph:

```json
{"root": 0,
 "nodes": [{"op": "constant", "dtype": "float", "args": [], "detail": {"value": 0.5}}],
 "resources_resolved": true, "complete": true}
```

`nodes` is a list of operations (`constant`, `input`, arithmetic, comparisons, `if`, function calls such as `sin`, `pow`, texture lookups); `args` are indices into `nodes`; `root` is the result. `complete` is false when part of the program could not be exported, and `resources_resolved` is false when it reads something the analysis could not resolve (a random texture, memory written elsewhere). The core recipe removes these graphs; the full recipe keeps them so a port can evaluate controls exactly.

## The prediction record

Next to every prediction image (`prediction.json`):

| Field | Meaning |
|---|---|
| `policy` | `sdk-prediction-illustration-v1` |
| `summary_sha256`, `illustrator_sha256`, `image_sha256` | Hashes of the input summary, the illustrator code and the image |
| `declared_time_seconds`, `history_steps` | 5.0 and 150 |
| `drawn_components` | Elements drawn (e.g. `wave_0`, `wave_1`) |
| `limitations` | What the drawing omits or approximates ([full list](prediction-images.md#recorded-limitations)) |
| `uses_rendered_images`, `reads_preset_source` | Both false |
| `evaluates_exported_closed_form_graphs`, `graph_evaluation_scope` | Which exported programs were evaluated |
| `declared_audio_sha256` | Hash of the declared audio |

## The self-comparison record

| Field | Meaning |
|---|---|
| `checkpoint`, `preset` | Checkpoint id and preset |
| `frozen_before_capture` | Hashes of the prediction, its record, the summary, the recipe and the look description, taken before the render |
| `capture_result_sha256` | Hash of the capture record |
| `review_measurements_v1.prediction_luma`, `screenshot_luma` | Single-frame mean brightness |
| `mean_rgb_prediction`, `mean_rgb_screenshot` | Single-frame mean colour |
| `blurred_luma_correlation` | Layout agreement of the two single frames |
| `time_average_frames_60_149` | `luma`, `saturation` (prediction, render) and the `blurred_luma_correlation` of the time-averaged pictures |
| `mean_abs_frame_difference_60_149` | How busy each is (prediction, render) |
| `agreements`, `misses`, `verdict` | The reviewer's findings |
