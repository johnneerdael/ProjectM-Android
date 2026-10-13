# Preset predictor export contract

Contract: **source feature record schema 1**. Documentation snapshot: 2026-10-08,
producer source checkpoint `587e3f53`, with guide synchronized from remote main
`af164a97896646427f971ecbed8161f8d35c2fec` before this page was added.

This reference documents the **existing output**, not a new renderer or scene
format. It is intended for a Rust/wgpu consumer that makes a semantic adaptation:
use supported behavior as a visual brief, then choose an original native-4K scene.
The 47 simulated features provide a useful behavioral brief. A faithful adaptation
of a particular preset also needs semantic element/effect descriptors; it does
not require exporting the original shader program or pixel-identical geometry.

## 1. Choose the export

| Producer | Result | Schema/version | Current contents |
|---|---|---|---|
| `source_extract.py` / `strict_features(...)` | UTF-8 JSON file | `schema_version: 1` | 11 strict features; equations, custom-shape trajectory summaries, sparse built-in warp queries, supported uniform-composite palette evidence. No display fields. |
| `forecast_source(...)` → `report["source_features"]` | JSON-compatible dictionary | `schema_version: 1` | 47 features combining strict shape summaries and simulated display statistics. No captured/native reference images feed the prediction. |
| `forecast_source(...)` complete return | Python dictionary | **No top-level schema version** | Context, stage selection, descriptors, Q/custom state trace and optional NumPy surfaces. An experimental diagnostic API, not a stable scene interchange format. |
| `source_classify.py` | UTF-8 JSON file | `schema_version: 1`, `model_id: source-moods-assumed-v1` | Preference scores/intervals, bands, tags and profile suitability. These are assumed scoring mappings, not render instructions. |

Strict and simulated records share the envelope below, but have different feature
sets and evidence. `retain_surfaces=False` still simulates fields: it only removes
arrays from returned frames after descriptors are calculated. It does not convert
simulation into strict extraction. The shipped measured preset collections are a
separate product/export and should not be mistaken for these predictor records.

## 2. Exact feature-record envelope

All nine root keys currently emitted are required:

| JSON path | Type | Meaning |
|---|---|---|
| `schema_version` | integer, exactly `1` | Feature-envelope version. Reject unknown versions rather than guessing. |
| `feature_basis` | string enum | `strict-source-no-display-frames` or `source-field-simulation`. |
| `context` | object | Input identities, provenance, domain and extractor identity. |
| `context_sha256` | lowercase 64-character hex string | Digest of `context`, including extractor identity. |
| `features` | object: literal string key → feature object | Keys such as `geometry.speed_p95` are **flat strings containing dots**, not nested objects. |
| `uses_rendered_reference` | boolean, `false` | This source export consumes no native rendered reference. Simulation can still compute its own display fields. |
| `appearance_accuracy_verified` | boolean, `false` | The record itself does not certify appearance accuracy. Separate controls do not turn every record into a certificate. |
| `limitations` | array of strings | Producer's scope and unsupported-evidence statements. |
| `record_sha256` | lowercase 64-character hex string | Digest of the complete record with only this key omitted. |

The companion [JSON Schema](export-contract/source-feature-record.schema.json)
documents the envelope and scalar/event shapes. It permits additional properties
so additive metadata can be retained. It does **not** validate hash correctness,
visibility, physical ranges for each individual metric, event chronology or proof
claims. Use the reference guards as well. Current producers emit null intervals;
the schema also accommodates the interval form accepted by the scoring consumer.

### A scalar feature

This is an actual feature from the strict example; it is an excerpt, not a complete
hash-verifiable record:

```json
{
  "value": 0.060000178814104854,
  "unit": "normalized viewport coordinates/s",
  "evidence_kind": "sampled-source-geometry",
  "status": "computed",
  "interval": null,
  "interval_kind": null,
  "support": {
    "sample_count": 145,
    "scope": "custom shape fan vertices",
    "method": "consecutive-vertex divided differences; equal vertex weighting",
    "budget_exceeded": false,
    "derivative_sample_budget": 1000000,
    "visibility_established": false
  },
  "dependencies": [
    "executed equation geometry",
    "declared time schedule",
    "component and vertex identity"
  ],
  "unknown_reasons": []
}
```

`status` is `computed` or `unknown`. An unknown scalar has `value: null` and one or
more reasons; a computed stationary quantity can be genuinely zero. Preserve that
distinction. `support` is producer-specific metadata, not a confidence probability.
`dependencies` names calculation inputs; it is not a complete bass→parameter
causal graph. Intervals, when supplied to scoring by another producer, are bounds
with declared evidence, not automatically calibrated confidence intervals.

Current feature evidence kinds are `sampled-source-geometry`, `source-point-query`
and `source-field-statistic`. Do not relabel the latter as strict source evidence.

### Context and identity

