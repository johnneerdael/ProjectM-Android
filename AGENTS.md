# ProjectM TV contributor instructions

## Pull requests and release notes

Each successfully tested merge to `main` publishes a versioned APK and one Native core AAR, then updates Milkbeat through the canonical core alias. Use a feature branch and PR for changes. Android APK CI retains full Git history and tags with `filter: blob:none`; current source and historical version metadata are fetched on demand rather than downloading every historical evidence blob.

- Include a substantive `## Release notes` section in every PR body. Follow `.github/pull_request_template.md`.
- Write for people using the app: describe the changed behavior, its effect, and relevant limits. Include a concrete trigger or before/after example when useful.
- State only changes supported by the final diff and verified evidence. Avoid invented performance figures, broad crash-free claims, or promises beyond the implementation.
- Keep release notes aligned with the final PR scope. Rewrite them when implementation changes.
- Use an `Internal` subsection for documentation, tests, or CI-only work with no user-visible effect, and explain the actual change. A bare “No user-visible changes” is insufficient.
- Put test commands/results in `## Validation`, outside release notes. Omit badges, agent transcripts, implementation process, and manual install instructions from the release-notes section.
- Let CI append the current Downloader code, APK/core AAR links, checksums and comparison link. Update the canonical install blockquote in `README.md` when the Downloader code changes.
- Preserve upstream attribution when describing backported fixes.
- Do not bump versions in routine PRs. The base version/code/commit in `app/build.gradle` define the automatic release sequence. Change them together only for a planned new release line; follow `docs/RELEASING.md`.

For release tooling changes, run `python3 -m unittest discover -s .github/scripts/tests -v`. Review factual accuracy of the PR release notes: CI validates their presence and placeholders, not the truth of English prose.

## Maintaining this file

Keep the repository-specific sections below current whenever a task changes architecture, commands, dependencies, documentation or constraints, in the same worktree and PR as that task. Record only facts backed by repository files or observed command results; mark unverified commands and unresolved facts explicitly, and link to existing docs instead of duplicating them. Do not import assumptions from other repositories (including Milkbeat).

Resolution selector maintenance (2026-10-06): `resolution_mode` is the new opt-in app preference. Keep legacy `setMode` Auto-normalizing for Milkbeat; use `setResolutionMode` for explicit selections. Validate FPS stability, memory relief/recovery, pressure-cleanup signaling inside the height callback, display bounds and separate Auto history. Advanced is a framework ScrollView with D-pad focus scrolling; keep all rows within the overscan-safe bounds. Run the isolated resolution/trails setup cases with `./gradlew :app:assembleDebug :app:assembleDebugAndroidTest -PsetupScreenshotTest` then `adb -s SERIAL shell am instrument --user USER -w -e setup_case resolution nl.neerdael.projectmtv.setuptest.test/com.example.projectm.visualizer.MusicCategoryInstrumentation` (or `native_trails`). Optional `setup_case resolution_recording` records the actual menu at 4K with synthetic unsigned mono PCM; wait for `resolution-recording.ready` in the test app external cache, start the recorder, then create `resolution-recording.go`. Requires a 4K display and ample RAM; verified on the task-owned API36 TV emulator with 8 GB guest RAM and Apple M4 Pro/Metal host GPU 2026-10-06. Verified menu/trails cases on the task-owned API36 TV emulator 2026-10-06; 101 JVM tests and strict MkDocs pass.

CI/review workflow discovery: 2026-10-05 against `main` at `910e837b`; JDK 21.0.11, resolved JUnit 4.13.2/Hamcrest 1.3, release JVM tests, release APK/Native AAR and strict MkDocs build verified. Last full discovery: 2026-10-04, against `main` at `4fc66208` (projectM patch series 0001–0029). "Verified" below means the command was run with the stated result on that date; everything else is described from the source files and CI configuration.

## Repository overview

ProjectM TV is a music visualizer for Android TV, powered by **ProjectM TV Engine**, the maintained projectM fork based on upstream 4.1.7 plus this repository's patch series. It renders MilkDrop presets that react to the audio another app plays on the same TV; it is not a music player. It bundles 9,606 *Cream of the Crop* presets. GitHub: `johnneerdael/ProjectM-TV` (verified with `gh repo view`; a checkout's `origin` URL may still use the former name `projectm-android-tv`, which redirects).

| | `:app` | `:core` |
|---|---|---|
| Type | Android application (APK) | Android library (AAR), the engine |
| Namespace / Java package | `com.example.projectm.visualizer` (legacy package; the installed ID differs) | `nl.neerdael.projectm.core` |
| Application ID | `nl.neerdael.projectmtv` (since 1.9.7); suffixes `.profile`, `.presettest`, `.setuptest` for side-by-side builds | – |
| Languages | Java (source/target 1.8), XML views | Java + C++17 (JNI), CMake; builds `libprojectmtv.so` |
| SDK levels | compileSdk 34, targetSdk 34, minSdk 21 | compileSdk 34, minSdk 21; ABIs `armeabi-v7a`, `arm64-v8a` |
| Dependencies | `project(':core')`; test: JUnit 4.13.2. No AndroidX, Kotlin or Compose (framework APIs only, to keep the APK small) | test: JUnit 4.13.2; projectM built from source |

- **Devices:** Android TV only. The manifest requires `android.software.leanback`, OpenGL ES 3.0 and audio output; touchscreen, gamepad and microphone are optional. README: Android 5.0+ (API 21), at least 2 GB RAM highly recommended, no touch/phone support.
- **Build types (no product flavors):** `debug`; `release` (R8 minify + resource shrinking, release key when `SIGNING_KEYSTORE_PATH` is set, otherwise the local debug key); `profile` (`initWith release`, debug key, `.profile` suffix, `profileable` via `app/src/profile/AndroidManifest.xml`). Gradle properties `-PpresetLabDeviceTest` / `-PsetupScreenshotTest` give the debug build the `.presettest` / `.setuptest` suffix and a distinct app name.
- **Entry points:** `ProjectMApplication` (one-time preference migrations, `ProjectMCore.init`); `MainActivity` (single `singleTask` landscape activity: UI, remote keys, audio capture, settings panels); `TrackListenerService` (notification listener used only for media sessions); `Updater` + `UpdateFileProvider` (opt-in GitHub auto-update). Engine: `ProjectMCore`, `ProjectMJNI`, `VisualizerView`, `VisualizerRenderer`, `QualityController`, `DeviceProfile`, `DisplayInfo`; native `core/src/main/cpp/native-lib.cpp` plus `snapshot_fade.cpp` and `preset_prewarm.cpp`.
- **projectM relationship:** submodule `third_party/projectm` tracks upstream `https://github.com/projectM-visualizer/projectm.git`, pinned at tag `v4.1.7` (commit `e0b0a967`). All engine changes are the ordered patch series `tools/projectm-patches/NNNN-*.patch` (0001–0049;0048 consumes evaluated built-in wave mode/dots/thickness/additive flags and rebuilds mode math,0049 consumes evaluated legacy gamma/echo/filter controls;0045 owns repeat/linear main-shape sampling,0046 separates blur bounds with a coherent [0,1] fallback for unsupported float32 normalization,0047 preserves signed negative motion zoom when zoom exponent is exactly1;0044 preserves float32 shader literal round-trips and rejects nonfinite literals;0043 preserves authored shape/wave recurrence and explicit per-vertex shape inputs;0038 supplies the legacy diffusion/fallback,0039 is the historical capped-policy opt-out,0040 preserves implicit globals,0041 preserves blur framebuffer bindings,0042 adds instance-owned authored feedback/native trail detail), applied at CMake configure time by `core/src/main/cpp/CMakeLists.txt` and linked statically into `libprojectmtv.so`. The personal fork `johnneerdael/projectm` is not referenced by the build; it is used for upstream PRs.
- **App/core boundary and Milkbeat:** `:app` holds UI, audio capture, track titles and the updater; `:core` holds the engine, JNI, presets, textures and preset indexes. [Milkbeat](https://github.com/johnneerdael/Milkbeat) consumes the released core AAR: CI publishes the single Native `projectM-TV-core-<version>.aar` and canonical alias, then dispatches `projectm-core-release` to Milkbeat (see *Generated artifacts*). Milkbeat consumes canonical artifact names and uses QualityController; managed hosts acknowledge context/configuration generations and publish a coherent size/trails/transition tuple after live RAM review. Retired fixed-resolution and static-RAM methods normalize to Auto.
- **Build tasks:** `./gradlew assembleRelease` (APK at `app/build/outputs/apk/release/app-release.apk` and AAR at `core/build/outputs/aar/core-release.aar`), `./gradlew :core:assembleRelease`, `./gradlew assembleDebug`, `./gradlew assembleProfile`.
- **Single Native core:** `:core` and the APK use Native rendering; canonical `projectM-TV-core[-<version>].aar` names contain Native bytes. The separate capped/core-native artifacts are retired for new releases; preserve historical releases. Deprecated `-PprojectmCoreRenderingPolicy=native` remains accepted; `capped` is rejected. QualityController defaults to Auto up to the physical panel and uses live FPS/memory headroom. Its fixed-mode/static-RAM compatibility methods normalize to Auto. The additive resolution selector leaves legacy `setMode` Auto-normalizing for existing consumers. JNI defaults Standard trails; settings are additive (`setNativeTrails`, `getNativeTrailsStatus`). The underlying projectM C API retains explicit-off compatibility controls. See `docs/RELEASING.md`.

The focused `tools/milk-analyzer` subset imports PR #25's selector-domain proof and
models the native implicit-global policy. It also includes the separate beta activity
scorer using the published standard core AAR through JNI, and a source-bound collection
exporter/verifier. Its direct-delta beta model is fitted on eight historical user
judgments transferred onto native features; archived producer and derived-scoring
identities are kept separate. Optional offline refitting uses
`tools/milk-analyzer/requirements-calibration.txt`. These execution-based predictions are not independent source-only
visual forecasts. Build its source adapters against a hash-
identified host engine before `python -m pytest tools/milk-analyzer -q`; Preset Lab CI
performs this setup. Its results are source diagnostics, not visual certification.

Analyzer migration checkpoint (2026-10-07): source CPU adapters now support 4.2
split composite buffers/native Point waveform data and the patched stbi decoder,
while retaining historical 4.1.7 paths. New decoder manifests distinguish STBI
implementation identity from SOIL. Prepare the exact release snapshot before
adapter builds; bounded constants/input controls do not certify preset fidelity
or authorize relabelling historical engine guards. Revised experimental target:
20 rounds × 3 random presets × 30 frames, 60 consecutive scores of 100. Predictor failures gate
the next round. See `tools/milk-analyzer/README.md`; no app/AAR behavior changes
are made by this adapter checkpoint.

The experimental source forecaster is `tools/milk-analyzer/forecast.py`; it keeps
source CPU equation execution separate from published-AAR visual references.
Its explicit 2.3.4/2.3.5/2.3.7 cold-thread policies check the 41/42/43-patch engine identities and
equation seed `0x4141f00d`. The named GLES quad-line profile models the patched
hard-edge drawing path at/below the JNI 1024x768 reference area; larger sizes and
antialiasing remain unverified. Prepare pinned adapters before its tests. Do not
relabel historical capped2.3.4 evidence as canonical Native2.3.5 results. Patch0042
also caches shader random values for repeated detail passes within one frame.
Keep production source, lab-instrumented CPU archive and publishedAAR identities
distinct; the renderer reference always uses the checksum-verified publishedAAR.
Keep PCM cadence separate from equation FPS: the declared 30Hz cold JNI host
uses equation FPS35 through image30, then30. Point-grid precision is an explicit
renderer input; the verified Apple emulator grid must not be generalized to other
GPUs. Patch0043 preserves authored geometry in Native trails, but the source
forecaster still rejects its unmodeled high-resolution/detail path.
Verified41/42/43-patch source identities default to the patched main-sampler
binding order (unqualified main on unit0); unknown identities retain legacy order.
Keep the requested domain/hash unchanged and record the effective policy in
provenance. Explicit legacy policy is for labeled historical/diagnostic controls.
The43/44-patch shape sampler compatibility policy models the published2.3.8/2.3.10 state
leak: warp clears sampler0; first main-textured draw inherits only delayed blur
sampler0, otherwise uses repeat/nearest. Later draws after
unbinding use repeat/nearest attachment settings. Keep per-instance draw order,
named-image modes and actual blur allocation distinct. Unknown engine identities
retain the historical model; update the policy after a native repair.
Do not claim the entire imported analyzer suite passes from focused controls alone.
See the analyzer README and `docs/plans/2026-10-05-predictor-visual-loop.md`.

## Codebase navigation and knowledge tools

The user's current source-description priority is structured approximate baseline
appearance and audio→element-control relationships for mood/user-preference
matching and eventual reconstruction, not complete47-field replacement.
`source_appearance.py` feeds `analysis.visual_description`; see
`tools/milk-analyzer/SOURCE_APPEARANCE.md` and its export-contract schema.
Preserve numeric category IDs, units, nulls, causal live RGB/control slices,
complete32slot main/shape Q reload semantics, resource identities and explicit
unresolved context. Source control gains are not screen response strengths;
colourful/fractal candidates do not grant flash permission or calibrated confidence.
`source_temporal.py` supplies nominal affine shader-time RGB oscillator timing
without execution. Keep scalar casts in sink/phase graphs, per-channel unknowns,
the source31 shader clock's10000-second wrap, and masks/storage/frame-sampling
qualifications. These are not measured visible flash or screen-speed values.
`source_triggers.py` adds direct-band comparison sites to audio routes. Preserve
threshold units/expressions, reversed predicates, null whole-control levels for
nested switches and null frequency without audio history. Site presence is not
certification of a visible flash; empty results do not prove absence.
`source_geometry.py` adds nominal custom-shape footprints. Preserve NDC radius,
aspectY coefficients, native side conversion/clamp, configured draw counts and
null visible/union coverage. Static EEL frame inputs reload config/audio/Q/T as
the target does; writable persistent custom locals/shared registers remain
previous-state inputs. Init captures use namespaced inputs; EELvol is local,
packed shader volume remains aggregate. Branch assignments use native `_if`
environment merging. None of these facts establishes image or mood accuracy.
`source_motion.py` exports named constant/linear/sinusoidal source control curves.
Its paired shape-centre trajectory joins known axes into drift or common-rate
harmonic paths. Preserve phase offsets, signed rates and exact source degeneracy
conditions; use independent-axis speed bounds for unmatched rates. Source circles
are not physical-screen circle claims, and visible speed remains unresolved.
Keep source-time units, ranges and signed coefficients separate from visible
motion. Constant mesh controls apply each feedback step; zero derivative is not
zero image speed. Audio/state/nonlinear curves remain unknown without support.
`source_composition.py` adds conditional logical feedback/display flow, configured
drawing order and typed source sampler reads. Keep detail/blur ages/render context
unresolved without inputs; retain stale-composite feedback from possible warp
discard. Typed constant zero masks must prune data dependencies consistently while
execution/domain obligations stay separate. This graph is not scene completeness.
`source_material.py` reuses the qualified primitive colour-modulo helper for shape
vertex RGBA, gradient/border and int-style blending/texture flags.
`shape_fill_contribution` integrates known
untextured centre/perimeter RGBA with barycentric second moments; preserve
colour/alpha covariance and per-channel unknowns. Its per-aspect area coefficients
are nominal unclipped injection, not displayed prominence or overlap union.
`source_geometry.shape_audio_area_response` reuses constant-affine basis analysis
for the six current EEL bands. Export nominal squared-radius area and gradient,
including symmetric cross terms; preserve finite intermediates/radius conditions
and material factors independently. Init snapshots, state/time, nonlinear radii,
unknown side counts and nonfinite coefficients must not become known audio area.
Keep raw values,
per-channel unknowns, raw border-alpha enable gating, source texture requests and
unverified fallback/binding status. Perimeter/border/texture audio routes must not
invent visibility or final palette verification; prune known unused style controls.
`source_feedback.py` exports nominal warp RGB transfer matrices/bias and per-site
conditional colour bounds. Keep different sample sites separate when deriving
RGB intervals and infinity-norm perturbation decay. Contraction needs declared
nonexpansive image-independent sampling and matching external inputs; a failed
sufficient bound is not actual instability. Real storage/feedback stability stays
unknown. Absolute coefficient norms hold coordinates fixed. Fixed decay and custom returned
RGB stay distinct. Ideal positive scalar half-life is not actual trail persistence;
retain coordinate-feedback, storage/drawing/detail/discard and domain conditions.
Unknown/nonlinear/blur transfers cannot become low-reactivity or Chill evidence.
Warp `_vDiffuse` is the source-bound vec4 of capped float32 main decay in RGB
and one in alpha. Dynamic/nonfinite decay remains null; this is not an observed
runtime binding and must not leak into composite or multiply unused custom RGB.
`source_sampling.py` exports nominal constant-affine 2D sample matrices over
warp mesh/original UV columns plus spatially uniform offset programs, audio
routes and time curves. Keep typed quantization, image/interpolated-colour
offsets, dynamic scales and mixed/singular inverses unresolved. Local inverse
feature area is not screen coverage, copy count or visible motion.
`source_polar.py` adds conditional per-sample separable angle/depth parameters
with proved matching native or authored affine spatial anchors. Retain target
log(abs) and domain guards, nominal unrounded angular periods, shared-metric
checks and unresolved dynamic scales/image offsets. Radial derivatives describe
source sampling density, not visible speed or guaranteed tunnel/symmetry. Mixed
polar maps retain their explicit angle/depth-to-texture matrix and offset programs.
Axis-permutation radius proof must preserve the angle's ordered plane. Literal
matrix folding uses existing typed matrix rules and rejects every input/resource/
effect/loop even when native unbound defaults exist; vector/matrix order matters.
`source_forms.py` recognizes live periodic radial glow generators (familycode9)
and keeps distinct generator formulas in element.procedural_forms; identical
formulas may deduplicate, so records are not usage/layer counts. Require typed
native shader varying bases; shader globals named x/y/rad/ang are ordinary uniforms. Local cell core
radius/area is not visible coverage. Reject known rank<2, nonspatial, dead/alpha-only
and fully saturated cases; retain nonlinear mapping, reciprocal and later-mask
conditions. These are fields in a mapping plane, not independent particle IDs.
`source_advection.py` exports direct per-sample RGBA-to-UV matrices and a
location-held-fixed row-sum norm, sharing _affine_basis_map with source_sampling.
Conditional[0,1]sample boxes are premises, not certified texture/blur ranges.
Retain nested-coordinate dependencies, unknown full sensitivity/screen motion,
64sample/4096node budgets and source-only binding status. Dot constantweights
can be expanded; shader x/y globals are uniform offsets, not EEL coordinates.
`source_uniforms.py` derives source31 blur decode _c5/_c6 components only when
all6main-frame min/max fields are supported constants. Reuse blur.native_ranges
CORE_2315_BLUR; retain coherent fallback, float32 packing and native-vs-MD2
close-gap distinction. Never default-fill a dynamic/missing triplet. Injection
uses known_uniform_components and respects local shadows; observed binding false.
`source_colour_mix.py` exports3x4RGB/RGBA sample matrices, source UV gradients
and uniform offsets via shared affine/substitution code. Norms hold locations
fixed; signed main/blur mixture labels include all participating sample weights.
No sharpness, final palette, whole-loop gain or mood certainty follows. Warp
vertex substitution stays warp-only, retaining unknown RGB and known alpha.
Source native roam inputs (_c8–_c11) use typed symbolic uniform components and
private :native-render-time-f32, before shader-time wrapping. Preserve numeric
binding precedence/local shadows and clock_kinds_rgb; only actual wrapped-clock
reads get10000-second wrap metadata. Formula rates are nominal, not CPU/GPU-bit
identity, visible flash frequency or calibrated mood/colour confidence.
`source_hue.py` emits native composite hue recipes (generatorcode10, separate
from familycodes) only for consumed _vDiffuseRGB. Preserve per-corner max
normalization, unknown preset random phases, vertex-position blend followed by
triangle interpolation, red-only usage and alpha/dead/warp exclusions. Nominal
[2/3,1]input bounds are not a final palette or exact per-fragment bilinear claim.
`source_waveform.py` exports source built-in wave recipes using target checked
truncation/signedmod16 and evaluated nonzero flags. Share admission with
source_composition: wave_a=0 cannot exclude mode3 or dynamicmode because native
mode3replacesalpha with treble²/reference scaling. Keep input channels distinct
from stems, waveform data/context/visibility unknown and extended mode9 secondary
storage behaviour open. Nonfinite narrowing must preserve other descriptor data.
Source appearance literal folding supports typed single-lane projections of
constructors/arithmetic/nested swizzles; preserve integer conversion/channel
order, input/sample unknowns, nonfinite/depth guards and discarded-lane demand.
This improves raw source colour extraction, not final palette certification.
`source_colour_processing.py` exports ordered perRGB known tone suffixes and
constant/sample/source-expression bases. Keep translator abs/domain power lowering,
channel projections and unknown resources; alpha-only code is not RGB processing.
Suffix recognition does not grant a complete palette/material or appearance claim.

Canonical source31 corpus admission requires the exact qualified host CPU
archive pinned separately as `preset_corpus.CORE_2331_SOURCE_ARCHIVE_SHA256`;
a well-formed self-reported hash is insufficient. See the corpus export guide
and `docs/superpowers/evidence/pr67-review-fixes/README.md`. Static shader
mechanisms follow the typed native RGB sink; discarded fourth lanes cannot
preserve visible families or upstream contribution, while cross-lane/effect
dependencies retain their original qualifications.

`SourcePipeline` has opt-in `shader_lowering_policy='cached-program-v1'`,
forwarded from the forecast domain; default is `per-frame-v1`. Reuse only static
lowered programs with complete tree/context/type identity, one entry per stage.
Do not retain runtime tensors or loop state. Preserve update-specific sample
history and per-invocation shared sampler-policy aliases before grid domain
checks and callbacks. See `docs/superpowers/evidence/predictor-program-reuse/README.md`.
Mixed short-forecast timings do not justify automatic corpus enablement.

Experimental uniform final-expression reduction lives in
`tools/milk-analyzer/uniform_source_descriptors.py` and `uniform_descriptors.py`.
It is opt-in and not an automatic corpus route. Require selected final-stage,
binding/storage and later-blit premises separately; reject unsupported spatial,
texture, loop and effect dependencies. The current descriptor shortcut requires
qualified OpenCV5.0.0 optimized ARM64/NEON and retains optical-flow nulls. See
`docs/superpowers/evidence/predictor-uniform-descriptors/README.md` for controls
and the fixed100 zero-candidate coverage limit. Do not extrapolate synthetic
kernel speedups to the whole pack.

- No `.codegraph/` or `graphify-out/` exists at the repository root (checked 2026-10-04). Use `git grep`/`rg`; do not assume a code graph.
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) §5 (threading rules, transitions, resolution, frame pacing, threads, overlay UI, device tiers). Its title says v1.9 and §1–4 and §6–8 are historical analysis; verify against the code. Design specs, plans and evidence for engine work are in `docs/superpowers/{specs,plans,evidence}`.
- projectM sources: `third_party/projectm` shows patched code only after a CMake configure or a manual apply; the committed source of truth is `tools/projectm-patches/`. Search both the submodule and the patches.
- Logs for tracing behavior: native tag `projectM-Native` (`LOAD`, `PREWARM`, `TRANSITION`, `OUTPUT` lines per switch); `VisualizerRenderer` logs `STATS fps=… surface=… audio=…` every 5 s.
- Committed generated data indexes (not code indexes): `core/src/main/assets/presets.idx` (regenerate with `tools/gen-preset-index.py` whenever presets or textures change; CI enforces `--check`) and the collection bundle in `core/src/main/assets/preset-genres/` (current beta schema2 produced/verified with `tools/milk-analyzer/beta_export.py`;
  legacy schema1 Preset Lab imports are historical).

