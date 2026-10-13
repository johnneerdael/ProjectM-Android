# Preset predictor exports

Two separate contracts now serve different needs:

- **Static source description:** conditional constructions, geometry/material
  ingredients and audio-to-element control routes, without executing equations,
  shaders, audio or display frames. This is the current development priority.
- **Numerical feature record:** the preserved 2026-10-08 checkpoint with 47
  simulated statistics (plus a distinct 11-feature strict extractor). It still
  requires its declared inputs and numerical execution.

Publishing this reference does not merge the experimental predictor or change the
[shipped mood collections](predictive-collections.md). The
[predictor overview](predictor.md) explains the direction and current evidence.

## Preset-attributes bundle (shipped Mood facets)

The app's [Mood panel](predictive-collections.md) reads a measured bundle in `core/src/main/assets/preset-attributes/`. It is separate from the predictor exports above: its inputs are engine-ruler measurements (`tools/native-ruler/`) and source style facts, not source-classification output.

| File | Content |
|---|---|
| `facets.json` | The definition (`schema: projectm-tv-mood-facets`, `version: 1`): groups, option ids and labels, threshold rules, and the combination rule (OR within a group, AND across groups). Source: `tools/milk-analyzer/facets/facets-v1.json` |
| `attributes.tsv` | Header lines `#projectm-tv-preset-attributes<TAB>1`, `#definition<TAB><sha256 of facets.json>`, one `#group<TAB>id<TAB>label` and `#option<TAB>group<TAB>id<TAB>label` line per group and option, then `#columns<TAB>name<TAB>options<TAB>luminance<TAB>saturation<TAB>coloured_share<TAB>warm_cool<TAB>flow<TAB>frame_difference<TAB>jumps<TAB>activity`. Each data row is the preset file name, its comma-separated option ids and the eight measured values (activity is a 0-1 percentile against the frozen activity reference) |
| Activity reference (tools only) | `tools/milk-analyzer/facets/activity-reference-v1.json`, named with its SHA-256 by the definition's `activity_reference`: 1001-point quantile tables of `mean_abs_frame_difference`, `mean_flow_screen_widths_per_s`, `global_brightness_jumps_per_10s` and of their mean rank, frozen once from the 9,606 ruler results (provenance: ruler identity, preset count, ruler results manifest SHA-256). Activity is the mid-rank of the mean of the three metric mid-ranks, each looked up in these tables; it is not recomputed per release. Write it once per definition version with `--freeze-activity-reference <file> --ruler <dir> --ruler-manifest <file>`, which first runs the same evidence verification as a build |
| `manifest.json` | `schema`, `version`, `preset_count`, `measured_count`, per-option `option_counts`, SHA-256 of `attributes.tsv`, `facets.json`, `presets.idx`, the ruler results manifest and the style facts, plus the ruler conditions (`size` 480x270, `frames` 300, audio and engine identity) |

Build and verify (standard library only; CI runs `--check`):

```sh
python3 tools/milk-analyzer/attribute_bundle.py --ruler <ruler results dir> --style <style facts file> --ruler-manifest <committed ruler results manifest>
python3 tools/milk-analyzer/attribute_bundle.py --check
```

A build (and `--freeze-activity-reference`) first verifies the ruler results against the committed ruler results manifest in both directions: every measured result file must be a manifest row with the same result and preset SHA-256, and every manifest row marked measured must have exactly one measured result file, so a deleted result or a changed status fails; each result's seven ruler values and activity inputs must also equal the manifest row's `metrics` and `activity_inputs` (regenerate the manifest from the results with `--write-evidence-manifest OUTPUT --ruler <dir> --ruler-manifest <old manifest>`). Neither a measured result nor a measured manifest row may name a preset that is absent from `presets.idx`, so removed or renamed presets cannot leave stale evidence behind. It also hashes every preset named in `presets.idx` that has a measured row (in `--presets-dir`, default `presets/` next to `--presets-idx`) and requires the evidence `preset_sha256`.