`context` always contains `input_hashes`, `provenance`, `domain` and
`feature_extractor_sha256`.

`input_hashes` has these eight required keys:

```text
preset_sha256          exact .milk bytes
parsed_source_sha256   parsed values + sections + parser_inputs
pcm_sha256             declared PCM input identity
audio_sha256           complete declared audio report
domain_sha256          complete declared domain payload
compatibility_sha256   compatibility/descriptor evidence payload
random_sha256          explicit random-input identity, or null
materials_sha256       material/procedural-array identity, or null
```

Strict extraction currently sets both random/material identities to null. This
means **no supplied identity**, not proof that the program is independent of these
inputs. Every other input hash must be a lowercase 64-character digest.

Minimum `provenance` contains `engine` (`commit`: 40 hex characters and
`patches_sha256`: 64), `engine_archive_sha256`, `model_sha256` and
`reader_sha256`. Simulated records additionally require `wave_binary_sha256`.
Actual provenance is extensible: current records include `model_modules` and
policy/precision/asset/initialization information. Keep it rather than collapsing
it into a bare engine version. A source CPU archive hash is not a published AAR
hash; exact released artifacts are pinned separately in the producer profiles.

`domain` is an extensible object with a required `profile` and the producer's
requested dimensions, mesh, time/query/RNG/render settings. Its contents are
producer-specific and participate in identity. In the authored/native forecast,
width/height describe native render size; `physical_size` can differ and
`provenance.authored_detail_context` records authored and initial shader sizes.
The strict extractor has its own width/height/query scope; it does not inherit all
full-forecast Native4K or numeric policies merely because the engine hash matches.

### Hash encoding (important for Rust)

The reference digest is SHA-256 over UTF-8 bytes of:

```python
json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
```

Python's default `ensure_ascii=True` still applies: Unicode is escaped. Object
keys are sorted recursively, whitespace is removed, array order is preserved,
and the reference number spelling is Python's. This is **not RFC 8785/JCS**.
A generic Rust JSON serializer can differ in Unicode escapes, exponent spelling
or integer/float representation. Do not claim verification by hashing arbitrary
re-serialization. Match the reference encoding or verify through the reference
Python consumer; preserve original records unchanged as the exchange artifact.
Digest identity alone is not authentication of an external producer's claims.

## 3. Complete currently emitted feature catalog

Strict emits 11 entries; the simulated adapter emits 47, including one event array.
The union has 52 literal keys. This table is generated from the current producers
and real examples. A consumer should tolerate additive keys but require support
for the specific keys it actually uses.

| Literal key | Unit | Producer |
|---|---|---|
| `colour.hue_rate_p95_cycles_s` | hue cycles/s | simulated |
| `colour.maximum_hue_rate_cycles_s` | hue cycles/s | simulated |
| `colour.mean_coloured_fraction` | screen fraction | simulated |
| `colour.mean_contrast` | encoded RGB luma standard deviation | simulated |
| `colour.mean_effective_hue_bins` | effective hue bins | simulated |
| `colour.mean_hue_entropy_nats` | nats | simulated |
| `colour.mean_hue_query_support` | matched chromatic-query fraction | simulated |
| `colour.mean_luma` | encoded RGB luma | simulated |
| `colour.mean_saturation` | HSV saturation | simulated |
| `colour.temporal_effective_hue_bins` | effective hue bins | simulated |
| `colour.temporal_hue_entropy_nats` | nats | simulated |
| `colour.warm_cool` | warm/cool sector coordinate −1…1 | simulated |
| `flashing.coherent_brightening_transitions` | sampled transitions | simulated |
| `flashing.coherent_darkening_transitions` | sampled transitions | simulated |
| `flashing.coherent_transitions_per_second` | sampled transitions/s | simulated |
| `flashing.dominant_sampled_brightness_hz` | Hz | simulated |
| `flashing.events` | correlated sampled transition records | simulated |
| `flashing.frequency_resolution_hz` | Hz | simulated |
| `flashing.local_or_colour_change_transitions_per_second` | sampled transitions/s | simulated |
| `flashing.measured_duration_seconds` | s | simulated |
| `flashing.nyquist_hz` | Hz | simulated |
| `flashing.peak_brightening_screen_area` | screen fraction | simulated |
| `flashing.peak_brightness_change_area` | screen fraction | simulated |
| `flashing.peak_darkening_screen_area` | screen fraction | simulated |
| `flashing.peak_mean_luma_jump` | encoded RGB luma | simulated |
| `flashing.peak_paired_luma_area_product` | encoded RGB luma × screen fraction | simulated |
| `flashing.peak_rgb_change_area` | screen fraction | simulated |
| `flashing.peak_visible_brightening_fraction` | visible-content fraction | simulated |
| `flashing.peak_visible_darkening_fraction` | visible-content fraction | simulated |
| `flashing.spectral_peak_fraction` | power fraction | simulated |
| `geometry.acceleration_maximum` | normalized viewport coordinates/s² | strict, simulated |
| `geometry.acceleration_p95` | normalized viewport coordinates/s² | strict, simulated |
| `geometry.jerk_maximum` | normalized viewport coordinates/s³ | strict, simulated |
| `geometry.jerk_p95` | normalized viewport coordinates/s³ | strict, simulated |
| `geometry.speed_maximum` | normalized viewport coordinates/s | strict, simulated |
| `geometry.speed_p95` | normalized viewport coordinates/s | strict, simulated |
| `motion.available_transition_fraction` | transition fraction | simulated |
| `motion.matched_brightness_change_p95` | encoded RGB luma | simulated |
| `motion.mean_acceleration_viewports_per_second_squared` | normalized viewport coordinates/s² | simulated |
| `motion.mean_supported_area` | screen fraction | simulated |
| `motion.mean_warp_query_displacement` | normalized viewport coordinates | simulated |
| `motion.median_speed_viewports_per_second` | normalized viewport coordinates/s | simulated |
| `motion.p95_speed_viewports_per_second` | normalized viewport coordinates/s | simulated |
| `motion.peak_matched_brightening_screen_area` | screen fraction | simulated |
| `motion.peak_matched_brightness_change_p95` | encoded RGB luma | simulated |
| `motion.peak_matched_darkening_screen_area` | screen fraction | simulated |
| `motion.peak_untracked_brightness_change_screen_area` | screen fraction | simulated |
| `palette.coloured_support` | screen fraction | strict |
| `palette.effective_hue_bins` | effective hue bins | strict |
| `palette.warm_cool` | warm/cool sector coordinate −1…1 | strict |
| `warp.query_displacement_maximum` | normalized viewport coordinates | strict |
| `warp.query_displacement_mean` | normalized viewport coordinates | strict |

