# Mood Facets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Viewers multi-select preset attributes (Energy, Brightness, Colour, Movement, Style, Comfort) in a Mood sub-panel. The selection becomes the pool that auto-switch, Random and Previous draw from, with live counts and no dead ends. The same facets are available to Milkbeat through the core AAR and to the Python SDK through a versioned JSON contract.

**Architecture:** A single facet definition (`tools/milk-analyzer/facets/facets-v1.json`) states groups, options and threshold rules. A standard-library producer joins engine-ruler measurements of the bundled presets with source style facts. It writes `core/src/main/assets/preset-attributes/` (definition copy, a name-keyed attributes table and a manifest) and verifies it in CI with `--check`. The core library parses the table (`PresetFacets`, pure Java) and hands the resulting preset names to the native library, which plays them as a `facets` category through the existing category machinery (history, skip list, prefetch). The app adds a Mood sub-panel built from the definition.

**Tech Stack:** Python 3 standard library (`unittest`), Java 8 source level with framework views only, JNI/C++17 (`native-lib.cpp` and its host engine test), Gradle/AGP 8.12.0, MkDocs.

**Spec:** `docs/superpowers/specs/2026-10-12-mood-facets-design.md` (approved by the owner on 2026-10-12).

## Spec adjustments required by the current `main`

Since the spec was written, `main` gained distribution editions. The F-Droid build ships 20 starter presets, and an optional official archive (`tools/preset_distribution.py`, `OfficialPresetPack.java`) carries the full collection with its own `presets.idx` and `preset-genres/`. The spec's SDK files exist only on the unmerged predictor branch. The plan therefore makes four adjustments. Each is listed here so the reviewer can reject one independently.

1. **Name-keyed attributes, not presets.idx order.** `attributes.bin` (rows in presets.idx order) becomes `attributes.tsv`: a catalog header plus one row per preset name. The same file can then be filtered for the 20-preset starter edition and shipped unchanged in the official archive. APK asset compression keeps it small.
2. **`setPresetPool(String[] names)`, not `int[] indices`.** Names survive official-pack swaps and edition differences; indices do not. `PresetFacets.Selection.presetNames()` replaces `presetIndices()`.
3. **Legacy categories unchanged.** `setMusicCategory("chill"|"normal"|"intense")` and `getCategoryPresetCount` keep their current source, the predictive-collection bundle in `preset-genres/`, so Milkbeat is unaffected. The app migrates a stored legacy mood to the matching Energy option. Re-sourcing the legacy categories from ruler activity would change `beta_export.py --check` identities and is left out of v1.
4. **The SDK half runs on the predictor branch.** Task 11 extends the recipe, preference index, `preference_select.py`, `EXPORT_CONTRACT.md` and the `understand-preset` skill, which exist only there. It never merges to `main`, per the owner's standing instruction. Tasks 1–10 form the `main` PR.

## Global Constraints

- The `main` PR follows the mandatory workflow in `AGENTS.md`. It uses the worktree `<primary>/.worktrees/mood-facets` on branch `feat/mood-facets`, based on `origin/main`. It includes the documentation assessment, release notes, Codex review of the final head, and merge. No version bumps.
- Framework views only. No AndroidX, Leanback library or new runtime dependency. Java source level 1.8.
- Everything runs on the TV with no network. `PresetFacets` logic uses no Android types; the Android-only part is `load(AssetManager)`.
- Facet groups combine as OR within a group and AND across groups. No selection in a group means "any"; nothing selected anywhere is the full library, as **All** is today.
- Options that would leave zero presets are dimmed and cannot be selected. A selected option is never dimmed, so it can always be cleared.
- Bundled presets use engine-ruler measurements. Presets without measurements (custom packs) are excluded whenever any facet is active and remain under All/Custom.
- Thresholds are fixed constants in the definition, copied verbatim from the spec:
  - Energy: Chill activity ≤ 0.35; Normal 0.25–0.75; Intense ≥ 0.70.
  - Brightness: mean luminance < 0.12 / 0.12–0.40 / > 0.40.
  - Colour: Monochrome coloured share < 0.10; Pastel luminance > 0.35, saturation < 0.30 and not Monochrome; Vivid saturation ≥ 0.50; Warm warm-cool ≥ +0.25; Cool ≤ −0.25.
  - Movement: flow < 0.05 / 0.05–0.25 / > 0.25 screen widths per second.
  - Comfort: No strobe, global brightness jumps < 1 per 10 s.
  - Style: mirror fold or symmetry ≥ 0.55; radial zoom/tunnel mechanism; self-advection/organic ≥ 0.6; geometric ≥ 0.6; point clouds or particle mechanisms; recurrence/fractal mechanism or fractal ≥ 0.6.
- Ruler statistics are measured on frames 60–299 of a 300-frame, 30 fps, 480×270 render with the checkpoint audio. They are calibration and attribute data, never source-classification inputs.
- Owner decision (2026-10-12): source simulation outputs are diagnostics only. No facet value comes from `simulated_display_series`.
- Persistence: `mood_facets` in `projectm_settings` holds comma-separated option ids, plus a one-time migration key `mood_facets_migrated_1`.
- Public core API changes are additive only: `PresetFacets` is new, and `ProjectMJNI.setPresetPool(String[])` is a new native method.
- Remote contract: in the Mood panel Up/Down moves between rows, Left/Right moves between options and Center toggles. Back returns to the main panel. The panel auto-hides after 10 s without input, and every key restarts the timer. Every option is focusable, and its content description includes its count.
- Keep setting names identical in the UI, the README settings table and `docs/user-guide/settings.md`. Menu paths use `›`.

## Review Focus

- **The skip list empties the active pool after selection.** For example, the last two matching presets fail to load. The native library falls back to All, and the panel says so. The stored selection is kept so the mix returns when a reset frees presets. Task 6 adds an engine test; Task 9 adds a controller test.
- **The F-Droid starter edition or an official pack is active.** Counts reflect only presets present in the active library. Options with zero members are dimmed, and a pool never names an absent preset. Task 5 adds a starter filtering test, Task 6 an official-commit pool reapplication test, and Task 7 a test that absent names are ignored.
- **A custom pack is selected while facets are stored.** Facet rows are disabled and the custom pack plays. Switching back restores the stored facets. Task 9 adds a controller test.
- **The attributes asset is missing or malformed** (an older official archive, a truncated file). The Mood panel offers only the collection choice and does not crash. Task 7 adds parse-failure tests; Task 9 adds a fallback test.
- **A stored `mood_facets` contains unknown ids after a definition change.** Unknown ids are dropped and the rest is kept. Task 7 adds a selection test; Task 9 adds a persistence test.

---

### Task 1: Facet definition, Python selection semantics and shared vectors

**Files:**
- Create: `tools/milk-analyzer/facets/facets-v1.json`
- Create: `tools/milk-analyzer/preset_facets.py`
- Create: `tools/milk-analyzer/fixtures/facet-selection-vectors-v1.json`
- Create: `tools/milk-analyzer/test_preset_facets.py`
- Modify: `.github/workflows/android-build.yml` (add a test step after "Test diagnostics options")
- Copy: `docs/superpowers/specs/2026-10-12-mood-facets-design.md` and this plan from the predictor branch into the new worktree

**Interfaces:**
- Produces:
  - `preset_facets.load_definition(path=None) -> dict`
  - `preset_facets.option_ids(definition) -> list[str]`
  - `preset_facets.group_of(definition) -> dict[str, str]`
  - `preset_facets.memberships(values: dict, style: set[str], definition) -> list[str]`, where `values` keys are `luminance`, `saturation`, `coloured_share`, `warm_cool`, `flow`, `frame_difference`, `jumps` and `activity`
  - `preset_facets.select(rows: list[dict], selected: list[str], definition, excluded=()) -> dict`, where rows are `{'name': str, 'options': list[str]}` and the result keys are `selected`, `ignored`, `pool`, `count`, `option_counts` and `dimmed`

- [ ] **Step 1: Create the worktree and copy the spec and plan**

```bash
cd /Users/jneerdael/Scripts/Projectm-TV
git check-ignore -q .worktrees/ || echo ".worktrees/" >> "$(git rev-parse --git-common-dir)/info/exclude"
git fetch origin main
git worktree add -b feat/mood-facets .worktrees/mood-facets origin/main
cd .worktrees/mood-facets
cp ../../.worktrees/predictor-memory-repair/docs/superpowers/specs/2026-10-12-mood-facets-design.md docs/superpowers/specs/
cp ../../.worktrees/predictor-memory-repair/docs/superpowers/plans/2026-10-12-mood-facets.md docs/superpowers/plans/
cp ../../local.properties . 2>/dev/null || cp ../predictor-memory-repair/local.properties .
git submodule update --init --recursive
```

- [ ] **Step 2: Write the definition file**

`tools/milk-analyzer/facets/facets-v1.json`:

```json
{
  "schema": "projectm-tv-mood-facets",
  "version": 1,
  "combination": "OR within a group, AND across groups; no selection in a group means any",
  "measurement": "engine ruler: pinned patched projectM-TV, 480x270, 300 frames at 30 fps, checkpoint audio, statistics over frames 60-299",
  "activity": "percentile of the mean percentile rank of mean_abs_frame_difference, mean_flow_screen_widths_per_s and global_brightness_jumps_per_10s within the measured bundled corpus",
  "groups": [
    {"id": "energy", "label": "Energy", "options": [
      {"id": "chill", "label": "Chill", "all": [{"metric": "activity", "op": "<=", "value": 0.35}]},
      {"id": "normal", "label": "Normal", "all": [{"metric": "activity", "op": ">=", "value": 0.25}, {"metric": "activity", "op": "<=", "value": 0.75}]},
      {"id": "intense", "label": "Intense", "all": [{"metric": "activity", "op": ">=", "value": 0.70}]}]},
    {"id": "brightness", "label": "Brightness", "options": [
      {"id": "dark", "label": "Dark", "all": [{"metric": "luminance", "op": "<", "value": 0.12}]},
      {"id": "balanced", "label": "Balanced", "all": [{"metric": "luminance", "op": ">=", "value": 0.12}, {"metric": "luminance", "op": "<=", "value": 0.40}]},
      {"id": "bright", "label": "Bright", "all": [{"metric": "luminance", "op": ">", "value": 0.40}]}]},
    {"id": "colour", "label": "Colour", "options": [
      {"id": "monochrome", "label": "Monochrome", "all": [{"metric": "coloured_share", "op": "<", "value": 0.10}]},
      {"id": "pastel", "label": "Pastel", "all": [{"metric": "luminance", "op": ">", "value": 0.35}, {"metric": "saturation", "op": "<", "value": 0.30}, {"not_option": "monochrome"}]},
      {"id": "vivid", "label": "Vivid", "all": [{"metric": "saturation", "op": ">=", "value": 0.50}]},
      {"id": "warm", "label": "Warm", "all": [{"metric": "warm_cool", "op": ">=", "value": 0.25}]},
      {"id": "cool", "label": "Cool", "all": [{"metric": "warm_cool", "op": "<=", "value": -0.25}]}]},
    {"id": "movement", "label": "Movement", "options": [
      {"id": "still", "label": "Still", "all": [{"metric": "flow", "op": "<", "value": 0.05}]},
      {"id": "drifting", "label": "Drifting", "all": [{"metric": "flow", "op": ">=", "value": 0.05}, {"metric": "flow", "op": "<=", "value": 0.25}]},
      {"id": "fast", "label": "Fast", "all": [{"metric": "flow", "op": ">", "value": 0.25}]}]},
    {"id": "style", "label": "Style", "options": [
      {"id": "kaleidoscope", "label": "Kaleidoscope", "all": [{"style": "kaleidoscope"}]},
      {"id": "tunnel", "label": "Tunnel", "all": [{"style": "tunnel"}]},
      {"id": "liquid", "label": "Liquid", "all": [{"style": "liquid"}]},
      {"id": "geometric", "label": "Geometric", "all": [{"style": "geometric"}]},
      {"id": "particles", "label": "Particles", "all": [{"style": "particles"}]},
      {"id": "fractal", "label": "Fractal", "all": [{"style": "fractal"}]}]},
    {"id": "comfort", "label": "Comfort", "options": [
      {"id": "no_strobe", "label": "No strobe", "all": [{"metric": "jumps", "op": "<", "value": 1.0}]}]}
  ],
  "style_rules": {
    "kaleidoscope": "mechanism angular_mirror_fold or cartesian_mirror_fold, or structure.symmetry >= 0.55",
    "tunnel": "mechanism polar_radial_sampling or radial_feedback_transform, or a radial zoom profile contracting/expanding about the centre",
    "liquid": "mechanism image_driven_advection or gradient_driven_advection, or structure.organic >= 0.6",
    "geometric": "structure.geometric >= 0.6 (polygon/instanced shapes)",
    "particles": "mechanism point_cloud_primitive or procedural_point_motion",
    "fractal": "mechanism nonlinear_feedback_map or complex_quadratic_recurrence, or structure.fractal >= 0.6"
  },
  "provenance": {
    "energy": "engine-ruler-measured", "brightness": "engine-ruler-measured", "colour": "engine-ruler-measured",
    "movement": "engine-ruler-measured", "comfort": "engine-ruler-measured", "style": "source-structure-facts"
  }
}
```

- [ ] **Step 3: Write the shared vectors fixture**

`tools/milk-analyzer/fixtures/facet-selection-vectors-v1.json` uses eight synthetic presets so that the Python and JVM suites assert identical semantics:

