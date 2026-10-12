# MilkDrop source analysis and predictive collections beta

This focused subset of the experimental analyzer from [PR #25](https://github.com/johnneerdael/ProjectM-TV/pull/25)
imports its inductive main-Q domain and shader selector proof. The separate beta
collection tools below add numerical activity scoring using a published AAR. The source analysis
is a diagnostic tool; parsing or lowering success does not certify appearance.

## Four initialization cases

`martin - ludicrous speed.milk` initializes `index4` with native `rand(12)` and
updates it through a bounded Boolean increment and signed remainder. The main-Q
proof includes initialization, frame resets and persistent custom locals, proving
post-frame q29 in 0..7. Float32 narrowing and signed-int conversion establish
`int(q29)%4` in 0..3. Equality branches use immutable expression identity;
missing cases, negative/nonfinite/overflow inputs, changed recurrences, shared
register effects and local shadows cannot borrow the proof. Runtime scalar/grid
guards retain its premise even when the result folds to a constant.

The other three presets are `Serge + martin - crystal palace tunnel003.milk`
(`mus`), `martin - mandelbox explorer - wreck diver nz+ liquititty.milk`
(`dist_c`) and `martin - organic light.milk` (`uv3`). The Microsoft legacy compiler
reflects these globals as external constants with NULL defaults. Previously they
became uninitialized ordinary GLSL globals. Historical patch 0040 (retained in the 4.2 series as `0002-hlsl-compatibility-and-float-roundtrip.patch`) preserves uninitialized
scalar/vector float globals as uniform inputs and uses the existing initialized
per-invocation copies when shaders write them. Mixed comma declarations preserve
individual storage classes. Locals, static/const declarations, initialized globals,
arrays and matrices retain their previous handling.

The versioned `projectmtv-implicit-extern-zero-v1` target policy models GLES link-time
zero initialization for unbound implicit inputs. An explicit binding supplied when
lowering or evaluating a scalar/grid field overrides that default, including different
values for different grid lanes. The policy is enabled only for declarations carrying the native
implicit-uniform marker, in a reader stamped for the new engine. `strict-v1` keeps
external inputs symbolic. It never initializes a local just because its name matches.

This focused tool retains source parsing, equation-domain proof, shader lowering,
and offline compatibility checks. It does not include the experimental pipeline
simulation from PR #25. No image or device result is inferred from source checks.

This policy defines current core behavior. It does not claim equivalence to old
D3D9 device-register history, nor does NULL legacy reflection prove a zero value.
Authored presets and assignment order are unchanged. Before/after visual differences
for previously undefined values cannot be interpreted as appearance regressions
without a specified input policy.

## Build and validate

Initialize recursive submodules. Apply the committed projectM patch series through
an Android build or the native test runner before building source adapters. Build
host regressions using the normal repository prerequisites:

```sh
bash core/src/test/native/run_native_tests.sh
```

The Preset Lab CI job reuses its prepared engine and archive, builds the two CPU-only
adapters (`milk-native-reader`, `milk-shader-translate`), and runs:

```sh
python -m pytest tools/milk-analyzer -q
```

For a retained host engine build, configure adapters explicitly:

```sh
cmake -S tools/milk-analyzer -B build/milk-analyzer/native \
  -DENGINE_SOURCE=/absolute/path/to/patched/projectm \
  -DENGINE_BUILD=/absolute/path/to/host/build \
  -DENGINE_IDENTITY_FILE=/absolute/path/to/build-identity.json \
  -DSANITIZERS=OFF
cmake --build build/milk-analyzer/native -j 4
```

The shader adapter uses the engine’s `Logging.hpp` and existing `Logging` interface
for the diagnostic macros in its copied CPU bodies. Keep those bodies unchanged
when adapting to upstream headers so their recorded hashes remain source-bound.

Match `SANITIZERS` to the linked archive. The identity JSON records pinned commit,
patch digest and instrumentation scope. Native reader fixtures retain raw and
assembled equation trees separately and stamp the selected loading policy. Prepared
historical adapters cannot certify the new target policy. The broader original
PR #25 suite remains a supplemental compatibility check; it is not imported here.

Source stage selection uses the native preset parser’s lowercase key map with
case-insensitive setting lookups. Version flags such as `PSVERSION_WARP` therefore
select active stages; missing compatibility evidence remains unknown rather than
being classified as disabled. Results produced with the earlier case-sensitive
lookup can misclassify active shader stages and require a fresh analysis run.
Record the new source revision and hashes of `source_context.py` and
`stage_resolution.py` in that run’s identity. Keep historical exports, producer
identities and calibrated models unchanged; parsing and stage selection remain
source diagnostics, not fidelity certification.

The native tests exercise actual parser generation, default and nonzero input values,
copy reset across invocations, local/static/initialized controls and preset hashes
checked each time the tests run. Offline translator tests require `glslangValidator`.
Numerical source tests require NumPy and pytest from the existing
`tools/preset-lab/requirements.lock`. No app runtime dependency is added.

## References

- [D3D9 global shader inputs](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-writing-shaders-9)
- [D3D9 application-driven constant initialization](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-using-shaders-9)
- [GLSL ES 3.00 storage and initialization rules](https://registry.khronos.org/OpenGL/specs/es/3.0/GLSL_ES_Specification_3.00.pdf)


## Predictive collections beta

The app's Preset mood now opens the Mood panel: facet groups from the engine-ruler attribute bundle built by `attribute_bundle.py` (see `docs/user-guide/predictive-collections.md`). The legacy Chill1–30, Normal25–75 and Intense70–100 core categories described here remain for Milkbeat via `setMusicCategory`.
`beta_score.py` executes the standard published ProjectM-TV:core AAR through its
JNI interface on a task-owned Android emulator. `beta_export.py` verifies complete
source-bound results, preserves master memory weights and publishes the three
indexes. This is numerical activity-based prediction, not a claim of source-only
visual accuracy. The [Pages article](../../docs/user-guide/predictive-collections.md)
describes the formulas, relative ranking and limitations.

The initial run uses the pinned standard2.3.3AAR in
`profiles/published-core-v2.3.3.json`. Before a new run, verify the latest published
release and update the explicit pin if needed; never label another AAR flavour as
capped. Do not edit a live run's scorer, descriptor, model, input or runtime files.
A changed artifact creates a new run identity; old rows cannot be silently reused.

Install the dependencies from `tools/preset-lab/requirements.lock`. An ARM64 API34
emulator, adb, Android SDK34/build-tools34, NDK27.3.13750724 and JDK21 prepare the
runner. No user recordings or raw frames are committed.

Prepare a new runtime directory (for example `build/predictive-beta/runtime`):
extract `classes.jar` and `jni/arm64-v8a/libprojectmtv.so` from the exact standard
AAR. Compile the helper against that AAR's classes and Android34:

```sh
javac -source 8 -target 8 -cp ANDROID_SDK/platforms/android-34/android.jar:RUNTIME/classes.jar -d RUNTIME/java tools/milk-analyzer/CoreBackendRunner.java
ANDROID_SDK/build-tools/34.0.0/d8 --min-api 34 --lib ANDROID_SDK/platforms/android-34/android.jar --output RUNTIME RUNTIME/classes.jar RUNTIME/java/nl/neerdael/projectm/analysis/CoreBackendRunner.class
ANDROID_SDK/ndk/27.3.13750724/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android34-clang++ -shared -fPIC -O2 tools/milk-analyzer/core_backend_clock.cpp -o RUNTIME/libbackendclock.so
```

Replace `ANDROID_SDK` and `RUNTIME` with actual paths; use the NDK's `linux-x86_64`
prebuilt directory on Linux. Different compiler output has a different recorded
helper hash. The Java runner calls the published JNI API, selects one preset via
an asset-index overlay, and keeps the AAR's original preset and texture content.
The clock helper interposes only core-origin realtime/monotonic calls, calls
`srand(12345)`, and streams top-left RGB bytes with a bounded header. Native
`random_device` shader/noise/image choices remain production inputs.

Generate the fixed mono float32 reference using NumPy, then keep it immutable:

```python
import numpy as np
from pathlib import Path
sample=np.arange(420*1470,dtype=np.float64)
t=sample/44100
quiet=.04*np.sin(2*np.pi*220*t)+.02*np.sin(2*np.pi*440*t)
melody=.12*np.sin(2*np.pi*220*t)+.07*np.sin(2*np.pi*880*t)+.04*np.sin(2*np.pi*3200*t)
phase=(t*2.3)%1
kick=.5*np.exp(-phase*30)*np.sin(2*np.pi*55*t)
pcm=np.where(t<5,quiet,np.where(t<9,melody,melody+kick))
Path('build/predictive-beta/input.f32').write_bytes(pcm.astype('<f4').tobytes())
```

Launch a separate owned emulator. Record its actual PID, serial, AVD name and
launch command in `owner.json`; the scorer verifies the live process and AVD before
every preset. Its `pid`, `serial` and `avd` fields must refer to that owned instance.
Never use another task's device, running process or result folder. The initial run
owns emulator5592; this is a historical task identifier, not permission to reuse it.

```sh
python tools/milk-analyzer/beta_score.py --aar build/predictive-beta/core.aar --runtime build/predictive-beta/runtime --pcm build/predictive-beta/input.f32 --owner build/predictive-beta/owner.json --device emulator-5592 --remote /data/local/tmp/projectmtv-predictive-beta-20261005 --output build/predictive-beta/scores
```

Use `--limit 5` for a pilot. Reuse the same arguments to continue a matching run;
use `--retry-unscored --only-preset "EXACT PRESET.milk"` to repair a diagnosed case before continuing. The batch now stops at its first failed measurement and refuses to continue past unresolved failures. A 120-second timeout
is a failed measurement, not evidence that an effect is calm. Original315 language
coverage and this full numerical run are different checks; the other agent's saved
baseline stays read-only.

When every source-bound row is scored:

```sh
python tools/milk-analyzer/beta_export.py --run build/predictive-beta/scores --aar build/predictive-beta/core.aar --bundle core/src/main/assets/preset-genres
python tools/milk-analyzer/beta_export.py --check --bundle core/src/main/assets/preset-genres
python -m pytest tools/milk-analyzer -q
```

The final command needs the prepared source adapters described above. The new beta
unit tests do not launch devices. CI checks the committed bundle's source, weights,
model hashes, ranks, exact overlapping memberships and checksums. Parsing success,
compile success and these checks do not certify mood or appearance accuracy.


The diagnostic-only repair preserves the exact original scorer in
`profiles/scorers/beta-score-v1.py.txt`. Previously completed records retain their
original evidence identity. `evidence-contexts.json` declares the original and
repaired producers: all render/audio/model/runtime inputs must match, the archived
source hash is pinned, and the numerical program AST must remain unchanged outside
main's resume bookkeeping and measurement diagnostic cleanup. Changed numerical
code or inputs cannot reuse those records. The bundle retains each row's producer
identity and the exact source file for each context.

Diagnostic collection is best effort and its errors are separate from the primary
measurement. For example, no `.skip` file is normally created when the engine's
skip count is zero; failure to pull that optional file does not make a completed
native measurement unscored.


### Direct-delta calibration repair

The current `audience-model-direct-delta-v2.json` is a fresh nonnegative interval
fit on the actual 30-Hz direct brightness and 10-Hz native motion vectors, using the
unchanged original eight user judgments. The old `audience-model-v1.json` expected
motion-compensated brightness and is retained solely to validate historical
producer activity. Both original scorer versions are archived; retained measurement
files are not rewritten. The exporter recalculates activity with the new model,
stores original activity separately and pins a distinct `derived_scoring` identity.

Calibration inputs, original feedback, exact preset hashes and measurement
identities are in `profiles/direct-delta-calibration/`. Feedback was on core2.2.2
under mostly unspecified music/device conditions, with a tentative sample1 and
possible darkness defect. This transferred-label beta fit is not perceptual
certification: held-out base-model diagnostics match4/8strict bands and6/8within
five points. Final corpus ranks are a separate relative transform.

Reproduce the fit offline (not required for normal export/verification):

```sh
python -m pip install -r tools/milk-analyzer/requirements-calibration.txt
python tools/milk-analyzer/fit_activity_model.py
```

The timeout callback always kills its local streaming child in a `finally` block,
even if remote ADB cleanup fails. Its diagnostic errors are retained and the timer
is joined before the outcome is saved. Timeout still halts the batch.


Retries now select only existing unresolved records. Naming an unmeasured or
already scored preset with `--retry-unscored` is rejected; without `--only-preset`,
the retry invocation repairs only selected unresolved cases. Run the normal command
again after those failures are resolved to continue unmeasured cases. The required
metadata pull has a 15-second timeout and records an unscored outcome if it fails,
even after the renderer has exited. Ownership/remote setup and overlay transfers
are bounded separately; runtime artifact pushes have a 180-second limit.

## Shader literal identity

Current source adapters stamp `float_literal_policy` as `float32-roundtrip-v1` and the production formatter’s `float_formatter_sha256`.
The reader exports `renderer_literal` through that formatter, and lowering uses its
reparsed value. Rebuilding against historical patch 0044, retained in the consolidated 4.2 HLSL patch, therefore models the current renderer
rather than retaining the old six-digit emission. Historical adapters and archived
measurement fixtures keep their original identities; do not relabel them.

`test_float_literals.py` checks 99 authored AST witnesses in 95 hash-verified presets,
the adjacent-to-one coefficient and scale, both GLSL targets, and rejection of an
overflowed literal even when the shader declares `inf`. Native tests additionally
exercise finite float32 boundaries, signed zero, randomized bits, locale and a
one-frame full-engine render. These are source/controlled execution checks, not a
visual forecast for every affected preset.