### Units and interpretation

- X and Y are fractions of viewport width and height. A velocity norm is in
  this coordinate system; it is not pixels/s, meters/s or degrees/s. Conversion
  to pixels must account for the two axes separately; a scalar norm alone cannot
  recover direction or a 4K displacement vector.
- Shape speed/acceleration/jerk summarize vertices, with equal vertex weighting.
  They do not establish visibility, occlusion or whole-preset activity. Births,
  deaths and topology changes live in the optional geometry summary, not the
  strict feature envelope as complete renderable objects.
- Encoded RGB luma is a display-value statistic, not physical light output or a
  scene-linear luminance quantity. HSV saturation and screen-area fractions are
  dimensionless. Effective hue bins are `exp(entropy)`; entropy is in nats.
- Warm/cool uses −1=cool, +1=warm, with a documented sector convention. It is
  not an RGB palette, Kelvin temperature or audience preference probability.
- Sampled transition rates describe the declared window. They do not prove
  future flash absence, beat synchronization or medical safety.

### `flashing.events`: the non-scalar exception

Its `value` is null when unknown, or an array containing one record per measured
transition. Each record has exactly these currently produced fields:

```text
start_time, end_time, dt                  numbers, seconds; dt > 0
signed_mean_luma_delta                    signed number
brightening, darkening, rgb               region objects
coherent_up, coherent_down                booleans
motion_crossing_ruled_out                 boolean (currently false)
```

Each region has `area` (0…1 screen fraction), `mean_amplitude` and
`maximum_amplitude`. Empty regions have null amplitudes. RGB amplitude is the
largest absolute channel change; brightening/darkening use signed encoded-luma
change converted to a nonnegative magnitude. Consecutive events join at the same
timestamp. A coherent brightness change can still be a moving edge: the exporter
does not set `motion_crossing_ruled_out=true` or label each event as a flash/beat.

## 4. Full forecast diagnostic return

The complete dictionary currently has these 17 root keys:

```text
status, frames, domain, stage_resolution, feature_basis,
geometry_features, visibility_frames, source_proofs,
source_equation_states, descriptors, uses_rendered_reference,
appearance_accuracy_verified, input_hashes, provenance, limitations,
prediction_basis, source_features
```

The return currently has no root `schema_version`.
Use the versioned `source_features` member for interoperable evidence.

`status` is `computed` on successful return. Unsupported math/context or missing
resources normally raise an exception; there is no guaranteed JSON failure record
containing a fake zero rank.

With retained surfaces each frame contains:

| Key | Type / size | Meaning |
|---|---|---|
| `frame` | integer | Source frame identifier; use recorded IDs, not an assumed zero-based sequence. |
| `time` | number, seconds | Declared sampled time. |
| `display` | NumPy float32 `[display_height, display_width, 4]` | Normalized RGBA after composite/optional physical blit. |
| `feedback` | NumPy float32 `[native_height, native_width, 4]` | Native pre-composite feedback, not display; authored recurrence remains separately owned internally. |
| `warp_uv` | float32 `[native_height, native_width, 2]` or `None` | Dense sampling UV field when evaluated; Standard can omit native warp. |
| `history` | object | Phase/source ages, policies, canvas and gain metadata; extensible. |
| `visibility` | object | Sampled display-presence statistics, not a whole-program proof. |