```json
{
  "definition_version": 1,
  "rows": [
    {"name": "a.milk", "options": ["chill", "dark", "still", "no_strobe", "tunnel"]},
    {"name": "b.milk", "options": ["chill", "normal", "balanced", "drifting", "no_strobe", "liquid"]},
    {"name": "c.milk", "options": ["normal", "bright", "vivid", "warm", "drifting"]},
    {"name": "d.milk", "options": ["intense", "bright", "vivid", "fast", "kaleidoscope"]},
    {"name": "e.milk", "options": ["intense", "dark", "cool", "fast"]},
    {"name": "f.milk", "options": ["normal", "intense", "balanced", "monochrome", "drifting", "no_strobe", "fractal"]},
    {"name": "g.milk", "options": ["chill", "bright", "pastel", "still", "no_strobe", "particles"]},
    {"name": "h.milk", "options": ["normal", "balanced", "cool", "drifting", "geometric"]}
  ],
  "cases": [
    {"selected": [], "excluded": [], "pool": ["a.milk", "b.milk", "c.milk", "d.milk", "e.milk", "f.milk", "g.milk", "h.milk"],
     "option_counts": {"chill": 3, "intense": 3, "vivid": 2, "no_strobe": 4, "fractal": 1}, "dimmed": []},
    {"selected": ["chill"], "excluded": [], "pool": ["a.milk", "b.milk", "g.milk"],
     "option_counts": {"chill": 8, "intense": 6, "dark": 1, "vivid": 0, "no_strobe": 3, "tunnel": 1, "fractal": 0},
     "dimmed": ["vivid", "warm", "cool", "monochrome", "fast", "kaleidoscope", "fractal", "geometric"]},
    {"selected": ["chill", "intense"], "excluded": [], "pool": ["a.milk", "b.milk", "d.milk", "e.milk", "f.milk", "g.milk"],
     "option_counts": {"chill": 3, "dark": 2, "no_strobe": 4}, "dimmed": ["warm", "geometric"]},
    {"selected": ["chill", "no_strobe"], "excluded": ["a.milk"], "pool": ["b.milk", "g.milk"],
     "option_counts": {"tunnel": 0, "liquid": 1, "no_strobe": 2},
     "dimmed": ["dark", "tunnel", "vivid", "warm", "cool", "monochrome", "fast", "kaleidoscope", "fractal", "geometric"]},
    {"selected": ["chill", "unknown_option"], "excluded": [], "pool": ["a.milk", "b.milk", "g.milk"],
     "ignored": ["unknown_option"], "option_counts": {"chill": 8}, "dimmed": []}
  ]
}
```

Semantics of `option_counts[id]`: the pool size if `id` were toggled (added when unselected, removed when selected), excluding names in `excluded`. `dimmed` lists unselected options whose toggled count is 0; it is asserted as a set, and the last case asserts only that `dimmed` contains every listed id. Case 4 shows that exclusion (the skip list) feeds dimming.

- [ ] **Step 4: Write the failing test**

`tools/milk-analyzer/test_preset_facets.py`:

```python
import json
import unittest
from pathlib import Path

import preset_facets as F

HERE = Path(__file__).parent
VECTORS = json.loads((HERE / 'fixtures' / 'facet-selection-vectors-v1.json').read_text())


class DefinitionTest(unittest.TestCase):
    def test_groups_and_ids_are_unique_and_versioned(self):
        d = F.load_definition()
        self.assertEqual(d['version'], 1)
        ids = F.option_ids(d)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([g['id'] for g in d['groups']], ['energy', 'brightness', 'colour', 'movement', 'style', 'comfort'])
        self.assertEqual(F.group_of(d)['no_strobe'], 'comfort')


class MembershipTest(unittest.TestCase):
    def setUp(self):
        self.d = F.load_definition()

    def values(self, **kw):
        base = dict(luminance=.2, saturation=.4, coloured_share=.5, warm_cool=0., flow=.1, frame_difference=.02, jumps=0., activity=.5)
        base.update(kw)
        return base

    def test_thresholds_follow_the_spec_boundaries(self):
        m = F.memberships(self.values(activity=.30), set(), self.d)
        self.assertIn('chill', m); self.assertIn('normal', m); self.assertNotIn('intense', m)
        m = F.memberships(self.values(activity=.72), set(), self.d)
        self.assertIn('normal', m); self.assertIn('intense', m)
        self.assertIn('balanced', F.memberships(self.values(luminance=.12), set(), self.d))
        self.assertIn('dark', F.memberships(self.values(luminance=.1199), set(), self.d))
        self.assertIn('bright', F.memberships(self.values(luminance=.4001), set(), self.d))
        self.assertIn('no_strobe', F.memberships(self.values(jumps=.99), set(), self.d))
        self.assertNotIn('no_strobe', F.memberships(self.values(jumps=1.), set(), self.d))

    def test_pastel_excludes_monochrome_and_colour_options_are_independent(self):
        m = F.memberships(self.values(luminance=.5, saturation=.1, coloured_share=.05), set(), self.d)
        self.assertIn('monochrome', m); self.assertNotIn('pastel', m)
        m = F.memberships(self.values(luminance=.5, saturation=.1, coloured_share=.3), set(), self.d)
        self.assertIn('pastel', m)
        m = F.memberships(self.values(saturation=.6, warm_cool=.3), set(), self.d)
        self.assertIn('vivid', m); self.assertIn('warm', m)

    def test_style_options_come_from_style_facts_only(self):
        self.assertIn('tunnel', F.memberships(self.values(), {'tunnel'}, self.d))
        self.assertNotIn('tunnel', F.memberships(self.values(), set(), self.d))

    def test_missing_metric_never_matches(self):
        values = self.values(); del values['coloured_share']
        m = F.memberships(values, set(), self.d)
        self.assertNotIn('monochrome', m); self.assertNotIn('pastel', m)


class SelectionVectorTest(unittest.TestCase):
    def test_shared_vectors(self):
        d = F.load_definition()
        for case in VECTORS['cases']:
            with self.subTest(selected=case['selected']):
                result = F.select(VECTORS['rows'], case['selected'], d, case['excluded'])
                self.assertEqual(result['pool'], case['pool'])
                self.assertEqual(result['count'], len(case['pool']))
                for option, count in case['option_counts'].items():
                    self.assertEqual(result['option_counts'][option], count, option)
                if 'ignored' in case:
                    self.assertEqual(result['ignored'], case['ignored'])
                    self.assertTrue(set(case['dimmed']) <= set(result['dimmed']))
                else:
                    self.assertEqual(set(result['dimmed']), set(case['dimmed']))

    def test_selected_option_is_never_dimmed(self):
        d = F.load_definition()
        # fractal (style) AND vivid (colour) match no row; both stay clearable.
        result = F.select(VECTORS['rows'], ['fractal', 'vivid'], d)
        self.assertEqual(result['count'], 0)
        self.assertNotIn('fractal', result['dimmed']); self.assertNotIn('vivid', result['dimmed'])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `cd tools/milk-analyzer && python3 -m unittest test_preset_facets -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'preset_facets'`.

- [ ] **Step 6: Implement `preset_facets.py`**

```python
"""Mood facet memberships and selection (standard library).

Facet groups combine OR within a group and AND across groups; a group without a selection means
"any". Memberships come from the frozen definition (facets/facets-v1.json): metric thresholds on
display statistics and source style facts. The Java PresetFacets mirrors select() exactly; both
run fixtures/facet-selection-vectors-v1.json.
"""
import json
from pathlib import Path

DEFINITION = Path(__file__).with_name('facets') / 'facets-v1.json'
_OPS = {'<': lambda a, b: a < b, '<=': lambda a, b: a <= b, '>': lambda a, b: a > b, '>=': lambda a, b: a >= b}


def load_definition(path=None):
    return json.loads(Path(path or DEFINITION).read_text())


def option_ids(definition):
    return [option['id'] for group in definition['groups'] for option in group['options']]


def group_of(definition):
    return {option['id']: group['id'] for group in definition['groups'] for option in group['options']}


def _holds(condition, values, style, members):
    if 'metric' in condition:
        value = values.get(condition['metric'])
        return type(value) in (int, float) and _OPS[condition['op']](float(value), float(condition['value']))
    if 'style' in condition:
        return condition['style'] in style
    if 'not_option' in condition:
        return condition['not_option'] not in members
    raise ValueError('unknown facet condition: ' + json.dumps(condition))


def memberships(values, style, definition):
    """Option ids a preset belongs to; options are evaluated in definition order (not_option sees earlier ones)."""
    members = []
    for group in definition['groups']:
        for option in group['options']:
            if all(_holds(c, values, style, members) for c in option['all']):
                members.append(option['id'])
    return members


def _pool(rows, selected, groups, excluded):
    by_group = {}
    for option in selected:
        by_group.setdefault(groups[option], set()).add(option)
    return [row['name'] for row in rows if row['name'] not in excluded
            and all(set(row['options']) & wanted for wanted in by_group.values())]


def select(rows, selected, definition, excluded=()):
    groups = group_of(definition)
    excluded = set(excluded)
    chosen = [option for option in dict.fromkeys(selected) if option in groups]
    ignored = [option for option in dict.fromkeys(selected) if option not in groups]
    pool = _pool(rows, chosen, groups, excluded)
    counts = {}
    for option in option_ids(definition):
        toggled = [o for o in chosen if o != option] if option in chosen else chosen + [option]
        counts[option] = len(_pool(rows, toggled, groups, excluded))
    dimmed = [option for option, count in counts.items() if count == 0 and option not in chosen]
    return {'selected': chosen, 'ignored': ignored, 'pool': pool, 'count': len(pool),
            'option_counts': counts, 'dimmed': dimmed}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd tools/milk-analyzer && python3 -m unittest test_preset_facets -v`
Expected: all tests PASS. If a vector count disagrees, fix the fixture only after recomputing it by hand from the eight rows (the fixture is the contract the JVM suite also asserts).

- [ ] **Step 8: Run the facet tests in CI**

In `.github/workflows/android-build.yml`, after the step named "Test diagnostics options", add:

```yaml
      - name: Test mood facets (definition, selection vectors, attribute bundle)
        run: python3 -m unittest discover -s tools/milk-analyzer -p 'test_*facet*.py' -v
```

Run: `python3 -m unittest discover -s tools/milk-analyzer -p 'test_*facet*.py' -v` and `actionlint .github/workflows/android-build.yml`.
Expected: PASS; actionlint reports no errors (the `queue: max`/`cache-mode: none` ignores in `AGENTS.md` are the only permitted suppressions).

- [ ] **Step 9: Commit**

```bash
git add tools/milk-analyzer/facets tools/milk-analyzer/preset_facets.py tools/milk-analyzer/fixtures/facet-selection-vectors-v1.json \
  tools/milk-analyzer/test_preset_facets.py .github/workflows/android-build.yml \
  docs/superpowers/specs/2026-10-12-mood-facets-design.md docs/superpowers/plans/2026-10-12-mood-facets.md
