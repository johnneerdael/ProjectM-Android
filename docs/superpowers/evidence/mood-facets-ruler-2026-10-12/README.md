# Mood facets ruler evidence (2026-10-12)

Engine-ruler measurements of the 9,606 bundled presets, made with `tools/native-ruler` (see its README for conditions and limits).

- `ruler-results-manifest.json`: one row per preset (`preset`, `preset_sha256`, `result_sha256`, `status`). 9,606 rows, all `measured`. The raw per-preset results are not committed.
- Raw results archive (outside the repository): `ProjectM-TV-ruler-results-2026-10-12.tar.gz`, containing `results/*.json`.
  - sha256: `3ad37ffbc8b719d8e1cb23bc8583df7e260951ab7cf49e4f2985638084ba0818`
- Engine: patched projectM tree at VCS version `2449c627f6e7bc25041adefc2a6f3429da1343e5`, macOS GLES via SwiftShader.
- Style facts (Task 2): `facet-style-facts-v1.tsv`, produced by `tools/milk-analyzer/facet_style_facts.py` at commit `3ae40333` on branch `feat/predictor-static-output-bounds`.
  - sha256: `7ee12803eccf79cb4a5a6bdaadf312a1023bcefb23a607bdf33c66319a3d4821`
  - Counts: kaleidoscope 3989, tunnel 706, liquid 3730, geometric 1930, particles 3207, fractal 130, none 1382.

Verify the archive: `shasum -a 256 ProjectM-TV-ruler-results-2026-10-12.tar.gz`. Each row's `result_sha256` is the sha256 of the corresponding `results/<preset>.json` file.