`retain_surfaces=False` omits `display`, `feedback` and `warp_uv` from retained
frames while keeping metadata and calculated statistics. Surface arrays are
**not JSON serializable directly**. The current tooling stores them separately
as raw RGB8/NPZ or drops them from diagnostic JSON. There is no stable built-in
NPZ/blob transport contract. Arrays use top-row-first logical storage; shader UV
conventions are explicit and stage-dependent, so a new renderer must not apply
one blanket Y flip. RGB8 comparison artifacts exclude alpha; they are validation
outputs, not the source feature record.

`source_equation_states.states[]` contains `frame`, `eel_frame`, `time`, `q`
(`q1`…`q32`) and `custom` (main custom locals). This is a sampled trace, not live
animation equations or the shape/wave vertex stream. Some equation-state values
can use tagged IEEE dictionaries such as `{"ieee":"nan"}`; preserve
producer tagging rather than forcing every value into finite JSON f64.

`stage_resolution` identifies selected custom/fixed/legacy/default/unknown stages
and their compatibility context. `source_proofs` records untouched-Q analysis;
absence from a proof is unknown, not proof of influence. `prediction_basis` is
normally `independent-source-math`, with a distinct source-with-measured-operator
label when that optional numerical backend is used. This does not imply native
frames supplied the prediction.

## 5. Optional preference-score export

`source_classify.py` consumes the feature record; it does not execute the preset.
Its output currently includes:

```text
schema_version, model_id, model_status, scoring_source_sha256,
scoring_sources_sha256, feature_record_sha256, context_sha256,
feature_basis, scores, bands, ambiguous_bands, tags, chill_constraints,
profile_sha256, profile, limitations
```

`scores` has intensity, smoothness, warm, cold and psychedelic. Values can be null
when only an interval is supported. Activity intensity is 1…100; the other axes
are 0…100. Bands are inclusive Chill1–30, Normal25–75 and Intense70–100 with
additional support/bound requirements. Existing real examples may have no bands
and `profile.eligible=false`. These are explicit preference assumptions, not
verified descriptions of scene topology. See [SOURCE_SCORING.md](SOURCE_SCORING.md)
for exact formulas, aliases, thresholds and requirements.

### Custom warp persistence (`render.feedback.warp_transfer`)

