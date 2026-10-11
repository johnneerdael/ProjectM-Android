# Exact local dependencies and artifact identities

## Keep these paths

Main worktree:
`/Users/jneerdael/Scripts/Projectm-TV/.worktrees/predictor-memory-repair`.
Its build environments, pinned native source and evidence remain operational.
Both venv Python executables resolve to
`/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14`.
Do not delete that interpreter or assume a copied venv is portable.

- `build/preset-lab-venv`: numpy,OpenCV,pytest+subtests; main prepared tests.
- `build/docs-venv`: MkDocs,Material,jsonschema; no numpy. SDK stdlib import works.
- `/Users/jneerdael/Scripts/source-analysis-evaluation/`: prepared library checkouts,
  python-env(SymPy/Z3), compiler/state/precision workers and research outputs.
- `/Users/jneerdael/.bun/bin/bun`: optionalFPTaylor JS runtime.
- `/opt/homebrew/opt/llvm@21`: Enzyme experiment, not required for every source export.
- AndroidSDK `/Users/jneerdael/Library/Android/sdk`: native emulator37.1.11 and
  installed ARM64 API34/default,API35tablet,API36TV images; build-tools/JDK forJNI.
- Installed SwiftShader native dylibs under
  `/Users/jneerdael/Library/Android/sdk/emulator/lib64/gles_angle/`.
- Original MilkDrop2:
  `/Users/jneerdael/Scripts/milkdrop2_v2.25c_OPEN_SOURCED_20130514_orig_code`.
  Also historical user paths`~/Scripts/milkdrop2`,`~/Scripts/MilkDrop3`,BeatDrop,
  projectm-eval; verify existence instead of recreating known code.
- Local authoring guide `/Users/jneerdael/Scripts/projectm-visualizer.org` and
  https://www.geisswerks.com/milkdrop/milkdrop_preset_authoring.html;
  shader math https://iquilezles.org/articles/.
- Audio reference folder `/Users/jneerdael/Desktop/audio`; presets/shaders don't
  imply artist/genre from filenames. Main synthetic capture audio is included.

Earlier preset-genre-analyzer, predictor-visual-loop and other historical worktrees
were migrated/removed. Do not resurrect them based on old conversation paths;
current prepared environment JSON and actual filesystem are authoritative.

## Published pinned artifact

`build/preset-corpus/published34/projectM-TV-core-2.3.34.aar`
SHA256 `a2af1e99f81e6130c77167c11460b0bc9a02306b5fac7fc1b0a1d8c1e33b73a3`.
ARM64 library SHA256
`b04caf83c2d4b89015a727899225ecba970a9b732afc7997760e584dcc367013`.
Classes.jarSHA256 `a4e3f33e655a784551d064b4a16ce9c43ced202bc24103892b1fc861c3d2ff92`.
Release commit984bfe19e408bed374647e4bdea8c053f0922a15. Earlier verification recorded
unchanged artifact equivalence through later releases; **latest public release
was not live reverified at final handover**. Do not claim this is latest without
checking publication/checksums. User requires the published patched core/AAR,
not an unpatched library masquerading as equivalent.

Source34 engine identity: upstream6f64807467e312034883a4389e6aa80a675458bc,
patchesSHA256a6e0298331988d9777607f2cb75ade4bb362f69787e865aaaf6578479267d0df.
Prepared production tree `build/preset-corpus/source34/production-engine`.
CPU archive `build/preset-corpus/source34/native-build/projectm/src/libprojectM/libprojectM-4.a`,
SHA2569dbe2f4d472eeea9809706104bea64133a07dda4be4f5da4531b0a7d899fb197.
Reader `build/preset-corpus/source34/adapters/milk-native-reader`,
SHA256754e4f4129db585cb4f7d5bee915d6bb24ac10ab25901ee7ef0832ce50744afc.
Source/adapters/GLSL translator hashes are packed with examples.

## Important build folders

- source34/adapters and production-engine: exact source reader/translator and native
  CPU source graph; auxiliary adapters are declared in source-environment.json.
- source-compile-manifest-2026-10-10/manifest.json: source-bound100 compile manifest.
- source-shape-flash-size-2000-2026-10-10/compatibility: fixed2000 saved requests.
- source-sample-offset-scenario.json: explicit input/texture dimensions; don't
  silently confuse its854×480 assumptions with a480×270 rendering context.
- static-review-presets: fixed100 exact source selection.
- source-layer-spacing100-2026-10-11: final100 source-only exports.
- spiral-layer-spacing-v6-final-2026-10-11: refined current JSON.
- preset-understanding-checkpoint-2026-10-11: frozen predictions/images/audio.
- native-macos-checkpoint-2026-10-11: compiledGLES engine/worker, actual clip/screens,
  whole source-tree pre/post hashes and capture sanity evidence.
- runtime34: unchanged published Android library/classes/DEX/clock adapter and
  isolatedavd-home; no current emulator/capture job is live.

Do not package/delete every historical build just to continue. Most artifacts are
read-only evidence, many old adapters support tests explicitly pinned to prior
releases; source-environment.json tells which remain required.