For published-JNI predictor controls, use `core_backend.jni_pcm_inputs` before
CPU audio evaluation and `validate_jni_audio_context` before native capture.
Preserve raw transport and effective PCM hashes separately: the runner rounds
float32 samples to unsigned bytes; raw float FFT reports are a different input.
A shared input mismatch invalidates the comparison; stop remaining captures,
preserve artifacts, repair the contract and refreeze before resuming.

## Design and user experience

Follow the project's established design system and platform conventions. Reuse existing theme tokens and components. Preserve accessibility, keyboard/focus behavior, responsiveness, and supported input methods. Avoid introducing decorative styles or changing appearance incidentally during a refactor.

- **Toolkit:** framework Views and XML only (no AndroidX, Leanback library, Material or Compose). One layout, `app/src/main/res/layout/activity_main.xml`. Theme `Theme.Leanback` in `res/values/themes.xml` (parent `@android:style/Theme.Black.NoTitleBar.Fullscreen`); text styles `Overlay.*` in `res/values/styles.xml`; tokens in `res/values/colors.xml` and `dimens.xml`; drawables in `res/drawable*`. Reusable views: `OptionRow` (focusable settings row), `AudioMeterView`, `TrackCorner`. Dialogs use `android.R.style.Theme_DeviceDefault_Dialog_Alert`.
- **Remote/D-pad contract** (`MainActivity.onKeyDown`/`dispatchKeyEvent`; documented in the README *Remote control* table and `docs/user-guide/controls.md`; keep all three in sync):
  - No panel: Right/Next/Fast forward = random preset (hard cut); Left/Previous/Rewind = previous preset; Up/Down/Info = show the track again; Center/Enter/Menu = open the panel; Back exits.
  - Panel open: Up/Down move focus between rows, Left/Right change a value, Center cycles or runs an action; Back closes (from *Advanced* or *Track display* it returns to the main panel); Menu closes; it hides after 10 s without input, and every key event restarts that timer.
- **Layout:** landscape, fullscreen, immersive sticky. The GL surface renders at its own size (`SurfaceHolder.setFixedSize`) and is scaled by the display; the overlay UI uses the UI resolution.
- **Accessibility:** no documented requirements and no TalkBack verification found; the layout has only three `contentDescription` attributes. Keep every new control reachable by D-pad focus and give icon-only controls a `contentDescription`.
- **Visual references:** user-guide setup screenshots (`docs/user-guide/images/setup/`) come from the `-PsetupScreenshotTest` build on an Ugoos AM6. Rendering changes need before/after captures (PR template).

## Use existing platform and dependency APIs

Before implementing a component, parser, formatter, scheduler, transport, or similar utility:

1. Check existing project code for a suitable implementation.
2. Check the declared and resolved dependencies for a supported API.
3. Verify the API and recommended usage against the version in use and official documentation.
4. Implement a custom alternative only when the existing options are absent or unsuitable, and record the reason in the PR.

Prefer configuration, composition, or a small wrapper to copied library source or overlapping dependencies. Use maintained implementations for security-sensitive primitives.

| Need | Existing API / implementation | Version truth | Constraints |
|---|---|---|---|
| Audio input | `android.media.audiofx.Visualizer` on the player's session (`PlayerSessionFinder`), on the `AudioCapture` `HandlerThread` → `ProjectMJNI.addWaveform` | framework, minSdk 21 | 8-bit mono; needs `RECORD_AUDIO`; no microphone use |
| Playing track | `MediaSessionManager` via `TrackListenerService` / `TrackWatcher` | framework | needs notification access; no notification content is read |
| Rendering | `GLSurfaceView` + GLES 3.0 + projectM C API via JNI | `third_party/projectm` tag + `tools/projectm-patches/` | projectM handle only on the GL thread |
| Frame pacing | `Choreographer` in `VisualizerView` | framework | |
| Settings | `SharedPreferences` file `projectm_settings` | framework | see *Dependencies, state, and lifecycle* |
| Auto-update | `HttpURLConnection` + `Updater` + custom `UpdateFileProvider` (no AndroidX `FileProvider`) | framework | the app's only network use; off by default |
| Engine fixes | new patch in `tools/projectm-patches/` | patch series | never edit committed submodule files |
| Preset analysis | `tools/preset-lab` (numpy, opencv-python-headless) | `tools/preset-lab/pyproject.toml`, `requirements.lock` | offline only; does not change the Android renderer |
| Docs site | MkDocs | `docs/site-requirements.txt` (`mkdocs==1.6.1`) | |
| Build toolchain | AGP 8.12.0, Gradle 8.14.2, NDK 27.3.13750724, CMake 3.22.1 | `build.gradle`, `gradle/wrapper/gradle-wrapper.properties`, `app/build.gradle`, `core/build.gradle` | no version catalog |

Adding AndroidX or another runtime dependency departs from the documented small-APK policy (`app/build.gradle`) and affects F-Droid reproducibility; justify it in the PR.

## Performance and resource use

Avoid blocking work on latency-sensitive threads, unnecessary polling, duplicate requests, unbounded concurrency, and background work that outlives its owner. Honor existing cache, cancellation, visibility, lifecycle, and resource-release contracts. Back performance claims with measurements and state what was not measured.

- **Threads** ([ARCHITECTURE §5 *Threads*](docs/ARCHITECTURE.md)): GL thread (`THREAD_PRIORITY_DISPLAY`) owns the projectM handle (create, render, load, settings) and output measurement; `AudioCapture` HandlerThread (`THREAD_PRIORITY_AUDIO`); a native worker for preset indexing and prefetch; a background shader-compile `std::thread` started from the GL thread (`preset_prewarm`); the UI polls status every 500 ms. Other entry points only write atomics or mutex-protected buffers; keep it that way.
- **Visibility and cleanup:** `MainActivity.onPause` stops the track watcher, UI refresh, updater and audio, then calls `visualizerView.onPause()`; `onResume` restarts them and re-checks notification access. `onDestroy` releases projectM on the GL thread (`queueEvent(renderer::release)`); after context loss the next `onSurfaceCreated` cleans up.
- **Frame pacing/quality:** half-refresh-rate pacing uses Choreographer. QualityController defaults to Auto up to the detected panel, with FPS hysteresis/CPU-bound probe checks and a live ActivityManager memory budget initialized from application context in ProjectMCore.init. Standard is the Native trails default; Medium/High add the same passes with different gain. Advanced › Resolution uses additive `resolutionModes`, `validResolutionMode` and `setResolutionMode` for Auto/fixed/Native; fixed modes bypass FPS adaptation/slow-preset skipping but retain live memory relief/recovery. `resolution_mode` defaults to0 and is separate from retired `render_height`. Mode changes require a matching completed-frame height and no pending allocation before taking resident credit; reduced modes and fixed/Native recovery resizes remain pending until the replacement frame. A positive FPS sample acknowledges its received height before memory review can request another size. Capture the confirmed resident allocation before editing height: growth reviews the delta, confirmed non-growth waits for the new rendered tuple before memory sampling, and startup/recreated/pending allocations receive no resident credit. No static-RAM control remains. Use `QualityController.setRenderAllocationSettings(trails, transitionSeconds)` to review the final tuple atomically. The controller captures the pre-edit allocation before height callbacks. After renewing the FPS generation, use `revalidateForAllocationChange()`: confirmed reductions defer memory sampling until the new tuple renders and releases old textures, while net growth and pending allocations require a full review. Managed clients publish dimensions/trails/transition as one generation-tagged rendering configuration; GL holds allocation settings until surface-size acknowledgement. Use `revalidateForResume` for preserved/context-recreated resumes, reject stale generations, and base FPS on completed frames tagged with context/size. When an applied size change has `wasLastChangeForMemoryPressure()`, call the existing native pressure hook to flush pooled textures and pause prewarming. Do not claim a universal music-process survival guarantee from heuristic headroom.
- **No measured universal frame-time or memory bound is defined. Automatic memory uses documented conservative footprint/reserve estimates; see `docs/superpowers/specs/2026-10-05-native-trails.md`.** Compare before/after on the same TV, preset, render height and audio (PR template).
- **Measurement tools:** profile build + simpleperf ([docs/PROFILING.md](docs/PROFILING.md)); pin a preset with `adb shell setprop debug.projectmtv.preset '<name prefix>'` and clear it afterwards (`debug.projectmtv.update_from` also exists); `tools/tv-diagnostics.sh <tv-ip>:5555 --no-install --duration 180` ([docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md); profile builds require `--package nl.neerdael.projectmtv.profile` with a matching `--apk` or `--no-install`; build/`--release` modes reject alternate package IDs before connecting); Record actual render sizes; use Advanced › Resolution for fixed/Native tests and compare the same preset, audio and trails. Memory relief and automatic blend scaling can still reduce actual size, so confirm STATS/Diagnostics. Preset Lab provides offline rendering comparisons (desktop timings do not establish TV performance).
- **Documented device coverage:** NVIDIA SHIELD TV 2019 (`sif`, 2 GB, 32-bit) and SHIELD TV Pro 2019 (`mdarcy`, 3 GB), Android 11; Ugoos AM6 (Amlogic S922X, Mali-G52 MP6, Android 9). No emulator configuration is committed.
- **The notification listener restarts the app after `am force-stop`** (within about a second, verified on the AM6, Android 9, and the AM9 Pro, Android 14): a stop/start is warm, and the process reads `projectm_settings` at that restart. A process that reads the file mid-write saves its migration flags over it. Resolve `am get-current-user` once; use that numeric ID for settings/listener commands, permission grants, installation and `am force-stop`/`am start`. Filter `ps -A -o UID,PID,NAME` by exact process name and `UID / 100000` for that user; `pidof` includes other users. Failed/malformed queries must not mean "no process". Write `/data/user/<userId>/<package>/shared_prefs/projectm_settings.xml`, not user 0's `/data/data` alias. Disallow the listener only if that user enabled it, restore the same user's access, and check `surface=` in its STATS lines ([docs/PROFILING.md](docs/PROFILING.md)); `tv-diagnostics.sh` uses this scope for its cold start and records the user. Command support was checked in Android 9/14 sources; older releases remain unverified.
- **Diagnostics signing conflicts:** `--allow-uninstall` attempts removal only for the captured Android user. Before removing data, inspect `pm list users` and exact package results from `pm list packages --user <userId>` for every other user, including stopped users; refuse if another user has the package or a query fails/is malformed. Shared or preinstalled package code can retain the incompatible signing key. A retained conflict fails explicitly after the scoped retry; never broaden to all-user uninstall. Use `--no-install` or a matching-key APK instead ([docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md)).
- **Measured lessons (ARCHITECTURE §5):** listing ~10k assets took 8.4 s and blocked UI inflation → the worker reads `presets.idx`; GL linking at switches froze the picture 0.5–1.9 s → background prewarm and program caches; tile-based GPUs paid for render-target loads → patches 0009–0016.