git commit -m "feat(facets): mood facet definition, selection semantics and shared vectors"
git push -u origin feat/mood-facets
```

---

### Task 2: Style facts from source analysis (predictor branch)

Run in `.worktrees/predictor-memory-repair` on `feat/predictor-static-output-bounds`. This task produces an input for Task 4 and is never merged to `main`.

**Files (predictor branch):**
- Create: `tools/milk-analyzer/facet_style_facts.py`
- Create: `tools/milk-analyzer/test_facet_style_facts.py`

**Interfaces:**
- Consumes: whole-pack result rows (`results/*.json`, each with `name`, `sha256` and `summary_gzip_base64`) from `corpus_understanding.py`.
- Produces: `style_facts(summary) -> list[str]`, a subset of `['kaleidoscope', 'tunnel', 'liquid', 'geometric', 'particles', 'fractal']`. The CLI writes `facet-style-facts-v1.tsv` with a header line `#projectm-tv-facet-style-facts\t1\t<analyzer git sha>`, then rows `name<TAB>sha256<TAB>comma-separated styles`, sorted by name.

- [ ] **Step 1: Write the failing test**

```python
import unittest
import facet_style_facts as S


def summary(mechanisms=(), **structure):
    return {'facts': {'construction': [{'path': '/analysis/families/%d' % i, 'value': {'mechanism': m, 'stage': 'composite'}}
                                       for i, m in enumerate(mechanisms)]},
            'approximate_mood_features': {'structure.' + k: {'value': v} for k, v in structure.items()}}


class StyleFactsTest(unittest.TestCase):
    def test_mechanisms_map_to_styles(self):
        self.assertEqual(S.style_facts(summary(['angular_mirror_fold'])), ['kaleidoscope'])
        self.assertEqual(S.style_facts(summary(['polar_radial_sampling'])), ['tunnel'])
        self.assertEqual(S.style_facts(summary(['image_driven_advection'])), ['liquid'])
        self.assertEqual(S.style_facts(summary(['point_cloud_primitive'])), ['particles'])
        self.assertEqual(S.style_facts(summary(['complex_quadratic_recurrence'])), ['fractal'])

    def test_structure_scores_use_spec_thresholds(self):
        self.assertEqual(S.style_facts(summary(symmetry=.55)), ['kaleidoscope'])
        self.assertEqual(S.style_facts(summary(symmetry=.549)), [])
        self.assertEqual(S.style_facts(summary(organic=.6, geometric=.6, fractal=.6)), ['liquid', 'geometric', 'fractal'])

    def test_unknown_scores_do_not_match(self):
        self.assertEqual(S.style_facts(summary(symmetry=None)), [])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `build/preset-lab-venv/bin/python -m pytest tools/milk-analyzer/test_facet_style_facts.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Before writing, read `preset_understanding.py` to confirm where `approximate_mood` exposes features. In the recipe they live under `mood.features` with `{'value': …}` entries; `_features(summary)` below reads either location.

```python
"""Facet style facts (kaleidoscope, tunnel, liquid, geometric, particles, fractal) from source summaries.

Mechanisms are proven program constructions; structure scores are the approximate mood features.
Rules are the Mood facets definition's style_rules; no rendered image or simulation is used.
"""
import argparse, base64, gzip, json, subprocess
from pathlib import Path

STYLES = ('kaleidoscope', 'tunnel', 'liquid', 'geometric', 'particles', 'fractal')
MECHANISMS = {
    'kaleidoscope': {'angular_mirror_fold', 'cartesian_mirror_fold'},
    'tunnel': {'polar_radial_sampling', 'radial_feedback_transform'},
    'liquid': {'image_driven_advection', 'gradient_driven_advection'},
    'geometric': set(),
    'particles': {'point_cloud_primitive', 'procedural_point_motion'},
    'fractal': {'nonlinear_feedback_map', 'complex_quadratic_recurrence'},
}
SCORES = {'kaleidoscope': ('structure.symmetry', .55), 'liquid': ('structure.organic', .6),
          'geometric': ('structure.geometric', .6), 'fractal': ('structure.fractal', .6)}


def _mechanisms(summary):
    return {item['value'].get('mechanism') for item in (summary.get('facts') or {}).get('construction', [])
            if str(item.get('path', '')).startswith('/analysis/families/') and isinstance(item.get('value'), dict)}


def _features(summary):
    for key in ('approximate_mood_features',):
        if isinstance(summary.get(key), dict):
            return summary[key]
    from preset_understanding import approximate_mood
    return approximate_mood(summary).get('features', {})


def style_facts(summary):
    mechanisms = _mechanisms(summary)
    features = _features(summary)
    found = []
    for style in STYLES:
        hit = bool(mechanisms & MECHANISMS[style])
        if not hit and style in SCORES:
            name, threshold = SCORES[style]
            value = (features.get(name) or {}).get('value')
            hit = type(value) in (int, float) and value >= threshold
        if hit:
            found.append(style)
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('results', type=Path, help='whole-pack results directory (corpus_understanding)')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    sha = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    rows = []
    for path in sorted(args.results.glob('*.json')):
        row = json.loads(path.read_text())
        if row.get('status') != 'computed' or not row.get('summary_gzip_base64'):
            continue
        summary = json.loads(gzip.decompress(base64.b64decode(row['summary_gzip_base64'])))
        rows.append((row['name'], row['sha256'], ','.join(style_facts(summary))))
    rows.sort()
    with args.output.open('w') as out:
        out.write('#projectm-tv-facet-style-facts\t1\t%s\n' % sha)
        for name, digest, styles in rows:
            out.write('%s\t%s\t%s\n' % (name, digest, styles))
    print(json.dumps({'presets': len(rows), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Run the tests to verify they pass, then produce the facts**

Run: `build/preset-lab-venv/bin/python -m pytest tools/milk-analyzer/test_facet_style_facts.py -q -p no:cacheprovider`
Expected: PASS.

Then:

```bash
build/preset-lab-venv/bin/python tools/milk-analyzer/facet_style_facts.py build/preset-corpus/corpus-understanding-9606-r6-display/results --output build/mood-facets/facet-style-facts-v1.tsv
```

Expected: `{"presets": 9606, …}`. If fewer presets were computed, list the missing names, then rerun the whole-pack for them with the current analyzer (`corpus_understanding.py`) before continuing. Record `sha256sum build/mood-facets/facet-style-facts-v1.tsv` for Task 4.

- [ ] **Step 5: Commit (predictor branch)**

```bash
git add tools/milk-analyzer/facet_style_facts.py tools/milk-analyzer/test_facet_style_facts.py
git commit -m "feat(predictor): facet style facts from source mechanisms and structure scores"
git push
```

---

### Task 3: Engine ruler tool and evidence archive

**Files (`main` worktree):**
- Create: `tools/native-ruler/native-ruler.cpp` (copied from `build/preset-corpus/native-ruler-2026-10-12/src/native-ruler.cpp`)
- Create: `tools/native-ruler/CMakeLists.txt` (copied from `…/src/CMakeLists.txt`)
- Create: `tools/native-ruler/ruler.py` (copied from `…/ruler.py`, with paths adjusted)
- Create: `tools/native-ruler/README.md`
- Create: `docs/superpowers/evidence/mood-facets-ruler-2026-10-12/README.md` and `ruler-results-manifest.json`

**Interfaces:**
- Produces: a ruler results directory (one JSON per preset with `status`, `mean_luminance`, `mean_abs_frame_difference`, `mean_flow_screen_widths_per_s`, `global_brightness_jumps_per_10s`, `mean_saturation`, `coloured_share`, `warm_cool`, `preset` and `preset_sha256`). Task 4 consumes it.

- [ ] **Step 1: Copy the sources and fix paths**

```bash
R=../predictor-memory-repair/build/preset-corpus/native-ruler-2026-10-12
mkdir -p tools/native-ruler
cp $R/src/native-ruler.cpp $R/src/CMakeLists.txt tools/native-ruler/
cp $R/ruler.py tools/native-ruler/ruler.py
```

In `tools/native-ruler/ruler.py`:
- `ROOT=Path(__file__).resolve().parents[2]`
- `RULER=ROOT/'build/native-ruler/native-ruler'`
- `PCM` becomes a required `--pcm` argument.
- `SWIFTSHADER` becomes `--swiftshader` (default: the SDK `emulator/lib64/gles_angle` directory).

Keep the measurement code byte-for-byte; it defines the facet statistics.

- [ ] **Step 2: Write `tools/native-ruler/README.md`**

The README must state:
- **Purpose:** engine-ruler attribute measurements for the bundled presets, used by the mood facet bundle and as calibration targets for source analysis, never as source-classification inputs.
- **Build:** `cmake -S tools/native-ruler -B build/native-ruler -DPROJECTM_SOURCE=<patched submodule> && cmake --build build/native-ruler`, as recorded in `build/preset-corpus/native-ruler-2026-10-12/build.log`. Copy the exact configure line from that log.
- **Platform:** verified on macOS with SwiftShader (Android SDK `emulator/lib64/gles_angle`); Linux is unverified.
- **Run:** `python3 tools/native-ruler/ruler.py --pcm <checkpoint synthetic.f32> --output <dir>`
- **Conditions:** 480×270, 300 frames at 30 fps, statistics over frames 60–299, U8 audio ingress.
- **Limits:** one 10 s render with one synthetic track under SwiftShader. Emulator agreement on 83 presets was ρ 0.91–0.96, which is not a per-preset guarantee.

- [ ] **Step 3: Write the evidence manifest (raw results are not committed)**

```bash
python3 - <<'E'
import json, hashlib, os
d = '../predictor-memory-repair/build/preset-corpus/native-ruler-2026-10-12/corpus/results'
rows = []
for f in sorted(os.listdir(d)):
    raw = open(os.path.join(d, f), 'rb').read(); r = json.loads(raw)
    rows.append({'preset': r['preset'], 'preset_sha256': r['preset_sha256'], 'result_sha256': hashlib.sha256(raw).hexdigest(), 'status': r['status']})
out = {'policy': 'engine-ruler-results-manifest-v1', 'presets': len(rows), 'ruler': json.loads(open(os.path.join(d, os.listdir(d)[0])).read())['ruler'],
       'archive': 'ruler-results-2026-10-12.tar.gz (outside the repository; sha256 below)', 'rows': rows}
json.dump(out, open('docs/superpowers/evidence/mood-facets-ruler-2026-10-12/ruler-results-manifest.json', 'w'), indent=0)
E
tar -C ../predictor-memory-repair/build/preset-corpus/native-ruler-2026-10-12/corpus -czf ~/Downloads/ProjectM-TV-ruler-results-2026-10-12.tar.gz results
shasum -a 256 ~/Downloads/ProjectM-TV-ruler-results-2026-10-12.tar.gz
```

Write the archive SHA-256 into the evidence `README.md` together with the style-facts TSV SHA-256 from Task 2. Expected: the manifest lists 9,606 rows with `status` `measured`.

- [ ] **Step 4: Commit**

```bash
git add tools/native-ruler docs/superpowers/evidence/mood-facets-ruler-2026-10-12
git commit -m "feat(facets): engine ruler tool and attribute measurement evidence manifest"
git push
```

---

### Task 4: Attribute bundle producer, `--check` and Android assets

**Files:**
- Create: `tools/milk-analyzer/attribute_bundle.py`
- Create: `tools/milk-analyzer/test_attribute_bundle.py`
- Create: `core/src/main/assets/preset-attributes/facets.json`, `attributes.tsv` and `manifest.json` (generated)
- Modify: `.github/workflows/android-build.yml` (add a `--check` step after the preset index check)

**Interfaces:**
- Consumes:
  - `preset_facets.load_definition`, `preset_facets.memberships` and `preset_facets.option_ids` (Task 1);
  - ruler result rows (Task 3);
  - the style facts TSV (Task 2);
  - `core/src/main/assets/presets.idx` (`name<TAB>weight` per line).
- Produces:
  - `attribute_bundle.build(ruler_dir, style_tsv, presets_idx, output_dir, definition_path=None) -> dict` (the manifest);
  - `attribute_bundle.check(bundle_dir, presets_idx, definition_path=None) -> list[str]` (problems; empty means valid);
  - `attribute_bundle.activity_values(rows) -> dict[name, float]`.

The format of `attributes.tsv` (UTF-8, `\n` line endings) is the Java and SDK contract:

```
#projectm-tv-preset-attributes	1
#definition	<sha256 of facets.json bytes>
#group	energy	Energy
#option	energy	chill	Chill
… one #group line per group followed by its #option lines, in definition order …
#columns	name	options	luminance	saturation	coloured_share	warm_cool	flow	frame_difference	jumps	activity
<name>	<comma-separated option ids or empty>	<8 values, fixed 4 decimals>
```

Rows are sorted by name and limited to names in `presets.idx`. Every `presets.idx` name must have a row; a preset without a measurement gets empty options and `-` values. `manifest.json` holds:
- `schema`;
- `definition_sha256`;
- `presets_idx_sha256`;
- `attributes_sha256`;
- `preset_count` and `measured_count`;
- `ruler` (identity from the results);
- `style_facts` (header line and TSV sha256);
- `ruler_results_manifest_sha256`;
- `option_counts`.

- [ ] **Step 1: Write the failing tests**

```python
import json, tempfile, unittest
from pathlib import Path

import attribute_bundle as B

RULER = {'engine': 'test', 'size': [480, 270], 'frames': 300, 'audio': 'test'}


def make_inputs(tmp):
    tmp = Path(tmp)
    (tmp / 'ruler').mkdir()
    stats = {'a.milk': (.05, .1, .05, .0, .01, .005, 0.), 'b.milk': (.3, .6, .8, .3, .2, .05, 3.), 'c.milk': (.5, .2, .4, -.3, .5, .2, 30.)}
    for name, (lum, sat, col, wc, flow, diff, jumps) in stats.items():
        (tmp / 'ruler' / (name + '.json')).write_text(json.dumps({
            'status': 'measured', 'preset': name, 'preset_sha256': name * 2, 'ruler': RULER, 'mean_luminance': lum, 'mean_saturation': sat,
            'coloured_share': col, 'warm_cool': wc, 'mean_flow_screen_widths_per_s': flow, 'mean_abs_frame_difference': diff,
            'global_brightness_jumps_per_10s': jumps}))
    (tmp / 'style.tsv').write_text('#projectm-tv-facet-style-facts\t1\tabc\na.milk\tx\ttunnel\nb.milk\tx\t\nc.milk\tx\tkaleidoscope,fractal\n')
    (tmp / 'presets.idx').write_text('a.milk\t0\nb.milk\t2\nc.milk\t0\nd.milk\t0\n')
    return tmp


class BundleTest(unittest.TestCase):
    def test_build_then_check_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            manifest = B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out')
            self.assertEqual(manifest['preset_count'], 4); self.assertEqual(manifest['measured_count'], 3)
            self.assertEqual(B.check(t / 'out', t / 'presets.idx'), [])
            lines = (t / 'out' / 'attributes.tsv').read_text().splitlines()
            rows = {l.split('\t')[0]: l.split('\t') for l in lines if not l.startswith('#')}
            self.assertIn('tunnel', rows['a.milk'][1].split(',')); self.assertIn('dark', rows['a.milk'][1].split(','))
            self.assertIn('monochrome', rows['a.milk'][1].split(','))
            self.assertEqual(rows['d.milk'][1:], [''] + ['-'] * 8)  # unmeasured preset: no options, no values
            self.assertIn('fast', rows['c.milk'][1].split(',')); self.assertNotIn('no_strobe', rows['c.milk'][1].split(','))

    def test_activity_is_the_percentile_of_the_mean_metric_rank(self):
        rows = [{'preset': n, 'mean_abs_frame_difference': d, 'mean_flow_screen_widths_per_s': f, 'global_brightness_jumps_per_10s': j}
                for n, d, f, j in (('x', .01, .01, 0), ('y', .05, .1, 1), ('z', .2, .5, 30))]
        a = B.activity_values(rows)
        self.assertLess(a['x'], a['y']); self.assertLess(a['y'], a['z'])
        self.assertTrue(all(0 <= v <= 1 for v in a.values()))

    def test_check_detects_stale_index_definition_and_tampered_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out')
            (t / 'presets.idx').write_text('a.milk\t0\nb.milk\t2\nc.milk\t0\nd.milk\t0\ne.milk\t0\n')
            self.assertTrue(any('presets.idx' in p for p in B.check(t / 'out', t / 'presets.idx')))
            text = (t / 'out' / 'attributes.tsv').read_text().replace('tunnel', 'liquid')
            (t / 'out' / 'attributes.tsv').write_text(text)
            problems = B.check(t / 'out', t / 'presets.idx')
            self.assertTrue(any('attributes' in p for p in problems))

    def test_rejects_missing_ruler_fields_and_unknown_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = make_inputs(tmp)
            (t / 'style.tsv').write_text('#projectm-tv-facet-style-facts\t1\tabc\na.milk\tx\tspirals\n')
            with self.assertRaises(ValueError):
                B.build(t / 'ruler', t / 'style.tsv', t / 'presets.idx', t / 'out')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd tools/milk-analyzer && python3 -m unittest test_attribute_bundle -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'attribute_bundle'`.

- [ ] **Step 3: Implement `attribute_bundle.py`**

```python
"""Mood facet attribute bundle: engine-ruler measurements + source style facts -> Android assets.

build() writes preset-attributes/{facets.json, attributes.tsv, manifest.json}; check() verifies the
bundle against presets.idx, the definition and its manifest, and recomputes every membership from
the stored values and style options. Standard library only.
"""
import argparse, bisect, hashlib, json, shutil
from pathlib import Path

import preset_facets

COLUMNS = ('luminance', 'saturation', 'coloured_share', 'warm_cool', 'flow', 'frame_difference', 'jumps', 'activity')
RULER_FIELDS = {'luminance': 'mean_luminance', 'saturation': 'mean_saturation', 'coloured_share': 'coloured_share',
                'warm_cool': 'warm_cool', 'flow': 'mean_flow_screen_widths_per_s', 'frame_difference': 'mean_abs_frame_difference',
                'jumps': 'global_brightness_jumps_per_10s'}
ACTIVITY_METRICS = ('mean_abs_frame_difference', 'mean_flow_screen_widths_per_s', 'global_brightness_jumps_per_10s')
STYLES = {'kaleidoscope', 'tunnel', 'liquid', 'geometric', 'particles', 'fractal'}
SCHEMA = 'projectm-tv-preset-attributes'


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _mid_rank(sorted_values, value):
    low = bisect.bisect_left(sorted_values, value); high = bisect.bisect_right(sorted_values, value)
    return (low + high) / 2 / len(sorted_values)


def activity_values(rows):
    """Percentile of the mean percentile rank of the three activity metrics within these rows."""
    tables = {m: sorted(float(r[m]) for r in rows) for m in ACTIVITY_METRICS}
    raw = {r['preset']: sum(_mid_rank(tables[m], float(r[m])) for m in ACTIVITY_METRICS) / len(ACTIVITY_METRICS) for r in rows}
    order = sorted(raw.values())
    return {name: _mid_rank(order, value) for name, value in raw.items()}


def _index_names(presets_idx):
    names = [line.split('\t', 1)[0] for line in Path(presets_idx).read_text().splitlines() if line.strip()]
    if len(names) != len(set(names)):
        raise ValueError('duplicate names in presets.idx')
    return names


def _read_style(path):
    lines = Path(path).read_text().splitlines()
    if not lines or not lines[0].startswith('#projectm-tv-facet-style-facts\t1'):
        raise ValueError('style facts header missing')
    styles = {}
    for line in lines[1:]:
        name, _digest, found = line.split('\t')
        values = {s for s in found.split(',') if s}
        if values - STYLES:
            raise ValueError('unknown style in %s: %s' % (name, sorted(values - STYLES)))
        styles[name] = values
    return lines[0], styles


def _format(value):
    return '-' if value is None else '%.4f' % value


def _header(definition, definition_sha):
    lines = ['#%s\t1' % SCHEMA, '#definition\t' + definition_sha]
    for group in definition['groups']:
        lines.append('#group\t%s\t%s' % (group['id'], group['label']))
        lines += ['#option\t%s\t%s\t%s' % (group['id'], o['id'], o['label']) for o in group['options']]
    lines.append('#columns\tname\toptions\t' + '\t'.join(COLUMNS))
    return lines


def build(ruler_dir, style_tsv, presets_idx, output_dir, definition_path=None, ruler_manifest=None):
    definition_path = Path(definition_path or preset_facets.DEFINITION)
    definition_bytes = definition_path.read_bytes(); definition = json.loads(definition_bytes)
    names = _index_names(presets_idx)
    rows = {}
    ruler = None
    for path in sorted(Path(ruler_dir).glob('*.json')):
        row = json.loads(path.read_text())
        if row.get('status') != 'measured':
            continue
        missing = [f for f in RULER_FIELDS.values() if type(row.get(f)) not in (int, float)]
        if missing:
            raise ValueError('ruler result %s lacks %s' % (row.get('preset'), missing))
        rows[row['preset']] = row; ruler = ruler or row.get('ruler')
    style_header, styles = _read_style(style_tsv)
    measured = [rows[n] for n in names if n in rows]
    activity = activity_values(measured) if measured else {}
    lines = _header(definition, _sha(definition_bytes))
    counts = {o: 0 for o in preset_facets.option_ids(definition)}
    for name in sorted(names):
        if name in rows:
            values = {k: float(rows[name][f]) for k, f in RULER_FIELDS.items()}; values['activity'] = activity[name]
            options = preset_facets.memberships(values, styles.get(name, set()), definition)
            for option in options:
                counts[option] += 1
            lines.append('\t'.join([name, ','.join(options)] + [_format(values[c]) for c in COLUMNS]))
        else:
            lines.append('\t'.join([name, ''] + ['-'] * len(COLUMNS)))
    attributes = ('\n'.join(lines) + '\n').encode()
    output = Path(output_dir); output.mkdir(parents=True, exist_ok=True)
    (output / 'facets.json').write_bytes(definition_bytes)
    (output / 'attributes.tsv').write_bytes(attributes)
    manifest = {'schema': SCHEMA, 'version': 1, 'definition_sha256': _sha(definition_bytes),
                'presets_idx_sha256': _sha(Path(presets_idx).read_bytes()), 'attributes_sha256': _sha(attributes),
                'preset_count': len(names), 'measured_count': len(measured), 'ruler': ruler,
                'style_facts': {'header': style_header, 'sha256': _sha(Path(style_tsv).read_bytes())},
                'ruler_results_manifest_sha256': _sha(Path(ruler_manifest).read_bytes()) if ruler_manifest else None,
                'option_counts': counts}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
    return manifest


def check(bundle_dir, presets_idx, definition_path=None):
    bundle = Path(bundle_dir); problems = []
    definition_path = Path(definition_path or preset_facets.DEFINITION)
    try:
        manifest = json.loads((bundle / 'manifest.json').read_text())
        attributes = (bundle / 'attributes.tsv').read_bytes()
        shipped = (bundle / 'facets.json').read_bytes()
    except (OSError, ValueError) as error:
        return ['bundle unreadable: %s' % error]
    if shipped != definition_path.read_bytes():
        problems.append('facets.json differs from the definition')
    if manifest.get('definition_sha256') != _sha(shipped):
        problems.append('manifest definition hash is stale')
    if manifest.get('presets_idx_sha256') != _sha(Path(presets_idx).read_bytes()):
        problems.append('presets.idx changed since the bundle was built')
    if manifest.get('attributes_sha256') != _sha(attributes):
        problems.append('attributes.tsv does not match its manifest hash')
    definition = json.loads(shipped)
    header = _header(definition, _sha(shipped))
    lines = attributes.decode().splitlines()
    if lines[:len(header)] != header:
        problems.append('attributes header differs from the definition')
    rows = [line.split('\t') for line in lines[len(header):]]
    names = [r[0] for r in rows]
    if names != sorted(_index_names(presets_idx)):
        problems.append('attributes rows do not match presets.idx names')
    for row in rows:
        if len(row) != 2 + len(COLUMNS):
            problems.append('malformed row: ' + row[0]); continue
        if row[2] == '-':
            if row[1]:
                problems.append('unmeasured preset has options: ' + row[0])
            continue
        values = dict(zip(COLUMNS, map(float, row[2:])))
        options = row[1].split(',') if row[1] else []
        style = {o for o in options if o in {s['id'] for g in definition['groups'] if g['id'] == 'style' for s in g['options']}}
        if preset_facets.memberships(values, style, definition) != options:
            problems.append('attributes membership mismatch: ' + row[0])
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ruler', type=Path); parser.add_argument('--style', type=Path)
    parser.add_argument('--ruler-manifest', type=Path, help='committed engine-ruler results manifest (evidence)')
    parser.add_argument('--presets-idx', type=Path, default=Path('core/src/main/assets/presets.idx'))
    parser.add_argument('--bundle', type=Path, default=Path('core/src/main/assets/preset-attributes'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    if args.check:
        problems = check(args.bundle, args.presets_idx)
        for problem in problems:
            print(problem)
        raise SystemExit(1 if problems else 0)
    if not args.ruler or not args.style:
        parser.error('--ruler and --style are required to build')
    print(json.dumps({k: v for k, v in build(args.ruler, args.style, args.presets_idx, args.bundle, ruler_manifest=args.ruler_manifest).items() if k != 'option_counts'}))


if __name__ == '__main__':
    main()
```

Note that the style membership check in `check()` works because `memberships` evaluates style options only from the `style` set, and every other option only from metric values. A tampered style id or value therefore always mismatches.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd tools/milk-analyzer && python3 -m unittest test_attribute_bundle test_preset_facets -v`
Expected: PASS.

- [ ] **Step 5: Generate the real bundle and check it**

```bash
python3 tools/milk-analyzer/attribute_bundle.py \
  --ruler ../predictor-memory-repair/build/preset-corpus/native-ruler-2026-10-12/corpus/results \
  --style ../predictor-memory-repair/build/mood-facets/facet-style-facts-v1.tsv \
  --ruler-manifest docs/superpowers/evidence/mood-facets-ruler-2026-10-12/ruler-results-manifest.json
python3 tools/milk-analyzer/attribute_bundle.py --check
```

Expected: the build reports `preset_count` 9606 and `measured_count` 9606; the check exits 0; `manifest.json` carries `ruler_results_manifest_sha256`. Review `option_counts` and record them in the evidence README. Expected shares: Chill/Intense about 35%/30% by construction, and every option non-zero.

- [ ] **Step 6: Check the bundle in CI**

In `android-build.yml`, after "Check the preset index (names and memory weights) is up to date", add:

```yaml
      - name: Check the mood facet attribute bundle
        run: python3 tools/milk-analyzer/attribute_bundle.py --check
```

- [ ] **Step 7: Commit**

```bash
git add tools/milk-analyzer/attribute_bundle.py tools/milk-analyzer/test_attribute_bundle.py core/src/main/assets/preset-attributes .github/workflows/android-build.yml docs/superpowers/evidence/mood-facets-ruler-2026-10-12/README.md
git commit -m "feat(facets): attribute bundle producer, --check and bundled preset attributes"
git push
```

---

### Task 5: Distribution editions carry the attributes

**Files:**
- Modify: `tools/preset_distribution.py` (`source_files`, `starter_files`)
- Modify: `tools/preset-distribution/official-archive.json` (regenerated lock)
- Test: `.github/scripts/tests/test_distribution_artifacts.py`

**Interfaces:**
- Consumes: `attributes.tsv` format (Task 4).
- Produces: the starter asset tree and the official archive containing `preset-attributes/{facets.json, attributes.tsv, manifest.json}`. The starter `attributes.tsv` holds only starter rows, and its manifest's `presets_idx_sha256`, `attributes_sha256`, `preset_count`, `measured_count` and `option_counts` are recomputed for the subset.

- [ ] **Step 1: Write the failing test**

Read the existing starter tests in `test_distribution_artifacts.py` (search for `starter_files`) and add a sibling test using their fixture builder:

```python
    def test_starter_filters_preset_attributes_to_selected_presets(self):
        files = self.fixture_files()  # existing helper building presets/, presets.idx and preset-genres/
        header = '#projectm-tv-preset-attributes\t1\n#definition\tabc\n#group\tcomfort\tComfort\n#option\tcomfort\tno_strobe\tNo strobe\n#columns\tname\toptions\tluminance\tsaturation\tcoloured_share\twarm_cool\tflow\tframe_difference\tjumps\tactivity\n'
        names = sorted(n.removeprefix('presets/') for n in files if n.startswith('presets/'))
        rows = ''.join('%s\tno_strobe\t0.1000\t0.1000\t0.1000\t0.0000\t0.1000\t0.0100\t0.0000\t0.5000\n' % n for n in names)
        files['preset-attributes/attributes.tsv'] = (header + rows).encode()
        files['preset-attributes/facets.json'] = b'{}'
        files['preset-attributes/manifest.json'] = json.dumps({'preset_count': len(names), 'measured_count': len(names), 'option_counts': {'no_strobe': len(names)}}).encode()
        selection = names[:1]
        output = preset_distribution.starter_files(files, selection)
        lines = [l for l in output['preset-attributes/attributes.tsv'].decode().splitlines() if not l.startswith('#')]
        self.assertEqual([l.split('\t')[0] for l in lines], selection)
        manifest = json.loads(output['preset-attributes/manifest.json'])
        self.assertEqual(manifest['preset_count'], 1); self.assertEqual(manifest['option_counts']['no_strobe'], 1)
        self.assertEqual(manifest['attributes_sha256'], hashlib.sha256(output['preset-attributes/attributes.tsv']).hexdigest())
```

If no `fixture_files` helper exists, build `files` inline exactly as the nearest existing starter test does, and name the helper used in the commit message.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s .github/scripts/tests -p test_distribution_artifacts.py -v`
Expected: FAIL. The new test raises `KeyError` on `'preset-attributes/attributes.tsv'` because `starter_files` drops the folder.

- [ ] **Step 3: Implement**

In `tools/preset_distribution.py`:
- `source_files`: extend the folder tuple to `('presets', 'textures', 'preset-genres', 'preset-attributes')`.
- `starter_files`, after the genre filtering block:

```python
    attributes = files.get('preset-attributes/attributes.tsv')
    if attributes is not None:
        lines = attributes.decode().splitlines()
        header = [l for l in lines if l.startswith('#')]
        rows = [l for l in lines if not l.startswith('#') and l.split('\t', 1)[0] in selected]
        output['preset-attributes/attributes.tsv'] = ('\n'.join(header + rows) + '\n').encode()
        output['preset-attributes/facets.json'] = files['preset-attributes/facets.json']
        manifest = json.loads(files['preset-attributes/manifest.json'])
        counts = {option: 0 for option in manifest.get('option_counts', {})}
        for row in rows:
            for option in filter(None, row.split('\t')[1].split(',')):
                counts[option] = counts.get(option, 0) + 1
        manifest.update(preset_count=len(rows), measured_count=sum(1 for r in rows if r.split('\t')[2] != '-'), option_counts=counts,
                        attributes_sha256=digest(output['preset-attributes/attributes.tsv']),
                        presets_idx_sha256=digest(output['presets.idx']))
        output['preset-attributes/manifest.json'] = canonical(manifest)
```

Check that `digest()` in this module returns a hex SHA-256 string, and that the starter `presets.idx` key is `'presets.idx'` (read the surrounding code). Adjust names to match the module's existing helpers rather than adding new ones.

- [ ] **Step 4: Run the tests, rebuild the lock and verify the F-Droid assets**

```bash
python3 -m unittest discover -s .github/scripts/tests -v
python3 tools/preset_distribution.py lock --root . --output tools/preset-distribution/official-archive.json
./gradlew -PprojectmDistribution=fdroid :core:generateStarterPresets
```

Expected:
- All release-tooling tests pass.
- The lock changes only in collection identity, ZIP SHA and sizes.
- The generated starter assets contain `preset-attributes/attributes.tsv` with 20 rows.

Use the exact `lock` subcommand syntax from `tools/preset_distribution.py --help`.

- [ ] **Step 5: Commit**

```bash
git add tools/preset_distribution.py tools/preset-distribution/official-archive.json .github/scripts/tests/test_distribution_artifacts.py
git commit -m "feat(facets): starter and official collections carry preset attributes"
git push
```

---

### Task 6: Native preset pool (`facets` category)

**Files:**
- Modify: `core/src/main/cpp/native-lib.cpp` (`PresetLibrary`, worker official prepare, JNI)
- Modify: `core/src/main/java/nl/neerdael/projectm/core/ProjectMJNI.java`
- Test: `core/src/test/native/engine_test.cpp`

**Interfaces:**
- Produces:
  - Java: `public static native void setPresetPool(String[] names)`. It stores the pool; `null` or empty clears it. It does not change the selected category.
  - Callers select the pool with the existing `setMusicCategory("facets")`. `getCategoryPresetCount("facets")` returns the eligible (non-skipped) pool size.
  - C++: `int PresetLibrary::SetPool(std::vector<std::string> names)`, which returns the eligible count.
  - Constant `kFacetCategory = "facets"`.

Semantics:
- The pool holds only names in the current bundled inventory (`bundled_`), deduplicated, in the given order.
- When the active category is `facets`, `SetPool` rebuilds it: the shuffle is reset and history cleared, as any category change does.
- An official-pack prepare intersects the stored request with the new bundled names, so a committed official pack keeps the mix.
- An empty eligible pool falls back to All through the existing `EnsureEligibleCategoryLocked` path.

- [ ] **Step 1: Write the failing engine test**

In `engine_test.cpp`, next to the existing category checks (around the `library.CategoryCount("chill")` assertions), add a test block that uses the same fixture library:

```cpp
    // Facet pool: only bundled names, deduplicated; selection through the facets category.
    CHECK(library.SetPool({"good 1.milk", "good 1.milk", "missing.milk", "custom/x.milk"}) == 1);
    CHECK(library.CategoryCount("facets") == 1);
    CHECK(library.SetCategory("facets"));
    CHECK(library.Category() == "facets");
    for (int i = 0; i < 5; ++i) CHECK(library.Random("") == "good 1.milk");
    // The skip list empties the pool: the library falls back to All on the next pick.
    library.MarkSkipped("good 1.milk", "test");
    CHECK(library.CategoryCount("facets") == 0);
    CHECK(!library.Next().empty());
    CHECK(library.Category() == "all");
    library.ResetSkipped();
    // Clearing the pool keeps the category machinery valid.
    CHECK(library.SetPool({}) == 0);
    CHECK(!library.SetCategory("facets"));
```

Also add an official-commit reapplication check at the official-pack test. After an official pack commits, with the category at `facets` and a pool naming one name present in the new pack and one absent:

```cpp
    CHECK(library.SetPool({"good 1.milk", "absent-in-official.milk"}) == 1);
    CHECK(library.SetCategory("facets"));
    // … existing official request/prepare/commit sequence …
    CHECK(library.Category() == "facets" && library.CategoryCount("facets") == 1);
```

Adapt preset names to the fixture's actual names (search `engine_test.cpp` for `"good 1.milk"` and for the official-pack test's inventory).

- [ ] **Step 2: Run the native tests to verify they fail**

Run: `core/src/test/native/run_native_tests.sh`
Expected: compile error, `no member named 'SetPool' in 'PresetLibrary'`.

- [ ] **Step 3: Implement in `PresetLibrary`**

Add near `SetCategory`:

```cpp
    // Mood facet pool: bundled preset names chosen by the host (PresetFacets). Stored as requested so an
    // official-pack swap can intersect it with the new bundled inventory.
    int SetPool(std::vector<std::string> names) {
        std::lock_guard<std::mutex> lock(mutex_);
        facetPoolRequested_ = std::move(names);
        categories_[kFacetCategory] = FacetPoolFor(facetPoolRequested_, bundled_);
        categoryCounts_[kFacetCategory] = EligibleCountLocked(categories_[kFacetCategory]);
        if (category_ == kFacetCategory) {
            if (categoryCounts_[kFacetCategory] > 0) RebuildCategoryLocked(kFacetCategory);
            else RebuildCategoryLocked("all");
        }
        return categoryCounts_[kFacetCategory];
    }
```

Add to the private section:

```cpp
    static std::vector<std::string> FacetPoolFor(const std::vector<std::string>& requested,
                                                 const std::vector<std::string>& bundled) {
        std::unordered_set<std::string> inventory(bundled.begin(), bundled.end()), unique;
        std::vector<std::string> pool;
        for (const auto& name : requested)
            if (inventory.count(name) && unique.insert(name).second) pool.push_back(name);
        return pool;
    }
    std::vector<std::string> facetPoolRequested_;
```

Declare `static constexpr const char* kFacetCategory = "facets";` at namespace scope next to `kPresetDir`.

- In `SetCategory`: an empty `facets` count already redirects to `all` through `CategoryCountLocked`; no change is needed.
- In `RecountCategoriesLocked`: nothing to add, because `categories_` contains `facets` after `SetPool`.
- In the worker official prepare, capture `auto facetRequest = facetPoolRequested_;` next to `auto customNames = categories_["custom"];` while the lock is held. After `next->categories["custom"] = std::move(customNames);`, add:

```cpp
                    next->categories[kFacetCategory] = FacetPoolFor(facetRequest, next->bundled);
```

`CommitOfficialPack` swaps `categories_` with the prepared map, so the pool survives. Custom-pack commits replace only `categories_["custom"]` and need no change.

- [ ] **Step 4: Implement the JNI method and the Java declaration**

```cpp
JNIEXPORT void JNICALL JNI_FN(setPresetPool)(JNIEnv* env, jclass, jobjectArray names) {
    std::vector<std::string> pool;
    jsize count = names ? env->GetArrayLength(names) : 0;
    pool.reserve(static_cast<size_t>(count));
    for (jsize i = 0; i < count; ++i) {
        auto item = static_cast<jstring>(env->GetObjectArrayElement(names, i));
        if (!item) continue;
        const char* text = env->GetStringUTFChars(item, nullptr);
        if (text) { pool.emplace_back(text); env->ReleaseStringUTFChars(item, text); }
        env->DeleteLocalRef(item);
    }
    g_library.SetPool(std::move(pool));
    {
        std::lock_guard<std::mutex> lock(g_inputs.categoryMutex);
        ++g_inputs.categoryRequestedSerial;  // hosts poll isMusicCategoryPending until the rebuild is applied
    }
    g_inputs.categoryDirty = true;
}
```

Before relying on the dirty flag, read how `HandleCommands` applies `categoryDirty`. It must re-apply `g_inputs.requestedCategory` (which stays `facets`) and acknowledge the serial; the existing custom-pack JNI uses the same pattern.

In `ProjectMJNI.java`, after `isMusicCategoryPending`:

```java
    /**
     * Mood facet pool: bundled preset names (PresetFacets.Selection.presetNames()) that the
     * "facets" music category plays. Null or empty clears it. Select it with
     * setMusicCategory("facets"); names absent from the bundled library are ignored.
     */
    public static native void setPresetPool(String[] names);
