# Validation and evidence

A visualizer change is easy to get subtly wrong. A one-texel shift in a feedback preset becomes a different picture ten seconds later, and every GPU driver interprets edge cases its own way. ProjectM TV therefore asks three questions of each change and answers each with its own evidence. Native regression controls and single-patch ablations show whether the change does what it claims. Frozen fixed-seed comparisons across releases show whether it changed anything it should not. Every result also states explicitly what its evidence does not cover.

## Deterministic rendering

Comparing two renders is meaningful only if everything except the engine is frozen. Evidence runs fix the following inputs:

- Audio is a stored PCM stream, identical for every run.
- Time advances exactly one frame per frame (frame/30) instead of following the wall clock, and projectM's internal timer origins are frozen too.
- The evaluator's random numbers use seed 12345. Production random-texture choices use `std::random_device`, so evidence records which image was actually bound.
- Mesh and size are fixed, for example a 48×32 warp mesh at 512×288 or 1920×1080.
- The SHA-256 of the preset, textures, engine source, patch series, built binary and PCM is recorded with every result. A result whose inputs cannot be identified is not used.

Each role is run at least twice, and its frames must repeat byte for byte before any comparison counts.

## Regression controls

`core/src/test/native/run_native_tests.sh` builds the patched engine with AddressSanitizer and UndefinedBehaviorSanitizer and runs real-GL controls, including:

| Control | What it checks |
|---|---|
| `shader-parser-regressions`, `parser-presets` | HLSL constructs plus 16 unchanged bundled presets whose shaders failed before (hash-pinned) |
| `float-literal-regressions`, `float-literal-presets` | Bit-exact float32 round trips, locales, nonfinite rejection, 95 hash-pinned shader sections |
| `random-texture-*` | Slot identity, sampler modes and texel values against known textures |
| `shape-sampler-regressions`, `blur-range-regressions`, `warp-zoom-regressions` | Effective sampler state at real draws, blur normalization, vertex UV readback for signed and CPU-defined negative nested zoom powers |
| `dynamic-wave-controls`, `dynamic-display-controls`, `dynamic-original-presets` | Per-frame waveform and display controls against static controls, in all Native trails paths |
| `warp-rotation-regressions` | Signed, moderate, large and maximum finite rotation angles across four feedback frames; CPU negative-power uploads, raw equation values, NaNs, resize and prepared replay |
| legacy compatibility controls | Constant-colour output with disabled and fractional `fShader`, mode-1 waveform opacity and open-strip topology against MilkDrop 2.25c expectations |

`tools/projectm-host-tests.sh` runs projectM's own GoogleTest suite with the patches applied (329 tests at the 4.2 rebase).

## Release-to-release fidelity

When the engine moved from projectM 4.1.7 to 4.2 master, the rebased renderer was compared with the published v2.3.15 release:

| | |
|---|---|
| Presets | 100 randomly selected + 351 required regression witnesses (447 bundled, 4 overlaps) + 1 external witness |
| Profiles | 448 at 1080p + 61 at 4K (Native trails Standard, Medium, High) = 509 comparisons |
| Runs | 509 × 2 engines × 2 repeats = 2,036 fixed-seed runs |
| Result | Every RGB frame 0-479 identical across engines and repeats: 977,280 frame hashes, zero changed |
| Backend | API34 ARM64 Android emulator, Apple M4 Pro GPU, GLES 3.0 |

This establishes that the migration preserved behaviour on that set. It does not establish correctness against MilkDrop 2, and it does not cover all 9,606 presets or other GPUs. It also predates patches 0010 to 0013. [Evidence](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/upstream-master-4-2/fidelity-final/README.md).

## Single-patch proof images

The [patch catalog](patches.md) images come from rendering each witness three ways: upstream with only the GLES 3.0 admission, the full series *without* one patch, and the full series.

A difference between the second and third renders proves that the patch is responsible. A full-series image alone does not. Patch 0001 is too broad to remove in isolation, so its image shows only that the preset now loads.

The capture checkpoint holds 31 images from 134 successful runs. The ten failed runs are kept alongside them with their diagnostics. Proof workers disable the shader binary cache because of an emulator driver error, so the images do not validate caching.

## Negative-power source and runtime evidence

The [Tulip investigation](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/tulip-negative-zoom-power/README.md) examines CPU power, production vertex UVs, interpolation, texture sampling and full-AAR output separately. Defined nested exponents 1/2/3 reproduce a compatibility gap and pass after patch 0015. The exact original Tulip keeps 33 fractional-domain NaNs per frame, and its tested 30-frame AAR output stays byte-identical. Invalid sampling observations can differ between repeat and clamp on one backend, so they do not establish portable source-only pixels or the original Windows appearance. No randomized forecast credit or full-corpus claim is assigned.

## What is not claimed

- Windows appearance is not claimed. No Windows/Direct3D reference renders exist in this project's evidence, and MilkDrop 2 behaviour is established from its released source code, not from screenshots.
- Results are not claimed for every TV. Device checks ran on NVIDIA SHIELD TV (Tegra), Ugoos AM6 (Mali-G52) and Ugoos AM9 (Mali-G310) at various times, and on emulators. Other GPUs may differ, especially for GLES 3.0 float render targets.
- Historical speedups were measured on the 4.1.7-era engine and are not re-claimed for 4.2.
- No change is certified across the whole library of 9,606 presets.

## Continuous integration

Before anything is published, every reviewed pull request and every merge to `main` runs:

- the JVM tests;
- the native sanitizer suite;
- the asset checks (`tools/check-presets.py`, `tools/gen-preset-index.py --check`);
- Preset Lab and source-analysis tests;
- a verification of the shipped mood-collection bundle (source hashes, measurement provenance, score calculation, membership);
- a strict build of this guide.

A merge publishes a versioned APK and core AAR only after the full suite passes.

## Authored-fidelity followup

The five added patches, 0029 to 0033, have 63 normal and sanitizer renderer controls. They cover sample counts, discrete and single dots, circle closure, per-instance style, domain and replay, and the actual publication and consumption of the previous field. Partial feedback initialization failures exercise real constructor unwind and fallback. The Linux controls retain the unchanged mediump shader and document their premise of a same-backend arithmetic reference.

The focused Native 4K checkpoint contains 76 before/after jobs across 19 originals and fixtures, with 608 selected final-output RGB captures verified and repeated. Four active-canvas production JNI lifecycle jobs verify 120 boundary captures within matching schedules and context generations. Both sets use frozen audio, seed and clock, and artifact identities. The zero-reference lifecycle runs are kept separately as inactive or fallback evidence. [Evidence and review images](https://github.com/johnneerdael/ProjectM-TV/blob/main/docs/superpowers/evidence/authored-fidelity-followup/README.md).

These selected captures are not an all-frame or whole-library certification. The JNI pbuffer checks do not establish Activity Home or real-audio recovery, actual memory exhaustion, or physical-TV performance. The isolated cost matrix of seven workloads and 84 jobs verifies 672 selected captures and reports deltas per workload and per cycle; it does not establish physical-TV headroom. Final PR CI is a separate acceptance gate.