## Dependencies, state, and lifecycle

Follow the existing dependency injection and ownership model. Prefer explicit dependencies and testable boundaries. Preserve instance identity, initialization timing, lifecycle, cancellation, and cleanup when refactoring. Keep migrations focused on the task and avoid creating duplicate services, caches, clients, or background workers.

- **No DI framework.** `MainActivity` constructs its collaborators directly (`TrackWatcher`, `QualityController`, the `AudioCapture` handler thread). `Updater` is a process-wide singleton (`Updater.get`, own `Updater` background thread; the activity attaches/detaches its listener). The engine is a process-wide native singleton behind static `ProjectMJNI` methods.
- **Initialization:** `ProjectMCore.init(context)` once from `Application.onCreate` (safe to repeat); it keeps the application `AssetManager` for the process lifetime and starts native preset indexing and the one-time texture copy before the first preset loads.
- **Persistence:** `SharedPreferences` `projectm_settings` (`MainActivity`, `ProjectMApplication`); `files/skipped_presets.txt` (skip list, `ProjectMCore.skipListFile`); `files/textures/` (texture copy). `android:allowBackup="true"`. There is no schema version: one-time migrations in `ProjectMApplication` are guarded by boolean keys (`skip_list_reset_1_9`, `frame_rate_reset_30`); add a new key for a new migration rather than reusing one.
- **Settings flow:** Java writes settings through `ProjectMJNI` setters; native code applies dirty settings on the GL thread at the next frame.
- **Validation when changing these:** native engine tests (commands, skip list, transitions, context loss), `QualityControllerTest`, app JVM tests, and a TV check of pause/resume (Home and return), audio re-attachment and low-memory behavior.

## User-facing text and localization

Use the project's established resource or localization mechanism for user-facing text. Follow its locale ownership and translation workflow; do not invent an English-only or all-locales policy.

- **Not localized today.** `app/src/main/res/values/strings.xml` holds `app_name` (overridden by `resValue` for test builds) and the Resolution selector labels; there are no `values-*` locale directories and no translation workflow. UI text is English literals in Java (`MainActivity`, `OptionRow`, …) and the layout XML. Introducing localization is a deliberate change that should move strings to resources consistently.
- **Wording conventions:** the app name is "ProjectM TV" and its maintained engine is "ProjectM TV Engine". Use "based on projectM 4.1.7" for upstream provenance; do not present the patched engine as stock upstream 4.1.7. The core AAR shares the app release version; `ProjectMJNI.getVersion()` still reports the upstream version. Preserve package/API/artifact names and historical evidence identities. Menu paths use `›` (e.g. *Settings › Advanced › Auto-update*). Keep setting names and values identical in the UI, the README settings tables and `docs/user-guide/settings.md`.
- Store listing text: `fastlane/metadata/android/en-US/` (F-Droid metadata, English only).

## Code structure and modularization

Place code according to its responsibility and actual consumers. Reuse shared code when appropriate without creating speculative abstractions. Split oversized or mixed-responsibility files along meaningful boundaries. Preserve behavior during refactors and remove obsolete code.

| Responsibility | Location |
|---|---|
| App UI, audio capture, track titles, updater | `app/src/main/java/com/example/projectm/visualizer/` |
| App resources; profile-build manifest | `app/src/main/res/`; `app/src/profile/` |
| App JVM tests | `app/src/test/java/com/example/projectm/visualizer/` |
| On-device tests | `app/src/androidTest/…` (`MusicCategoryInstrumentation` is a custom `Instrumentation` and the configured runner; `TrackAccessSetupTest`) |
| Engine Java API | `core/src/main/java/nl/neerdael/projectm/core/` |
| JNI and native engine glue | `core/src/main/cpp/` (`native-lib.cpp`, `snapshot_fade.*`, `preset_prewarm.*`, `CMakeLists.txt`) |
| Core JVM tests | `core/src/test/java/…` (`QualityControllerTest`) |
| Native host tests | `core/src/test/native/` (`engine_test.cpp` against stubs, `fade_gl_test.cpp`, `projectm-regressions/`) |
| Presets, textures, indexes | `core/src/main/assets/{presets,textures,presets.idx,preset-genres}` |
| projectM changes | `tools/projectm-patches/NNNN-<slug>.patch` (4-digit order, header explains the change and any upstream source) |
| Upstream engine (do not commit edits) | `third_party/projectm` |
| Tools | `tools/*.sh`, `tools/*.py`, `tools/preset-lab/` |
| Release tooling / CI | `.github/scripts/` (+ `tests/`), `.github/workflows/` |
| Docs | `README.md`, `docs/`, `docs/user-guide/` |

- JNI functions bind by name (`Java_nl_neerdael_projectm_core_ProjectMJNI_*`), kept by `core/consumer-rules.pro`; renaming `ProjectMJNI`, its package or a native method requires matching native changes and breaks consumers.
- No file-size limits are established. `MainActivity.java` (~1,200 lines) and `native-lib.cpp` (~2,000 lines) are large; split only along real responsibilities.
- Root scripts `build.sh`, `build_android.sh`, `debug.sh`, `install.sh` are local helpers not used by CI (not validated).

## Repository-specific constraints

Preserve the release/version rules above. Treat the core AAR’s interface and compatibility with Milkbeat as an integration boundary; verify the actual API and consumers before changing it.

- **Core API:** public classes in `nl.neerdael.projectm.core` (`ProjectMCore`, `ProjectMJNI` incl. `TRANSITION_*` constants, `VisualizerView`, `VisualizerRenderer`, `QualityController`, `DeviceProfile`, `DisplayInfo`) are used by `:app` and by Milkbeat through the released AAR. There is no API/ABI compatibility check. Before removing or changing public members or native signatures, inspect Milkbeat's usage. Because every `main` merge publishes the core and triggers a Milkbeat rebuild, a deliberate incompatible change needs a coordinated Milkbeat change; no written procedure exists yet (unresolved).
- **Native toolchain:** NDK `27.3.13750724`, CMake `3.22.1`, C++17, ABIs `armeabi-v7a`/`arm64-v8a`, projectM linked statically. Keep the reproducible-build settings in `CMakeLists.txt` (`-ffile-prefix-map`, disabled flex/bison) and `dependenciesInfo` off in `app/build.gradle`: F-Droid rebuilds and compares the release APK.
- **projectM patches:** never commit edits inside `third_party/projectm` (submodule has `ignore = dirty`). To write a patch: apply the existing series in `third_party/projectm` and stage it (`git -C third_party/projectm add -A`) so new edits show as a clean diff, then use `tools/regen-projectm-patch.sh <name>`. That script only diffs `src/` and `tests/`; patches touching `vendor/hlslparser` (0003, 0008, 0018, 0019, 0021, 0030, 0031) must be produced manually with a `git diff` that includes `vendor/hlslparser`. `vendor/projectm-eval` is a nested submodule (patches 0004, 0020, 0034): diff it with `git -C third_party/projectm/vendor/projectm-eval diff --src-prefix=a/vendor/projectm-eval/ --dst-prefix=b/vendor/projectm-eval/` and stage it with `git -C third_party/projectm/vendor/projectm-eval add -A`. Its `Scanner.c`/`Compiler.c` are pre-generated (the build disables flex/bison); for a `Scanner.l` change commit only the delta between two runs of the same flex (`flex --noline --prefix=prjm_eval_ --header-file=Scanner.h -o Scanner.c Scanner.l` before and after), because Apple's flex 2.6.4 skeleton differs from the committed one (patch 0034). Patch numbers are taken in merge order: check `main` for new patches before numbering yours. For several new patches at once, a local-only branch in the submodule with one commit per patch (series, then each new patch) lets `git diff <commit> <commit>` regenerate any of them; never stage `third_party/projectm` in the superproject, and reset the submodule to the pinned commit afterwards. After pulling patch changes, reset the submodule (`git submodule foreach --recursive git checkout -- .`). Shader changes must link as GLSL ES 3.00 (`glslangValidator -l` with `#version 300 es` prepended; PR template).
- **Preset equation loading (patches 0029, 0033–0035):** code the evaluator rejects is compiled once more in MilkDrop's form (numbered records joined, `//`/`\\` comments removed, NS-EEL's stray `;` in parentheses read as a space); a lone `.` is the number 0; a block that still does not compile is left out like MilkDrop's `CState::RecompileExpressions` (q/t variables zero after a failed init) and reported through `projectm_set_preset_initialization_warning_event_callback`, which `native-lib.cpp` logs as `Preset code left out (<preset>): <reason> (line N, column M)`. Only parse errors fail a load. Keep accepted programs on the unchanged path.
- **Random textures (0037):** image selection belongs to slots 00–15 in a preset and is reused across warp/composite and shader reloads. Rebuild the descriptor for each exact alias and requested mode. Within a shader, filtered `randNN_prefix` aliases choose an empty slot before unfiltered aliases; competing prefixes keep lexical precedence. Across stages, the already selected slot wins. `sampler_state` fields remain ignored (0032); name prefixes select mode. Default user-texture mode is linear/wrap. Bind emitted short aliases to the same unit as their full alias and deduplicate declaration lines. Preserve `Texture::SourcePath()` and base names for diagnostics; generated textures have no source path. Production uses `std::random_device` for each new texture choice; a host seed does not establish Android/AAR association.
- **GLES sampling fixtures:** allocate sized RGBA8 storage before an RGBA upload and assert allocation/upload GL errors immediately. An unsized RGB texture can accept RGBA uploads on desktop GL while GLES rejects them. Use unit-slope, exactly representable edge-crossing UV/filter weights for cross-driver numerical oracles; keep strict pixel tolerances and inspect actual texture bytes/sampler state before attributing differences to the engine.
- **Native regression GL linkage:** link engine-dependent regressions to `libprojectM::projectM` and the harness-selected EGL/GL target. System projectM GLES discovery creates a directory-scoped imported target; the parent harness must not reference `OpenGL::GLES3` directly unless the explicit-flag override made it global. Validate both normal discovery and explicit `GL_LIBS`/`GL_CFLAGS` routes on Linux/Mesa, as well as macOS.
- **Matched TV benchmark selection:** temporarily select All when a curated collection excludes the witness, restore the original selection afterward, and verify exact `BENCHMARK`/`LOAD` filenames before accepting FPS rows. A short prefix can select a sibling (`widest swing zero-sum.milk`); use the full filename when it fits the Android property limit. Cold-start with the captured-user/listener recipe above so a preserved preset cannot override the debug pin. Record actual surface size, target FPS and audio state; silence windows do not establish live-music performance.
- **Predictor-established renderer fixes (0045–0047):** main-textured shapes own a repeat/linear sampler for every fill, including authored/native geometry; preserve named-image descriptor qualifiers. Blur bounds retain clamp-then-expand ordering, but upper bounds expand upward; reject nonfinite/unrepresentable ranges and progressive float32 cancellation using coherent `[0,1]` defaults for storage and decoding. Signed negative motion zoom with `zoomExp == 1` bypasses undefined GLSL `pow` in the shared warp vertex shader; other negative-base power domains remain unsupported. Native controls `shape-sampler-regressions`, `blur-range-regressions` and `warp-zoom-regressions` exercise real draws, production normalization and vertex UV readback. Do not infer Windows appearance or TV GPU performance from host/emulator checks.
- **Live controls (0048–0049):** rendering consumes per-frame values without writing configuration defaults; keep reset-per-frame and instance ownership intact. Rebuild wave math when the truncated signed-remainder mode changes (16 modes). Legacy-only filters must support equation-only activation; custom composites retain shader policy. Run `dynamic-wave-controls`, `dynamic-display-controls` and `dynamic-original-presets`; preserve historical predictor/static-policy results. See `docs/ARCHITECTURE.md` and the live-controls evidence.
- **Blur framebuffer ownership (0041):** capture both caller read/draw framebuffer bindings before allocating or resizing blur textures. `Framebuffer::SetSize` unbinds both targets; saving after allocation sends later shapes/waves/borders to framebuffer zero when warp shaders sample blur. The native runner checks first use, unchanged size, resize, scaled blur, constant-color output and the unchanged midgit preset with isolated TGA assets. The same ownership control is verified on AM6/Mali-G52; Android framebuffer zero can be valid and hide the host error, so assert binding identity as well as checking GL errors (evidence: `docs/superpowers/evidence/midgit-framebuffer/`).
- **Predictive collection identity:** `tools/milk-analyzer/beta_export.py --check --bundle core/src/main/assets/preset-genres` validates the beta schema2 source/texture/weight inventory, frozen scoring code/model, standard published-AAR identity, raw activity formula, relative ranks and exact overlapping group membership. The numerical profile is capped2.3.3 at128×72, not a certificate of Native/TV fidelity. A changed renderer needs a separately identified run; historical schema1 Preset Lab imports do not produce the current bundle.
- **Presets and textures:** CI rejects presets that cannot react to audio or use excluded or missing textures (`tools/check-presets.py`) and a stale `presets.idx` (`tools/gen-preset-index.py --check`). Preset Lab CI rejects tracked audio/raw capture files under `tools/preset-lab` and `core/src/main/assets/preset-genres`.
- **Licensing and attribution:** app code LGPL-2.1 (`LICENSE`); presets and textures CC0 1.0 (`LICENSES/CC0-1.0.txt`). Record new third-party content and new patches in [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md); keep upstream attribution in patch headers and release notes.
- **Privacy claims:** README states no network access except opt-in auto-update to GitHub, and in-memory audio analysis only. New network use or data storage contradicts published documentation and must update it.
- **Worktrees:** never remove another task's worktree. Follow the mandatory workflow below for cleanup of this task's clean, pushed and merged worktree; it is authorized as part of implementation. For this research checkpoint the user has authorized removal of `.worktrees/native-feedback-recovery` only after the main merge, all intended work is pushed, its tracked state is clean, task-owned jobs are stopped and external evidence archives are hash-verified. This exception does not authorize removing any other worktree or its data.
- **Native trails/fallback:**0042 owns authored feedback/resources per preset; Standard skips native warp, Medium/High use centered headroom-limited detail. Preserve per-frame RNG reuse, native viewport restoration after canvas init, UV-map invalidation on resizing/mode changes, authored blur timing and authored geometry recurrence. Patch0043 reuses evaluated shape/wave geometry for native presentation and alternates the existing canvas buffers; do not rerun persistent equations or RNG for the native draw. Shader/canvas failures retain0038 and diagnostics. The new Android core defaults Standard, while the projectM C API remains off by default for compatibility tests. Historical dual-AAR/capped evidence does not validate new automatic quality. Use the owner-approved17 known-preset focused matrix against source/released2.3.3, rather than claiming whole-corpus coverage. Record source/PCM/clock/seed/capture identities and quantify brightness/structure; chaotic and near-black cases need visual review.
- **Device ownership for native-trails-validation-fixes:** use only this task's `emulator-5602` (AVD/logs in ignored `build/native-trails-investigation/`), or the user-authorized AM9 `192.168.51.53:5555` and AM6 `192.168.50.80:5555`. AM9 runs64-bit Android14/Mali-G310; AM6 runs32-bit Android9. Build matched validation roles with `--abi armeabi-v7a` for AM6. Do not operate other tasks' emulators. Always pass an explicit `adb -s SERIAL` and captured Android user. Never wake a TV remotely; stop testing when it sleeps.
- **Do not commit:** `local.properties`, keystores, APK/AAR outputs, `build/`, raw diagnostics (see `.gitignore`).

## Formatting and linting

Follow the repository's configured formatting and lint rules. Review automatic formatting changes and avoid unrelated churn. Fix violations rather than disabling checks to obtain a passing result.

- No project-wide source formatter or linter is configured: no `.editorconfig`, `.clang-format`, ktlint/detekt, `lint.xml`, pre-commit or Python lint configuration outside `third_party/`. CI does not run Android Lint. Match the surrounding style (Java: 4-space indent).
- Validate workflow changes with `actionlint`. Older local versions reject GitHub's documented `queue: max` and `cache-mode: none`; use narrow ignores for those two schema fields only if necessary, and do not suppress other errors. Also run `git diff --check`.
- The JNI library compiles with `-Wall -Wextra -Wno-unused-parameter`; do not add warnings.
- Checks that act as lint in CI: `release_notes.py validate` (PR body), `tools/gen-preset-index.py --check`, `tools/check-presets.py`, `mkdocs build --strict` (user guide). `tools/check-patch-series.sh` is not in CI; CI applies the series through CMake during the native tests and `assembleRelease`.

## Building and testing

Choose validation that exercises the changed behavior. Compilation alone does not establish functional correctness. For UI or integration changes, exercise relevant user journeys and error paths when the environment supports them. Record baseline failures and environmental limitations honestly.

For release tooling changes, the required check is:

```bash
python3 -m unittest discover -s .github/scripts/tests -v
```

