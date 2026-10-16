# Export contracts

This page collects the file formats behind the predictor: the shipped Mood bundle, the knowledge pack and its reader in the core library, and the static source-description record that every analysis starts from. The [JSON output](predictor/json-output.md) page explains the recipe and evidence fields one by one; the [Predictor overview](predictor.md) explains how they fit together.

## Preset-attributes bundle (shipped Mood facets)

The app's [Mood panel](predictive-collections.md) reads a bundle in `core/src/main/assets/preset-attributes/`. Since 2026-10-16 it is generated entirely from static source analysis (the predictor on the research branch `feat/predictor-static-output-bounds`); no value comes from a render. Main does not run the predictor: it carries the committed evidence the table was built from and checks the table against it.

| File | Content |
|---|---|
| `facets.json` | The definition (`schema: projectm-tv-mood-facets`, `version: 1`): groups, option ids and labels, rules, and the combination rule (OR within a group, AND across groups). Source: `tools/milk-analyzer/facets/facets-v1.json`. The `palette` group (ids `red` … `pink`, rule `{"palette": family}`) and the `main_colour` group (ids `main_red` … `main_pink`, rule `{"main_colour": family}`) read the preset's colour tags |
| `attributes.tsv` | Header lines `#projectm-tv-preset-attributes<TAB>1`, `#definition<TAB><sha256 of facets.json>`, one `#group<TAB>id<TAB>label` and `#option<TAB>group<TAB>id<TAB>label` line per group and option, then `#columns<TAB>name<TAB>options<TAB>luminance<TAB>saturation<TAB>coloured_share<TAB>warm_cool<TAB>flow<TAB>frame_difference<TAB>jumps<TAB>activity`. Each data row is the preset file name, its comma-separated option ids in definition order and eight static estimates (4 decimals, `-` for none). The app reads only the options; the parser checks the column count |
| `manifest.json` | `schema`, `version`, `source: static-analysis`, `preset_count`, `measured_count` (rows with any value), `analysis_errors`, per-option `option_counts`, SHA-256 of `attributes.tsv`, `facets.json`, `presets.idx` and the static evidence, and the evidence `producer` (research commit, calibration model SHA-256, policy) |
| Static evidence (tools only) | `docs/superpowers/evidence/static-mood-table-2026-10-16/static-evidence.json.gz`: gzip JSON `{schema: projectm-tv-static-mood-evidence, version, producer, rows}`, one row per bundled preset with `name`, preset `sha256`, static `options` (without colour ids), `palette` (hue families with at least 10% of the static display palette), `dominant` (a family only when the predicted top-colour share is at least 0.65 and the palette's top share at least 0.55, else null) and the eight `values` |

Build and verify (standard library only; CI runs `--check`):

```sh
python3 tools/milk-analyzer/attribute_bundle.py --build-static docs/superpowers/evidence/static-mood-table-2026-10-16/static-evidence.json.gz
python3 tools/milk-analyzer/attribute_bundle.py --check
```

A static build requires exactly one evidence row per `presets.idx` preset and no row for any other preset, and hashes every preset (in `--presets-dir`, default `presets/` next to `--presets-idx`) against the row's `sha256`, so an edited, added or renamed preset fails until it is analysed again. An evidence option or colour the definition does not know fails the build. Palette and Main colour options come from `palette` and `dominant`; a preset whose static options include `monochrome` gets neither. Presets whose analysis failed get no options and `-` values; the build fails if there are any (the limit is 0). The deflated `attributes.tsv` must stay within 450,000 bytes.

For a manifest with `source: static-analysis`, `--check` verifies `facets.json` against the definition, the manifest hashes, the header, that the rows name exactly the `presets.idx` presets, that every row equals the row rebuilt from the evidence (`--static-evidence`, default above, whose SHA-256 must match the manifest), every preset's bytes against the evidence, the size budget, and the manifest's `schema`, `version`, `source`, `producer`, `preset_count`, `measured_count`, `analysis_errors` and `option_counts` recomputed from the rows. `tools/milk-analyzer/preset_facets.py` implements the selection semantics (counts, toggled counts, dimming) and shares test vectors with the Java `PresetFacets` class in the core library. The core also exposes `ProjectMJNI.setPresetPool(String[])`; the legacy `setMusicCategory("chill"|"normal"|"intense")` is unchanged.

### Earlier engine-ruler bundle (history)

Until 2026-10-16 the table held engine-ruler measurements (`tools/native-ruler/`, 300 frames at 480x270 on macOS GLES under SwiftShader) and source style facts. `attribute_bundle.py` keeps that path (`--ruler`, `--style`, `--ruler-manifest`, `--write-evidence-manifest`, `--freeze-activity-reference`) and `--check` still verifies a manifest without `source` against the ruler results manifest (`docs/superpowers/evidence/mood-facets-ruler-2026-10-12/ruler-results-manifest.json`) and the frozen activity reference (`tools/milk-analyzer/facets/activity-reference-v1.json`), recomputing memberships from the stored values. That path no longer produces the shipped bundle.

## Preset knowledge pack reader (core library)

A preset knowledge pack (`preset-knowledge-pack-v1`) holds source-only recipes
for a whole preset collection: effects, audio reactivity, calibrated
brightness and motion estimates, and facets. It is plain gzip, JSON and
SHA-256, so any platform can read it. The reader contract is
[`tools/milk-analyzer/export-contract/knowledge-pack/FORMAT.md`](https://github.com/johnneerdael/ProjectM-TV/blob/main/tools/milk-analyzer/export-contract/knowledge-pack/FORMAT.md):

- check the pack and recipe policy strings;
- check the core file hash, and each line's hash over the stored line bytes;
- require exactly one valid gzip member (header CRC when present, CRC-32 and
  size trailer), a `presets` array and LF line endings (no CR, final LF
  present);
- decode UTF-8 strictly;
- check the JSON types of the fields it exposes (a missing or `null`
  container means empty);
- keep manifest order;
- ignore fields you do not know;
- hand out nothing from a rejected pack.

The core library's `PresetKnowledgePack` implements it for the app and for
Milkbeat. `read(File)`, `read(File, visitor)` and `read(manifest, core,
visitor)` read the compressed core once into memory, verify its file hash,
then decompress it line by line, check every line before parsing it, and keep
only a per-preset view:

- effects with their parameters;
- reactivity as band, target, kind and response;
- mean luminance and frame difference, each with an interval;
- activity and activity bands;
- facet options and values;
- energy tags.

A `RecipeVisitor` receives each full parsed recipe once, from the same
verified bytes, only after the whole pack has passed. A rejected pack
publishes nothing. Memory is the compressed core plus the views; the
decompressed recipes are never held all at once. `load(AssetManager, dir)`
returns `null` for a missing or invalid pack. A pack that breaks a rule
throws `InvalidPackException`, whose `rule` names the rule. Lookups work by
preset name or by the preset file's SHA-256.

The golden vectors in `export-contract/knowledge-pack/golden-v1/` (one valid
pack, one with unknown fields, one with null containers, and twelve packs
that each break one rule) are
the shared tests for every reader. `PresetKnowledgePackTest` runs them on the
JVM. Estimates and facets come from calibrated source analysis, not from
rendered frames. No pack ships in the app yet.

## Static source-description contract

The record produced by `effect_family_export.py` on the research branch `feat/predictor-static-output-bounds` (first published at checkpoint `9c8ff632`, 2026-10-10).
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
defaults separate. Recognizable whole-preset reconstruction remains pending validation; final palettes and calibrated mood options are now produced from this record (see [From estimates to moods](predictor/mood-table.md)).
Current bounded expression support and work budgets are extendable implementation
choices. Join records by exact preset SHA-256, and never relabel simulated statistics as static facts.

## Earlier numerical feature records (history)

Before the static analysis, the predictor simulated presets numerically and exported a 47-field statistical record (the 2026-10-08 checkpoint) with its own JSON Schema, examples and an accuracy rubric. That approach was abandoned in favour of static analysis: a simulation that matches the engine explains nothing the engine does not already show, and costs seconds to minutes per preset ([research journal](predictor/journal.md#58-october-a-numerical-forecaster)). The contract, its schema and its examples remain readable in the [repository history](https://github.com/johnneerdael/ProjectM-TV/blob/806d1282c92e6c5638c9fbde7607d2ed9317105e/docs/user-guide/predictor-export.md#preserved-numerical-feature-record-contract).
