# Preset knowledge pack format (`preset-knowledge-pack-v1`)

A knowledge pack holds source-only preset recipes for a whole preset
collection. It is plain data: gzip, JSON and SHA-256. A reader needs nothing
that is specific to Python, Java, Android or a desktop OS. This document is
the contract for every reader (the ProjectM TV app, Milkbeat, tools). The
golden vectors in [`golden-v1/`](golden-v1/) decide whether a reader is
correct.

Implementations:

- Producer and Python reference reader: `tools/milk-analyzer/knowledge_pack.py`
  (`build`, `load_core`) on the predictor research branch
  (`feat/predictor-static-output-bounds`).
- Java reader: `nl.neerdael.projectm.core.PresetKnowledgePack` in the core
  library, used by the ProjectM TV app and by Milkbeat through the released
  core AAR. It has no Android dependency outside `load(AssetManager, …)`.

## Layout

```
manifest.json          pack identity and per-preset index (UTF-8 JSON)
core.jsonl.gz          one recipe per line (gzip of UTF-8 JSON Lines)
full/<sha256>.json.gz  optional: complete recipes with program graphs
```

`manifest.json` follows
[`../knowledge-pack-manifest.schema.json`](../knowledge-pack-manifest.schema.json).
Each core line follows
[`../preset-recipe.schema.json`](../preset-recipe.schema.json) with the
serialised program graphs removed (the keys listed in
`manifest.core.graphs_removed`).

## Encoding

- `core.jsonl.gz` is one gzip member. Its content is UTF-8 text: one compact
  JSON object per line, each line ending in `\n` (LF). Producers write ASCII
  only, escaping other characters as `\uXXXX`. Readers must still decode
  UTF-8, strictly: a byte sequence that is not valid UTF-8, in the manifest
  or in a line, rejects the pack (rule: *encoding*). Never substitute
  replacement characters.
- Lines appear in the order of `manifest.presets`. Readers must use that
  order and must not re-sort; sort orders differ between languages.
- Empty lines are ignored.
- Numbers are JSON numbers (IEEE-754 doubles). Compare them with the
  tolerance in `expected.json` (`1e-9`), never as text.

## Reader rules

A reader must reject the pack, not just one preset, when any rule fails. It
must not hand out any recipe or view from a pack it rejects. A streaming
reader therefore verifies the whole core before it publishes anything.

1. `manifest.policy` is exactly `preset-knowledge-pack-v1` (rule: *pack policy*).
2. `manifest.recipe_policy` is exactly `preset-visual-recipe-v1` (rule: *recipe policy*).
3. SHA-256 of the `core.jsonl.gz` file bytes equals `manifest.core.sha256`,
   lowercase hex (rule: *core file hash*). Hash the file as stored, before
   decompressing.
4. The number of non-empty lines equals the number of `manifest.presets`.
5. For the *i*-th line, SHA-256 of its UTF-8 bytes, without the trailing
   `\n`, equals `manifest.presets[i].core_line_sha256` (rule: *core line
   hash*). Hash the bytes as stored; never re-serialise the parsed object.
6. Each line's `policy` is `preset-visual-recipe-v1` and its `preset.name` and
   `preset.sha256` equal the manifest entry.
7. The fields of the reader view below have their JSON types (rule: *recipe
   types*):
   - `preset.name`, `preset.sha256` and each `intent.effects[].effect` are strings;
   - effect `stage` and the reactivity fields are strings or null;
   - estimate values, `activity` and facet values are numbers or null;
   - an interval is null or two numbers;
   - lists of names are lists of strings;
   - containers are objects or lists of objects.

   Readers do not type-check other fields.

Readers must ignore object fields they do not know, both in the manifest and
in recipes. Fields can be added within v1. A change of meaning or unit
changes the policy string, and v1 readers then reject the pack by rule 1, 2
or 6.

To match a pack to installed preset files, compare the SHA-256 of each
preset file with `presets[i].sha256`. A missing or changed file means that
recipe does not describe that file.

## Reader view

Readers expose at least the following, per preset. Paths are into the recipe
object. A missing object gives an empty list or `null`; it is not an error.

| View field | Recipe path |
|---|---|
| name, sha256 | `preset.name`, `preset.sha256` |
| effects | `intent.effects[].effect` (each row also carries its own parameters) |
| reactivity | `intent.reactivity[]` → `[band, target, kind, response]` |
| mean_luminance | `display_estimate.statistics.mean_luminance` → `{value, interval}` |
| mean_abs_frame_difference | `display_estimate.statistics.mean_abs_frame_difference` → `{value, interval}` |
| activity, activity_bands | `display_estimate.activity.activity`, `.bands` |
| facet_options | `facets.options` |
| facet_values | `facets.values.<name>.value`, keys sorted |
| energy_tags | `intent.energy.tags` |

All other fields remain available as raw JSON. Display estimates and facets
are calibrated estimates from source analysis, not measurements of a
rendered frame. Statistic values and intervals lie inside their physical
range (luminance, frame difference and saturation in [0, 1], warm/cool in
[−1, 1], rates ≥ 0).

## Golden vectors

[`golden-v1/expected.json`](golden-v1/expected.json) lists the reader view
for the packs a reader must accept, and the rule each rejected pack breaks:

| Pack | Expected |
|---|---|
| `valid` | accept; views as listed |
| `unknown-fields` | accept; same views (extra manifest and recipe fields are ignored) |
| `bad-policy` | reject: pack policy |
| `bad-recipe-policy` | reject: recipe policy |
| `bad-core-hash` | reject: core file hash |
| `bad-line-hash` | reject: core line hash |
| `bad-utf8` | reject: encoding |
| `bad-field-type` | reject: recipe types |

`knowledge_pack_golden.py` (predictor branch) regenerates the vectors byte for
byte from `golden-v1/recipes/`. `test_knowledge_pack_golden.py` checks the
Python reader against them and `PresetKnowledgePackTest` checks the Java
reader. A reader in another language should run the same eight cases in its
own tests.
