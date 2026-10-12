# Native ruler

## Purpose

Engine-ruler attribute measurements (luminance, saturation, colour, motion, flashing) for the bundled presets. They feed the mood facet bundle and serve as calibration targets for source analysis. They are never source-classification inputs.

## Build

The ruler links the patched projectM engine. Obtain a patched source tree by applying `tools/projectm-patches` in order to a clean export of `third_party/projectm` at the pinned commit (the series CMake applies for `:core`; see `tools/check-patch-series.sh`). The verified run used the predictor's pinned patched tree (VCS version `2449c627f6e7bc25041adefc2a6f3429da1343e5`).

```bash
cmake -S tools/native-ruler -B build/native-ruler -DCMAKE_BUILD_TYPE=Release \
  -DPROJECTM_SOURCE=<patched projectM source> \
  -DJSON_INCLUDE=$PWD/tools/preset-lab/src/preset_lab/native \
  && cmake --build build/native-ruler
```

`JSON_INCLUDE` supplies `vendor/json.hpp`. The recorded build used these three settings (read from the build's `CMakeCache.txt`; the original log did not contain the configure line).

## Platform

Verified on macOS with SwiftShader (Android SDK `emulator/lib64/gles_angle`). Linux is unverified.

## Run

```bash
python3 tools/native-ruler/ruler.py --pcm <checkpoint synthetic.f32> --output <dir>
```

Python needs `numpy` and `opencv-python-headless`. Options: `--swiftshader DIR` (default `~/Library/Android/sdk/emulator/lib64/gles_angle`), `--presets DIR` (default the bundled presets), `--workers N` (default 6), and `--preset NAME` (repeatable, limits the run to those preset file names). Output is `<dir>/results/<preset>.json` (one per preset, a cached result is reused only when its recorded identity matches the current run, otherwise the preset is rendered again), plus `thumbs/`. Each result holds `status`, `mean_luminance`, `mean_abs_frame_difference`, `mean_flow_screen_widths_per_s`, `global_brightness_jumps_per_10s`, `mean_saturation`, `coloured_share`, `warm_cool`, `preset`, `preset_sha256` and `identity`.

### Cache semantics

Each result records `identity`: the preset sha256, the PCM file sha256, the `native-ruler` binary sha256, a hash of the SwiftShader directory (file names, sizes and contents), a hash of the bundled `textures` directory passed to the renderer (relative paths, sizes and contents, computed once per run), and the configuration (size, frames, measurement window, measurement version). A rerun into the same output directory reuses a result only when every part matches; a changed preset, PCM, engine build, SwiftShader, texture file or setting re-renders it, and results written before identities existed are always re-rendered, and failed rows (`render_error`, `timeout`, `error`) are never reused, so rerunning the command retries them. Bump `MEASURE_VERSION` in `ruler.py` when the measurement code changes. Run `python3 -m unittest discover -s tools/native-ruler -v` for the cache tests (standard library only).

## Conditions

480x270, 300 frames at 30 fps, statistics over frames 60-299, U8 audio ingress.

## Limits

One 10 s render with one synthetic track under SwiftShader. Emulator agreement on 83 presets was rho 0.91-0.96, which is not a per-preset guarantee.