```

`core/consumer-rules.pro` keeps all `ProjectMJNI` natives. Confirm that the rule is class-wide; otherwise add the method.

- [ ] **Step 5: Run the native and JVM tests**

Run: `core/src/test/native/run_native_tests.sh && ./gradlew :core:testDebugUnitTest :core:assembleDebug`
Expected: the engine tests pass under ASan/UBSan, and the build succeeds.

- [ ] **Step 6: Commit**

```bash
git add core/src/main/cpp/native-lib.cpp core/src/main/java/nl/neerdael/projectm/core/ProjectMJNI.java core/src/test/native/engine_test.cpp
git commit -m "feat(core): facet preset pool as the facets music category"
git push
```

---

### Task 7: `PresetFacets` (core, pure Java)

**Files:**
- Create: `core/src/main/java/nl/neerdael/projectm/core/PresetFacets.java`
- Test: `core/src/test/java/nl/neerdael/projectm/core/PresetFacetsTest.java`

**Interfaces:**
- Consumes: the `attributes.tsv` format (Task 4) and the shared vectors (Task 1), read from `../tools/milk-analyzer/fixtures/facet-selection-vectors-v1.json` relative to the `core` module directory.
- Produces (all public):

```java
public final class PresetFacets {
    public static final class Option { public final String id; public final String label; public final String groupId; }
    public static final class Group { public final String id; public final String label; public final List<Option> options; }
    public static PresetFacets parse(Reader reader) throws IOException;            // IllegalArgumentException on malformed input
    public static PresetFacets fromRows(List<Group> groups, Map<String, Set<String>> rows); // tests and hosts with their own data
    public static PresetFacets load(AssetManager assets);                          // null when the asset is missing or malformed
    public List<Group> groups();
    public int presetCount();
    public boolean contains(String presetName);
    public Selection select(Collection<String> optionIds, Collection<String> excludedNames);
    public final class Selection {
        public List<String> selected();      // known ids, request order, duplicates removed
        public List<String> ignored();       // unknown ids
        public int poolSize();
        public int countIfToggled(String optionId);
        public boolean isDimmed(String optionId);
        public String[] presetNames();       // pool names, attribute-table (name) order
    }
}
```

Semantics are identical to `preset_facets.select` (Task 1): one `long[]` bitset per option over rows, OR within a group, AND across groups, and an excluded bitset removed. `countIfToggled` returns 0 for an unknown id.

- [ ] **Step 1: Write the failing tests**

```java
package nl.neerdael.projectm.core;

