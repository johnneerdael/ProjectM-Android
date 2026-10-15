# Static-only Mood grouping for all 9,606 presets (2026-10-15)

`static_grouping_export.py` (run from `build/colour-gap-2026-10-15/`, 12 workers) groups every corpus preset from
source analysis only. For each preset it computes the recipe render probes, the source-calibrated display estimate
with the shipped model (r15q at the 80% middle floor), and `facets_block` with the preset identity removed, so the
bundled engine-ruler row is never used. It also records the display palette and dominant colour. No simulation output
and no rendered frame is read. The result is `static-index.json.gz` (`{preset: {options, possible, unresolved,
palette, dominant_hue, dominance}}`).

Coverage: all 9,606 presets. The first run failed on 10 presets ($$$ Royal – Mashup and martin/amandio shader
presets), whose per-pixel zoom reads `megabuf`. The recipe ray probe drew every unknown stage input as a random
number, memory buffers included. `preset_recipe._stage_draw` now gives `memory:*` inputs a zero-initialised buffer
(test `test_stage_draws_give_memory_inputs_an_empty_buffer`), and all 10 export.

Agreement with the engine-ruler options (`report.md`): pooled precision 93.3%, recall 54.2%; 427 presets get no Mood
option (uncertain everywhere). **This is in-sample:** the bundled presets are the calibration's training set. The
honest out-of-fold estimate is the scoreboard: about 79% precision and 41% recall pooled
(`docs/superpowers/evidence/facet-readiness-2026-10-15/README.md`). Presets outside the bundle can be expected to
behave like the out-of-fold figures.

A dominant colour is named for 1,323 presets; every preset has a palette.

Grey presets: 1,002 presets have an engine coloured share below 0.1. The first export named hues for all of them and
a dominant colour for 16%. When the monochrome classifier admits a preset (93% precision out of fold, and in the export
never admitted for a coloured preset), `display_palette` now returns an empty palette, no dominant colour and
`monochrome: true` (test `test_display_palette_is_grey_when_monochrome_is_admitted`). In the index, 473 presets are
grey; 9,133 carry a palette and 1,236 a dominant colour.
