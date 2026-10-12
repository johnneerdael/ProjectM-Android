# Mood facets: multi-select preset attributes (design)

Status: proposed, 2026-10-12. Author: predictor work stream.

## Brief (agreed with the owner)

- Viewers open **Mood** and multi-select attributes they want; the result is the mix
  that auto-switch, Random and Previous draw from. No learning: the selection *is* the
  preference.
- The panel always shows how many presets remain in the pool.
- TV remote (D-pad) in the existing settings panel, framework views only, everything on
  the TV (no network, no new runtime dependencies).
- The engine lives in the **core library** so Milkbeat can use it through the AAR.
- Selections combine as **facet groups**: OR within a group, AND across groups.
- Bundled presets use **engine-ruler measurements**; presets without measurements
  (custom packs) are excluded whenever any facet is active (they remain under All/Custom).
- **Dead ends are prevented**: options that would leave zero presets are dimmed and not
  selectable.
- Facets are part of the **Python SDK and the JSON contract** with one source of truth.

Success: a viewer can say "calm, colourful, no strobe, kaleidoscope", sees immediately
how many presets match, and the visualizer stays inside that mix without empty pools.

## 1. Facet set (v1)

Each option is a boolean property per preset. Thresholds are fixed constants recorded in
the definition file (not recomputed per release). Ruler statistics are measured on frames
60–299 of a 300-frame, 30 fps, 480×270 render with the checkpoint audio.

| Group (id) | Option (id) | Rule |
|---|---|---|
| Energy (`energy`) | Chill (`chill`), Normal (`normal`), Intense (`intense`) | Activity = rank-average of frame difference, flow speed and brightness jumps; Chill: activity percentile ≤ 0.35; Normal: 0.25–0.75; Intense: ≥ 0.70 (overlapping like today). The percentile cut points are converted once to absolute activity values and frozen in the definition. |
| Brightness (`brightness`) | Dark (`dark`), Balanced (`balanced`), Bright (`bright`) | Mean luminance < 0.12 / 0.12–0.40 / > 0.40 |
| Colour (`colour`) | Monochrome (`monochrome`), Pastel (`pastel`), Vivid (`vivid`), Warm (`warm`), Cool (`cool`) | Monochrome: coloured share < 0.10. Pastel: mean luminance > 0.35 and saturation < 0.30 and not monochrome. Vivid: saturation ≥ 0.50. Warm: warm-cool ≥ +0.25. Cool: ≤ −0.25. Options are independent (Vivid + Warm possible). |
| Movement (`movement`) | Still (`still`), Drifting (`drifting`), Fast (`fast`) | Flow < 0.05 / 0.05–0.25 / > 0.25 screen widths per second |
| Style (`style`) | Kaleidoscope (`kaleidoscope`), Tunnel (`tunnel`), Liquid (`liquid`), Geometric (`geometric`), Particles (`particles`), Fractal (`fractal`) | Source structure facts: mirror fold ≥ 2 or symmetry ≥ 0.55; radial zoom/tunnel mechanism; self-advection/organic ≥ 0.6; polygon/instanced shapes geometric ≥ 0.6; closed-form point clouds or particle mechanisms; recurrence/fractal mechanism ≥ 0.6 |
| Comfort (`comfort`) | No strobe (`no_strobe`) | Global brightness jumps < 1 per 10 s (measured) |

No selection in a group means "any". The default (nothing selected) is the full library,
identical to today's **All**.

## 2. Data bundle and build pipeline

- Single definition: `tools/milk-analyzer/facets/facets-v1.json` — schema version, groups,
  options, labels, thresholds, combination rule, per-option provenance.
- Android asset `core/src/main/assets/preset-attributes/`:
  - `facets.json`: byte-identical copy of the definition;
  - `attributes.bin`: header (magic, schema version, preset count, value scales) then one
    row per bundled preset in `presets.idx` order: uint32 option bitmask, six uint16
    fixed-point values (luma, saturation, warm-cool offset, flow, frame difference,
    jumps), uint16 flags (measured/unmeasured). ≈150 KB.
  - `manifest.json`: checksums, ruler identity (engine source/patches, renderer, size,
    frames, audio hash), definition hash, presets.idx hash.
