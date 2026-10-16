# Static mood table evidence (2026-10-16)

`static-evidence.json.gz` is the evidence the shipped Mood table (`core/src/main/assets/preset-attributes/`) is built
from and checked against. It holds one row per bundled preset: preset file SHA-256, static mood options (without
colour ids), static display palette, main colour (`dominant`, or null) and the eight value columns, plus the producer
identity (research branch, commit, calibration model SHA-256, policy).

- Producer: `static_evidence_export.py` (copy in this folder) on the research branch
  `feat/predictor-static-output-bounds`, run from `build/colour-gap-2026-10-15/` with 12 workers over the stored
  corpus summaries (`build/preset-corpus/corpus-understanding-9606-r14/`). It is a research harness and does not run on
  `main`: it imports the analyzer modules of that branch.
- Policy: static source analysis only. Per preset it runs the recipe probes, the source-calibrated display estimate and
  `facets_block` with the preset identity removed, so no engine-ruler row of the earlier table can be used; then the
  static display palette and the frozen-reference activity. No simulation output and no rendered frame is read.
- Build: `python3 tools/milk-analyzer/attribute_bundle.py --build-static docs/superpowers/evidence/static-mood-table-2026-10-16/static-evidence.json.gz`
- Check (CI): `python3 tools/milk-analyzer/attribute_bundle.py --check`. It rebuilds every table line from its evidence
  row, compares names with `presets.idx` in both directions, hashes every bundled preset against the evidence SHA-256,
  recomputes the manifest metadata and enforces the 450,000-byte deflated size budget.

A changed, added or renamed preset fails the check until the export is rerun for it on the research branch and the
table regenerated. Accuracy (out of fold and in sample) and the method are documented in the user guide:
`docs/user-guide/predictor/accuracy.md` and `docs/user-guide/predictor/mood-table.md`.