When the decay control does not reach the canvas (a custom warp shader:
projectM returns the shader's colour unchanged), `render.feedback.decay` is null
and `warp_transfer` holds the exported warp shader evaluated on flat colours
(levels 0–1, neutral bands, times 2/5/8 s): `levels`, mean output `rgb` per
level, `gain_rgb` = W(1) − W(0), `offset_rgb` = W(0) and `halving_frames` =
ln 0.5 / ln(mean gain) for uniform content (null when the gain is not in
(0, 1)). The `trails` intent entry uses it when decay is null. `linear` says
whether the table is affine within 0.02. For a nonlinear table,
`retention_by_level` lists W(c)/c, `halving_frames` counts the iterations of
the channel-mean table from full level down to half, and
`steady_level_from_full` is where that iteration settles. `per_channel` gives
the same `gain`, `linear`, `halving_frames` and `steady_level_from_full` for each
of `r`, `g` and `b`. When the channel gains differ by more than 0.1,
`channel_selective` is true and the channel-mean `halving_frames` and
`steady_level_from_full` are null (no single persistence describes the canvas);
the `trails` intent then takes the longest-lived channel. `wrap` (or null)
reports a modulo transfer: interior levels shift by a constant
`shift_per_frame` while the end the shift runs into jumps to the other end, so
levels cycle every `cycle_frames` = 1/|shift|; `halving_frames` and
`steady_level_from_full` are then null and the intent gains a `level_cycling`
effect (`cycle_s`). It is the shader's
arithmetic on uniform inputs, not a measured trail length; image structure,
blur and injected terms can change local persistence.

`render.feedback.steady_state` holds the `feedback_equilibrium` settled colour:
`display_local_rgb` (energy kept where drawn), `display_spread_rgb` (mixed over
the screen), `canvas_local_rgb`, `hue_family` (null below 0.02),
`composite_model` and `substitution_count` (neutral colour priors used). It is a
hue cue; its level is a lower bound, and brightness comes from `display_estimate`.

Built-in wave layers carry `builtin_wave.effective_base_radius_model_units` for
modes 0 and 1: `base_radius_model_units` plus the normalised `wave_mystery`
(projectM `Circle.cpp`/`XYOscillationSpiral.cpp` add it to every vertex radius;
a negative value draws the same ring through the opposite side of the centre).
When the material maximises colour (`colour.max_normalised`, `bMaximizeWaveColor`),
`colour.max_normalise_rule` states projectM's gate (`Waveform.cpp`): a largest
channel above 0.01 divides every channel by it; otherwise the authored values
are drawn unchanged. Channels without a time-only expression carry their
band-driven `frame_expression` and `value_at_unit_bands` (every band and
attenuated band at 1, projectM's long-run normalisation).

The warp mechanism `blur_difference_feedback` (intent effect `pattern_growth`)
is reported when an output lane of the custom warp linearly adds a finer level
of the fed-back image (main = level 0, blur1–3) and subtracts a coarser level.
Its parameters are `lanes` (0–2 for r, g, b), `fine_levels`, `coarse_levels` and
`flat_gain_by_lane` (sum of the lane's sample coefficients: the gain on flat
content). Component selections and constant blur decodes are looked through;
nonlinear products do not count. It is a source construction: how far the
patterns spread depends on seeds, retention and clamping.

Custom-wave point clouds: per-point programs export up to 1,024 graph nodes
(other controls keep 256). A record whose colour graphs cannot be resolved but
whose positions can keeps `positions_closed_form`, the resolvable programs and
`positions_only: true` (status stays `unknown`); every record carries the
wave's `authored_rgba`. Recipe layers show `point_cloud` for closed-form,
frame-state and positions-only records, with `colour_resolved` and
`authored_rgba`.

`render.composite.flat_transfer` (custom composites) holds the composite shader
evaluated on flat canvas colours (`levels`, mean displayed `rgb` per level): the
displayed palette, including texture lookups.

`render.composite.per_load_random` and `render.feedback.warp_per_load_random`
report a shader's use of `rand_preset` (four `floatRand()` values drawn when
`MilkdropShader` is built, once per preset load): `switches` (component,
`condition` against a constant, `probability_true` under a uniform draw) and
`continuous_components` read in other ways. The illustration holds
`rand_preset` at 0.5, i.e. one branch. Each switch also appears as an intent
effect `per_load_variant` (stage, condition, `probability_true`) and as a
sentence appended to the recipe `description`.

`render.random_redraws` (or null) reports per-frame state whose update is
`select(condition, …rand…, itself)`: `states`, the frame outputs they `feed`,
`event_times_s` (first eight rising edges of the condition evaluated per frame
over 60 s with bands at 1; null when the condition reads other state) and the
median `period_s`. The intent gains `random_redraw` and the description a
sentence. Draws come from projectm-eval's process-wide `rand` stream.

`render.composite.hue_shader` (composites reading `hue_shader`/`_vDiffuse`)
summarises `FinalComposite::ApplyHueShaderColors` from the element's
`native_colour_generators` fact: `channels` read, `cycle_periods_seconds_rgb`
(2π / (30 · rate constant)), `range_rgb` after per-corner normalisation, and
`phase`: `PresetState::hueRandomOffsets` come from `std::random_device` at every
preset load, so the hue at a given place and time is not fixed by the source.

### Mood facets block (`facets`, policy `preset-facets-v1`)

`preset_recipe.py` adds a `facets` block to every recipe, and
`corpus_understanding.py` copies the same block into each entry of
`preference-index.json` (`presets[].facets`). The facets, their thresholds and
the combination rule come from the frozen definition
`tools/milk-analyzer/facets/facets-v1.json`; `preset_facets.py` evaluates them
(`memberships`, `select`), and `fixtures/facet-selection-vectors-v1.json` holds
the selection vectors that the Android `PresetFacets` shares. An existing
results directory gains facets with `corpus_understanding.py --rescore`.

```json
{"policy": "preset-facets-v1", "definition_sha256": "046aad75…",
 "evidence": "source-calibrated", "style_evidence": "source-structure-facts",
 "options": ["chill", "normal", "balanced", "still", "tunnel", "particles", "no_strobe"],
 "possible_options": ["chill", "normal", "dark", "balanced", "bright", "vivid", "warm", "still", "drifting", "no_strobe"],
 "unresolved_options": ["monochrome", "pastel"],
 "style": ["tunnel", "particles"],
 "values": {"luminance": {"value": 0.288, "interval": [0.086, 0.547], "evidence": "source-calibrated"},
            "activity": {"value": 0.313, "interval": [0.006, 0.641], "evidence": "source-calibrated"},
            "coloured_share": {"value": null, "evidence": "not-estimated"}, "…": "…"},
 "activity_source": "frozen-facet-reference-from-calibrated-statistics"}
```

Where the values come from (no simulation output and no rendered frame of the
described preset feeds any value):

- **`engine-ruler-measured`**: the preset name has a measured row in the bundled
  table `core/src/main/assets/preset-attributes/attributes.tsv`, and, when the
  summary carries a preset hash, the bundled preset file has the same bytes.
  `values` are the table's stored values (`warm_cool` is null when the table has
  `-`, meaning no coloured pixels); `options` are the table's options column
  unchanged; `possible_options` and `unresolved_options` are empty;
  `activity_source` is `engine-ruler-measured-bundle`; `bundle` names the table
  and its SHA-256. A name match with different bytes falls back to the
  source-calibrated path and says so in `note`.
