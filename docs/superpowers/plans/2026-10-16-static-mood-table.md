# Static Mood Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a mood table whose every facet comes from static source analysis, plus Palette and Main colour groups.

**Architecture:** The research worktree exports one static evidence file (per preset: sha256, options, palette,
dominant hue, 8 values, producer identity). On main, `attribute_bundle.py` gains `build_static()` (evidence →
`attributes.tsv` + `manifest.json` + `facets.json`) and a static `check()` path (two-way evidence match, preset bytes,
size budget). `facets-v1.json` gains the two colour groups; `preset_facets.py` learns their rule kinds. The Java parser
is unchanged.

**Tech Stack:** Python 3 standard library (main tools), numpy/sklearn venv on the research worktree, Java/JUnit (core).

**Spec:** `docs/superpowers/specs/2026-10-16-static-mood-table-design.md`

## Global Constraints

- TSV grammar unchanged: `#group`, `#option`, `#columns name options luminance saturation coloured_share warm_cool flow frame_difference jumps activity`.
- Palette: hue family share ≥ 0.10 of the static display palette; grey (monochrome admitted) → none.
- Main colour: predicted top-colour share ≥ 0.65 and palette top share ≥ 0.55; ids `main_<family>`.
- Families in order: red, orange, yellow, green, cyan, blue, purple, pink.
- Size budget: deflated `attributes.tsv` ≤ 450,000 bytes.
- No value from a ruler render; manifest `source` is `static-analysis`.
- Research branch is never merged; main does not import the predictor.

## Review Focus

- A preset in presets.idx with no evidence row → check must fail naming it (not silently skip).
- A preset file edited after analysis → check fails (evidence sha256 vs bytes).
- An evidence row naming an option not in the definition → build and check fail.
- Duplicate option ids across groups (e.g. `red` used twice) → definition load rejects (test in Task 1).
- Legacy ruler bundles (no `source` field) still check with the ruler path (existing tests keep passing).

---

### Task 1: Colour groups in the definition and rule kinds

**Files:**
- Modify: `tools/milk-analyzer/facets/facets-v1.json` (append groups `palette`, `main_colour` after `colour`)
- Modify: `tools/milk-analyzer/preset_facets.py` (`_holds`, `memberships`)
- Test: `tools/milk-analyzer/test_preset_facets.py`

**Interfaces:**
- Produces: `preset_facets.memberships(values, style, definition, colours=())` where `colours` is a set of tags
  `'palette:<family>'` and `'main:<family>'`; conditions `{"palette": f}` and `{"main_colour": f}`.

- [ ] **Step 1: Write the failing tests**

```python
    def test_colour_groups_follow_the_preset_colour_tags(self):
        d = F.load_definition()
        ids = F.option_ids(d)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn('palette', [g['id'] for g in d['groups']]); self.assertIn('main_colour', [g['id'] for g in d['groups']])
        members = F.memberships({}, set(), d, colours={'palette:red', 'palette:blue', 'main:red'})
        self.assertIn('red', members); self.assertIn('blue', members); self.assertIn('main_red', members)
        self.assertNotIn('green', members); self.assertNotIn('main_blue', members)
        self.assertFalse({'red', 'main_red'} & set(F.memberships({}, set(), d)))
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s tools/milk-analyzer -p 'test_preset_facets.py' -v`
Expected: FAIL (no palette group / unexpected keyword `colours`).

- [ ] **Step 3: Implement**

In `facets-v1.json`, after the `colour` group:

```json
{"id": "palette", "label": "Palette", "options": [
  {"id": "red", "label": "Red", "all": [{"palette": "red"}]}, ... one per family ...]},
{"id": "main_colour", "label": "Main colour", "options": [
  {"id": "main_red", "label": "Red", "all": [{"main_colour": "red"}]}, ... one per family ...]}
```

In `preset_facets.py`:

```python
def _holds(condition, values, style, members, colours=()):
    ...
    if 'palette' in condition:
        return 'palette:' + condition['palette'] in colours
    if 'main_colour' in condition:
        return 'main:' + condition['main_colour'] in colours
    raise ValueError(...)

def memberships(values, style, definition, colours=()):
    ... _holds(c, values, style, members, colours) ...
```

- [ ] **Step 4: Run the facet and bundle tests** — `test_preset_facets.py`, `test_attribute_bundle.py` pass.
- [ ] **Step 5: Commit** `feat(moods): Palette and Main colour groups in the facet definition`

### Task 2: Static builder and check in attribute_bundle.py

**Files:**
- Modify: `tools/milk-analyzer/attribute_bundle.py`
- Test: `tools/milk-analyzer/test_attribute_bundle.py`