import static org.junit.Assert.*;

import java.io.IOException;
import java.io.StringReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.Test;

public class PresetFacetsTest {
    private static final String HEADER =
            "#projectm-tv-preset-attributes\t1\n#definition\tabc\n"
            + "#group\tenergy\tEnergy\n#option\tenergy\tchill\tChill\n#option\tenergy\tnormal\tNormal\n#option\tenergy\tintense\tIntense\n"
            + "#group\tbrightness\tBrightness\n#option\tbrightness\tdark\tDark\n#option\tbrightness\tbalanced\tBalanced\n#option\tbrightness\tbright\tBright\n"
            + "#group\tcolour\tColour\n#option\tcolour\tmonochrome\tMonochrome\n#option\tcolour\tpastel\tPastel\n#option\tcolour\tvivid\tVivid\n#option\tcolour\twarm\tWarm\n#option\tcolour\tcool\tCool\n"
            + "#group\tmovement\tMovement\n#option\tmovement\tstill\tStill\n#option\tmovement\tdrifting\tDrifting\n#option\tmovement\tfast\tFast\n"
            + "#group\tstyle\tStyle\n#option\tstyle\tkaleidoscope\tKaleidoscope\n#option\tstyle\ttunnel\tTunnel\n#option\tstyle\tliquid\tLiquid\n#option\tstyle\tgeometric\tGeometric\n#option\tstyle\tparticles\tParticles\n#option\tstyle\tfractal\tFractal\n"
            + "#group\tcomfort\tComfort\n#option\tcomfort\tno_strobe\tNo strobe\n"
            + "#columns\tname\toptions\tluminance\tsaturation\tcoloured_share\twarm_cool\tflow\tframe_difference\tjumps\tactivity\n";

    /** Builds attributes.tsv text from the shared vector rows. */
    private static String vectorsAsTable(String vectors) {
        StringBuilder table = new StringBuilder(HEADER);
        Matcher row = Pattern.compile("\\{\"name\": \"([^\"]+)\", \"options\": \\[([^\\]]*)\\]\\}").matcher(vectors);
        List<String[]> rows = new ArrayList<>();
        while (row.find()) rows.add(new String[]{row.group(1), row.group(2).replace("\"", "").replace(" ", "")});
        rows.sort(Comparator.comparing(r -> r[0]));
        for (String[] r : rows) table.append(r[0]).append('\t').append(r[1]).append("\t0.1\t0.1\t0.1\t0\t0.1\t0.01\t0\t0.5\n");
        return table.toString();
    }

    private static String vectors() throws IOException {
        return new String(Files.readAllBytes(Paths.get("../tools/milk-analyzer/fixtures/facet-selection-vectors-v1.json")), StandardCharsets.UTF_8);
    }

    private static List<String> list(String json) {
        List<String> out = new ArrayList<>();
        Matcher item = Pattern.compile("\"([^\"]+)\"").matcher(json);
        while (item.find()) out.add(item.group(1));
        return out;
    }

    @Test public void sharedVectorsMatchPythonSemantics() throws IOException {
        String text = vectors();
        PresetFacets facets = PresetFacets.parse(new StringReader(vectorsAsTable(text)));
        assertEquals(8, facets.presetCount());
        Matcher c = Pattern.compile("\\{\"selected\": \\[([^\\]]*)\\], \"excluded\": \\[([^\\]]*)\\], \"pool\": \\[([^\\]]*)\\],(?:\\s*\"ignored\": \\[([^\\]]*)\\],)?\\s*\"option_counts\": \\{([^}]*)\\},\\s*\"dimmed\": \\[([^\\]]*)\\]\\}").matcher(text);
        int cases = 0;
        while (c.find()) {
            cases++;
            PresetFacets.Selection s = facets.select(list(c.group(1)), list(c.group(2)));
            assertEquals(list(c.group(3)), Arrays.asList(s.presetNames()));
            assertEquals(list(c.group(3)).size(), s.poolSize());
            Matcher count = Pattern.compile("\"([a-z_]+)\": (\\d+)").matcher(c.group(5));
            while (count.find()) assertEquals(count.group(1), Integer.parseInt(count.group(2)), s.countIfToggled(count.group(1)));
            for (String dimmed : list(c.group(6))) assertTrue(dimmed, s.isDimmed(dimmed));
            if (c.group(4) != null) assertEquals(list(c.group(4)), s.ignored());
        }
        assertEquals(5, cases);
    }