- **`source-calibrated`**: any other preset. `luminance`, `saturation`,
  `warm_cool`, `flow`, `frame_difference` and `jumps` are the recipe's
  `display_estimate.statistics` (`mean_luminance`, `mean_saturation`,
  `warm_cool`, `mean_flow_screen_widths_per_s`, `mean_abs_frame_difference`,
  `global_brightness_jumps_per_10s`) with their 10th–90th percentile
  out-of-fold intervals. `activity` is computed from the calibrated frame
  difference, flow and jumps point values against the frozen facet activity
  reference `facets/activity-reference-v1.json` (mean of the three metric
  mid-ranks, placed in the frozen mean-rank table, as the bundle does); its
  interval combines the all-low and all-high metric ends.
  `display_estimate.activity.activity` is not used for facets: it is remapped
  into the distribution of calibrated estimates, a different percentile scale.
  `coloured_share` is not estimated, so Monochrome and Pastel (which depends on
  "not Monochrome") are listed in `unresolved_options` and are never members.
- **`unavailable`**: no calibrated display model is installed; metric options
  are unresolved and only style facets can be members.

Membership rules:

- `options`: options whose rule holds for the point values (definition order),
  minus unresolved options.
- `possible_options`: options whose rule is not constant across the reported
  intervals: it holds for some values inside them and fails for others. A
  member can be listed (its interval straddles a threshold) and so can a
  non-member that could hold inside the interval. Options absent from both
  lists fail everywhere in the intervals.
- `unresolved_options`: options whose rule needs a value that is not available,
  directly or through `not_option`.
- Style facets (`style`) come from `facet_style_facts.style_facts(summary)`:
  proven source mechanisms and approximate structure scores
  (`style_evidence: source-structure-facts`).

The bundle format: header `#projectm-tv-preset-attributes\t1`, `#definition\t<sha256
of facets-v1.json>`, `#group`/`#option` lines in definition order, then
`#columns\tname\toptions\tluminance\tsaturation\tcoloured_share\twarm_cool\tflow\tframe_difference\tjumps\tactivity`.
Each row is `name`, comma-separated options and eight values with four
decimals; `-` marks an unmeasured preset (all values, no options) or an
undefined `warm_cool`. The measurement is the engine ruler named in the
definition's `measurement` field.

`preference_select.py` accepts `"facets": ["chill", "no_strobe"]`: option ids
combine OR within a group and AND across groups (`preset_facets.select`);
unknown ids are reported in `facets.ignored`. The facet pool is intersected with
all other filters (profiles, comfort, activity window, palette, confidence and
feedback). The response gains `facets` with `selected`, `ignored`, `count`,
`option_counts` (the pool size if that option were toggled) and `dimmed`
(options that would leave nothing), computed over the presets the other
filters keep. An index entry without a facets block matches no facet request.

## 6. Consume it for a native-4K adaptation

A downstream renderer can build a **new scene guided by supported evidence**:

| Current data | Useful adaptation input | Information it does not provide |
|---|---|---|
| Palette warmth/chromatic support/hue diversity | Pick a curated palette family and colour-change targets. | Exact colours, their positions, gradients or original palette stops. |
| Supported motion statistics | Set activity/smoothness goals for an independently chosen movement model. | Exact trajectories, velocities, source objects or complete visible motion. |
| Correlated brightness/RGB events | Reproduce a sampled brightness envelope, explicitly bound to that input timeline. | A reusable beat trigger or causal bass→effect function for arbitrary new music. |
| Warp query displacement | Suggest a distortion budget for declared queries. | Tunnel/fractal identity, a full vector field, symmetry order or a shader. |
| Context and provenance | Decide whether evidence matches requested inputs and keep adaptation reproducible. | Transfer of a source fidelity score to a different renderer. |

A practical first consumer should validate schema/basis/hashes, keep unknowns,
select an explicit template (or ask for one), map supported targets into that
renderer and record its choices separately. Read flat feature keys from a map.
Use f64 for analysis metadata; narrow explicitly to your GPU parameter format.
Do not feed intervals or unknown values to shader uniforms as though they were
measured points. Keep unrelated future keys as extensible JSON data.

