# Source understanding checkpoints, 2026-10-11 (continuation session)

Branch `feat/predictor-static-output-bounds`, worktree `predictor-memory-repair`.
Captures use the unchanged published core 2.3.34 AAR (`a2af1e99…b73a3`) through
its public JNI inside the task-owned Android emulator `emulator-5610`
(API 34 arm64, SwiftShader GLES through ANGLE). Physical devices were not used.
Captured frames are review evidence only and never classification inputs.

Each checkpoint froze the SDK description, a generated prediction image and,
from v4 onward, the approximate mood before capture. Frozen files are hashed
into each `capture-result.json` and checked unchanged after capture. Outputs
live under `build/preset-corpus/` (not committed); review copies of every
screenshot, 10-second clip (synthetic 110 BPM bass/pads/noise audio) and
prediction image are in `~/Downloads/ProjectM-TV-checkpoints-2026-10-11/`.

## Checkpoints

| Preset | Checkpoint | Main lesson → general mathematics added |
|---|---|---|
| Zylot - Spiral (handover preset) | v7 480×270, v8 640×360 (unseen) | Filled gaps and concentric rings → RGBA8 decay orbit and floor, persistence sweep, bilinear spread, radius-locked colour, sweep front. v8 radial colour profile correlation 0.95–0.99 |
| Rovastar and Krash - Seas Of Tron (seed 2026101102) | v2, v3 640×360, v4 640×480 (unseen aspect) | Band compression, travelling ripples, motion-vector row, echo/gamma → per-pixel mesh-field structure, motion-vector element, legacy `bMotionVectorsOn` fix, composite prose, closed-form wave colour. v4 pink lines, ripples and vector row predicted before capture |
| Stahlregen & AdamFX + flexi + Geiss - Dragonfly Wings (seed 2026101103) | v1 480×270, v2 640×480 (unseen) | Black prediction versus a dark-red flowing scene → scalar palette maps, flat-field steady state, shader mechanism prose. v2 text predicted the dark-red background and orange/yellow features; the illustration had a flat-colour bug and cannot place advection veins |

Self-comparison JSON files (`self-comparison-*.json`) record frozen hashes,
agreements, misses and the general cause of each miss. No calibrated
appearance score is claimed.

## Committed increments

- `5fdc19a1` material-marker motion integration (independently reviewed)
- `105681ea`, `6a435f22` decay persistence, layer sweep, spread, radius-locked colour, sweep front, profile-qualified orbits
- `0214eef2`, `3b8d779e` per-pixel mesh field, motion vectors, composite prose, approximate mood, corpus runner, time expressions
- `146db806` scalar palette, flat-field state, mechanism prose, review fixes

Each increment passed the prepared full suite (latest 4166 tests + 92 subtests)
and an independent review whose findings were fixed before or in the next
increment.

## Whole-pack grouping

`tools/milk-analyzer/corpus_understanding.py` runs source-only export, SDK
summary and approximate mood for all 9,606 presets. Results and the band report
are written under `build/preset-corpus/corpus-understanding-9606-r2/`. The
approximate bands are editable, assumption-based preference groups with
explicit confidence and abstention; they are not calibrated moods. Strict
eligible bands remain separate and empty for these presets.