    @Test public void selectedOptionIsNeverDimmedAndUnknownIdsAreIgnored() throws IOException {
        PresetFacets facets = PresetFacets.parse(new StringReader(vectorsAsTable(vectors())));
        PresetFacets.Selection s = facets.select(Arrays.asList("fractal", "tunnel", "nonsense"), Collections.emptyList());
        assertFalse(s.isDimmed("fractal")); assertFalse(s.isDimmed("tunnel"));
        assertEquals(Collections.singletonList("nonsense"), s.ignored());
        assertEquals(0, s.countIfToggled("nonsense"));
    }

    @Test public void absentPresetNamesAreIgnoredForExclusion() throws IOException {
        PresetFacets facets = PresetFacets.parse(new StringReader(vectorsAsTable(vectors())));
        assertEquals(8, facets.select(Collections.emptyList(), Collections.singletonList("not-bundled.milk")).poolSize());
        assertFalse(facets.contains("not-bundled.milk"));
    }

    @Test public void unmeasuredRowsNeverJoinAPool() throws IOException {
        PresetFacets facets = PresetFacets.parse(new StringReader(HEADER + "m.milk\t\t-\t-\t-\t-\t-\t-\t-\t-\nz.milk\tchill\t0.1\t0.1\t0.1\t0\t0.1\t0.01\t0\t0.1\n"));
        assertEquals(2, facets.select(Collections.emptyList(), Collections.emptyList()).poolSize());
        assertArrayEquals(new String[]{"z.milk"}, facets.select(Collections.singletonList("chill"), Collections.emptyList()).presetNames());
    }

    @Test public void malformedInputIsRejected() {
        String[] bad = {"", "#projectm-tv-preset-attributes\t2\n", HEADER + "a.milk\tchill\n", HEADER + "a.milk\tspirals\t1\t1\t1\t1\t1\t1\t1\t1\n",
                        HEADER.replace("#columns", "#group\tenergy\tAgain\n#columns")};
        for (String text : bad) {
            try { PresetFacets.parse(new StringReader(text)); fail("accepted: " + text.length()); }
            catch (IllegalArgumentException | IOException expected) { /* rejected */ }
        }
    }
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./gradlew :core:testDebugUnitTest --tests nl.neerdael.projectm.core.PresetFacetsTest`
Expected: FAIL, `cannot find symbol: class PresetFacets`.

- [ ] **Step 3: Implement `PresetFacets.java`**

```java
package nl.neerdael.projectm.core;

import android.content.res.AssetManager;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.util.*;

/**
 * Mood facets over the bundled presets (preset-attributes/attributes.tsv, built by
 * tools/milk-analyzer/attribute_bundle.py). Options combine OR within a group and AND across
 * groups; an unselected group means "any". Mirrors tools/milk-analyzer/preset_facets.py; both run
 * the shared selection vectors. No Android types are used outside load().
 */
public final class PresetFacets {
    public static final String ASSET = "preset-attributes/attributes.tsv";
    private static final String MAGIC = "#projectm-tv-preset-attributes\t1";
    private static final int VALUE_COLUMNS = 8;

    public static final class Option {
        public final String id, label, groupId;
        Option(String id, String label, String groupId) { this.id = id; this.label = label; this.groupId = groupId; }
    }

    public static final class Group {
        public final String id, label;
        public final List<Option> options;
        Group(String id, String label, List<Option> options) { this.id = id; this.label = label; this.options = Collections.unmodifiableList(options); }
    }

    private final List<Group> groups;
    private final Map<String, Option> options = new LinkedHashMap<>();
    private final String[] names;
    private final Map<String, Integer> index = new HashMap<>();
    private final Map<String, long[]> members = new HashMap<>();
    private final int words;

    private PresetFacets(List<Group> groups, List<String> names, Map<String, Set<String>> rows) {
        this.groups = Collections.unmodifiableList(groups);
        for (Group g : groups) for (Option o : g.options) options.put(o.id, o);
        this.names = names.toArray(new String[0]);
        this.words = (this.names.length + 63) / 64;
        for (int i = 0; i < this.names.length; i++) index.put(this.names[i], i);
        for (String id : options.keySet()) members.put(id, new long[words]);
        for (int i = 0; i < this.names.length; i++)
            for (String id : rows.get(this.names[i])) members.get(id)[i >>> 6] |= 1L << (i & 63);
    }

    public static PresetFacets fromRows(List<Group> groups, Map<String, Set<String>> rows) {
        List<String> sorted = new ArrayList<>(rows.keySet());
        Collections.sort(sorted);
        Set<String> known = new HashSet<>();
        for (Group g : groups) for (Option o : g.options) if (!known.add(o.id)) throw new IllegalArgumentException("duplicate option " + o.id);
        for (Map.Entry<String, Set<String>> row : rows.entrySet())
            if (!known.containsAll(row.getValue())) throw new IllegalArgumentException("unknown option in " + row.getKey());
        return new PresetFacets(groups, sorted, rows);
    }

    public static PresetFacets parse(Reader reader) throws IOException {
        BufferedReader in = new BufferedReader(reader);
        String line = in.readLine();
        if (!MAGIC.equals(line)) throw new IllegalArgumentException("not a preset attribute table");
        List<Group> groups = new ArrayList<>();
        Map<String, List<Option>> groupOptions = new LinkedHashMap<>();
        Map<String, String> groupLabels = new LinkedHashMap<>();
        Map<String, Set<String>> rows = new LinkedHashMap<>();
        boolean columns = false;
        while ((line = in.readLine()) != null) {
            if (line.isEmpty()) continue;
            String[] f = line.split("\t", -1);
            if (!columns) {
                switch (f[0]) {
                    case "#definition": break;
                    case "#group":
                        if (f.length != 3 || groupLabels.containsKey(f[1])) throw new IllegalArgumentException("bad group line");
                        groupLabels.put(f[1], f[2]); groupOptions.put(f[1], new ArrayList<>()); break;
                    case "#option":
                        if (f.length != 4 || !groupOptions.containsKey(f[1])) throw new IllegalArgumentException("bad option line");
                        groupOptions.get(f[1]).add(new Option(f[2], f[3], f[1])); break;
                    case "#columns":
                        if (f.length != 3 + VALUE_COLUMNS || !"name".equals(f[1]) || !"options".equals(f[2])) throw new IllegalArgumentException("bad columns");
                        columns = true; break;
                    default: throw new IllegalArgumentException("unexpected header line");
                }
                continue;
            }
            if (f.length != 2 + VALUE_COLUMNS || f[0].isEmpty() || rows.containsKey(f[0])) throw new IllegalArgumentException("bad row");
            Set<String> ids = new LinkedHashSet<>();
            if (!f[1].isEmpty()) ids.addAll(Arrays.asList(f[1].split(",")));
            rows.put(f[0], ids);
        }
        if (!columns || groupLabels.isEmpty()) throw new IllegalArgumentException("incomplete attribute table");
        for (Map.Entry<String, String> g : groupLabels.entrySet()) groups.add(new Group(g.getKey(), g.getValue(), groupOptions.get(g.getKey())));
        return fromRows(groups, rows);
    }

    /** The bundled table, or null when it is missing or malformed (older official archives). */
    public static PresetFacets load(AssetManager assets) {
        try (Reader reader = new InputStreamReader(assets.open(ASSET), StandardCharsets.UTF_8)) {
            return parse(reader);
        } catch (IOException | IllegalArgumentException missingOrMalformed) {
            return null;
        }
    }

    public List<Group> groups() { return groups; }
    public int presetCount() { return names.length; }
    public boolean contains(String presetName) { return index.containsKey(presetName); }

    public Selection select(Collection<String> optionIds, Collection<String> excludedNames) {
        return new Selection(optionIds, excludedNames);
    }

    public final class Selection {
        private final List<String> selected = new ArrayList<>();
        private final List<String> ignored = new ArrayList<>();
        private final long[] excluded = new long[words];
        private final long[] pool;

        Selection(Collection<String> optionIds, Collection<String> excludedNames) {
            for (String id : new LinkedHashSet<>(optionIds)) (options.containsKey(id) ? selected : ignored).add(id);
            for (String name : excludedNames) {
                Integer i = index.get(name);
                if (i != null) excluded[i >>> 6] |= 1L << (i & 63);
            }
            pool = poolFor(selected);
        }

        private long[] poolFor(List<String> chosen) {
            long[] result = new long[words];
            for (int w = 0; w < words; w++) result[w] = ~excluded[w];
            if (names.length % 64 != 0) result[words - 1] &= (1L << (names.length % 64)) - 1;
            Map<String, long[]> byGroup = new LinkedHashMap<>();
            for (String id : chosen) {
                long[] union = byGroup.get(options.get(id).groupId);
                if (union == null) byGroup.put(options.get(id).groupId, union = new long[words]);
                long[] bits = members.get(id);
                for (int w = 0; w < words; w++) union[w] |= bits[w];
            }
            for (long[] union : byGroup.values()) for (int w = 0; w < words; w++) result[w] &= union[w];
            return result;
        }

        private int cardinality(long[] bits) { int n = 0; for (long w : bits) n += Long.bitCount(w); return n; }

        public List<String> selected() { return Collections.unmodifiableList(selected); }
        public List<String> ignored() { return Collections.unmodifiableList(ignored); }
        public int poolSize() { return cardinality(pool); }

        public int countIfToggled(String optionId) {
            if (!options.containsKey(optionId)) return 0;
            List<String> toggled = new ArrayList<>(selected);
            if (!toggled.remove(optionId)) toggled.add(optionId);
            return cardinality(poolFor(toggled));
        }

        public boolean isDimmed(String optionId) {
            return options.containsKey(optionId) && !selected.contains(optionId) && countIfToggled(optionId) == 0;
        }

        public String[] presetNames() {
            String[] out = new String[poolSize()];
            int n = 0;
            for (int i = 0; i < names.length; i++) if ((pool[i >>> 6] & (1L << (i & 63))) != 0) out[n++] = names[i];
            return out;
        }
    }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./gradlew :core:testDebugUnitTest --tests nl.neerdael.projectm.core.PresetFacetsTest`
Expected: PASS (5 tests). If the vector regex finds fewer than 5 cases, the fixture formatting differs from the regex. Keep the fixture's one-case-per-object layout from Task 1 and adjust only the regex whitespace (`\s*`).

- [ ] **Step 5: Commit**

```bash
git add core/src/main/java/nl/neerdael/projectm/core/PresetFacets.java core/src/test/java/nl/neerdael/projectm/core/PresetFacetsTest.java
git commit -m "feat(core): PresetFacets selection over bundled preset attributes"
git push
```

---

### Task 8: `FacetRow` view and focus cursor

**Files:**
- Create: `app/src/main/java/com/example/projectm/visualizer/FacetCursor.java` (pure logic)
- Create: `app/src/main/java/com/example/projectm/visualizer/FacetRow.java` (view)
- Test: `app/src/test/java/com/example/projectm/visualizer/FacetCursorTest.java`
- Modify: `app/src/main/res/values/dimens.xml` and `colors.xml` (two new tokens: `facet_chip_gap` and `facet_dimmed`), reusing `Overlay.*` text styles

**Interfaces:**
- Produces:
  - `FacetCursor`: `static int move(int current, int direction, boolean[] selectable)`. It returns the next selectable index in the direction (±1) without wrap, or `current` when none exists.
  - `FacetRow`: `void bind(String title, List<PresetFacets.Option> options, Listener listener)`, `void update(Set<String> selected, Map<String,Integer> counts, Set<String> dimmed, boolean enabled)` and `interface Listener { void onToggle(String optionId); }`.
  - Behaviour:
    - Left/Right move the option cursor and skip dimmed options. Center toggles the focused option; a tap on a chip toggles it.
    - An option is selectable if it is selected or not dimmed.
    - Each chip shows "Label → N", and a selected chip is highlighted.
    - Each chip's content description is "<Label>, selected|not selected, N presets".
    - When `enabled` is false, the whole row is dimmed and ignores toggles but remains focusable, so D-pad navigation does not break.

- [ ] **Step 1: Write the failing test**

```java
package com.example.projectm.visualizer;

import static org.junit.Assert.assertEquals;
import org.junit.Test;

public class FacetCursorTest {
    @Test public void skipsDimmedOptionsWithoutWrapping() {
        boolean[] selectable = {true, false, false, true, true};
        assertEquals(3, FacetCursor.move(0, 1, selectable));
        assertEquals(4, FacetCursor.move(3, 1, selectable));
        assertEquals(4, FacetCursor.move(4, 1, selectable));
        assertEquals(0, FacetCursor.move(3, -1, selectable));
        assertEquals(0, FacetCursor.move(0, -1, selectable));
    }

