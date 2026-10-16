# Static mood table: every Mood facet from static analysis, plus colour palettes

Date: 2026-10-16. Status: design approved by the owner; this spec awaits review.

## Purpose

The Mood menu groups the 9,606 bundled presets by facets (energy, brightness, colour, movement, style, comfort).
Today `core/src/main/assets/preset-attributes/attributes.tsv` is built from engine-ruler renders (pinned patched
source34, macOS GLES/SwiftShader, 300 frames at 480x270). The owner wants that dependency on rendered simulation to
stop: "They are today still based on simulation, that needs to stop, so we need to change the entire corpus."

Outcome: the shipped mood table comes entirely from static source analysis (the predictor on the research branch
`feat/predictor-static-output-bounds`), and adds two colour groups, Palette and Main colour.

Success criteria:

1. Every option in `attributes.tsv` comes from static analysis. No value is taken from a ruler render.
2. Palette and Main colour appear in the Mood menu with no app or core code change (`PresetFacets` is data driven).
3. The asset stays within a committed compressed-size budget.
4. CI validates the table against committed static evidence, as it validated the ruler table against ruler evidence.

## Decisions and accepted trade-offs (owner)

- **Static moods for the whole corpus,** accepting smaller mood pools. Counts from the current static index:
  Balanced 4,304 → 1,236, No strobe 4,969 → 712, Normal 4,807 → 2,072, Drifting 4,752 → 1,712. 427 presets get no
  Mood option apart from style. The owner: "Its fine to have unlabelled presets, it allows me as human to give
  feedback on the quality."
- **Precision over recall:** middle options (Balanced, Drifting, Normal) are held to the shipped 80% precision floor,
  Pastel to 70%. Out of fold the static facets are about 79% precise with about 41% recall pooled. On bundled presets
  (the calibration's training set) 86–100% of static admissions per option agree with today's ruler table.
- **Palette + Main colour** (owner choice). Palette: every hue family with at least 10% of the static display palette.
  Main colour: set only when the predicted top-colour share is at least 0.65 and the palette's top share is at least
  0.55 (out of fold: 84% of claims name the engine's top colour). Grey presets (monochrome admitted) get neither.
- **No new asset format:** the table stays the existing TSV, deflated inside the APK/AAR. "Compressed fashion" needs no
  separate format: 1.56 MB raw is 377 KB compressed, and the colour groups add about 25 KB (about 2.6 bytes per preset).

## Architecture

### Producer (research branch, offline)

The static predictor lives on `feat/predictor-static-output-bounds`, which is never merged to main. A generator there
(`tools/milk-analyzer/static_attribute_table.py`) writes, from the static grouping export (per preset: options,
palette, dominant hue, calibrated estimates):

- `attributes.tsv`: same header grammar (`#group`, `#option`, `#columns`) and the same 8 value columns, now holding the
  static calibrated estimates (luminance, saturation, coloured share, warm/cool, flow, frame difference, jumps,
  activity). The app does not read these values; the parser only checks their count.
- `static-evidence.json`: a committed evidence manifest with one row per preset (name, preset sha256, options,
  palette, dominant hue, the 8 values), the producer identity (research commit, calibration model sha256, analyzer
  policy versions) and its own sha256. It replaces the ruler results manifest as the table's evidence.
- `manifest.json`: `schema` unchanged; `source: "static-analysis"`; `static_evidence_sha256`; model and producer
  identities; option counts; `presets_idx_sha256` and `definition_sha256` as before. The `ruler` block and
  `ruler_results_manifest_sha256` are removed.

The generated files are copied into the main-based feature branch. Main does not import or run the predictor.

### Definition (`facets.json`)

Two groups are added after `colour`:

- `palette` (label "Palette"): options `red`, `orange`, `yellow`, `green`, `cyan`, `blue`, `purple`, `pink`, each with
  rule `{"palette": "<family>"}`.
- `main_colour` (label "Main colour"): options `main_red` … `main_pink` (ids must be unique across groups), each with
  rule `{"main_colour": "<family>"}`.

`preset_facets.py` (Python mirror of the selection logic) learns the two rule kinds, reading the per-preset palette and
dominant hue from the evidence row, like the existing style rules. `PresetFacets.java` needs no change: it builds groups
from the TSV header and memberships from each row.

### Checks (main)

`attribute_bundle.py` gains a static path, replacing the ruler path for the shipped bundle:

- `--check` validates `attributes.tsv` against `static-evidence.json` in both directions (same names, same options, same
  values), checks the evidence sha256 against the manifest, checks `presets.idx` and every preset's bytes against the
  evidence sha256 (so a changed preset fails until re-analysed), and checks `facets.json` against the definition.
- **Size budget:** the deflated size of `attributes.tsv` must be at most 450 KB, so growth needs a deliberate change.
- The ruler-only builders (`build`, `freeze_activity_reference`, `write_evidence_manifest`) are kept for history but no
  longer produce the shipped bundle; their tests stay.

CI keeps its existing steps (`test_attribute_bundle.py`, `attribute_bundle.py --check`, `test_*facet*.py`).
`tools/preset_distribution.py`, which rewrites `attributes.tsv` for distribution builds, is checked for compatibility
with the added groups.

### App

No code change. The Mood menu shows Palette and Main colour as two more `FacetRow`s (horizontal chip strips with
existing D-pad handling). Selection semantics are unchanged: OR within a group, AND across groups. `MoodFacetsController`
counts and dimming work from the table.

## Data flow

research predictor (static only) → static grouping export (9,606 presets) → `static_attribute_table.py` →
`attributes.tsv` + `static-evidence.json` + `manifest.json` → copied to `feat/static-mood-table` →
`attribute_bundle.py --check` in CI → `PresetFacets` in the core AAR → Mood menu (app; Milkbeat if it uses PresetFacets).

## Error handling

- A preset whose static analysis failed gets no options and empty values (`-`). The generator reports the count and
  fails if it exceeds a small limit (0 for the current export, which covers all 9,606 presets).
- Grey presets: no palette and no main colour (consistent with Monochrome).
- `--check` reports every mismatch (missing or extra preset, option drift, stale hash, budget exceeded) and fails CI.

## Testing

- Generator (research branch): palette 10% threshold, main-colour double condition, grey presets, unique option ids,
  value formatting.
- `test_attribute_bundle.py` (main): the static check passes on the shipped bundle; it fails on option drift, a missing
  or extra preset, a stale evidence hash, a changed preset file and a budget overrun (synthetic fixtures).
- `test_*facet*.py`: the new rule kinds in `preset_facets.py`.
- `PresetFacetsTest` (Java): the shipped table parses with the new groups and selection across Palette/Main colour
  behaves (OR within, AND across).
- `MoodFacetsControllerTest`: unchanged behaviour with extra groups.
- Manual: Mood menu on the emulator shows the two new rows and filters as expected.

## Documentation

- User guide (`docs/user-guide/`): the Mood/collections page explains that moods come from static source analysis, the
  two colour groups, and that some presets are deliberately unlabelled for feedback.
- README settings/Mood section and `docs/user-guide/settings.md`: Palette and Main colour.
- `tools/milk-analyzer/README.md` and `AGENTS.md`: the static bundle provenance and check.
- PR release notes: moods now from static analysis (smaller, more precise groups; some presets unlabelled); new Palette
  and Main colour filters.

## Out of scope

- On-device analysis of presets that are not bundled (the analyzer is offline Python).
- Merging the research branch; changing `PresetFacets` or the TSV grammar; feedback collection UI.
- Re-tuning facet thresholds (the shipped research model is used as is).
