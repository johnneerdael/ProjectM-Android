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