    @Test public void firstSelectableIsUsedWhenTheCurrentOptionBecomesDimmed() {
        boolean[] selectable = {false, false, true};
        assertEquals(2, FacetCursor.first(selectable, 0));
        assertEquals(-1, FacetCursor.first(new boolean[]{false, false}, 0));
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./gradlew :app:testDebugUnitTest --tests com.example.projectm.visualizer.FacetCursorTest`
Expected: FAIL, `cannot find symbol: class FacetCursor`.

- [ ] **Step 3: Implement `FacetCursor`**

```java
package com.example.projectm.visualizer;

/** Option cursor of a facet row: moves skip options that cannot be selected (dimmed). */
final class FacetCursor {
    private FacetCursor() {}

    static int move(int current, int direction, boolean[] selectable) {
        for (int i = current + direction; i >= 0 && i < selectable.length; i += direction)
            if (selectable[i]) return i;
        return current;
    }

    /** The preferred index if selectable, else the first selectable one, else -1. */
    static int first(boolean[] selectable, int preferred) {
        if (preferred >= 0 && preferred < selectable.length && selectable[preferred]) return preferred;
        for (int i = 0; i < selectable.length; i++) if (selectable[i]) return i;
        return -1;
    }
}
```

- [ ] **Step 4: Implement `FacetRow`**

Model it on `OptionRow` (same padding, focus background drawable and `Overlay.*` styles; read `OptionRow.java` and copy its constructor and focus handling). It is a vertical `LinearLayout` with a title `TextView` and a horizontal `LinearLayout` of chip `TextView`s. Key handling:

```java
    @Override public boolean onKeyDown(int keyCode, KeyEvent event) {
        boolean[] selectable = selectable();
        switch (keyCode) {
            case KeyEvent.KEYCODE_DPAD_LEFT: setCursor(FacetCursor.move(cursor, -1, selectable)); return true;
            case KeyEvent.KEYCODE_DPAD_RIGHT: setCursor(FacetCursor.move(cursor, 1, selectable)); return true;
            case KeyEvent.KEYCODE_DPAD_CENTER: case KeyEvent.KEYCODE_ENTER: case KeyEvent.KEYCODE_NUMPAD_ENTER:
                if (enabled && cursor >= 0 && selectable[cursor]) listener.onToggle(options.get(cursor).id);
                return true;
            default: return super.onKeyDown(keyCode, event);
        }
    }
```

Further requirements:
- `update()` calls `setCursor(FacetCursor.first(selectable(), cursor))` so the cursor never rests on a dimmed chip.
- Chips get `setOnClickListener` for touch (phone edition), and the same `enabled`/selectable test applies.
- The row is `focusable` and `focusableInTouchMode=false`, like `OptionRow`, and returns `false` for Up/Down so `MainActivity` keeps moving between rows.
- Selected chip: highlight colour from existing tokens. Dimmed chip: `@color/facet_dimmed`. The focused chip is underlined via `Paint.UNDERLINE_TEXT_FLAG`.

- [ ] **Step 5: Run the tests and a build**

Run: `./gradlew :app:testDebugUnitTest :app:assembleDebug`
Expected: PASS and BUILD SUCCESSFUL.

- [ ] **Step 6: Commit**

```bash
git add app/src/main/java/com/example/projectm/visualizer/FacetCursor.java app/src/main/java/com/example/projectm/visualizer/FacetRow.java app/src/test/java/com/example/projectm/visualizer/FacetCursorTest.java app/src/main/res/values/dimens.xml app/src/main/res/values/colors.xml
git commit -m "feat(app): facet row with dimmed-aware D-pad cursor and touch chips"
git push
```

---

### Task 9: Mood sub-panel, persistence, migration and on-device journey

**Files:**
- Create: `app/src/main/java/com/example/projectm/visualizer/MoodFacetsController.java` (state, persistence and pool application; no views)
- Create: `app/src/test/java/com/example/projectm/visualizer/MoodFacetsControllerTest.java`
- Create: `app/src/androidTest/java/com/example/projectm/visualizer/MoodSetupTest.java`
- Modify:
  - `MainActivity.java`: `Menu.MOOD`, the Preset mood action row opening the panel, and Back/Menu/auto-hide handling;
  - `app/src/main/res/layout/activity_main.xml`: a `mood_menu` container modelled on `advanced_menu`, a header, a collection row, a facet rows container, Clear all and Back;
  - `ProjectMApplication.java`: the migration;
  - `MusicCategoryInstrumentation.java`: the `mood` setup case.

**Interfaces:**
- Consumes: `PresetFacets` (Task 7), `ProjectMJNI.setPresetPool`, `setMusicCategory`, `getCategoryPresetCount("custom")` and `isMusicCategoryPending` (Task 6 and existing), and `FacetRow` (Task 8).
- Produces: `MoodFacetsController`, built as `new MoodFacetsController(PresetFacets facets /*nullable*/, Prefs prefs, Engine engine, SkipList skips)` with three small interfaces so JVM tests need no Android:
  - `interface Prefs { String get(String key, String fallback); void put(String key, String value); }`
  - `interface Engine { void setPresetPool(String[] names); void setMusicCategory(String id); int customCount(); }`
  - `interface SkipList { Set<String> names(); }` (reads `ProjectMCore.skipListFile` lines in the app adapter)
- Controller methods:
  - `Set<String> selected()`, `String collection()` (`"bundled"` or `"custom"`) and `boolean facetsAvailable()`;
  - `PresetFacets.Selection selection()` (null when unavailable);
  - `void toggle(String optionId)`, `void clearAll()` and `void setCollection(String id)`;
  - `void apply()`, which pushes the pool and category to the engine;
  - `String header()`, e.g. "1,234 presets in your mix", with the hint "few presets: some repetition" when the pool is below 20.
- Preference keys:
  - `mood_facets`: comma-separated ids;
  - `music_category` (existing): set to `facets`, `all` or `custom` by `apply()`;
  - `mood_collection`: `bundled` or `custom`.

- [ ] **Step 1: Write the failing controller tests**

```java
package com.example.projectm.visualizer;

import static org.junit.Assert.*;
import java.io.IOException;
import java.io.StringReader;
import java.util.*;
import nl.neerdael.projectm.core.PresetFacets;
import org.junit.Before;
import org.junit.Test;

public class MoodFacetsControllerTest {
    private static final String TABLE =
            "#projectm-tv-preset-attributes\t1\n#definition\tx\n#group\tenergy\tEnergy\n#option\tenergy\tchill\tChill\n#option\tenergy\tintense\tIntense\n"
            + "#group\tcomfort\tComfort\n#option\tcomfort\tno_strobe\tNo strobe\n"
            + "#columns\tname\toptions\tluminance\tsaturation\tcoloured_share\twarm_cool\tflow\tframe_difference\tjumps\tactivity\n"
            + "a.milk\tchill,no_strobe\t0\t0\t0\t0\t0\t0\t0\t0\nb.milk\tintense\t0\t0\t0\t0\t0\t0\t0\t0\nc.milk\tchill\t0\t0\t0\t0\t0\t0\t0\t0\n";
    private final Map<String, String> store = new HashMap<>();
    private final List<String> calls = new ArrayList<>();
    private final Set<String> skipped = new HashSet<>();
    private int customCount = 0;
    private PresetFacets facets;

    @Before public void setUp() throws IOException { facets = PresetFacets.parse(new StringReader(TABLE)); }

    private MoodFacetsController controller(PresetFacets table) {
        return new MoodFacetsController(table,
                new MoodFacetsController.Prefs() {
                    public String get(String k, String f) { return store.containsKey(k) ? store.get(k) : f; }
                    public void put(String k, String v) { store.put(k, v); }
                },
                new MoodFacetsController.Engine() {
                    public void setPresetPool(String[] names) { calls.add("pool:" + (names == null ? "null" : String.join(",", names))); }
                    public void setMusicCategory(String id) { calls.add("category:" + id); }
                    public int customCount() { return customCount; }
                },
                () -> skipped);
    }

    @Test public void toggleAppliesPoolThenFacetsCategoryAndPersists() {
        MoodFacetsController c = controller(facets);
        c.toggle("chill");
        assertEquals(Arrays.asList("pool:a.milk,c.milk", "category:facets"), calls);
        assertEquals("chill", store.get("mood_facets"));
        assertEquals("facets", store.get("music_category"));
        assertEquals("2 presets in your mix · few presets: some repetition", c.header());
    }

    @Test public void clearingEverythingRestoresAll() {
        store.put("mood_facets", "chill");
        MoodFacetsController c = controller(facets);
        c.clearAll();
        assertEquals("", store.get("mood_facets"));
        assertTrue(calls.contains("category:all"));
    }

    @Test public void dimmedOptionsCannotBeToggledOn() {
        store.put("mood_facets", "no_strobe");
        MoodFacetsController c = controller(facets);
        assertTrue(c.selection().isDimmed("intense"));
        c.toggle("intense");
        assertEquals("no_strobe", store.get("mood_facets"));
    }

    @Test public void unknownStoredIdsAreDroppedAndTheRestKept() {
        store.put("mood_facets", "chill,retired_option");
        MoodFacetsController c = controller(facets);
        assertEquals(Collections.singleton("chill"), c.selected());
        c.apply();
        assertEquals("chill", store.get("mood_facets"));
    }

    @Test public void customCollectionDisablesFacetsAndKeepsThemStored() {
        customCount = 3;
        store.put("mood_facets", "chill");
        MoodFacetsController c = controller(facets);
        c.setCollection("custom");
        assertTrue(calls.contains("category:custom"));
        assertEquals("chill", store.get("mood_facets"));
        c.toggle("intense");  // ignored while custom plays
        assertEquals("chill", store.get("mood_facets"));
        c.setCollection("bundled");
        assertEquals("category:facets", calls.get(calls.size() - 1));
    }

    @Test public void skippedPresetsAreExcludedFromCountsAndPool() {
        skipped.add("a.milk");
        MoodFacetsController c = controller(facets);
        c.toggle("chill");
        assertEquals("pool:c.milk", calls.get(0));
    }

    @Test public void missingTableOffersOnlyTheCollection() {
        MoodFacetsController c = controller(null);
        assertFalse(c.facetsAvailable());
        assertNull(c.selection());
        c.toggle("chill");
        assertTrue(calls.isEmpty());
        assertEquals("All presets", c.header());
    }
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./gradlew :app:testDebugUnitTest --tests com.example.projectm.visualizer.MoodFacetsControllerTest`
Expected: FAIL, `cannot find symbol: class MoodFacetsController`.

- [ ] **Step 3: Implement `MoodFacetsController`**

```java
package com.example.projectm.visualizer;

import java.text.NumberFormat;
import java.util.*;
import nl.neerdael.projectm.core.PresetFacets;

/** Mood panel state: facet selection, collection choice, persistence and engine pool. No views. */
final class MoodFacetsController {
    interface Prefs { String get(String key, String fallback); void put(String key, String value); }
    interface Engine { void setPresetPool(String[] names); void setMusicCategory(String id); int customCount(); }
    interface SkipList { Set<String> names(); }

    static final String PREF_FACETS = "mood_facets", PREF_COLLECTION = "mood_collection", PREF_CATEGORY = "music_category";
    private static final int FEW = 20;

    private final PresetFacets facets;
    private final Prefs prefs;
    private final Engine engine;
    private final SkipList skips;
    private final LinkedHashSet<String> selected = new LinkedHashSet<>();
    private String collection;

    MoodFacetsController(PresetFacets facets, Prefs prefs, Engine engine, SkipList skips) {
        this.facets = facets; this.prefs = prefs; this.engine = engine; this.skips = skips;
        collection = "custom".equals(prefs.get(PREF_COLLECTION, "bundled")) ? "custom" : "bundled";
        String stored = prefs.get(PREF_FACETS, "");
        if (facets != null && !stored.isEmpty())
            selected.addAll(facets.select(Arrays.asList(stored.split(",")), Collections.<String>emptySet()).selected());
    }

    boolean facetsAvailable() { return facets != null; }
    Set<String> selected() { return Collections.unmodifiableSet(selected); }
    String collection() { return collection; }

    PresetFacets.Selection selection() {
        return facets == null ? null : facets.select(selected, skips.names());
    }

    void toggle(String optionId) {
        if (facets == null || "custom".equals(collection)) return;
        PresetFacets.Selection current = selection();
        if (!selected.remove(optionId)) {
            if (current.isDimmed(optionId) || current.countIfToggled(optionId) == 0) return;
            selected.add(optionId);
        }
        apply();
    }

    void clearAll() { selected.clear(); apply(); }

    void setCollection(String id) {
        collection = "custom".equals(id) && engine.customCount() > 0 ? "custom" : "bundled";
        apply();
    }

    void apply() {
        prefs.put(PREF_FACETS, String.join(",", selected));
        prefs.put(PREF_COLLECTION, collection);
        String category;
        if ("custom".equals(collection)) category = "custom";
        else if (facets != null && !selected.isEmpty()) {
            engine.setPresetPool(selection().presetNames());
            category = "facets";
        } else category = "all";
        prefs.put(PREF_CATEGORY, category);
        engine.setMusicCategory(category);
    }

    String header() {
        if ("custom".equals(collection)) return "Custom pack";
        if (facets == null || selected.isEmpty()) return facets == null ? "All presets" : "All presets in your mix";
        int size = selection().poolSize();
        String text = NumberFormat.getIntegerInstance(Locale.US).format(size) + " presets in your mix";
        return size < FEW ? text + " · few presets: some repetition" : text;
    }
}
```

The header when nothing is selected ("All presets in your mix") is not asserted by the tests above. Add a one-line assertion for it in `clearingEverythingRestoresAll`.

- [ ] **Step 4: Run the controller tests to verify they pass**

Run: `./gradlew :app:testDebugUnitTest --tests com.example.projectm.visualizer.MoodFacetsControllerTest`
Expected: PASS (7 tests).

- [ ] **Step 5: Add the migration in `ProjectMApplication`**

Next to the existing guarded migrations:

```java
    private static final String PREF_MOOD_MIGRATED = "mood_facets_migrated_1";
    …
        if (!prefs.getBoolean(PREF_MOOD_MIGRATED, false)) {
            String legacy = prefs.getString("music_category", "all");
            SharedPreferences.Editor edit = prefs.edit().putBoolean(PREF_MOOD_MIGRATED, true);
            if ("chill".equals(legacy) || "normal".equals(legacy) || "intense".equals(legacy))
                edit.putString("mood_facets", legacy).putString("music_category", "facets");
            else if ("custom".equals(legacy)) edit.putString("mood_collection", "custom");
            edit.apply();
        }
```

Add a JVM test only if `ProjectMApplication` already has one. Otherwise the migration is covered by the `mood` setup case in Step 8.

- [ ] **Step 6: Build the panel in `MainActivity` and the layout**

- **Layout:** add `mood_menu` as a sibling of `advanced_menu`, copying its container attributes (overscan-safe bounds, `ScrollView` with D-pad focus scrolling, as in Advanced). It contains:
  - `mood_header` (`TextView`, `Overlay.*` style);
  - `row_mood_collection` (`OptionRow`, visible only when a custom pack exists);
  - `mood_rows` (vertical `LinearLayout`, filled in code with one `FacetRow` per group);
  - `row_mood_clear` (`OptionRow` action "Clear all");
  - `mood_back` (copy of `advanced_back`).
- **`MainActivity`:**
  - Add `MOOD` to `enum Menu` and map it in the method that returns a menu's view.
  - Make `showMenu` handle `MOOD` like `ADVANCED`: slide-in, and Back returns to `MAIN` with focus on `row_music_category`.
  - Replace `refreshMusicCategory`'s `musicCategoryRow.setup(…)` cycling list with `musicCategoryRow.setupAction("Preset mood", <summary>, () -> showMenu(Menu.MOOD))`. The summary is `controller.header()`, shortened to "Custom" / "All" / "<N> presets" for the row value.
  - Keep the custom-pack commit path, which currently writes `music_category = "custom"`. It must now call `controller.setCollection("custom")`.
  - Construct the controller in `onCreate` after `ProjectMCore.init`:
    - facets from `PresetFacets.load(getAssets())`; when an official pack is active, load from the official pack's directory instead (read how `OfficialPresetPack` exposes it on the fdroid source set, and add a `PresetFacets.parse(new FileReader(dir/preset-attributes/attributes.tsv))` path, with `null` on failure);
    - prefs over `projectm_settings`;
    - engine over `ProjectMJNI`;
    - skips reading `ProjectMCore.skipListFile(context)` lines.
  - Call `controller.apply()` once at startup in place of the existing `ProjectMJNI.setMusicCategory(requestedMusicCategory)` line.
  - **Rendering rows:** for each `PresetFacets.Group` call `FacetRow.bind`. On every change call `update(selected, counts, dimmed, collection == bundled)` for all rows and refresh `mood_header`. Counts come from `selection.countIfToggled(id)` for unselected options and from `poolSize()` for selected ones.
  - Every key event in the Mood panel restarts the 10 s hide timer, using the existing call used by Advanced.
  - When the native library falls back to All (an empty pool after skips), the existing `refreshMusicCategory` toast path fires. Do not overwrite `mood_facets` in that path: change it to update only `music_category`.
- **Accessibility:** `mood_header` gets `android:accessibilityLiveRegion="polite"`. `FacetRow` sets chip content descriptions (Task 8).

- [ ] **Step 7: Run the JVM tests and the build**

Run: `./gradlew :app:testDebugUnitTest :core:testDebugUnitTest :app:assembleDebug`
Expected: PASS and BUILD SUCCESSFUL.

- [ ] **Step 8: Add the `mood` setup case and run it on the task emulator**

`MoodSetupTest.run(Instrumentation)`, modelled on `ResolutionSetupTest`, performs this journey:
1. Clear `projectm_settings`, launch, press Menu, open Preset mood.
2. Assert the header reads "All presets in your mix".
3. Move to Energy and press Center on Chill. Assert the header count equals `PresetFacets.load(...).select(["chill"], skips).poolSize()`.
4. Move to Comfort and toggle No strobe; the count shrinks.
5. Assert at least one option shows as dimmed and that pressing Center on it changes nothing.
6. Clear all.
7. Press Back and assert the main panel has focus on Preset mood.
8. Wait 10 s and assert the panels are hidden.
9. Relaunch and assert `mood_facets` persisted and the header is restored.
10. Seed `music_category=intense` with `mood_facets_migrated_1` absent, relaunch, and assert `mood_facets == "intense"`.

Save a screenshot to the test app's external cache as `mood.png`. Register the case in `MusicCategoryInstrumentation.onStart` (`else if ("mood".equals(setupCase)) MoodSetupTest.run(this);`).

```bash
./gradlew :app:assembleDebug :app:assembleDebugAndroidTest -PsetupScreenshotTest
adb -s emulator-5610 install -r app/build/outputs/apk/debug/app-debug.apk
adb -s emulator-5610 install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
U=$(adb -s emulator-5610 shell am get-current-user | tr -d '\r')
adb -s emulator-5610 shell am instrument --user $U -w -e setup_case mood nl.neerdael.projectmtv.setuptest.test/com.example.projectm.visualizer.MusicCategoryInstrumentation
```

Expected: `OK`. Use only the task-owned emulator (`emulator-5610`), never a physical device. Pull `mood.png` into `docs/user-guide/images/setup/mood.png`.

- [ ] **Step 9: Commit**

```bash
git add app/src/main/java/com/example/projectm/visualizer/MoodFacetsController.java app/src/test/java/com/example/projectm/visualizer/MoodFacetsControllerTest.java \
  app/src/androidTest/java/com/example/projectm/visualizer/MoodSetupTest.java app/src/androidTest/java/com/example/projectm/visualizer/MusicCategoryInstrumentation.java \
  app/src/main/java/com/example/projectm/visualizer/MainActivity.java app/src/main/java/com/example/projectm/visualizer/ProjectMApplication.java \
  app/src/main/res/layout/activity_main.xml docs/user-guide/images/setup/mood.png
git commit -m "feat(app): Mood sub-panel with facet groups, live counts, dimming and migration"
git push
```

---

### Task 10: Documentation, PR, Codex review and merge (`main`)

**Files:**
- Modify:
  - `README.md` (settings table: Preset mood → Mood sub-panel; remote control table if wording changes);
  - `docs/user-guide/settings.md`, `docs/user-guide/controls.md` and `docs/user-guide/predictive-collections.md` (a "Preset moods" section: facets, counts, how attributes are measured, limits);
  - `docs/user-guide/predictor-export.md` (the `preset-attributes/` bundle format);
  - `docs/THIRD_PARTY.md` (only if the ruler tool adds third-party content; it does not, so state that in the assessment);
  - `AGENTS.md` (facet bundle commands, the native-ruler tool, `setPresetPool`, preference keys).
- PR body following `.github/pull_request_template.md`.

- [ ] **Step 1: Update the docs.** Use the exact UI labels everywhere:
  - "Preset mood" and "Clear all";
  - group names Energy, Brightness, Colour, Movement, Style and Comfort;
  - option labels as in `facets-v1.json`;
  - menu path "Settings › Preset mood".
  
  The limits paragraph states:
  - one 10 s render per preset with one synthetic track at 480×270 under SwiftShader;
  - real music and TV GPUs differ;
  - Style rests on source structure and is the least certain;
  - custom-pack presets are excluded while any facet is active.

- [ ] **Step 2: Validate**

```bash
build/docs-venv/bin/mkdocs build --strict   # or: pip install -r docs/site-requirements.txt && mkdocs build --strict
python3 -m unittest discover -s tools/milk-analyzer -p 'test_*facet*.py' -v
python3 -m unittest discover -s tools/milk-analyzer -p 'test_attribute_bundle.py' -v
python3 -m unittest discover -s .github/scripts/tests -v
python3 tools/milk-analyzer/attribute_bundle.py --check
tools/gen-preset-index.py --check
core/src/test/native/run_native_tests.sh
./gradlew testReleaseUnitTest assembleRelease
git diff --check
actionlint .github/workflows/android-build.yml
```

Expected: everything passes. Record actual results in `## Validation`.

- [ ] **Step 3: Open the PR.**
  - **Release notes:** under user-visible behaviour, "Preset mood now opens a Mood panel…" with the six groups, live counts, dimmed options and Clear all. Migration: a previous Chill/Normal/Intense choice becomes the Energy option. Limits as in Step 1. Use an `Internal` subsection for the bundle, ruler tool and CI checks.
  - **Documentation assessment:** list each evaluated file.
  - **Milkbeat:** the additive API (`PresetFacets`, `setPresetPool`) leaves legacy categories unchanged.

```bash
gh pr create --base main --head feat/mood-facets --title "Mood facets: multi-select preset attributes with live counts" --body-file /tmp/mood-facets-pr.md
```

- [ ] **Step 4: Codex review loop.** Follow `AGENTS.md` §5:
  - Post `@codex review` if no automatic review started.
  - Wait for completion on the head SHA. Fix every finding with tests, reply in each thread, resolve, and re-request until the final head has a completed review with no open findings.
  - Run quick targeted checks per review fix; CI runs the full suites.

- [ ] **Step 5: Merge and confirm.**
  - Refresh the PR state. Verify that the head SHA matches the reviewed one, that the required `Reviewed PR builds` check passed, and that there are no unresolved threads. Merge through GitHub.
  - Record the merge SHA. Monitor the release workflow (APK/AAR publication and Milkbeat dispatch) and report its outcome.
  - Keep the worktree (memory: never remove worktrees without asking).

---

### Task 11: SDK and JSON contract (predictor branch, never merged to `main`)

Run in `.worktrees/predictor-memory-repair` after Task 10 merges. First bring in the definition, selection module and vectors: `git checkout origin/main -- tools/milk-analyzer/facets tools/milk-analyzer/preset_facets.py tools/milk-analyzer/fixtures/facet-selection-vectors-v1.json tools/milk-analyzer/test_preset_facets.py`.

**Files (predictor branch):**
- Modify:
  - `tools/milk-analyzer/preset_recipe.py`: a versioned `facets` block;
  - `tools/milk-analyzer/corpus_understanding.py`: the preference index carries per-preset facets;
  - `tools/milk-analyzer/preference_select.py`: a `"facets": [...]` request;
  - `tools/milk-analyzer/EXPORT_CONTRACT.md`;
  - `tools/milk-analyzer/skills/understand-preset/SKILL.md` ("select by facets");
  - `docs/user-guide/predictor-export.md` (predictor-branch copy).
- Test: `tools/milk-analyzer/test_preset_recipe.py` and `tools/milk-analyzer/test_preference_select.py` (add cases).

**Interfaces:**
- Consumes: `preset_facets.memberships` and `preset_facets.select`; `display_estimate` statistics from `calibrated_display` (already in the recipe); the bundled `attributes.tsv` (read by name for measured values).
- Produces the recipe block `facets`:

```json
{"policy": "preset-facets-v1", "definition_sha256": "...",
 "options": ["chill", "dark", ...],
 "unresolved_options": ["monochrome", "pastel"],
 "values": {"luminance": {"value": 0.17, "interval": [0.0, 0.43], "evidence": "source-calibrated"}, ...},
 "evidence": "engine-ruler-measured | source-calibrated", "style_evidence": "source-structure-facts"}
```

Rules:
- A bundled preset with a measured row uses its measured values, with `evidence` `engine-ruler-measured`.
- Otherwise values come from `display_estimate.statistics`, with `evidence` `source-calibrated` plus intervals. Activity comes from `display_estimate.activity.activity`.
- An option whose rule needs a value the calibrated model does not estimate (`coloured_share`, so Monochrome and Pastel) is listed in `unresolved_options`, never guessed.
- An option is a member only if its rule holds for the point value. If the interval straddles a threshold, the option is still a member when the point value satisfies the rule, and it is also added to `possible_options`.
- Owner rule: no simulation output feeds any value.

- [ ] **Step 1: Write the failing tests**

```python
def test_recipe_facets_block_uses_calibrated_values_and_marks_unresolved(self):
    recipe = self.recipe_for_fixture()  # existing helper in test_preset_recipe.py building a recipe from a fixture summary
    facets = recipe['facets']
    self.assertEqual(facets['policy'], 'preset-facets-v1')
    self.assertEqual(facets['evidence'], 'source-calibrated')
    self.assertIn('monochrome', facets['unresolved_options']); self.assertIn('pastel', facets['unresolved_options'])
    self.assertTrue(set(facets['options']) <= set(preset_facets.option_ids(preset_facets.load_definition())))

def test_preference_select_filters_by_facets(self):
    index = {'policy': 'x', 'presets': [{'name': 'a.milk', 'facets': {'options': ['chill', 'no_strobe']}},
                                        {'name': 'b.milk', 'facets': {'options': ['intense']}}]}
    result = preference_select.select(index, {'facets': ['chill']})
    self.assertEqual([p['name'] for p in result['presets']], ['a.milk'])
    self.assertEqual(result['facets']['count'], 1); self.assertEqual(result['facets']['option_counts']['intense'], 1)
```

Read `test_preset_recipe.py` and `test_preference_select.py` first. Reuse their fixture builders and the real entry-point names (`preference_select.select` or its CLI-level function) and adjust the calls to the actual signatures.

- [ ] **Step 2: Run them to verify they fail**

Run: `build/preset-lab-venv/bin/python -m pytest tools/milk-analyzer/test_preset_recipe.py tools/milk-analyzer/test_preference_select.py -q -p no:cacheprovider`
Expected: FAIL with `KeyError: 'facets'`.

- [ ] **Step 3: Implement the facets block, the index field and the selection filter** following the rules above. In `preference_select`:
  - the pool is the facet `select()` pool intersected with the existing profile and comfort filtering;
  - the response gains `facets` (`selected`, `ignored`, `count`, `option_counts`, `dimmed`).

- [ ] **Step 4: Update `EXPORT_CONTRACT.md`, the skill and the docs.** Document the facets block and the bundle format, and in the skill: "select by facets: pass option ids; OR within a group, AND across groups".

- [ ] **Step 5: Run the full suite while editing nothing**

Run: `build/preset-lab-venv/bin/python build/full-suite-2026-10-11/run.py`
Expected: all pass, with no edits to analyzer files while it runs.

- [ ] **Step 6: Commit and push the predictor branch**

```bash
git add tools/milk-analyzer docs/user-guide/predictor-export.md
git commit -m "feat(predictor): facets block in the recipe/preference index and facet selection in the SDK"
git push
```

---

## Self-review notes

- **Spec coverage:**
  - §1 facet set → Task 1 (definition), Task 2 (style) and Task 4 (memberships).
  - §2 bundle and pipeline → Tasks 3–5 (adjusted to name-keyed TSV; ruler tool moved to `tools/native-ruler/`).
  - §3 core API → Tasks 6–7 (adjusted to names; legacy categories unchanged).
  - §4 panel UI → Tasks 8–9.
  - §5 SDK and JSON → Task 1 (`preset_facets.py` and shared vectors) and Task 11 (recipe, index, selection, docs, skill).
  - §6 compatibility and testing → Tasks 6, 7, 9 and 10.
  - Limits → Task 10 docs.
- **Placeholders:** where a step depends on code the executor must read first (existing test helpers, the official pack directory accessor, `HandleCommands`), the step names the exact symbol to read and the behaviour to preserve.
- **Type consistency:**
  - `PresetFacets.Selection.presetNames()` returns `String[]`, matching `ProjectMJNI.setPresetPool(String[])` and `MoodFacetsController.Engine.setPresetPool(String[])`.
  - The `attributes.tsv` columns are the same in Tasks 4, 5, 7 and 11.
  - The `facets` category id is the same in Tasks 6 and 9.
