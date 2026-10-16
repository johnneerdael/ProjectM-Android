# ProjectM TV Engine

**ProjectM TV Engine** is the renderer inside ProjectM TV, ProjectM Android and apps that use its core library, such as [Milkbeat](https://github.com/johnneerdael/Milkbeat). It is projectM, the open-source reimplementation of Winamp's MilkDrop 2, with an ordered series of patches that make it behave more like MilkDrop 2 and run well on TV hardware up to 4K.

| | |
|---|---|
| Upstream base | [projectM](https://github.com/projectM-visualizer/projectm) master at commit `6f6480746` |
| Upstream version | Unreleased projectM 4.2 master. CMake reports `4.2.0`, but **no projectM 4.2 has been released**; this is a development snapshot |
| Expression evaluator | projectm-eval 1.0.7 (`22fb0cfd`) |
| Patches | [35, applied at build time](patches.md) from [`tools/projectm-patches/`](https://github.com/johnneerdael/ProjectM-TV/tree/main/tools/projectm-patches) |
| Graphics | OpenGL ES 3.0 (upstream at the pin requires 3.2) |
| Library | Linked statically into `libprojectmtv.so`, shipped in the APK and the [core AAR](../development.md#use-the-engine-in-another-app) |
| Version label | Settings panel: *v‹version› · ProjectM TV Engine / Based on unreleased projectM 4.2 master / Upstream 4.2.0 · 6f6480746* |

## Why a fork

projectM targets desktop and embedded hosts and keeps a careful compatibility contract. ProjectM TV needed three problems solved sooner than upstream could solve them:

1. Some presets did not load or looked wrong: equation code that MilkDrop accepted, HLSL that Microsoft's compiler accepted, and Direct3D 9 pixel rules that OpenGL handles differently. See the [patch catalog](patches.md).
2. On 4K TVs, MilkDrop's pixel-sized lines, blurs and `texsize` steps make presets dark and thin at 3840×2160. See [Rendering MilkDrop at 4K](resolution.md), which addresses the resolution-scaling part of projectM issue [#682](https://github.com/projectM-visualizer/projectm/issues/682).
3. TV hardware has tile-based GPUs and 2 GB of RAM shared with the music app, and shader compilation froze the picture for up to 1.9 s at every preset change. See [How a frame reaches your TV](pipeline.md).

The fork follows upstream closely. In October 2026 the whole series was rebased from projectM 4.1.7 onto 4.2 master. Forty-four historical patches were consolidated into three, and nine were dropped because upstream had made the same fix; one of those ([PR #1031](https://github.com/projectM-visualizer/projectm/pull/1031)) was contributed from this project. The rebased engine was checked against the previous release (see [Validation](validation.md)).

## Design rules

- The preset file is the source of truth. No bundled preset is edited to work around an engine difference; the engine changes instead.
- MilkDrop 2 is the reference. Where projectM and MilkDrop 2 disagree, the engine aims to follow MilkDrop 2's released source, and a patch that reproduces MilkDrop behaviour cites that source. Two exceptions are documented: [0010](patches.md#0010-each-preset-keeps-its-own-textures) adds behaviour MilkDrop never had (per-pack texture folders), and [0005](patches.md#0005-blur-ranges-that-cannot-collapse) repairs a MilkDrop typo.
- Resolution and performance features are opt-in at the API and on in the app. Quad lines, Native trails, direct output and the texture pool default to upstream behaviour in the C API, and the Android core switches them on. Compatibility fixes, such as tolerant equation loading and the HLSL and evaluator repairs, apply to every host; only their warning callback is opt-in. Other projectM hosts can adopt each piece independently.
- Each patch has evidence before it makes a claim: a reproducing witness preset (or a synthetic fixture where no bundled preset activates the change), a regression control in the native test suite, and a statement of what its evidence does *not* establish.

## Pages in this section

- [Patch catalog](patches.md): patch descriptions and the available visual evidence.
- [Rendering MilkDrop at 4K](resolution.md): quad lines, reference scaling, virtual `texsize`, Native trails.
- [How a frame reaches your TV](pipeline.md): audio capture, threads, prewarming, transitions, automatic quality, skipping.
- [Validation and evidence](validation.md): how changes are proven, and what the proofs cover.