The build requires exactly one style facts row per `presets.idx` preset (no missing or duplicate rows) and compares each row's SHA-256 with the current preset bytes (`--presets-dir`), so style facts for an edited preset fail the build. The style facts file lives outside the repository, so `--check` cannot re-verify it; style provenance is verified at build time and its SHA-256 is recorded in the manifest.

`--check` verifies the bundle against `presets.idx`, the definition, the activity reference's SHA-256 and the manifest, compares the committed ruler results manifest (`--ruler-manifest`, default `docs/superpowers/evidence/mood-facets-ruler-2026-10-12/ruler-results-manifest.json`) with the SHA-256 recorded in the bundle manifest (a missing or changed file fails), hashes every bundled preset with a measured manifest row and compares it with that row's `preset_sha256` (a preset edited after measuring fails), requires every bundle row to be measured exactly when its manifest row is marked measured, requires each measured row's seven value columns to equal the manifest row's `metrics` and its activity column to equal the activity recomputed from the manifest's `activity_inputs` against the frozen reference (so edited values cannot be re-hashed into a passing bundle), recomputes every option membership from the stored values and style options, and recomputes the manifest's `schema`, `version`, `preset_count`, `measured_count` and `option_counts` from the bundle rows (a stale or hand-edited value fails). `tools/milk-analyzer/preset_facets.py` implements the selection semantics (counts, toggled counts, dimming) and shares test vectors with the Java `PresetFacets` class in the core library. The core also exposes `ProjectMJNI.setPresetPool(String[])`; the legacy `setMusicCategory("chill"|"normal"|"intense")` is unchanged.

## Preset knowledge pack reader (core library)