The adaptation can evaluate its own geometry at native 3840×2160, choose scene-
linear/HDR working storage and antialiasing, and use continuous-time motion and
resolution-independent line widths. These are **new renderer design choices**;
the source context's MilkDrop compatibility policies identify the analyzed
behavior rather than requiring pixel-identical reuse. Test the adaptation's
own motion, brightness and response targets separately. No Rust/wgpu backend is
implemented by this documentation.

### What a stronger semantic render-plan export would need (proposal only)

To preserve the *particular* preset's effect family and response while optimizing
its rendering, add a separately versioned export in future; do not disguise it
as existing schema1. At minimum it would need:

1. Component identity/type, geometry or generators and drawing order.
2. Portable coordinate systems, transforms and time/audio parameter curves.
3. Explicit effect-family evidence (tunnel/fractal/flow/particles), not inferred
   from a mean speed or hue-bin count.
4. A semantic effect recipe with its parameters/response, or typed operations when useful; exporting the original shader is optional.
5. Feedback recurrence, decay/transport/blending semantics and texture/resource
   inputs, including random lifetimes and reproducible seeds.
6. Causal band/beat response including affected component, modulation function,
   gain/sensitivity, activation range and whether that relationship was proven.
7. Interpretation support, unknown operations and per-component provenance.

`read_source`, `execute_scene`, `source_builtin_wave`, `source_custom_waves`,
`warp_fields` and the shader field DAG are useful internal building blocks. They
are **not** an exported stable WGSL/Rust scene IR today; full forecast JSON drops
most of their prepared component geometry. Isolated shader queries also do not
supply an arbitrary reusable final-colour program. Without the stronger export,
your tool can make an evidence-guided visual interpretation. To preserve a
particular effect family, extend the exporter with semantic descriptors derived
from the existing internal analysis; a shader-program export is not mandatory.

### Recognizing effects and generating from the same vocabulary

The 47 fields help distinguish viewer experience: colour diversity/warmth,
measured motion, abruptness and correlated brightness/colour changes. They can
suggest a calm colour flow or a fast, bright visual brief. They do not uniquely
identify the spatial structure or which element caused those statistics. For
example, matching speed/hue/brightness can arise from a waveform, particle-like
points or a feedback tunnel. Brightness events do not by themselves prove flashes
or beat triggers; shape derivatives do not describe complete visible movement.

Effect recognition should use the source representation alongside these metrics:

| Family | Required semantic evidence | Main false-positive check |
|---|---|---|
| Waveform | Enabled built-in/custom audio-driven wave, draw mode, geometry and contribution. | Wave exists but alpha/branch/occlusion makes it ineffective. |
| Particle-like points | Repeated point/sprite elements with identities, independent movement or lifetimes. | Dots can be a dotted waveform with no particle dynamics. |
| Tunnel | Radial/perspective structure plus repeated depth-like transport/feedback layering. | Zoom or radial coordinates alone do not imply a visible tunnel. |
| Kaleidoscope | Angular folding/repetition with a symmetry order that reaches final colour/geometry. | Unused angle math or a zero-weight branch. |
| Fractal | Recursive/iterative self-similar construction, folding, or recognizable recurrence affecting output. | A loop, preset name or function name alone is insufficient; feedback can also create fractal-like structure. |
| Flow/swirl | Coherent field transport/rotation/distortion, with smooth evolution and contribution. | Fast or discontinuous modulation can defeat a smooth label. |

Normalize expressions, trace temporary variables/functions to output, identify
patterns, establish reachable activation and preserve audio/time/texture/state
conditions. Numerical source queries or simulations can test invariants,
symmetry, trajectories and contribution under declared inputs without native
image inspection. Samples are bounded evidence; they cannot turn arbitrary
program behavior into a universal classification proof. Mixed presets need
multiple labels and component-level support, with unknowns retained.

A practical complexity assessment, based on the current code rather than a
measured delivery estimate: exporting explicit elements is small-to-moderate;
parameter motion/audio descriptions are moderate; composite tunnel/kaleidoscope/
particle recognition is substantial; arbitrary fractal and emergent-feedback
recognition is research-heavy. Start with explicit components and a limited,
tested pattern vocabulary; do not attempt universal shader recognition first.

Existing tools help with representation, not finished semantic classification:

- [projectM preset state](https://github.com/projectM-visualizer/projectm/blob/master/src/libprojectM/MilkdropPreset/PresetState.hpp)
  separates equation phases, custom waves/shapes and warp/composite resources.
  It is upstream structure, not a replacement for our pinned patched semantics.
- [projectM-eval](https://github.com/projectM-visualizer/projectm-eval) supplies the
  expression parser/evaluator. Our source adapters use the identified patched
  target rather than silently substituting an unpatched evaluator.
- [Butterchurn](https://github.com/jberg/butterchurn) is another MilkDrop renderer;
  [milkdrop-preset-utils](https://github.com/jberg/milkdrop-preset-utils) offers
  preset-reading utilities. They provide useful comparison/conversion pieces.
- [SPIRV-Cross reflection](https://github.com/KhronosGroup/SPIRV-Cross/wiki/Reflection-API-user-guide)
  describes resource and shader-interface reflection;
  [SPIRV-Tools](https://github.com/KhronosGroup/SPIRV-Tools) provides parsing,
  validation and optimization machinery. Semantic effect recognition is an
  additional analysis pass; raw MilkDrop HLSL needs a compatible frontend first.
- [Naga IR](https://wgpu.rs/doc/naga/ir/index.html) supplies a shader intermediate
  representation shared by its frontends/backends, useful for a Rust renderer.
  It does not itself assign tunnel/fractal/particle labels.

For generation, use a typed catalog of understood building blocks with motion,
colour, feedback and audio-response descriptors. Generate a program from a brief,
then analyze it using the same vocabulary and check support/constraints. This can
produce useful personalized presets before arbitrary-library recognition is
complete. Semantic recognition is important for learning/reusing the existing
library and preserving its effect families, but a universal classifier is not a
prerequisite for generation from a deliberately restricted, understood grammar.
No such semantic exporter or generator is implemented by this documentation.

## 7. Reproduce and inspect the examples

From the predictor worktree root, using already prepared pinned adapters/audio:

```sh
build/preset-lab-venv/bin/python tools/milk-analyzer/source_extract.py \
  --preset tools/milk-analyzer/export-contract/examples/example.milk \
  --audio build/visual-loop/runtime2327/detail-qualification/audio-context.json \
  --binaries build/visual-loop/source-pr59/adapters \
  --profile gles300 --width 256 --height 144 \
  --equation-rng-policy projectmtv-core-2.3.27-cold-thread-v1 \
  --output /tmp/preset-strict-features.json

build/preset-lab-venv/bin/python tools/milk-analyzer/source_classify.py \
  --features /tmp/preset-strict-features.json --profile neutral-v1 \
  --output /tmp/preset-scores.json
```

The CLI defaults to the historical2.3.15 RNG policy; declare the matching27 policy
explicitly for these adapters. Missing adapters/audio are preparation failures,
not unknown-zero feature values. Native GPU/device use is unnecessary for this
strict export. Rescoring simulation requires explicit `--allow-simulated`.

The bundle contains actual producer records, not hand-written invented values:

- [Strict JSON](export-contract/examples/strict-features.json): newly generated
  by the strict CLI from the included synthetic moving-shape preset.
- [Simulated JSON](export-contract/examples/simulated-features.json): exact feature
  member of the previously frozen2.3.27 30-frame 4K feedback/shape forecast.
- [Forecast metadata](export-contract/examples/forecast-metadata.json): exact
  saved full report generated with `retain_surfaces=False` (no NumPy arrays).
- [Scores](export-contract/examples/scores.json): neutral-v1 rescoring of the strict
  record, which abstains because complete required evidence is not supplied.
- [Machine catalog](export-contract/feature-catalog.json),
  [schema](export-contract/source-feature-record.schema.json) and manifest.

The strict example is analyzed at256×144, while simulation is at native/physical
4K with an authored1280×720 canvas. Their feature magnitudes are not interchangeable
merely because the preset bytes match. Example hashes bind each actual input
context. The fixture has duplicate decay settings: the effective first value is1,
not the later .97. Preserve its original bytes and declared identities.

### Recipe schema (`export-contract/preset-recipe.schema.json`)

The preset recipe (`preset-visual-recipe-v1`, from `preset_recipe.build_recipe`)
has a draft 2020-12 JSON Schema covering its stable sections: identity, render
feedback (including `warp_transfer` with `per_channel` and `wrap`), layers
(built-in wave radius, maximise rule, point clouds), composite (`flat_transfer`,
`hue_shader`, `per_load_random`), `random_redraws`, display estimate, facets
and intent effects. `contract_schema.recipe_errors(recipe)` validates a recipe
without extra dependencies, and `test_contract_schema.py` validates a real
fresh export end to end. Unlisted properties are allowed, so additive fields
stay within v1. A change of meaning, unit or basis needs a new policy string
and a schema update in the same change. Consumers should check `policy`,
validate against the schema, and ignore fields they do not know.

## 8. Authority and compatibility

This document and companion schema describe producers at the stated checkpoint.
The schema has no independent runtime enforcement in `source_extract.py`; producer
and existing consumer guards are the authority. Additive fields should not break
a consumer, while changed meaning/units/basis require explicit migration. No
compatibility promise for the unversioned full diagnostic report is invented.

Implementations: `source_features.py`, `strict_source_features.py`,
`source_extract.py`, `forecast.py`, `source_classify.py`, `mood_scoring.py`.
See also [feature evidence](SOURCE_FEATURES.md),
[strict extraction](STRICT_EXTRACTION.md) and [source math](SOURCE_MATH.md).
