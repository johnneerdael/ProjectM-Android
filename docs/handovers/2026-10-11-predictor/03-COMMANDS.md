# Reproducible continuation commands

Run from the existing worktree. Do not use the root docs branch.

```sh
cd /Users/jneerdael/Scripts/Projectm-TV/.worktrees/predictor-memory-repair
git status --short
git log -1 --oneline
```

## Verify exact prepared environments before tests

`source-environment.json` is copied from
`build/preset-corpus/source-components-qualification-env.json`; it declares all
optional solver/compiler/legacy-native adapter locations. Merge it with the process
environment. Do not rename HOME/CODEX_HOME. Simple pytest without these adapters
can skip/fail or does not establish the prepared suite.

```python
import json, os, subprocess
from pathlib import Path

env = os.environ.copy()
env.update(json.loads(Path('build/preset-corpus/source-components-qualification-env.json').read_text()))
env['PRESET_UNDERSTANDING_FRESH_EXPORT'] = str(Path(
 'build/preset-corpus/spiral-layer-spacing-v6-final-2026-10-11/results/Zylot - Spiral.json'
).resolve())
subprocess.run(['build/preset-lab-venv/bin/python','-m','pytest',
               'tools/milk-analyzer','-q','-rs'], env=env, check=True)
```

Pending module focused controls:
```sh
build/preset-lab-venv/bin/python -m pytest tools/milk-analyzer/test_source_material_marker_motion.py tools/milk-analyzer/test_source_parametric_wave.py tools/milk-analyzer/test_source_curve_projection.py tools/milk-analyzer/test_source_curve_feedback_relation.py -q
```

Fresh source-only export (choose a NEW output directory, freeze model files first):
```sh
build/preset-lab-venv/bin/python tools/milk-analyzer/effect_family_export.py 'core/src/main/assets/presets/Zylot - Spiral.milk' --reader build/preset-corpus/source34/adapters/milk-native-reader --output build/preset-corpus/NEW-NUMBERED-CHECKPOINT --compile-manifest build/preset-corpus/source-compile-manifest-2026-10-10/manifest.json --input-scenario build/preset-corpus/source-sample-offset-scenario.json --behaviour-context build/preset-corpus/spiral-layer-spacing-context-2026-10-11.json --symbolic-python /Users/jneerdael/Scripts/source-analysis-evaluation/python-env/bin/python --proof-python /Users/jneerdael/Scripts/source-analysis-evaluation/python-env/bin/python --phase-dependencies
```

SDK:
```sh
build/preset-lab-venv/bin/python tools/milk-analyzer/preset_understanding.py 'build/preset-corpus/NEW-NUMBERED-CHECKPOINT/results/Zylot - Spiral.json' --output build/NEW-NUMBERED-SUMMARY.json
build/docs-venv/bin/mkdocs build --strict --site-dir build/NEW-DOCS-CHECK
```

The committed compile manifest covers100 specific presets; don't claim whole9606
stage-selection evidence from it. Saved2000 compiler records are a separate subset.
Appearance schema applies to record.analysis.visual_description, not the47-field
source-feature schema. Verify every selected model hash and exact fact pointer/value.

## Native source-matched GLES comparison

Already-built worker:
`build/preset-corpus/native-macos-checkpoint-2026-10-11/native-build/native-checkpoint`.
It loads installed SwiftShader dylibs, the matching patched source engine, and the
frozen synthetic.f32. Freeze new description+generated illustration FIRST.

```sh
build/preset-corpus/native-macos-checkpoint-2026-10-11/native-build/native-checkpoint /Users/jneerdael/Library/Android/sdk/emulator/lib64/gles_angle 'core/src/main/assets/presets/Zylot - Spiral.milk' build/preset-corpus/preset-understanding-checkpoint-2026-10-11/synthetic.f32 build/preset-corpus/NEW-NATIVE-CHECKPOINT/spiral 300
```

Create output directory first. The binary writes RGB24 top-down, bandJSONL and
metadata; source/header/audio/context/worker/dylib hashes must accompany the result.
The CMakeLists/driver/source pin are in includednative evidence. No production source
changes. Use ffmpeg to mux declared WAV+raw RGB into10s clip; preserve original bytes.
This is macOS patched-source/GLES comparison, not Android AAR/JNI qualification.

## Recovery if the existing tree is unavailable

The incremental Git bundle has six prerequisite commits listed in state.json
and bundle-verification.txt, including43023889ec38cf1250f3bfcaaf079a840acbdf76.
The existing root/local Git object store has all six; bundle verification passes.
A new clone must fetch the prerequisite history before importing it.
```sh
git bundle verify /PATH/TO/EXTRACTED/predictor-history.bundle
git fetch /PATH/TO/EXTRACTED/predictor-history.bundle feat/predictor-static-output-bounds:handover/predictor
```

Existing worktree already contains the dirty modifications. **Do not apply patch
again there.** For a clean8c0bdfe6 recovery checkout only:
```sh
git apply --check /PATH/TO/EXTRACTED/tracked-pending.patch
git apply /PATH/TO/EXTRACTED/tracked-pending.patch
```
Then restore the two new material-marker files from pending-files. The unrelated
fixture is separately preserved; don't overwrite a newer user copy. Source-snapshot
is a portable inspection backup, not a blind overwrite instruction. No venv or
entire historical native build is packed; retain dependencies listed next.