A preset knowledge pack (`preset-knowledge-pack-v1`) holds source-only recipes
for a whole preset collection: effects, audio reactivity, calibrated
brightness and motion estimates, and facets. It is plain gzip, JSON and
SHA-256, so any platform can read it. The reader contract is
[`tools/milk-analyzer/export-contract/knowledge-pack/FORMAT.md`](https://github.com/johnneerdael/ProjectM-TV/blob/main/tools/milk-analyzer/export-contract/knowledge-pack/FORMAT.md):

- check the pack and recipe policy strings;
- check the core file hash, and each line's hash over the stored line bytes;
- require a `presets` array and LF line endings (no CR, final LF present);
- decode UTF-8 strictly;
- check the JSON types of the fields it exposes;
- keep manifest order;
- ignore fields you do not know;
- hand out nothing from a rejected pack.

The core library's `PresetKnowledgePack` implements it for the app and for
Milkbeat. `read(File)`, `read(File, visitor)` and `read(manifest, core,
visitor)` verify the core file hash first, then stream the core, check every
line before parsing it, and keep only a per-preset view:

- effects with their parameters;
- reactivity as band, target, kind and response;
- mean luminance and frame difference, each with an interval;
- activity and activity bands;
- facet options and values;
- energy tags.

A `RecipeVisitor` receives each full parsed recipe once, only after the whole
pack has passed, so memory follows the views rather than the recipes and a
rejected pack publishes nothing. `load(AssetManager, dir)`
returns `null` for a missing or invalid pack. A pack that breaks a rule
throws `InvalidPackException`, whose `rule` names the rule. Lookups work by
preset name or by the preset file's SHA-256.

The golden vectors in `export-contract/knowledge-pack/golden-v1/` (one valid
pack, one with unknown fields, and nine packs that each break one rule) are
the shared tests for every reader. `PresetKnowledgePackTest` runs them on the
JVM. Estimates and facets come from calibrated source analysis, not from
rendered frames. No pack ships in the app yet.

## Static source-description contract

Implementation checkpoint: `9c8ff632`, 2026-10-10, experimental
`feat/predictor-static-output-bounds`.
The [reference documentation archive](https://github.com/johnneerdael/ProjectM-TV/tree/fab54330f0144a63f1c30ed7afe7cb8b72191bc2/docs/superpowers/evidence/predictor-docs-reference-9c8ff632)
preserves the cited contracts and evidence summaries. The implementation
checkpoint is local and is not published by this documentation update. The
following command requires that implementation and its prepared environment;
the archive alone cannot run it.

Use `effect_family_export.py` from that prepared checkout:

```sh
build/preset-lab-venv/bin/python tools/milk-analyzer/effect_family_export.py path/to/preset.milk --output ~/Downloads/ProjectM-TV-static-single
```

The CLI requires the prepared hash-identified source31 native parser and Python
environment. It consumes no PCM, frame schedule, dimensions or GPU render. Omit
the preset argument for the bundled pack, or supply a folder. Results retain
relative filenames, exact `.milk` bytes and matched JSON, with a ZIP every 100
completed attempts and a final partial batch. Failures retain `analysis: null`
and their reason. Resume/cache reuse requires matching source, parser, model and
profile identities; use a fresh process and output folder after code changes.

| JSON location | Meaning |
|---|---|
| `export_kind` | `preset-effect-families`; separate from numerical feature records. |
| `preset` and `provenance` | Exact preset metadata and parser/model/target identities. |
| `analysis.schema_version`, `analysis.analysis_policy` | Semantic schema 1; `source-effect-families-v1`. |
| `analysis.families`, `analysis.stages`, `analysis.unknowns` | Supported contributing mechanisms, selected/conditional stages and interpretation gaps. |
| `analysis.visual_description` | Structured baseline traits, schema 1, policy `source-appearance-and-control-traits-v1`. |
| `analysis.visual_description.elements` | Source component IDs, numeric construction/colour codes, supported parameters, materials and audio routes. |
| Other description members | Conditional logical composition, sample transforms, colour processing/mixtures and feedback inputs. |
| Execution flags | `uses_equation_execution`, `uses_shader_execution`, `uses_rendered_images`: false. |
| Appearance qualification | `appearance_accuracy_verified`: false; `appearance_match_accuracy`: null. Successful extraction is not a visual certificate. |
| Semantic `record_sha256` members | Canonical content digests at their respective nested record scopes; not signatures or confidence values. |

This table locates the contracts; it is not a complete example record. Read the
[full mechanism reference](https://github.com/johnneerdael/ProjectM-TV/blob/fab54330f0144a63f1c30ed7afe7cb8b72191bc2/docs/superpowers/evidence/predictor-docs-reference-9c8ff632/tools/milk-analyzer/EFFECT_FAMILIES.md),
[appearance fields and numeric dictionaries](https://github.com/johnneerdael/ProjectM-TV/blob/fab54330f0144a63f1c30ed7afe7cb8b72191bc2/docs/superpowers/evidence/predictor-docs-reference-9c8ff632/tools/milk-analyzer/SOURCE_APPEARANCE.md)
and [appearance JSON Schema](https://github.com/johnneerdael/ProjectM-TV/blob/fab54330f0144a63f1c30ed7afe7cb8b72191bc2/docs/superpowers/evidence/predictor-docs-reference-9c8ff632/tools/milk-analyzer/export-contract/source-appearance.schema.json)
for exact object shape, enum meanings, units and unknown variants. The schema
alone does not verify hashes, source truth, visibility or reconstruction readiness.

Source audio routes name a component and changed control, engine band, supported
source gain/formula and conditions. They do not isolate vocals/instruments or
measure visible bass-response strength. Source-time rates describe control math;
constant feedback rotation can keep rotating the picture on every feedback step.
Selected images, random phases, initial feedback, audio and clock values are
additional inputs when a consumer needs an exact instance. Approximate baseline
traits can still be useful without them. Final prominence, flash events and
complete feedback interpretation remain open implementation and validation work.

A consumer can select an original Rust/wgpu implementation for a supported
construction and preserve its known parameters. It must keep unknowns and its own
defaults separate. Recognizable whole-preset reconstruction, final palette and
calibrated mood/genre assignment are pending validation, not proven impossible.
Current bounded expression support and work budgets are extendable implementation
choices. Join source and numerical
records by exact preset SHA-256 and compatible target/input context, retaining
both kinds of evidence rather than relabeling simulated statistics as static.

## Preserved numerical feature-record contract

The remainder documents the **2026-10-08 numerical checkpoint**, producer
`587e3f53`. Its guide was synchronized from remote main
`af164a97896646427f971ecbed8161f8d35c2fec` at that time. These historical examples,
counts and reproduction commands retain their original contexts; they have not
been regenerated against the newer source-description implementation.

The 47 simulated fields provide a statistical behavioral brief, not a unique
scene description. The newer semantic export adds some of the construction and
control information that this older format lacks. The full forecast diagnostic
return remains unversioned; use the explicitly versioned exports for interchange.
For historical fidelity scores, see
[how behavioral accuracy was measured](authoring/testing.md#how-are-you-measuring-97-accurate).

## 1. Choose the export

The static contract above is separate. It does not replace or change this
47-field numerical checkpoint contract.

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

The companion [JSON Schema](assets/predictor-export/source-feature-record.schema.json)
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
verified descriptions of scene topology. See [SOURCE_SCORING.md](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-visual-loop/tools/milk-analyzer/SOURCE_SCORING.md)
for exact formulas, aliases, thresholds and requirements.

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

### Information needed for a complete semantic render plan

The static source-description export now covers supported subsets of the
following information. Full coverage and independently recognizable reconstruction
remain unverified. Keep this separate from the numerical feature schema:

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
The static semantic exporter described above exists on the experimental branch.
It is partial; no complete render-plan exporter or production generator is
certified by this documentation.

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

- [Strict JSON](assets/predictor-export/examples/strict-features.json): newly generated
  by the strict CLI from the included synthetic moving-shape preset.
- [Simulated JSON](assets/predictor-export/examples/simulated-features.json): exact feature
  member of the previously frozen2.3.27 30-frame 4K feedback/shape forecast.
- [Forecast metadata](assets/predictor-export/examples/forecast-metadata.json): exact
  saved full report generated with `retain_surfaces=False` (no NumPy arrays).
- [Scores](assets/predictor-export/examples/scores.json): neutral-v1 rescoring of the strict
  record, which abstains because complete required evidence is not supplied.
- [Machine catalog](assets/predictor-export/feature-catalog.json),
  [schema](assets/predictor-export/source-feature-record.schema.json) and manifest.

The strict example is analyzed at256×144, while simulation is at native/physical
4K with an authored1280×720 canvas. Their feature magnitudes are not interchangeable
merely because the preset bytes match. Example hashes bind each actual input
context. The fixture has duplicate decay settings: the effective first value is1,
not the later .97. Preserve its original bytes and declared identities.

## 8. Authority and compatibility

This numerical section and its companion schema describe producers at the
2026-10-08 checkpoint; the separate static contract has its own current references.
The schema has no independent runtime enforcement in `source_extract.py`; producer
and existing consumer guards are the authority. Additive fields should not break
a consumer, while changed meaning/units/basis require explicit migration. No
compatibility promise for the unversioned full diagnostic report is invented.

Implementations: `source_features.py`, `strict_source_features.py`,
`source_extract.py`, `forecast.py`, `source_classify.py`, `mood_scoring.py`.
See also [feature evidence](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-visual-loop/tools/milk-analyzer/SOURCE_FEATURES.md),
[strict extraction](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-visual-loop/tools/milk-analyzer/STRICT_EXTRACTION.md) and [source math](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-visual-loop/tools/milk-analyzer/SOURCE_MATH.md).