- Producer `tools/milk-analyzer/attribute_bundle.py` joins ruler results with source facts
  and writes the bundle; `--check` verifies it against `presets.idx`, the definition and the
  manifest (CI). The bundle is regenerated deliberately when presets, engine or facets change.
- The engine ruler (macOS GLES + SwiftShader harness and driver) moves to
  `tools/native-ruler/` with a README; raw results are archived as evidence, not committed.

## 3. Core engine API (additive)

Package `nl.neerdael.projectm.core`:

- `PresetFacets` (pure Java, no Android types in its logic):
  - `static PresetFacets load(AssetManager)`; `List<Group> groups()` (ids, labels, options);
  - `Selection select(Set<String> optionIds)` with `int poolSize()`,
    `int countIfToggled(String optionId)`, `int[] presetIndices()`.
  - One `long[]` bitset per option; pool = AND over groups of OR within group; counts by
    bitset cardinality.
- `ProjectMJNI.setPresetPool(int[] indices)` restricts random/auto-switch/Previous to the
  given bundled-preset indices; `null` restores the full library. Skip list and prefetch
  still apply; displayed counts exclude skipped presets as today.
- `setMusicCategory(id)` / `getCategoryPresetCount(id)` keep their behaviour and map onto
  the Energy facet, so existing Milkbeat calls are unchanged.

## 4. Panel UI and remote behaviour (`:app`)

- **Preset mood** row opens a **Mood** sub-panel (same pattern as Advanced/Track display).
- Header: "N presets in your mix", live.
- One row per group; Left/Right moves between options, Center toggles; selected options
  highlighted; each option shows "→ N"; zero-result options dimmed and skipped by focus.
- **Clear all** row; Back returns to the main panel; 10 s auto-hide and per-key reset as today.
- Pool < 20: hint "few presets: some repetition".
- Persistence: `mood_facets` in `projectm_settings` (comma-separated option ids); one-time
  migration key maps the old single mood to the matching Energy option.
- Every option focusable with a content description including its count.

## 5. SDK and JSON contract

- `tools/milk-analyzer/preset_facets.py` (standard library) mirrors `PresetFacets`
  semantics exactly; shared test vectors (`fixtures/facet-selection-vectors-v1.json`)
  are run by both the JVM and Python tests.
- `preset_recipe.py` adds a versioned `facets` block per preset: option memberships, the
  raw values behind them, and per value its evidence (`engine-ruler-measured` or
  `source-calibrated`), label identity and, for calibrated values, an interval. Additive.
- `preference-index.json` carries each preset's facet bitmask and values;
  `preference_select.py` accepts `"facets": [...]` and returns pool, count, per-option
  counts and selected presets alongside existing profiles/comfort rules.
- Presets without ruler measurements get facet values from `calibrated_display.py`
  (source-calibrated), marked as such; bundled presets use measured values.
- Docs: `EXPORT_CONTRACT.md` (facets block, bundle format), the `understand-preset` skill
  ("select by facets"), user guide `predictor-export.md`.

## 6. Compatibility, documentation and testing

- Milkbeat: additive API only; no changed signatures or behaviours.
- User docs: README settings table, `docs/user-guide/settings.md`, `controls.md`,
  `predictive-collections.md` (Preset moods: facets, counts, how attributes are measured,
  limits).
- Tests: JVM `PresetFacetsTest` (group logic, counts, dimming, migration) and the shared
  vectors; Python tests for `preset_facets.py` on the same vectors; bundle `--check` in CI;
  native test that `setPresetPool` restricts selection; setup-screenshot instrumentation case
  for the Mood sub-panel and a D-pad journey on the task emulator.
- Delivery: a feature branch and PR to main through the mandatory workflow (Codex review),
  separate from the unmerged experimental predictor branch. The bundle requires the full
  ruler run (all 9,606 presets) before release.

## Limits

- Ruler values come from one 10 s render per preset with one synthetic audio track at
  480×270 under SwiftShader; real music and TV GPUs differ. Emulator agreement on 83
  presets was ρ 0.91–0.96, not a per-preset guarantee.
- Style options rest on source structure, not measurement, and are the least certain.
- Custom-pack presets are excluded while any facet is active.