**Prerequisites** (from `app/build.gradle`, `core/build.gradle`, wrapper and CI): JDK 21 (CI Temurin 21, matching F-Droid; sources compile as Java 1.8), Gradle wrapper 8.14.2, AGP 8.12.0, Android SDK platform 34, NDK `27.3.13750724`, CMake `3.22.1` (CI installs the last three with `sdkmanager`), `local.properties` with `sdk.dir` (git-ignored; CI writes it), initialized submodules. CI runs on `ubuntu-24.04`.

| Command | Covers | Status |
|---|---|---|
| `git submodule update --init --recursive` | setup | Verified |
| `tools/check-patch-series.sh` | full series applies to a clean export of the submodule's `HEAD` (so the submodule must be at the pinned commit) | Verified: "all 29 patches apply" on `main`; the 32-patch series was verified with the same steps against `e0b0a967`; "all 35 patches apply" on 2026-10-04 with 0033–0035; 37 patches verified after integrating the parser fix for the random-binding task; all 41 patches verified on 2026-10-05; all 44 patches verified on 2026-10-06 for the float-literal fix; all 47 verified for predictor-established sampler/blur/zoom corrections |
| `tools/projectm-host-tests.sh [--gtest_filter=…]` | patched projectM GTest suite (build in `build/projectm-host`); needs CMake, Ninja, C++ compiler, Homebrew googletest | Verified on macOS: 179/179 on `main`, 204/204 with 0030–0032, 261/261 with 0001–0047 on 2026-10-06; earlier 222/222 with 0001–0035 (configured with `-DCMAKE_DISABLE_FIND_PACKAGE_FLEX=ON -DCMAKE_DISABLE_FIND_PACKAGE_BISON=ON` to match the Android build's pre-generated parser) |
| `python3 -m unittest discover -s .github/scripts/tests -v` | release tooling | Verified: 74 tests OK (Python 3.13.12) |
| `python3 -m unittest discover -s tools -p test_tv_diagnostics.py -v` | diagnostics package/APK-source options; user-scoped cold start, process filtering, fail-safe queries and signing-conflict recovery; isolated fake adb, no TV/build/network | Run by Android CI; see task validation for the current revision |
| `core/src/test/native/run_native_tests.sh` | engine tests, GL fade overlay, patched-projectM regressions (ASan/UBSan); needs a C++17 compiler, JDK (`jni.h`), CMake, EGL/GLES dev libs on Linux (macOS uses OpenGL) | Verified on macOS 2026-10-06 (JDK 21): engine/Native policy tests and all 26 projectm-regressions pass with ASan/UBSan; GL fade overlay skipped without EGL/GLES; CI runs all on Linux |
| `./gradlew testReleaseUnitTest` (CI) / `./gradlew testDebugUnitTest` (PR template) | app and core JVM tests | Verified 2026-10-04: `testReleaseUnitTest` BUILD SUCCESSFUL |
| `./gradlew assembleRelease` / `./gradlew :core:assembleDebug` / `./gradlew assembleProfile` | APK + AAR; patch application through CMake; profile build | CI runs `assembleRelease`; verified 2026-10-04: `:app:assembleProfile :core:assembleRelease`, and `:core:assembleDebug` from a fresh recursive clone (CMake applied the series); a new worktree needs `local.properties` copied from the primary checkout |
| `tools/gen-preset-index.py --check`, `tools/check-presets.py` | asset checks | CI; not validated in this pass |
| `python -m pytest tools/preset-lab/tests` (`-m native` needs the native worker; see `tools/preset-lab/README.md`) | Preset Lab | CI (Preset Lab workflow); not validated in this pass |
| `mkdocs build --strict` (after `pip install -r docs/site-requirements.txt`) | user guide | CI (User guide workflow); verified 2026-10-04, no warnings |
| `./gradlew -PpresetLabDeviceTest :app:assembleDebug :app:assembleDebugAndroidTest`, then `adb -s DEVICE shell am instrument -r -w -e live_audio true nl.neerdael.projectmtv.presettest.test/com.example.projectm.visualizer.MusicCategoryInstrumentation` | music-category behavior on a TV ([development guide](docs/user-guide/development.md)) | needs a TV; not validated in this pass |

**What to run when:**

- JNI, `native-lib.cpp`, transitions, skip list: native tests, JVM tests, a build, and a TV check for rendering/audio/frame rate.
- Random-binding changes: real-GL `random-texture-*` controls in `core/src/test/native/projectm-regressions/` inspect units/samplers and compare known TGA bytes. The optional `random-texture-regressions presets <new-fixture-dir>` diagnostic records exact bundled asset identities and full-load/render results separately; full JPEG decoding exposes pre-existing SOIL2 UBSan warnings. See the random-binding evidence for unverified appearance/device limits.
- projectM patches: `check-patch-series.sh`, `projectm-host-tests.sh`, native tests, `:core:assembleDebug` log, TV before/after; complete the PR template's *projectM patches* checklist. Shader translation changes: the native runner includes float32 round-trip/locale/nonfinite controls (`float-literal-regressions`), a one-frame warp/composite RGB control (`float-literal-render`), 95 unchanged hashed shader sections (`float-literal-presets`), and `shader-parser-regressions`, `shader-render-regressions` and `parser-presets` (16 original files pinned by `parser-presets.tsv` hashes); also run `PresetShaderTranslationTest` (generated GLSL plus composite shaders rendered through the engine on macOS CGL; render cases skip without a GL context) and, where useful, translating the bundled presets' shaders before and after and compiling both with `glslangValidator` as GLSL ES 3.00.
- GL test readback: use `GL_RGBA` / `GL_UNSIGNED_BYTE` for normalized RGBA8 GLES targets, and drop alpha only when exporting RGB artifacts. Desktop CGL accepting `GL_RGB` does not establish GLES portability; validate readback changes on Linux EGL/Mesa as well. Keep GL errors checked before and after readback.
- Presets/textures: `check-presets.py`, regenerate `presets.idx`, consider the genre bundle.
- UI, settings, remote keys: JVM tests plus a D-pad journey on a TV (open panel, sub-panels, Back/Menu, auto-hide); refresh setup screenshots with `-PsetupScreenshotTest` when visuals change.
- Audio and track titles: a TV with a verified music app (Spotify, SoundCloud, SmartTube, Milkbeat); include pause/resume.
- Public core API: build `:core:assembleRelease` and build Milkbeat against the new Native core (`-PprojectmCoreRepo=<dir> -PprojectmCoreVersion=<version>`, see [docs/RELEASING.md](docs/RELEASING.md)); not validated in this pass.
- After TV work: clear `debug.projectmtv.*` properties and restore app settings.

## Generated artifacts and release preparation

Feature pushes and PRs targeting other branches do not start builds. Ready PRs targeting main need a completed latest-commit Codex or qualified non-author human review, no outstanding review requests, observable pending reviews or changes requested, and no unresolved threads (including outdated ones). Preserve trusted-main execution of the review controller and status reporter: never check out PR code in a write-token job, pass publishing/signing secrets to PR code, or let PR code write main caches. Private draft reviews are visible only to their author and cannot be detected here; require an outstanding review request to represent planned unfinished reviews. Codex approval is the connector’s `+1` reaction on the PR itself; completed comments and submitted review records supply revision/time metadata only and cannot approve without that reaction. Resolve authenticated Codex 7–40-character identifiers through GitHub to the full current head; reject stale/ambiguous identifiers, malformed responses, and hex-named branch/tag aliases. Preserve full 40-character head/base/merge IDs in dispatch and preflight. Require the reaction at or after the current review’s completion; old reactions cannot authorize a new head or pending rereview. Submitted review API `commit_id` values must be full IDs consistent with any written marker; empty bot replies do not count. Qualified non-author human reviews remain a separate approval path, but never treat the connector as a human reviewer even if an endpoint labels it `User`. Track Codex request commands by the latest comment update time, falling back to creation time only when no update timestamp is available. Only current-head completions strictly later than the request at whole-second precision fulfill explicit Codex commands, including retained commands after a push. Automatically rerun successful validation invalidated by review eligibility, a preflight error with no builds started, or a final reporter API error after successful builds, once eligibility recovers; actual build failures require an explicit retry. Read the live main ref and verify the immutable test merge parents; recheck head/base/review before reporting success. Require `Reviewed PR builds` from GitHub Actions in the main ruleset, with up-to-date-branch and thread-resolution enforcement. GitHub's approving-review count remains zero because a completed Codex review is allowed; the custom status enforces the one-review minimum. See `docs/RELEASING.md` for exact completion signals, scheduled rechecks, unstructured-feedback limits and manual retry.

A successful tested merge to `main` triggers the versioned APK/single Native core AAR release and Milkbeat update through the canonical alias. Routine PRs must not manually bump the base version/code/commit. Follow `docs/RELEASING.md` for a planned new release line.

| Workflow (file) | Trigger | What it does |
|---|---|---|
| Android CI/CD (`android.yml`) | main push or main manual run | Calls Android build, Preset Lab and User guide; publishes only after the full suite passes, updates Milkbeat and deploys Pages. Main runs queue without cancellation |
| Android build (`android-build.yml`) | reusable call only | Native/tooling/assets and JVM tests; Native APK/AAR/mapping artifacts (30 days). Main receives signing secrets; PR calls receive none and disable Gradle cache access |
| PR review gate (`review-gate.yml`) | PR/comment/main-push events, trusted workflow_run relay from an unprivileged review signal, five-minute schedule, validation completion, manual | Trusted-main controller checks current Codex or qualified human review, outstanding review requests/changes and every thread; dispatches eligible PR validation and cancels obsolete runs. Schedules may be delayed by GitHub |
| PR review signal (`review-signal.yml`) | submitted/edited/dismissed review events | Unprivileged relay with no checkout; default-branch controller follows its completion |
| Reviewed PR validation (`pr-builds.yml`) | controller/manual dispatch on main | Preflight validates immutable head/base/test-merge SHAs; runs all Android, Preset Lab and guide builds without secrets; required `Reviewed PR builds` status passes only after actual success and a final eligibility/revision check |
| PR release notes (`release-notes.yml`) | PR opened, synchronized, reopened, edited, ready for review | `release_notes.py validate` on the PR body |
| User guide build (`docs-build.yml`) | reusable call from main, reviewed PRs or the manual guide workflow | Read-only `mkdocs build --strict` and Pages artifact; no publishing token |
| User guide (`docs.yml`) | manual run on main | Calls guide build and the shared Pages deployer; other branches skip |
| Publish user guide (`pages-deploy.yml`) | reusable call from main Android or manual User guide | Shared `projectm-tv-pages` queue with no cancellation; publish only if caller SHA still equals current main; API failure stops publication |
| Preset Lab (`preset-lab.yml`) | reusable call from main/eligible PR validation, or main manual run | Native/source-analysis tests under xvfb; rejects tracked audio/raw captures |

- **Versioning (`.github/scripts/release_version.py`):** publishing happens only for `refs/heads/main` on `push` or `workflow_dispatch`. Version = `baseVersionName` patch + (first-parent ordinal since `baseVersionCommit` − 1); the code advances in step from `baseVersionCode`. Other builds get a `-ci.<run>` suffix and file names `…-ci.<run>-<sha>.apk/.aar`. The user-planned Native minor release line sets the base triple to 2.3.0 / code 49 / `8b70620339018cfaf5ac05acdb4ea8104dc2eb59`; this deliberate line change is the documented exception to routine no-bump rules. Publication remains contingent on successful main CI.
- **Signing secrets (names only):** `SIGNING_KEYSTORE_BASE64`, `SIGNING_STORE_PASSWORD`, `SIGNING_KEY_ALIAS`, `SIGNING_KEY_PASSWORD`. A publishing build without the keystore fails; PR artifacts use a temporary debug key.
- **Publication:** GitHub Release `v<version>` with `projectM-TV-<version>.apk`, `projectM-TV-core-<version>.aar` (Native), stable-named `projectM-TV.apk` / `projectM-TV-core.aar`, `projectM-TV-<version>-mapping.txt` and `checksums.txt`. Notes come from merged PRs' `## Release notes` sections plus a CI footer.
- **Downloader code:** read by `release_notes.py` from the README blockquote `` > **Install on your TV with the Downloader app: code `4821216`** `` (exact regex; changing its format breaks release-note generation). The code is an AFTVnews short link to `releases/latest/download/projectM-TV.apk`; who manages the short link is not recorded in the repository.
- **Milkbeat:** `publish_release.py milkbeat` (token secret `MILKBEAT_TOKEN`) sends `repository_dispatch` `projectm-core-release` with the version to `johnneerdael/Milkbeat`, unless Milkbeat's latest release already names this core version or newer.
- **Committed generated files:** `core/src/main/assets/presets.idx`, `core/src/main/assets/preset-genres/`. Not committed: APKs, AARs, `build/`, raw diagnostics. `RELEASE_NOTES.md` is a manual archive (last entry 2.1.5) and is not used by CI.

## Documentation map

| Source | Role |
|---|---|
| `README.md` | Product overview, settings tables, permissions, install (canonical Downloader blockquote), troubleshooting, developer build/test |
| `docs/user-guide/*.md` + `mkdocs.yml` | User guide source, built by the User guide build reusable workflow and published through the shared main/manual Pages deployer to https://johnneerdael.github.io/ProjectM-TV/ (`docs/user-guide/development.md` covers build/test and the docs site) |
| `docs/ARCHITECTURE.md` | Engine design, threading, transitions, resolution, device tiers, measurements |
| `docs/RELEASING.md` | CI publishing, versioning, signing, downloads, Milkbeat |
| `docs/THIRD_PARTY.md` | projectM pin, per-patch descriptions, presets/textures sources and licences |
| `docs/PROFILING.md`, `docs/DIAGNOSTICS.md` | Profile build + simpleperf; `tools/tv-diagnostics.sh` |
| `docs/DANCE-COLLECTION.md` | Pointer to `docs/user-guide/dance-measurement.md` |
| `tools/preset-lab/README.md` | Preset Lab installation and commands |
| `docs/superpowers/` | Design specs, plans and evidence for engine work |
| `.github/pull_request_template.md` | Required PR sections and checklists |
| `RELEASE_NOTES.md`, `fastlane/metadata/android/en-US/` | Historical release notes; F-Droid store listing and changelogs |

Known documentation drift: `docs/ARCHITECTURE.md` §5 still describes embedding
`core/` as a Gradle module, while `docs/RELEASING.md` describes Milkbeat consuming
released AARs. Historical Dance research is retained; current collection behaviour
is documented in `docs/user-guide/predictive-collections.md`. The beta exporter
and numerical scoring commands are documented in `tools/milk-analyzer/README.md`.

## Mandatory workflow — scope and completion

This workflow applies to all repository changes targeting `github.com/johnneerdael/*`. Confirm the target repository from its Git remote and GitHub metadata before making changes. Do not assume a remote named `origin` is the correct target.

For implementation tasks, carry the work through to a validated, Codex-reviewed pull request merged into `main`. Creating a branch, pushing changes, opening a PR, or requesting review is an intermediate step, not completion.

The requested implementation authorizes the routine commits, pushes, PR creation, review comments and replies, and merge needed to complete this workflow. Do not ask for confirmation at each step. Honor explicit user instructions, repository permissions, required human approvals, and branch protection rules.

Read the repository's applicable `AGENTS.md` files, contribution guidelines, PR template, and CI configuration. Follow repository-specific conventions in addition to this agreement. If a conflict prevents compliance, explain the exact conflict instead of silently skipping a requirement.

**Documentation precedence:** The mandatory documentation evaluation and update rule below overrides any conflicting repository instructions, nested `AGENTS.md` rules, conventions, or workflow guidance that would skip documentation evaluation or prevent necessary documentation updates. It applies to every `feat/` and `bug/` change, including small fixes and internal changes. It remains subject to higher-priority system/platform instructions and later explicit user instructions.

**Markdown editing exemptions:** User guides (including their Pages/GitHub Pages source files) and the root/default `README.md` are explicitly exempt from any rule saying "do not edit Markdown unless asked." Keep them accurate as part of every affected change without requesting separate authorization. Maintaining `AGENTS.md` as instructed above is also explicitly authorized. Other Markdown files still require evaluation; make task-relevant corrections as required by the documentation rule, without unrelated rewrites.

Read-only investigations and review-only tasks do not require a worktree or a PR. A reviewer assigned only to review must report findings without starting an implementation or merge workflow.

## 1. Work in an isolated worktree

- Make every tracked repository change in a dedicated Git worktree under `<primary-checkout>/.worktrees/<task-slug>`. The path is relative to the primary checkout, not the current directory of an existing worktree.
- Use a unique branch based on the latest fetched `main`: `feat/<task-slug>` for features, improvements, and maintenance, or `bug/<task-slug>` for bug fixes. Follow additional repository naming requirements where compatible.
- Never implement directly in the primary checkout or on `main`. Never share a task worktree with unrelated work.
- Inspect the current checkout and existing worktrees first. Preserve existing changes and branches. Resume an existing task worktree only after confirming it belongs to this task and is based on the intended branch.
- Ensure `.worktrees/` is ignored before creating a worktree. Prefer an existing ignore rule; otherwise use the shared Git `info/exclude` so setup does not require tracked changes in the primary checkout.
- Run editing, dependency installation, builds, tests, and Git staging from the task worktree. Verify the worktree path and branch before mutations.

Typical setup, after identifying the correct remote and primary checkout:

```bash
git fetch <target-remote> main
git worktree add -b feat/<task-slug> <primary-checkout>/.worktrees/<task-slug> <target-remote>/main
cd <primary-checkout>/.worktrees/<task-slug>
```

Use `bug/<task-slug>` instead for a bug fix. Replace the placeholders with verified values.

## 2. Implement, validate, commit, and push regularly

- Keep changes focused on the requested outcome and follow existing repository patterns.
- Run an appropriate baseline check when useful, then the tests, lint, type checks, and builds required by the repository and affected code. Add meaningful regression coverage for behavior changes where appropriate.
- Commit coherent progress at regular milestones and push each checkpoint to the task branch. Do not keep all work uncommitted or unpushed until the end of a long task. Clearly identify incomplete checkpoints in commit messages.
- Inspect the diff and stage only task-related files. Exclude credentials, local configuration, generated clutter, and `.worktrees/` contents.
- Set the branch's upstream on its first push. Push only the task branch; never push directly to `main`.
- Prefer additional commits over rewriting published history. Do not force-push unless explicitly authorized and consistent with repository rules.
- Report useful progress while continuing work. Recover from routine failures autonomously and preserve checkpoints if interrupted.

## 3. Evaluate documentation for every change

For every `feat/` and `bug/` change, documentation evaluation is mandatory before the work can be considered ready for review or merge. Do not assume that a small change or an internal bug fix has no documentation impact.

1. Identify and evaluate the user guide, if one exists, including any guide published on Pages or GitHub Pages and the source used to generate it. Also evaluate the README and inventory the repository's other Markdown files to identify affected documentation, then read the relevant files. Follow documentation links to the applicable user-facing guidance.
2. Compare the final implementation with documented behavior, setup, configuration, examples, troubleshooting, compatibility, and limitations. Check whether the change makes existing guidance incomplete, misleading, or incorrect.
3. Update all affected documentation in the same task worktree and PR. Follow the repository's documentation structure and publishing workflow, including required source changes for its Pages site. Ensure the README, user guide, and other affected Markdown files agree.
4. Validate changed documentation using the repository's applicable build, link, example, or formatting checks. Reevaluate documentation after review fixes or scope changes that alter behavior.
5. Include a documentation assessment in the PR: which sources were evaluated, which were updated, and why. If no documentation update is needed, state the specific reason; silence is not an assessment. If a user guide or Pages site does not exist, record that and evaluate the documentation that does exist.

Do not waive this requirement because another rule labels documentation optional, excludes it from bug fixes, or discourages editing Markdown. If an existing guide or Pages site cannot be inspected or updated because of a real access or publishing constraint, report the blocker and keep the task open until the requirement can be fulfilled or the user explicitly changes it.

In particular, an instruction requiring an explicit request before Markdown edits must not prevent updates to the user guide, its publishing sources, or the root/default `README.md`. These updates are a normal part of completing the feature or bug fix.

## 4. Open a pull request against main

Once implementation is ready and local validation passes:

1. Push all intended changes.
2. Open a PR from the task branch to the target repository's `main`, or update the existing PR for this task.
3. Follow `.github/pull_request_template.md`, title conventions, linked-issue requirements, and other repository rules. Include substantive `## Release notes` and a separate `## Validation` section as required above. Describe the problem, resulting behavior, validation performed, documentation assessment, and material limitations. Keep CI-owned artifact details out of authored release notes.
4. Ensure the PR is ready for review, not left as a draft when implementation is complete.
5. Monitor CI and fix failures caused by the change. Investigate other failures and follow the repository's policy; do not silently treat failed or pending required checks as passing.

## 5. Obtain and complete Codex review

- Check whether an automatic Codex review has actually started for the current PR revision. If it has not, post a PR comment containing exactly:

  ```text
  @codex review
  ```

- Wait for Codex to finish. Monitor PR reviews, comments, review threads, and any associated review status. A submitted request, an acknowledgement or eyes reaction, elapsed time, or the absence of comments does not prove completion.
- Verify that the completed review applies to the latest PR head commit. Record the reviewed commit SHA. If the integration does not expose it directly, establish the revision from the review/task metadata and timeline; ambiguous evidence does not satisfy this gate.
- Read the complete review and all findings, including inline comments. Process every finding, regardless of severity.
- Fix valid findings, add relevant coverage, run affected validation, commit, and push the corrections to the same branch. Reply in the corresponding thread with the resolution and supporting evidence. Resolve a thread only after its finding has been addressed.
- If a finding is incorrect or inapplicable, provide a concrete explanation and evidence in its thread and obtain reviewer acceptance or explicit maintainer disposition. Do not silently dismiss findings or mark them resolved just to enable merging.
- After any review-driven changes, obtain another Codex review of the new head commit. Use an automatic review if it starts; otherwise post `@codex review` again. Repeat the fix, validate, push, and review loop as many times as needed.
- Avoid duplicate requests while a review of the same revision is running. For complex changes, allow additional focused review passes as useful; complexity never removes the final review requirement.
- Close the review cycle only when Codex has completed review of the final head commit, every finding has a documented disposition, all review threads are resolved, and no further changes are requested. Codex review completion does not replace any separately required GitHub approval.

If review cannot start or finish because of access, configuration, service failure, or quota, investigate available diagnostics and report the concrete blocker. Keep the PR open and preserve the branch. Never substitute self-review or a timeout for the required Codex review.

## 6. Merge the validated and reviewed change

Merge autonomously once all of these conditions hold:

- The requested work is complete and the final diff contains only intended changes.
- The user guide/Pages, README, and other Markdown documentation have been evaluated, necessary updates are included and validated, and the PR records the documentation assessment.
- Repository-specific guidance in `AGENTS.md` has been populated or maintained as required by the task, with unresolved facts identified honestly.
- Local validation and all required CI checks pass for the final revision.
- Codex review is complete for the current PR head commit, with all findings addressed and review threads resolved.
- All repository-required approvals and merge conditions are satisfied.
- PR release notes are factual and match the final diff; validation is recorded separately, and any required release-tooling tests pass. Routine changes have not manually bumped release versions.
- The PR targets `main`, is mergeable, and meets any requirements to be current with its base branch.

Refresh the PR state immediately before merging and verify that its head SHA still matches the validated and reviewed SHA. Use the repository's permitted merge method through GitHub. Do not bypass protections, use an administrative override, or merge an unreviewed revision.

If updating from `main` or resolving conflicts changes the PR head, push the update, rerun appropriate validation, and obtain Codex review of that new head before merging. Any further change reopens the validation and review gates.

If the repository requires a merge queue, enqueue the eligible PR and monitor until it actually merges. Continue responding to failures or new findings. Enabling auto-merge or entering a queue does not itself complete the task.

## 7. Confirm and close the work

- Verify on GitHub that the PR is merged into `main` and record the merge commit or squash commit SHA.
- Monitor the automatic APK/core AAR release and Milkbeat update workflow. Verify reported publication/update results before claiming success. If a job fails, investigate and address task-related failures through another isolated branch and reviewed PR where appropriate, or report the concrete release/update blocker. Do not manually bypass the release pipeline or push fixes directly to `main`.
- Preserve unrelated worktrees, branches and uncommitted changes. The user authorized removal only of this task's `.worktrees/native-feedback-recovery` after the merged/pushed/clean and verified-external-archive conditions in *Worktrees* are satisfied. Do not generalize that authorization to another task or force-remove unchecked tracked changes. Delete a branch only when repository policy and explicit user constraints permit.
- Report the outcome concisely: what changed, relevant validation, PR link, Codex review disposition, and merge confirmation.
- If a real blocker prevents completion, report the current branch, worktree, PR, completed checks, exact blocker, and next required action. Describe the task as blocked, not completed.

## Native trails follow-up validation notes (2026-10-05)

- Current0042 host253/253 andASan/UBSan253/253 pass;42patchesapply; scoped review fixes viewport and UV-map state errors. Direct authored-state test covers20 animated geometry-free frames; full preset fidelity remains separate. First-frame blur fixture can emit a macOS zero-texture warning; image/GL assertions pass.
- Automatic quality JVM suite42 tests passes (FPS/memory/migration/budget). Release tooling82 tests passes. Revalidate after final integration/review changes.
- Focused actual-AAR workers: `tools/native-trails/README.md`; no full-corpus claim. Released2.3.3 Native/capped AARs are local historical controls only. Native AAR Acid4K smoke480frames passed. Instrumented comparison, liveAM6, finalCI/Codex/merge/release remain required evidence, not established by these host results.
- Owner authorizes awake rootedAM6 at192.168.50.80 for live debug/profile in this task. Verify current Android user and media-session state3; never wake remotely; restore task properties/profile preferences. Initial link briefly connected then went offline before player/user queries.

Experimental analyzer validation uses paired current adapters through
`MILK_TEST_CURRENT_BINARIES`, `MILK_NATIVE_READER`,
`MILK_NATIVE_RANDOM_BINARY` and `MILK_NATIVE_RANDOM_ENGINE_SOURCE`. Historical
source/translation fixtures live in `tools/milk-analyzer/fixtures/historical-profiles`;
keep their request/payload/engine/header identities intact and retain real native
EEL/installed GLSL checks. Normal tests do not require another worktree.
Use this task's `build/preset-lab-venv`; keep transport/effective audio hashes distinct.


Experimental source predictor integration (2026-10-06): keep native bare `*` helper
input/resultfloat32 conversion distinct from raw compound `*=` integer/domain
semantics. Historical THREE/TEN gates use2.3.8; the sealed randomized100audit uses
canonical published2.3.11 (byte-identical2.3.10). Do not reinterpret their observable
scores as pixel accuracy, calibrated probabilities or shipped mood-index validation.
Source adapterCMake accepts `ENGINE_IDENTITY_FILE` or defaults to the identified
engine build's `build-identity.json`; pass `-DSANITIZERS=OFF` for non-sanitized archives.
Never rebuild adapters inside a frozen audit directory; use a new build location.

Source feature integration (2026-10-07): `geometry_features.py` computes custom-shape
vertex trajectories without display fields; speed/acceleration/jerk are sampled
divided-difference estimates, not visibility or whole-domain smoothness proofs.
`source_features.py` keeps strict geometry evidence separate from source-field
simulation, preserves units/unknown support and hashes the declared context.
Do not promote missing motion to zero or relabel native beta descriptors as source
evidence. See `tools/milk-analyzer/SOURCE_FEATURES.md`; shipped mood indexes remain
on their original beta identity until a separately validated migration.
Palette/event evidence uses `palette_features.py`: no hue meaning for achromatic
queries, fixed circular entropy bins and explicit weighting/sector policy.
Keep correlated transition records and their positive durations intact when
caching; local/colour change rates are not flash cycles. Same-position changes
do not rule out motion crossings. Simulated-display values retain mode B evidence.

Source49 predictor policy (2026-10-07): `engine_profiles.py` pins published2.3.15's
49-patch digest and versioned shape/blur/zoom/wave/display math. Keep exact-source
selection guards and historical profiles. Decode native reader IEEE tags only at
known consumer boundaries; preserve gamma/echo-zoom min/max order and skip unused
wave inputs after mode omission. `test_core2315_wave.py` uses prepared source49 CPU
adapters (`MILK_TEST_2315_BINARIES`); CPU checks are not published-AAR JNI appearance
certification. Keep the standard AAR as the native reference, not the CPU archive.

Cached source scoring (2026-10-07): `source_classify.py` consumes source feature
records, with mode B allowed only explicitly. `mood_scoring.py` preserves missing
components as intervals, checks context/domain identities and applies strict Chill
bound declarations; it does not prove those bounds or substitute partial shape
motion for complete preset motion. `mood_profiles.py` contains editable assumed
genre/viewing defaults; optional70+first-use defaults never override explicit tastes.
See `tools/milk-analyzer/SOURCE_SCORING.md`. A one-frame exact2.3.15JNI control is
bounded loading/readback evidence; published appearance and index calibration are
separate. Keep all shipped beta identities/indexes unchanged until validated migration.

Strict extraction (2026-10-07): `source_extract.py` is the no-display-frame entry
point. It runs source equations, custom-shape trajectories, sparse warp queries
and isolated typed shader-colour queries. Do not promote spatial samples into
screen-area proofs, query displacement into visible speed, or scalar recurrence
estimates into a preset proof. `source_transport.py` supplies restricted inverse
affine transport/linear decay helpers. `SOURCE_MATH.md` pins the user's beta guide
and original `~/Scripts/milkdrop2` reference, keeping original intent, historical
defects and TV policies distinct. Review the mathematical reference before filling
missing data; do not use an image classifier as the strict path's fallback.

Published runtime binding (2026-10-07): numerical runner CLIs require
`runtime-java.json`, prepared with `tools/milk-analyzer/java_runtime.py` as documented
in the analyzer README. Verification rebuilds DEX from the exact AAR classes and
hashed D8/platform/helper inputs; native libraries are checked against their AAR
ABI. Keep private runtime snapshots alive through provenance/deployment/execution.
Do not replace this relationship check with independent file hashes or apply new
binding claims retroactively to historical evidence. Local real-D8 checks passed
with build-tools36.1.0; an absent SDK/JDK skips those compiler tests explicitly.
Freeze scorer sources before preflight, compare with import hashes, and reject
source changes before result persistence. Model identities hash the once-read
model bytes. Source edits require a fresh scorer process.
Cached mood scoring and feature-record creation use the same import-checked
source guard. Scores record the frozen production-module map; the classifier
rechecks it before atomic result replacement. Do not label loaded code with a
late filesystem digest or silently accept an edited scoring module.
Source-field forecasts privately copy material/noise banks together, preserving
shared array aliases. `materials_sha256` uses the effective decoded float32 arrays
and manifests under `effective-texture-arrays-v1`, including delegated procedural
sampling. Revalidate before returning; do not substitute unchanged file manifests
for the texture bytes actually consumed. Historical material identities stay sealed.
Pass observers private frame copies; callback edits must not change retained
frames after descriptor calculation. The opt-in GLES300 highp infinity policy
applies only to supported custom-shader math and normalized output, not mediump
warp coordinates. Keep NaN/pow/FTZ/sign and sampler-domain negative controls.
Copy compatibility evidence at forecast entry. Longer equation schedules may
declare a finite `equation_timeout_seconds` in (0,3600], default60; preserve
deadline failures and distinguish wall-clock cost from the predicted duration.
Bind waveform/image-decoder/equation outputs to a pre-execution binary digest.
Resolve reader paths and reject changes during request preparation or execution;
forecast/strict parsing and execution share identity; historical standalone
equation diagnostics retain distinct parser/executor digests. Do not
rebuild task adapters during active predictions.

When declaring Android noise clock inputs, use the explicit libc++ microsecond
period and active-bank generation timestamp. JNI replaces the initial bank when
setting texture paths on the first preset draw; that bank uses the first-frame
clock. Establish the sampled bank’s epoch before crediting paired controls.
Forecasts reject seed/clock mismatches; preserve discarded and active banks separately.
Never overwrite frozen source descriptors with comparison-derived labels.

Source parsers and random adapters execute private snapshots of their hashed
bytes. Corpus parsing freezes each authored source and rejects a reader digest
that differs from the corpus identity before creating a cache row.

Paired production noise must use the explicit raw-clock export policy and
effective per-texture generator seeds. The default exporter retains Preset Lab’s
subsystem/dimension seed mixing; it is not a production clock-seed bank. Verify
the private instrumentation identity before reversing that mixing.

The predictor’s exact50-patch2.3.16 identity shares49-patch scalar/drawing
policies while retaining distinct source/archive/AAR/Java identities. Cold
bundled-load compatibility does not model cross-pack transitions or cache resets.
Prepare source50 adapters separately; preserve older frozen binaries and grades.

Audience review exports require native/AAR and reproduced-DEX binding metadata;
verification also checks actual embedded ARMv7 native/classes bytes. Independent
runtime hashes alone cannot certify an exported review collection.

Before freezing temporal colour prose, validate the claimed RGB/area predicate
on every stated source frame and list exact phases when colour alternates.
Preserve an incorrect frozen sentence as a prediction miss; do not reinterpret
it after viewing the native result.

For new source comparisons, declare the motion-window reporting policy.
Coverage-gated speed requires >=3 supported transitions and >=50% temporal
coverage; retain sparse samples as diagnostics, never replace unknown speed by0.
Use the same frozen policy on source/native arrays; preserve legacy evidence.


Predictor maintenance (2026-10-07): the task branch qualifies unreleased4.2 source
adapters against published core v2.3.22; v2.3.23 AAR bytes were downloaded and
verified identical (SHA256 `c8b93297aa84e6e5c1e860b7ef136fb84deb1ef946c4f66dd1863f1bd9379d65`).
Restore the declared native case-insensitive setting policy with
`scene_equations.source_settings` at public consumer boundaries after JSON reload;
retain raw lowercase parser payloads and historical case-sensitive behavior.
Unknown explicit policies reject. Exact CORE2322/GLES300 custom-wave smoothing and
blur-FMA controls are numerical backend qualifications, not full visual certification.
See `tools/milk-analyzer/fixtures/core42-setting-key-lookup-repair-2026-10-07.json`
and `core2322-blur-arithmetic-repair-2026-10-07.json`. The randomized goal remains
20rounds of3presets/30frames,60consecutive100scores; preserve original failed
predictions and give retrospective repairs zero streak credit. No main merge is
authorized yet.

Forecast explanations must inspect `source_proofs.untouched_main_q_components`
before asserting active shader effects. Presence of a texture sample is not proof
of visible influence: zero coefficients, inactive branches and framebuffer clipping
can remove it. Preserve original failed narrative grades even when predicted RGB
already matches; retrospective explanation repairs receive no fresh streak credit.


Original patch0010 animation witness (2026-10-08):
`tools/milk-analyzer/witnesses/patch-0010-aurora/` contains a deterministic builder,
SOL/LUNA MilkDrop files and distinct PNGs sharing one basename. Build with
`build/preset-lab-venv/bin/python tools/milk-analyzer/witnesses/patch-0010-aurora/build_witness.py`.
Shape0 performs the per-frame named-image lookup; shaders never cache that emblem.
The matched host sequence changes roots at20, soft-loads at21, resets at40.
Published-AAR30frame creation forecasts and source-ablation120frame ownership checks
are separate; the latter removes only0010. Both ablation roles repeat exactly and
first differ at20. See the fixture README and verification-summary.json. No random
streak credit is granted to authored/retrospective controls.


Predictor PR57 migration (2026-10-08): exact14-patch core2.3.25 source adapters
preserve historical profiles and add static fShader legacy tint, post-volume
mode1 alpha1.25 and open spiral topology. Require matching source/archive for
live waveform adapters. Full published AAR SHA256
`f9c920b76a616a24b6754d350db4eac73cd425aef4106474a3dadea3df4579c3`
is bound to reproduced Java DEX and ARM64 JNI. Five of six visible30frame controls repeat
twice with exact RGB8 agreement; the normal spiral retains four differing pixels
in frame24 pending quad arithmetic/raster diagnosis.1,506 tests and78subtests pass. This is bounded
qualification with zero random acceptance credit. Do not broaden GPU arithmetic
profiles without controls or resolve negative nonunit zoom powers by guessing.
See `tools/milk-analyzer/fixtures/core2325-legacy-tint-mode1-controls-2026-10-08.json`.
The current target remains20perfect3preset/30frame rounds and no main merge.


Predictor viewport follow-up (2026-10-08): the four-pixel spiral mismatch is
source coordinate loss, not an AAR defect. Preserve projected clip precision
through float64 viewport coordinates before the unchanged fixed-grid ties-to-even
snap. `retained-clip-window-v1` is scoped to built-in waves with exact2.3.25/GLES
quad/grid admission; historical defaults and other draws retain their original
path. Reject a missing grid even for degenerate strips. Six repaired30-frame
controls match all RGB8 samples in two fresh unchanged-AAR repeats; original
failures remain immutable, with zero random acceptance credit. See
`tools/milk-analyzer/fixtures/core2325-line-viewport-coordinate-repair-2026-10-08.json`.

Final viewport-repair validation:1,510 prepared analyzer tests and78subtests pass;
strict MkDocs passes. Repairs remain separate from randomized acceptance.

Always compare predictor/renderer discrepancies with the read-only original
MilkDrop2 source at `/Users/jneerdael/Scripts/milkdrop2`, as explicitly required
by the user2026-10-08. Record source commit/file hashes and distinguish authored
semantics, existing TV policies and observed GPU precision. Source inspection
does not establish a Windows renderer appearance match.

Predictor understanding requirement (user2026-10-08): derive and explain the
behaviour of a reference operation before implementing it. Do not copy opaque
MilkDrop/projectM routines. Use controlled simulations to isolate unknown
operations, specify types/casts/order/state/units, and compare numerical inputs
and outputs. Preserve unresolved domains until supported by evidence. Primary
reference: `/Users/jneerdael/Scripts/milkdrop2_v2.25c_OPEN_SOURCED_20130514_orig_code`.
Its `vis_milk2/milkdropfs.cpp` is byte-identical to the current read-only
`/Users/jneerdael/Scripts/milkdrop2/src/vis_milk2/milkdropfs.cpp` (verified2026-10-08).
The supplied `../milkdrop` alias does not currently exist.


Six-area audit delivery checkpoint (2026-10-08): 33 I/M library handoffs are
ranked and hash-verified in `/Users/jneerdael/Downloads/projectm-library-audit-handoffs-2026-10-08/`.
D01 corrects border attribution only; do not repair library-owned M02 math here.
U01 authored/native operators and coordinator are experimental building blocks;
the full forecast high-resolution guard remains until integration and latest-AAR
qualification. Preserve separate init/frame shader canvas inputs, authored
recurrence, native prepared-geometry replay, blur ages, shared authored UV state
and positive-versus-zero gain-class resets. Exact prepared suite: 1,565 tests and
92 subtests pass; strict MkDocs passes. See the analyzer README and
`docs/superpowers/plans/2026-10-08-six-area-audit-delivery.md`. v2.3.27 is the latest
downloaded full AAR; no runtime qualification of it is claimed at this checkpoint.


U01/core2.3.27 integration checkpoint (2026-10-08): source-pr59 prepares the exact
15-patch engine (`65313919430bd6d1531292b405463d8ec400a44bcfddfb1eb808fbaba16b5ad0`).
Three producer guard rejections were reproduced, then exact live-wave/cold-audio/raw-noise
admission controls pass. Full prepared suite: 1,577 tests and 92 subtests pass.
The full forecast has an explicit experimental authored/native route conditioned
on declared successful allocation; default high-resolution ordinary/diffusion
and uncertain allocation remain guarded. Preserve one equation/geometry execution,
shared shader random banks, native composite and physical display blit. Negative
CPU zoom powers use a separately versioned policy with host producer attribution;
source inspection does not certify Android bit parity. Full published 2.3.27 AAR
numerical/high-resolution qualification remains open. See the analyzer README
and `profiles/published-core-v2.3.27.json`. Do not clear U01 from tests alone.


Six-area audit delivery completed (2026-10-08): D01 attribution fixed;33 I/M
handoffs ranked/hash-verified in Downloads; U01 resolved within explicitly
allocated pinned2.3.27 Apple GLES authored/native contexts. Four full-AAR
30framecontrols pass(maxRGB8 0/1/1/1); six isolated blitRGBA8 comparisons match
exactly. Feedback control effectivefDecay1 (duplicate .97 notselected), zoom1.002,
30distinct fields and single shared-register shape update. Analytical blur/motion/
gain-switch evidence is separate. Preserve resource/domain guards and appearance
uncertified flag; no universal GPU/preset/transition or new random-streak claim.
See `docs/superpowers/evidence/six-area-audit-delivery/DELIVERY.md` and the pinned
published2.3.27 profile for exact evidence/limitations. Do not merge main based
on this audit: the user's original visual prediction acceptance remains separate.


Export contract documentation (2026-10-08): `tools/milk-analyzer/EXPORT_CONTRACT.md`
and the user-guide `predictor-export.md` document the current schema1 envelope,
11 strict/47 simulated feature keys and unversioned forecast diagnostics. The
schema/catalog/real examples in `export-contract/` describe existing producers;
they do not introduce a semantic scene export. Guide assets mirror those files.
Guide/config/dependency sync was taken from remote main `af164a97896646427f971ecbed8161f8d35c2fec`
before the export page/navigation was added; no analyzer or engine merge occurred.
Keep future semantic effect/element descriptors explicitly versioned and separate
from statistics, preserve unknowns, and never infer a causal beat response or
fractal/tunnel identity from field aggregates alone. Update the source reference
and guide copy together when the actual export changes. Docs use main's pinned
MkDocs1.6.1/Material9.7.7 requirements.


Offline corpus export maintenance (2026-10-09): `tools/run-preset-corpus.command`
executes `tools/milk-analyzer/preset_corpus.py` in the prepared Python environment.
Defaults are60actual15Hz updates at854×480, two workers and paired ZIPs every100
completed attempts in Downloads. Source adapters are pinned to published2.3.29's
16-patch identity; this CPU forecast does not render the AAR or consume captured
frames. Computed records retain47keys/null unknowns; unsupported/error/timeout
cases retain null records. Configuration/input hashes bind resumable output;
changed identities stop the run and require a new folder. No AI/device operation
is required. See `tools/milk-analyzer/CORPUS_EXPORT.md` and the user-guide
`preset-corpus-export.md`; do not infer30Hz fidelity or no-flash certification.


Corpus allocation fix (2026-10-09): quad strips and independent motion-vector
quads share one ordered triangle batch per draw. Keep vector endpoint topology,
triangle blend order and per-blend quantization unchanged; `test_quad_batching.py`
compares against ordered per-quad raster calls and guards full-frame allocation
counts. Never change code under an active checksum-bound corpus run. A fresh
output folder is required for the changed code identity. The prepared isolated
`predictor-corpus-batching` worktree shares the old Python environment and pinned
source29 adapters read-only; keep those dependencies during execution. See
`CORPUS_EXPORT.md` for the restart procedure. No AAR, presets or native numerical
producer code changes are part of this fix.


Predictor memory repair (2026-10-09): evaluation cache/binding/contexts and local
input/sampler references are released in finally; exact read-only lane/state
contexts are interned, with loop updates retaining unique epochs. Keep pixel
arithmetic, domain guards and caller ownership unchanged. `process_memory.py`
monitors only worker-owned groups, using Darwin physical footprint/Linux resident
plus swap; ps queries have a2s timeout. Corpus memory budget failures retain null
features and explicit errors. Fatal diagnostics use unique timestamp/PID JSON
files. These are sampled resource safeguards, not a universal memory/performance
bound. No unchanged failing full-corpus retry is required to verify the fix.

Source31 migration checkpoint (2026-10-09): remain in `predictor-memory-repair`.
PR67 merged into `bug/predictor-grid-memory` as6680a910; continuation is on
`feat/predictor-static-output-bounds` in the same worktree;
do not create another worktree or merge the
experimental predictor to main. The complete published2.3.31 AAR, both libraries
and 9,606 preset/74 texture bytes are hash-verified; source31 adapters live under
`build/preset-corpus/source31/adapters`, separate from immutable historical
adapters. New `test_core2331_*.py` controls cover the18 release patches using
versioned actual-path policies. Full published-AAR runtime/appearance qualification
remains separate. Explicit conditional/packed motion backends must not inherit
Apple float-path evidence. Historical configurations retain their source29 identity.
Published2.3.33 is byte-identical to2.3.32/2.3.31 (fresh download, SHA256 and direct
comparison verified); use the33 publication/profile with the same qualified
source31 adapters. See the analyzer README, published-core-v2.3.33 profile
and `docs/superpowers/plans/2026-10-09-source31-static-families.md`. Source-based
effect-family research is available with its separately versioned detector/export.

Static family maintenance (2026-10-09): `effect_families.py` detects contributing
typed shader/EEL constructions without numerical execution or frames. Keep live
lane/loop/output masks, exact profile conditions, unknowns and finite work budgets.
`effect_family_export.py` provides an AI-free cached parser/detector CLI and paired
100-preset ZIPs; parent import hashes require fresh-process operation after edits,
not arbitrary hot reload. The100-preset cold/cache benchmark is25.61s/.704s;
it is timing evidence, not corpus classification accuracy. Read
`tools/milk-analyzer/EFFECT_FAMILIES.md` and the guide's `predictor-effects.md`.

Source temporal maintenance (2026-10-10): `source_temporal.py` derives nominal
affine-time rates through typed scalar vector projections. Preserve lane order,
explicit constant float32 conversion and unknown dynamic integer/sample/state
inputs. Failed nonfinite literal narrowing must not use the pre-conversion
double value; uniform literal folding in `effect_families.py` returns unknown
on the typed evaluator's `UnresolvedMath`, without changing runtime math.
Authored shader arithmetic carries `numeric_domain=shader-float32`; preserve
that detail through component projection and explicit scalar source casts.
Literal folding must not erase overflowing terms as double-valued cancellation.
See `tools/milk-analyzer/SOURCE_APPEARANCE.md` and `test_source_temporal.py`.

Source34 preparation (2026-10-10): the exact full published v2.3.34 AAR is
hash-verified locally. Matching source34 adapters retain their own commit,
35-patch identity and archive hashes. `engine_profiles.matches` remains strict;
`math_matches` admits only the explicit source31-to34 math lineage, without AAR
byte equivalence, observed-binding or runtime credit. Random contracts require
matching actual parser/translator/contract identities; cold audio/RNG policies
use separate34 names. Static export accepts an explicit source34 reader and
preflights its actual identity. Defaults remain source31/published33 until the
candidate runtime gate passes. `candidate-core-v2.3.34.json` is unqualified.
The isolated SDK emulator failed SIGILL in host `init_cache_info` before loading
the AAR; do not retry unchanged or operate shared devices. See
`docs/superpowers/evidence/predictor-core2334-migration/README.md`.

The numerical corpus now defaults to source31 with a separate full published-AAR
and profile identity. Latest publication output suffix `-core2333` prevents
relabeling historical31/29 rows; the `core2331` target names the unchanged engine
source policy, not the publication filename.
`corpus_worker.py` keeps47 numeric fields and separately exports `effect_analysis`,
including explicit failures. Exact source31 noise admission retains all six
byte-identical source29 generators. No full numerical corpus rerun was started.
Three full published-AAR/public-JNI30frame128×72 controls pass at RGB8errors0/1/0;
see `docs/superpowers/evidence/predictor-source31`. Do not claim whole-preset or
whole-corpus appearance certification from those controls.

Uniform reduction experiment (2026-10-09): forecast domain
`shader_work_policy=uniform-proof-v1` hoists statically uniform pure shader DAGs
using the same one-lane numerical interpreter; default remains `full-grid-v1`.
Do not hoist sampler coordinate roots/consumers, loop state, effects or unknown
operations. Keep mutable callback/cache ownership and selected domains intact.
The next metric-routing work must preserve47field meanings and nulls; geometry
speed must never stand in for optical-flow speed. Read the static-metric-routes
research and `docs/superpowers/evidence/predictor-uniform-reduction/README.md`.

Source shape motion maintenance: `source_motion.shape_vertex_motion` combines
continuous nominal centre/radius/angle derivatives under a constant side-count
and finite-conversion premise. Exported NDC speeds are conservative geometry
bounds, not visible motion or mood certification; keep audio/state/nonlinear
controls unresolved and preserve original MD2/native projection references.
The latest observed v2.3.35 full AAR is byte-identical to the verified v2.3.34
artifact; `profiles/candidate-core-v2.3.35.json` retains runtime-unqualified
status. Explicit source34 analysis is conditional; no old runtime certification
is transferred to this artifact.

EEL static equality maintenance: `_EEL.operation` lowers EEL equal to
`eel_equal`; `_number` uses finite-operand `abs(a-b)<0.00001`. Retain strict
threshold boundary and exact shader `equal` separately. Do not route an EEL
control DAG through shader-only numerical evaluators as an EEL execution proof.

Source instance motion: `source_instances.shape_instance_motion` substitutes
the original native index and preserves state/audio inputs. Literal sin/cos
are nominal double formulas. Keep processed/known counts distinct and group
speed null unless every authored instance is processed with a known bound.
Expansion/node/depth budgets are source-tool limits, not native count clamps;
retain partial evidence and isolate per-instance symbolic caches.

Compound motion maintenance: `source_control_bounds` derives continuous
nominal time envelopes/rate bounds; `compound_time` keeps periods unknown.
Preserve exact-versus-bound metadata, cusp/unknown regularity in all joins,
EEL denominator guards and rate-underflow abstention. These are not native
precision, visible-motion or mood certificates. No input/frame sampling is used.

Source material temporal maintenance: preserve native float32 double-fmod
colour conversion separately from MilkDrop2packed bytes. `material_temporal`
wrap candidates are conditional envelope risks with an explicit rounding
margin, not visible flashes or complete no-flash certificates. Border gating
uses raw double alpha and the native float32 threshold; skip disabled-border
channels in consumed-risk summaries. Keep missing/nonfinite domains unknown.

Source value-envelope maintenance: `scalar_value_envelope` reuses the bounded
control walker in value-only mode. Named finite-input premises must be exposed;
internal unbounded intervals are not infinity/defaultzero input values. Reject
known overflow/singular/opaque/uninitialized cases and serialize finite bounds
only. Value envelopes never infer unknown rates, continuity or mood readiness.

Source fill-envelope maintenance: preserve existing exact point integrals.
`source_fill_envelopes` bounds nonnegative fan RGB-times-clippedAlpha using
second moments and valid clipping inequalities. Native channel domains and
nominal radius-area ranges remain conditional; textured input, missing channels,
overlap union and final visibility stay unresolved. No point brightness/mood
score follows from an upper bound.

Source copy-lattice maintenance: preserve sampling-map bases and wrap policy.
`source_copy_lattice` derives periodic coordinate preimages/density and fixed-
matrix offset motion, not visible copies or screen trajectories. Unknown wrap
is conditional, mixed/singular maps stay unknown, and positive origin-rate
product underflow must not create a stationary certificate.

Source native-warp maintenance: `source_native_warp` exports nominal uniform
feedback sampling recipes from float32-converted literal controls. Preserve
zoom/stretch/wave-warp/rotation/translation/aspect/texel ordering and
runtime aspect/texel inputs. Preserve selected legacy/custom spatial signs;
unresolved nonzero warp branches stay unknown. Radial/dynamic/singular/nonfinite controls stay
unknown. Affine identity/area describe only the affine component; procedural
warp, sampling interpolation, content, display motion and moods remain separate.

Source warp-transport maintenance: `source_warp_transport` joins supported
native float32 control envelopes into uniform affine scaling/area bounds.
Require zoomexp=1, nonzero sign-definite zoom/stretch domains and finite
reciprocals. Prove uniformity through readonly input dependencies and pure scalar
operations; dependency-free random/memory operations are not uniform proofs.
Keep independent control rows even when aggregate transport is unresolved.
Principal scales are aspect-corrected, not display-space. No procedural-map
Jacobian, visible motion or mood certificate follows from these bounds.

Source radial-zoom maintenance: `source_radial_zoom` consumes the independent
positive uniform zoom/zoomexp rows, even when later mesh controls are spatial.
Preserve native nested-power order and nominal aspect-corrected radius range.
Guard inner/outer float32 power and reciprocal endpoint domains; negative zoom
stays unresolved here. Nominal derivatives and sufficient no-fold results do
not certify GPU rounding, visible tunnels or the complete transformed map.

Source sampling-displacement maintenance: `source_warp_displacement` integrates
nominal backward-map affine displacement over uniform original UV, keeping
aspect-corrected units and texel alignment separate. Constant RMS coefficients
and varying-control triangle bounds are not forward-feature/display speed.
Keep procedural warp as a distinct envelope; validate warp-scale reciprocal
even for zero warp. Preserve invalid/unknown uniform domains and finite bounds.


Source phase-provenance maintenance: `_EEL` tags bare/persistent scalar inputs
with equation_phase/value_binding, preserving unknown state values and named
finite-input assumptions. Uniform transport may consume main/init snapshots,
but not pixel-local/shared-register state or random/memory calls. Preserve Q
copy/reset versus pixel mutation. Geometric dependency tests exclude scoped
main locals named like coordinates; shader and actual pixel coordinates keep
spatial meaning. Use the per-analysis spatial cache; no state execution occurs.

Source built-in wave-material maintenance: `source_wave_material` models
float32 RGB clamps followed by optional max normalization above0.01; do not
apply custom-shape modulo. Preserve mode1alpha boost, mode2/5reference-size
attenuation, mode3authored-alpha replacement/native treble input, and unbounded
volume multiplication before final clamp. Invalid volume config affects only
its enabled domain. Gate candidates are not visible flashes; material draw threshold
applies to quad and hardware wave paths before scaled-dot alpha adjustment. Keep missing audio/history and dynamic flags
unresolved, independent from constant vertex colour or raw channel timing.

Source time-switch maintenance: `source_time_switches` derives nominal schedules
from supported sinusoidal threshold and affine real-floor sites. Preserve
signed phase and amplitude, strict/tangent domain guards, cast/outer-transfer
uncertainty and event-site versus whole-control scope. Current EEL int/floor
share native floor; shader int casts remain distinct. Keep clock resets and
sampled/native precision separate. Bounded nonexhaustive scans and per-analysis
cache avoid recursion via the internal motion-control switch-scan opt-out.

Source offline-compile evidence maintenance: `effect_family_export` optionally
consumes `--compile-manifest` through `source_compile_manifest`. Bind exact
preset/shader/request/profile/engine/archive/compiler hashes and preserve
declared sampler assumptions. Seals provide integrity, not producer identity
or GPU/texture binding certification. Missing cases remain unknown; native
driver and runtime texture flags must stay false. Freeze manifest bytes across
each preset and before result commitment, including the final case. The source
exporter itself still only invokes the native reader, never compile/render/eval.

Source Q-uniform maintenance: `main_q_component_fields` binds shader _qa.._qh
to q1..q32 after main-frame evaluation, before per-pixel Q writes, preserving
double-to-float32 upload. Constants convert only at this boundary; dynamic
programs remain narrow symbolic fields and known nonfinite uploads unknown.
Keep Q init reload/reset and shader-local shadows separate. Preserve native
uniform-role provenance in expressions/audio bridges; Q-mediated scalar gain
does not become certified across the upload boundary. No equation execution
or observed GPU binding follows from this source contract.

Source varying-feedback maintenance: `source_feedback_envelopes` factors only
supported affine-in-main RGB expressions, preserving per-site coefficient
envelopes and fixed-coordinate infinity-norm bounds. Reuse scalar_value_envelope
with explicit locally derived input_domains for native narrow ranges; expose
declared domain premises and reject nonfinite upload/invalid domains. Nonlinear,
unbounded, singular, blur/history and unresolved paths remain unknown. Keep
colour-only contraction/half-life distinct from native rounding, sampling-map
sensitivity, storage/drawing/detail and actual persistence or mood readiness.

Source texture-envelope maintenance: `source_texture_envelopes` consumes the
existing affine texture-colour transfer matrices, using exact binary-rational
endpoint/norm sums. Keep independent RGBA sample premises and declared history/
external source identities distinct from observed bindings/fallbacks. Coordinate
terms or unknown constant offsets withhold RGB boxes without erasing valid
input norms. Main/blur history norms never become shared-recurrence contraction
or visible persistence, palette, brightness or mood claims.

Source nonlinear-colour maintenance: `source_nonlinear_colour` reuses sample
substitution and scalar_value_envelope for declared unit-RGBA inputs. Value-only
clamp/power/root/lerp/dot support must preserve finite/domain guards, patched
shader abs lowering and pow1 sign exception. Native Q uploads require finite
endpoint conversion before downstream clamps; unknowns cannot become zero.
Keep partial channels and source assumptions explicit. No gain/continuity,
full feedback, displayed flashing/brightness/palette or mood certificate follows
from raw colour ranges. Interpolation weights are not implicitly clamped.

Source audio-response maintenance: `scalar_response_envelope` reuses nominal
scalar calculus with selected named input rates1 and other finite inputs held
fixed. Route aliases include EEL names and scalar packed shader-band members.
Do not replace an unknown cross-band amplitude with an assumed audio range.
Dynamic casts/narrowing, thresholds, singular domains and unsupported effects
retain null bounds. Sufficient partial response is not a minimum/typical gain,
audio time-rate, recurrent-state derivative or final screen/mood certificate.

Source oscillatory-band maintenance: `source_forms.spatial_oscillatory_band`
uses constant-affine phase in one native UV basis or the radius lane alone.
Additive family/form code10 exports nominal raw generator period, signed
normal and uniform phase controls, not visible stripes/ring count or dominance.
Keep coordinate-only sampling oscillations separate: colour-data traversal
stops at sample nodes, retaining shared expressions that also reach RGB/masks.
Do not infer exact analytic circles from the interpolated native radial varying.

Source periodic-sampling maintenance: `source_periodic_sampling` models a
uniform-affine lookup baseline plus scalar sine/cosine waves with uniform
symbolic amplitude/frequency/phase controls. Retain allsix native spatial
columns, memo source-node references and complete coefficient/offset programs.
Guard known invalid domains, spatial integer casts, types and export budgets.
Exact constant Jacobian row sums support a nominal unwrapped no-fold condition
only for identity baseline and one UV basis with bound below1. Dynamic/mixed
cases remain uncertain; no actual fold, screen speed or mood claim follows.

Uniform-wave distribution uses512visits/depth64 and64result terms to expand
shared uniform multipliers/divisors over add/subtract branches. Preserve signed
weights and original-graph domain checks; never linearize spatial-wave products
or discard terms when budgets fail. Zylot's original warp is a source control
for amplitude and spatial-frequency audio routes; no captured appearance credit.

Ripple-envelope maintenance: `source_ripple_envelopes` projects uniform scalar
coefficient lanes with original-node retention and explicit float32 upload
endpoint domains. Propagate finite premises and per-axis unknowns. ExactFraction
amplitude/gradient bounds round outward; overflow withholds only the affected
bound and positive underflow cannot certify zero. Mixed/radial or nonidentity
maps do not receive an identity UV no-fold claim. Extent/spatial deformation
does not establish time-rate, perceived intensity, feedback or a mood.

Declared source-input scenarios are opt-in through effect_family_export
--input-scenario. Validate named engine audio intervals and explicit shader
canvas inputs; do not infer canvas from display size or bind EEL custom vol
registers. Preserve unconstrained descriptors and add separate ripple scenario
bounds. Bind cache/run records to semantic/raw-file hashes and reject changed
files during runs. These declarations are assumptions, never observed runtime
inputs, music/genre guarantees or native appearance certification.

Nonlinear sampled-offset maintenance: lift direct RGBA samples as explicitly
bounded local parameters, never spatially uniform images. Reuse typed scalar
projection/domain guards; retain per-axis unknowns and original sampling sites.
Only offset bounds with sample-independent spatial coefficients qualify; image
dependent scale stays unknown. Check original zero-product/singular domains
before certification. Ranges do not establish image gradients, full feedback,
visible motion or moods; input scenarios do not implicitly override this model.

Sample-offset scenarios: export additional bounds in `scenario_offset_envelope`
with the validated scenario hash. Preserve unconstrained offset results and
independent local RGBA domains. Missing canvas/bands remain unknown; scenarios
must not suppress singular image domains or image-dependent spatial coefficients.

Coordinate interpolation maintenance: distribute scalar lerp only with uniform
weights for ripple extraction. For affine spatial coefficients use A+t*(B-A)
and preserve an explicit offset lerp. Sampled local weights qualify only after
sample substitution and sample-independent baseline verification. Keep original
zero-weight branch domain checks; nominal algebra does not certify GPU rounding.

Explicit planar folds: distinguish frac from triangular mirror kernels; retain
per-axis partials, kernel range/derivative versus output scale, and dynamic phase
programs/audio routes. Constant inverse repeat lattices require one UV basis and
finite invertible phase coefficients. Preserve original-domain checks; no tile
count, native precision, final kaleidoscope or mood credit follows.

Typed outer fold inspection (2026-10-10): `source_field_index.py` reuses existing
semantic children and analysis-local caches to attach `outer_fold_structure` when
numeric fold projection remains unknown. Preserve the old descriptor and its
unknown/range fields; opaque captures cannot earn quantitative or mood credit.
Index paths/`semantic_child_slot` are semantic traversal locations, not authored
AST slots. Cache only root/stage-bound index results in the parent analysis; keep
optional inspection work/memos in a private bounded cache so caught failures do
not exhaust later ordinary queries. Retain local budget/domain/native-selection failures. The implementation
is original Python inspired by the external indexed-query experiment, with no
copied glsl-transformer AGPL source or Java dependency. See
`tools/milk-analyzer/SOURCE_APPEARANCE.md` and the glsl-transformer validation report.

Quantized colour: floor/frac provide value enclosures only, never continuous
rate or flash certification. Preserve conservative integer-seam padding and
known-invalid/native-upload guards. `scenario_colour_envelope` supplements the
ordinary nonlinear stage record with a scenario hash; local texture premises
remain independent and missing bands/nonfinite Q inputs stay unresolved.

Retain caller-declared input premises through colour native-upload projection;
exclude only local sample/derived placeholders. Convert floor integer endpoints
outward before publishing float bounds; accepted large integer domains must stay
enclosed in both signs.

Direct colour/audio response: discover bands after sample substitution and hold
independent local samples fixed. Reuse nominal per-channel response bounds and
scenario premises. Track band dependencies of derived native upload placeholders;
withhold affected gains rather than treating those values as constants. Empty
colour routes do not prove absent coordinate/feedback/audio behavior.

Continuous response calculus: clamp/saturate are nonexpansive under constant
limits; lerp uses product-rule triangle bounds. Positive constant powers require
finite nonnegative base bounds; exponents below one require a positive minimum.
Retain exact exponent-one identity and numeric/domain guards. Keep value-only
quantized ranges separate from response rates and native-upload taint.

Fixed-predicate response: selected input identities must be absent from a pure,
finite, domain-checked predicate. Bound both branches; retain predicate finite
premises and use maximum branch rate. This is per fixed coordinate/state, not a
spatial-uniformity proof. Reject selected-band switches, quantized/unsupported
predicates and any unresolved branch; keep native-upload band taint separate.

Scenario source-time components: reuse nominal partial-response calculus for
source-time aliases and declare audio/frame/FPS/progress/state held fixed.
Preserve ordinary motion records and remap units explicitly. Keep total rate and
visible speed null; zero partial rate is not stationarity or mood proof. Native
quantized Q uploads/time switches remain guarded; scenarios cannot imply actual
clock, native precision, geometry or feedback qualification.

Vector norms: require matching float scalar/vector widths, preserve scalar lane
identity and distance subtraction. Use component-box hypot for value enclosures
and hypot(component rates) for sufficient norm response, including the origin.
Do not reinterpret a finite norm bound as normalization, positive reactivity,
geometry, feedback or mood proof; singular/quantized components remain guarded.

Scalar calculus memo entries retain (original node, result) and verify identity.
Distance generates temporary subtraction nodes; an id-only cache can silently
reuse stale bounds. Keep the repeated20-distance=210 regression and existing
node/depth budgets. Strong references are required even outside family cache scope.

Normalized colour components: retain the shader domain guard and require a
strict positive padded norm minimum. Typed lane/width checks and signed unit
component bounds are mandatory. Normalization guards discharge only a proved
internal normalized_component; arbitrary/zero/singular/native-quantized inputs
remain unresolved. Rate ceilings are sufficient bounds, not reaction/palette proof.

Activity priority: focus on flashing and physical movement pathways. A constant
feedback rot/zoom is motion per step, not zero speed from a parameter derivative.
Source blackout gates require the same uniform binary multiplier across all live
RGB channels; added backgrounds/spatial predicates do not qualify. Keep source
mechanism/cadence, geometry speed and actual visibility/combined screen intensity
separate. No empty-evidence Chill certification or unsupported mood percentage.

Shape activity rates use fixed barycentric/destination partial time variation:
bound incoming alpha*RGB by alpha_max*colour_rate+alpha_rate*colour_max;
source-alpha-over adds alpha_rate under explicit destination RGB [0,1]. Require
stable modulo/continuity domains, retain transparent centre RGB when perimeter
alpha participates, and withhold textured fill rates. Quantization, coverage,
local modulo/draw-gate hazards and whole-screen flashing are separate.

Shader direct time response varies time/_c2.x/native-render-time together, with
sample RGBA, audio/state/coordinates/frame/FPS/progress fixed. Native time formulas
remain expressions; time-dependent narrow/Q uploads retain taint. Zero partial
rate is not static-image/no-flash proof; texture coordinate/history response and
total displayed variation remain separate. Default/scenario records retain identity.

Affine sampling motion checks supported offset candidates before original-domain
preflight; keep the original Grind budget control and do not raise MAX_FIELD_VISITS.
Use exact rational inverse coefficients for feature velocity in a single basis.
Bilinear rate coefficients require fixed [0,1] texels and actual uploaded W/H;
do not substitute canvas dimensions or give nearest/mipmapped sampling a smooth
bound. Native mesh, texture history, direct RGB and later feedback remain separate.

Nonlinear sample response varies one declared RGBA lane at a time, with all other
inputs/coordinates fixed. Sum Lipschitz columns for simultaneous changes, not
signed Jacobian cancellation. Ordinary float-width coercions follow typed parts;
int/bool/native narrow and unresolved vector sample dependencies stay guarded.
Direct sample colour matrices exclude nested lookup-coordinate chains explicitly.

Nested lookup motion composes per-lane UV gains, linear base-level W/H gradients
and direct RGB gains as nonnegative dimension polynomials. Actual uploaded sizes
remain inputs; native aspectXY [0,1] requires positive finite viewport context.
Keep nonexhaustive/total-bound flags false, preserve quantized/singular/nearest
guards and 64-site/4096-term budgets. No history, direct coefficient-time or
complete feedback/mood claim follows from modeled path terms.

Nearest-time hazards require a declared nearest base-level sampler, positive
nominal lookup ceiling and possible RGB route. Only repeat +constant drift gets
grid-crossing W/H coefficients; speed alone cannot bound oscillatory recrossings.
Direct RGBA gain row sums bound conditional jumps; nested magnitudes stay unknown.
Keep possible local mechanism, texel contrast and verified screen flashing distinct.

Native lookup transport composes aspect-corrected uniform RMS displacement with
affine warp mesh-UV column norms and caller-supplied positive aspects. Composite
and original-UV-only maps bypass it; shader offsets cancel at fixed inputs.
Preserve coordinate-domain guards, exclude texel alignment and pointwise/temporal
speed claims, and keep nearest-main feedback hazards possible rather than observed.

Global mesh-UV certificates use independent coordinate Lipschitz columns over
unbounded finite mesh UV, with original UV/uniforms fixed. Do not invent a UV box
or treat raw frac seam derivatives as global. Typed continuous triangular folds
use outward exact slopes; image-dependent coordinates need full texture chains.
Nonlinear/native scenario composition retains separate identity and default status.

UV-response qualification includes original Grind under the source34 reader,
sealed compile manifest and full declared audio/canvas scenario. Plain source31
tests alone do not cover its budget boundary. Reuse strong-identity uniform facts
inside one analysis; do not raise traversal limits or treat schema-valid unknown
descriptions as preserved structured output.

Radial displacement fallback reuses the existing positive zoom/exponent factor
envelope, with all10native controls uniform and finite; signed stretch must avoid
zero and native reciprocal/warp-scale guards hold. Radial inverse-scale intervals
bound the same-frame operator pointwise before RMS integration. Exact affine
coefficients stay on exponent-one; do not grant new negative-zoom or visible-speed policy.

Spatial displacement uses ONLY native_mesh_reset_input-tagged coordinates and
pure typed formulas; persistent/shared/random/state inputs retain unknowns.
Native float32 endpoint padding must cover reset radius/angle values. Pointwise
control/operator bounds precede nominal RMS integration; do not label them uniform
affine transforms or certify interpolated mesh area/folds/visible speed. Spatial
lookup composition is separate from the existing uniform result.

Channel reset hazards require a complete scalar select between its signal and
constant reset at a literal threshold. Fold only identical nonnull typed branches,
preserve original-domain checks, and exclude continuous/unreachable boundaries.
Require supported nominal continuity with every contributing signal input varied;
value intervals alone cannot justify jumps for floor/integer/boolean signals.
Source jump magnitude is a limiting gap, not a discrete-frame or whole-screen
flash. Sample-driven timing remains unknown; packed shader-clock schedules retain wrap semantics.

Non-affine sampling-time maintenance: reuse scalar coefficient response calculus
with source-time aliases varied together and mesh/audio/state held fixed. Preserve
partial per-axis unknowns and separate scenario identity; never invent warped UV
boxes, inverse-feature velocity or total speed. Exclude sampled-coordinate chains,
retain original-domain checks and keep native upload time taint. Skip dependency
walks only when the taint set is empty; preserve the exact-profile Grind regression
and fixed traversal budgets. RGB gradient propagation remains conditional on
filtering/dimensions and fixed texture contents, not feedback or visible intensity.

Nonlinear feedback-colour maintenance: aggregate all sampled RGBA derivative
columns and feedback sites in RGB infinity norm. Keep fixed-sample gain separate
from the previous-image operator: require valid image-independent coordinates,
nonexpansive main sampler policy, no active blur transfer and no clip/discard.
External lookups can also add image-dependent coordinate response and must pass
the coordinate guard. Preserve per-row unknowns, source alpha semantics and
scenario identity; never infer full stored feedback stability, persistence or
mood from the raw warp sufficient contraction test.

Expanded source audit (2026-10-10): frozen c564bda0 model ran a seeded hash-ranked
2,000-preset sample from 9,606 in 483.54 seconds with four CPU workers. 2,000
terminal exports include 1,995 structured descriptions and five explicit traversal
fallbacks; schema validity includes unknown records. Twenty archives preserve all
2,000 exact source/result pairs and compile proofs are source-bound offline
evidence, not rendering. Keep sample fixed and count affected presets by unique
source identity; do not reroll unresolved cases or infer accuracy from coverage.
Scripts, sealed selection and ranked descriptor/source gaps are recorded under
`docs/superpowers/evidence/source-random-2000-2026-10-10/`. Retain original 100
controls. Loose outputs/proofs are under the matching `build/preset-corpus/`
directory; no duplicated analysis cache is generated by this wrapper.

Typed source projection maintenance: apply `ShaderFields.parts` before selecting
converted lanes, including full-width cast/constructor swizzles. Preserve scalar
numeric conversion nodes and native upload markers; traverse only their consumed
source lanes without recursively reconstructing casts. Keep normalization/matrix
and loop dependencies, invalid component guards and discarded-lane negatives.
Output multiplier conditions use one complete budget-charged causal DAG inventory
with strong node identities per analysis; shared masked/unmasked paths retain
existential semantics and uncached callers retain the prior traversal. Never cache
partial facts on failure or raise traversal limits to hide a lost description.

Shape flashing math: two-state material bounds use fixed barycentrics/geometry
and destination[0,1], untextured inputs and converted endpoint domains. Retain
shared fan weights in quadratic maxima, alpha-clipping fallback, over-blend
contrast and border off-state alpha0. Area weighting is nominal peraspectY and
sum-over-instances, excluding overlap union/rasterization/later feedback. Large
two-state range is not an abrupt-event certificate. Modulo cadence uses supported
affine/sinusoidal source curves and exact strict-boundary enumeration≤16; native
singletons, tangent/native-margin timing, unknown inputs and numeric domains
stay separate. Never sum channel schedules into a visible flash frequency.

Source query reuse: radial/angle presence and sampling-coordinate uniformity
memoize only successfully completed answers within the per-analysis ContextVar.
Retain the original node strongly; sampling uniformity also keys the complete
basis tuple. Keep witness short-circuit semantics, unsafe-node predicates and
unchanged first-query traversal charging. A structured description can still
contain per-field budget unknowns; do not equate it with complete interpretation.
Local feedback-envelope identity caches likewise retain original canonical and
projected nodes until return, including manufactured nested-swizzle nodes.

Blackout colour projection retains original sample objects as leaves; do not
rebuild their coordinate programs to find multiplicative RGB gates. Preserve
typed scalar int/bool conversions and original sample identity. Validate the
original contributing composite (including sample coordinates) before reporting
a common periodic blackout gate. No candidate implies no absence/safety proof.
The traversal-budget flag also records locally caught `_walk` exhaustion; it
still does not summarize every separate helper's budget. Keep nested unknowns.

Declared shape material inputs: `scenario_material_envelope` supplements ordinary
`material_temporal` without replacing its lifetime domains or hazards. Reuse
scalar value envelopes with validated scenario names and native modulo/conversion
rules; value bounds infer no time continuity or audio change rate. Conditional
`activity.flashing.scenario_material_jump_bounds` reuses fixed-barycentric blend
ceilings with scenario hash and false runtime-observation/binding flags. Keep
missing bands, persistent state, unknown texture colours and native overflow
unresolved. Nominal area bounds remain the ordinary lifetime geometry envelope.

Wave normalization: clamp RGB first and normalize only when max(RGB)>float32(.01),
matching current Waveform.cpp and original MilkDrop2. The nominal boundary
difference c*(1/T-1) uses c≤T at the seam; optional alpha weighting holds the same
alpha/destination/geometry fixed. Retain native division/quantization, dynamic
alpha, waveform footprint, draw gates and source reachability as unresolved.
Existing possible normalization risk now appears as an activity hazard with
null event rate/visible strength, not a whole-screen flashing certificate.

Shape centre audio response: `audio_center_response` exports two source axes by
six current EEL bands, retaining continuous-response nulls, init/private-state
identities and source expressions. Per-band NDC norm uses centre mapping
(2*x-1,1-2*y); it is neither pixel distance nor a temporal speed. Scenario value
envelopes separately bound a two-state source-coordinate box diameter. Do not
infer simultaneous reachability, audio time rate, future state trajectory,
native float32 projection/overflow parity or visibility from those bounds.

Source-analysis component research (2026-10-10): external shallow/sparse checkouts
and an isolated SymPy/Z3 environment live under
`/Users/jneerdael/Scripts/source-analysis-evaluation/`. They are evaluation inputs,
not predictor/runtime dependencies. The component report pins identities and
distinguishes exact GLES300 AST from ES310/auto-binding inspection SPIR-V. Pure
nominal real simplification and explicit float32 proof results stay separate.
Do not import other MilkDrop hosts' Q/init/random policies without target adapters.
See `docs/research/2026-10-10-component-reuse-evaluation.md` and its evidence ZIP.

Optional source components (2026-10-10): the isolated SymPy worker consumes a
strict pure scalar graph and returns derivative programs for the existing range
calculator. Original response/value-domain errors and phase-qualified inputs
remain guarded; no native numeric or visible-response credit follows. Request
writing and reading share a bounded deadline; failures disable the caller-owned
session rather than repeatedly retrying. `--symbolic-python` changes provenance
and cache identity. Default-off operation remains independent of SymPy/Z3.
See `tools/milk-analyzer/SOURCE_COMPONENTS.md` and the adoption plan.

Worktree cleanup (2026-10-10): six obsolete worktrees were removed with branch
history retained. The active predictor owns local `build/preset-lab-venv`,
`build/docs-venv`, `build/visual-loop`, `build/milk-analyzer` and
`build/preset-corpus/source29`; no external ProjectM-TV worktree symlink remains.
Copied environment imports, focused source/adapter tests and strict docs pass.
The primary checkout's separate unsaved files were preserved. Detailed inventory
and migration records are in `~/Downloads/ProjectM-TV-worktree-cleanup-2026-10-10/`.

Source-component adoption (2026-10-10): the optional `--proof-python` worker
adds Z3 nominal value/predicate/private-state proof evidence; it never promotes
real proofs into native Q selector bounds. `--phase-dependencies` adds a
Stims-derived private main-frame predecessor fixpoint with init/Q/phase/RNG
uncertainty retained. Backend/policy identities participate in static export
cache keys, and publication checks occur after supplemental analysis. Optional
compiler/Naga/Slang/Crab and precision-query bridges are auxiliary source exports,
not native or visual certification. Prepared component environments and exact
artifact hashes are required for their optional controls. See
`tools/milk-analyzer/SOURCE_COMPONENTS.md` and component evidence/research reports.
The component adoption checkpoint is historical. The active user goal now covers
source-only effect understanding and automatic mood grouping across all9,606
presets, using ongoing research/manual additions and a documented LLM skill/SDK.
Exact image recreation is not the product objective; keep source evidence,
approximate interpretations and native observations distinct. No main merge or
duplicate device corpus is authorized by this follow-up.


Static behaviour integration (2026-10-10, in progress): the source description
now includes `static_behaviour` with separate flashing, motion, prominence and
colour evidence. `source_static_behaviour.validate_context` freezes declared
viewport/FPS/scalar domains; export/cache identities include that context.
`static_behaviour_scoring` is an uncalibrated source-potential preference mapping;
its point estimate is not typical visible intensity. Missing contributing
trajectories and execution/domain gaps veto automatic eligibility. Preserve
source-only/no-render flags and all conditional bounds. `static_behaviour_validate`
reuses one frozen parser per worker, validates saved compiler seals/source/profile
joins and optionally enters caller-selected SymPy/Z3 sessions. Its cohort counts
are interpretation evidence, not appearance or human mood accuracy. Prepared
qualification and completed coverage belong in task evidence; do not infer success
from synthetic controls or constant final RGB with unresolved execution.


Static behaviour qualification follow-up (2026-10-10):3472 prepared tests plus
92subtests,100 paired source exports with schema/model checks, and the unchanged
fixed2000 source cohort complete. All2000 retain behaviour reports;1552 have useful
hue descriptions and367 conditional source-potential indices. Automatic activity
eligibility remains empty; this is coverage, not visual/mood accuracy. See
`docs/superpowers/evidence/static-behaviour-2026-10-10/final-v5/`. The reference
`output_storage` defaults to declared normalized-unorm; unknown storage vetoes
automatic eligibility. Preserve raw RGB modulation separately from stored clamp
bounds and the restricted binary32 finite-source guard. No implicit shader clock
domain, generic native precision or target-driver certificate follows from a
nominal envelope. Arbitrary resampling must retain aggregate instance alpha and
possible borders; input context domains must propagate into motion/prominence.


Static preference mapping follow-up (2026-10-10): `activity_preferences` in the
declared behaviour context supplies validated overrides to `score_static_behaviour`.
Resolved rules enter export/cache identity; physical evidence remains unchanged.
`partial_contributions` may inform the source-potential index but never closes
texture/history uncertainty or supplies a total-activity lower bound.49 focused
scorer/builder/export tests pass. Derived scoring on unchanged final-v5 evidence
adds0indices (367remain). Follow-up review found both unresolved final transfers
and a consumer continuity-tag mismatch; the frozen derived snapshot predates that
correction and must not be treated as corrected coverage.
See `tools/milk-analyzer/STATIC_BEHAVIOUR.md`; do not report this as improved
whole-preset grouping or rewrite the preserved producer rows.

Conditional final-transfer follow-up (2026-10-10): legacy
gamma is summed redraw gain with native post-equation clamps, not `pow`. Echo
and portrait aspect expansion do not preserve source area. Authored nonlinear
sample-colour moduli may bound two-state changes without a finite derivative;
their delta is independent sampled RGBA lane change, not elapsed time/history.
Only main-only sampled-site moduli may join incoming drawing without additional
image-operator bounds; blur normalization remains a separate propagation question.
Keep native precision, invalid inputs, sample-dependent seams and unknown feedback
explicit. See `tools/milk-analyzer/STATIC_BEHAVIOUR.md`.
The frozen transfer-v6 check passes3552 prepared tests plus92subtests,100 paired
schema/model-valid source exports and2000 computed source rows. Conditional
potential indices change367→378; useful hue descriptions stay1552 and automatic
eligible bands remain empty. See the transfer-v6 evidence folder; these are
conditional source-coverage counts, not mood or appearance accuracy.

Input-rate/blur follow-up (2026-10-11): optional
`scalar_input_maximum_rates_per_second` context declares exact scalar input change
ceilings; it defaults empty and cannot redefine source/native clocks. Combined
shape transport needs finite amplitude/original argument domains and all relevant
rates. Preserve unknown state/topology, native projected/perimeter overflow,
positive-product underflow and constituents' partial records. The reusable
`original_scalar_domain_evidence` owns a bounded private cache. Blur operator gains
are exported separately from current drawing because previous-feedback timing,
RGB/alpha, encoded/GetBlur decode and native pair-error obligations remain distinct.
Uniform final RGB cycle screen lower weight requires a complete unclipped source
model and declared full-cycle clock interval. Source decisions do not certify
native frame sampling or mood accuracy.3633prepared tests plus92subtests and100
schema/model-valid exports pass. The declared772-case diagnostic obtains229finite
combined geometry records across120presets; same-context scorer ablation204→217
potential indices, with no whole-preset eligibility. Experimental rational shader
translation is not integrated (zero first-ten source gains). See
`docs/superpowers/evidence/static-behaviour-2026-10-11-input-rates/README.md`.

Sequential-shape source follow-up (2026-10-11): `shape_state` independently exports
conditional nominal private-state induction and per-instance output boxes. Use
only the exact source34 private-local allocation policy; preserve native saved
instance count, reset inputs, unsupported tan, cross-phase/register and numerical
conditions. State boxes do not clear motion/finite-domain or mood guards. Large
groups use an aggregate ideal polygon-area upper over the full instance domain,
without enumerating shapes or claiming clipping/overlap lower support. Random
EEL calls retain distinct value identities and stable phase/site metadata; copied
draws preserve correlation. Bounded stochastic material recipes must union every
live border/fill group and never certify distribution or visible flashing.
See `tools/milk-analyzer/SOURCE_SHAPE_STATE_DOMAINS.md` and
`tools/milk-analyzer/STATIC_BEHAVIOUR.md`; completed qualification counts belong
in the corresponding evidence folder.

Effect-understanding SDK/curves (2026-10-11): `preset_understanding.py` is a
standard-library consumer of source JSON with exact fact pointers and a local
`skills/understand-preset/SKILL.md`. Keep approximate LLM mood estimates separate
from strict physical eligibility. `source_parametric_wave.py` adds conditional
affine polar recipes and interior locus relations; point speed, curve drift,
raw colour rates, finite polylines and visible motion are distinct. Use exact
coefficients/outward bounds and early term/factor budgets. Stochastic brightness
partials preserve unresolved total activity. Checkpoint captures require an
isolated emulator only, frozen description plus generated illustration before
native screenshot/10-second declared-audio clip, and separate comparison outcomes.
At that source-only checkpoint, capture infrastructure was unresolved and no
native screenshot/clip existed; the later native GLES checkpoint is recorded below.
See `docs/superpowers/evidence/source-understanding-2026-10-11/README.md` for
3,784tests+92subtests,100 source exports and full9,606 primitive-census scope.

Current-preset projection/feedback (2026-10-11): keep the selected Zylot Spiral
through iterative general repairs before another random selection. Additive
`source_curve_projection.py` distinguishes source geometry, final orthographic
Y orientation, aspect projection and negative-weight smoothing envelopes from
raster/visible coverage. `source_affine_radial_feedback.py` qualifies source34
engine/default-warp lineage before exporting affine radial sampler and inverse
feature maps; custom shaders and unmatched engines cannot acquire that evidence.
SDK feedback facts retain colour-only gain/half-life separately from observed
persistence. Preserve authored source and unknown mood eligibility. Capture
helper requires an explicit emulator serial and verifies `ro.kernel.qemu=1`
before pushing or launching; no physical-device fallback. CPU feature queries
are denied in the current managed session; their relationship to emulator
startup failures remains unproved. See the projection-feedback evidence folder
for current qualification rather than extrapolating earlier counts.

Native capture alternative (user steering2026-10-11): native patched engine-code
execution is authorized alongside the emulator path; physical devices remain
excluded. Android ARM64 ELF libraries cannot load directly on macOS ARM64.
The pinned source34 engine builds for native macOS GLES and successfully captures
the same selected preset through installed SwiftShader GLES3 without WindowServer.
Record macOS ABI/driver/C++ binding separately from Android AAR/JNI qualification.
Use public SetFrameTime, explicit Native-trails disable, declared line reference
and recorded U8 audio conversion; never use the renderer frames as classification
inputs. The frozen v5 prediction identified spiral/clipping but underestimated
dense feedback layers. Continue general curve/feedback math on this preset.
See `docs/superpowers/evidence/source-projection-feedback-2026-10-11/native-gles/README.md`.