**Interfaces:**
- Consumes: `preset_facets.option_ids`, `_header`, `_index_names`, `_presets_dir`, `_sha`, `_format`, `COLUMNS`.
- Produces:
  - `STATIC_EVIDENCE_SCHEMA = 'projectm-tv-static-mood-evidence'`, `SIZE_BUDGET = 450000`,
    `DEFAULT_STATIC_EVIDENCE = Path('docs/superpowers/evidence/static-mood-table-2026-10-16/static-evidence.json.gz')`
  - `load_static_evidence(path) -> dict` (gzip JSON: `{'schema', 'producer': {...}, 'rows': [{'name', 'sha256',
    'options', 'palette', 'dominant', 'values': {column: float|None}}]}`)
  - `build_static(evidence_path, presets_idx, output_dir, definition_path=None, presets_dir=None) -> manifest`
  - `check(...)`: routes to `check_static(bundle, presets_idx, evidence_path, definition_path, presets_dir)` when
    `manifest.get('source') == 'static-analysis'`.

- [ ] **Step 1: Write failing tests** (synthetic two-preset fixture written in a temp dir: presets.idx, two preset
  files, a definition copy, an evidence file with matching sha256): build_static then check → `[]`; edit one
  evidence option → check reports `evidence`; drop a row from evidence → build raises naming the preset; change a preset
  file → check reports `preset bytes`; set budget to 10 bytes via `size_budget=` → check reports `size budget`;
  an unknown option in evidence → build raises; the committed bundle passes check (uses DEFAULT_STATIC_EVIDENCE).
- [ ] **Step 2: Run** — FAIL (no build_static).
- [ ] **Step 3: Implement** `load_static_evidence`, `build_static` (rows sorted by name, options ordered by definition,
  values formatted with `_format`, manifest fields: schema, version, source, definition_sha256, presets_idx_sha256,
  attributes_sha256, static_evidence_sha256, producer, preset_count, measured_count (rows with any value),
  option_counts), `check_static` (facets.json equals definition; manifest hashes; header; names equal presets.idx;
  each row equals the evidence row; preset bytes equal evidence sha256; recomputed metadata; deflated size ≤ budget).
  `--check` passes `static_evidence=args.static_evidence or DEFAULT_STATIC_EVIDENCE`; add `--build-static EVIDENCE`.
- [ ] **Step 4: Run all bundle tests** — legacy ruler tests and new static tests pass.
- [ ] **Step 5: Commit** `feat(moods): static mood bundle builder and check`

### Task 3: Export the static evidence (research worktree)

**Files (research worktree `feat/predictor-static-output-bounds`):**
- Create: `build/colour-gap-2026-10-15/static_evidence_export.py` (research harness; not shipped)

**Interfaces:**
- Produces: `static-evidence.json.gz` with the schema above; per preset `values` = calibrated estimates
  (`mean_luminance`, `mean_saturation`, `coloured_share`, `warm_cool`, `mean_flow_screen_widths_per_s`,
  `mean_abs_frame_difference`, `global_brightness_jumps_per_10s`) and `activity` from `preset_recipe.facet_activity`;
  `options` = static facet options (style included) without colour ids; `palette` = display_palette palette;
  `dominant` = dominant_hue or null; `sha256` from the corpus record; producer = research commit, model sha256.

- [ ] **Step 1:** run the export for all 9,606 presets (12 workers); verify 0 errors, 9,606 rows.
- [ ] **Step 2:** copy the file to `docs/superpowers/evidence/static-mood-table-2026-10-16/` on the main worktree.

### Task 4: Generate and ship the bundle

**Files:**
- Modify: `core/src/main/assets/preset-attributes/{attributes.tsv,manifest.json,facets.json}`
- Create: `docs/superpowers/evidence/static-mood-table-2026-10-16/{static-evidence.json.gz,README.md}`
- Test: `core/src/test/java/nl/neerdael/projectm/core/PresetFacetsTest.java`

- [ ] **Step 1: Failing Java test**

```java
    @Test public void bundledTableHasStaticColourGroups() throws IOException {
        PresetFacets f = PresetFacets.parse(Files.newBufferedReader(Paths.get("src/main/assets/preset-attributes/attributes.tsv")));
        assertEquals(9606, f.presetCount());
        List<String> ids = new ArrayList<>(); for (PresetFacets.Group g : f.groups()) ids.add(g.id);
        assertTrue(ids.contains("palette")); assertTrue(ids.contains("main_colour"));
        int red = f.select(Collections.singletonList("red"), Collections.emptyList()).poolSize();
        int redOrBlue = f.select(Arrays.asList("red", "blue"), Collections.emptyList()).poolSize();
        assertTrue(red > 0 && redOrBlue >= red);
    }
```

- [ ] **Step 2:** `python3 tools/milk-analyzer/attribute_bundle.py --build-static <evidence>`; `--check` passes.
- [ ] **Step 3:** `./gradlew :core:testReleaseUnitTest :app:testReleaseUnitTest` pass.
- [ ] **Step 4: Commit** `feat(moods): ship the static mood table`

### Task 5: Documentation

- [ ] User guide Mood page, README Mood section, `docs/user-guide/settings.md`, `tools/milk-analyzer/README.md`,
  `AGENTS.md` provenance line; `mkdocs build --strict` passes. Commit `docs(moods): static moods and colour groups`.

### Task 6: PR to merge

- [ ] Push, open PR (template, release notes, validation, documentation assessment), CI green, Codex review of the
  final head, threads resolved, merge, verify release workflow.
