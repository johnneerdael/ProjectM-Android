# Full knowledge pack build, 2026-10-13

First complete `preset-knowledge-pack-v1` build from the 9,606-preset r11
corpus run (`corpus-understanding-9606-r11`), with programs. The pack itself
is not committed; `full-pack-summary.json` records its identity, sizes and
timings.

- 9,606 recipes, 0 failures; `knowledge_pack.py check --presets` passed.
- `core.jsonl.gz` 52.5 MB (52,454,337 bytes); `full/` 115 MB in 9,606 files.
- Build: 2.1 hours with 4 workers. The builder streams results, so its main
  process peaked at 1.47 GB (the earlier in-memory version passed 2 GB and
  was still growing).
- The Python reference reader (`load_core`, with every FORMAT.md rule)
  accepts the pack in 3.2 s. It keeps each full recipe (2.7 GB).
- The Java `PresetKnowledgePack` (merged in PR #82) accepts the pack and
  visits every recipe in 7.8 s on a desktop JVM. 129 MB of views remain on
  the heap after GC. Not measured on a TV.

The pack was built before the stricter reader rules (single gzip member, LF
endings, strict UTF-8, view types, presets array) were written down; both
readers accept it under those rules.

## Correction: statistics outside their physical range

This pack was built at d584df77, before `calibrated_display.predict` clamped
values and intervals to their physical domain (46c21e4b). It breaks the
FORMAT.md rule that statistic values and intervals lie inside their physical
range: 3,580 presets have at least one out-of-range bound (2,328 luminance
intervals, 1,793 saturation intervals, 328 warm/cool intervals, and 22
values). Both readers accepted it because the rule is a producer guarantee,
not a reader rule, and `knowledge_pack.py check` did not test it. `check` now
reports these bounds, and a pack built with the current recipe code clamps
them. The "every FORMAT.md rule" statement above covers the reader rules
only.
