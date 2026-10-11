# projectM Android TV: Codebase Analysis & Architecture (v1.9)

This document retains the historical v1.8/v1.9 analysis and verification below. Section 5 includes current rendering and integration guidance; older measurements are identified as historical and do not establish the current Auto policy or device limits. Current settings and validation are documented in the [user guide](user-guide/settings.md) and [Native trails design](superpowers/specs/2026-10-05-native-trails.md).

The maintained engine is named **ProjectM TV Engine**: an extensively modified projectM fork based on unreleased projectM 4.2 master (commit `6f6480746`), built from the pinned submodule plus `tools/projectm-patches/`. The app and Milkbeat's core AAR share this engine. The settings panel names the fork and shows the upstream base separately. Public Java/JNI names and artifact filenames are retained; `ProjectMJNI.getVersion()` still returns the upstream numeric version (`4.2.0`); this development snapshot is not an upstream 4.2 release. Identify a patched build by its release version, source revision and artifact checksum. [Third-party attribution](THIRD_PARTY.md) records upstream backports and local changes.

## 1. Summary

Version 1.8 rebuilds the rendering and preset pipeline. The goals were to start visuals right away, skip presets that show nothing, and fix the causes of black presets, several of which were already present before 1.7.

| Area | Before (tag `v1.7`, app "1.6") | After (1.8) |
|---|---|---|
| Startup | Deleted and re-extracted ~9,800 presets (~130 MB) on **every** launch; UI waited up to 15 s | Presets read straight from the APK; indexing (~10k names) on a native background thread; first preset on the first frames |
| Preset switching | D-pad, menu buttons and the startup preset switched presets **from the UI thread** (no GL context) | Commands are queued; the GL thread executes them |
| GL context | OpenGL ES **2.0** requested, but projectM 4 needs ES 3 | ES 3.0 requested (and declared in the manifest) |
| Audio | 8-bit mono samples misread as 16-bit stereo | Raw 8-bit mono passed to `projectm_pcm_add_uint8` |
| Render resolution | Forced to full screen (1.7), setting had no effect; earlier versions shrank the image | Hardware scaler (`SurfaceHolder.setFixedSize`); full screen at any resolution |
| Broken or black presets | Retried forever | Skipped automatically and remembered; reset from the menu |
| Adaptive "performance mode" | Changed preset duration, transition, beat sensitivity and resolution behind the user's back; oscillated | Removed; the user's settings are respected |
| Code size (Java) | 2,830 lines | ~670 lines |
| Tests | None | Host-side engine test suite (23 checks, ASan/UBSan) |

## 2. The 1.7 regression

Tags are off by one: tag `v1.6` = app `versionName "1.5"`, and tag `v1.7` = app `versionName "1.6"` (commit `6b21612`). The regression is the diff `v1.6..v1.7`.

| # | Change in 1.7 | Effect |
|---|---|---|
| R1 | `nativeOnSurfaceChanged` and `VisualizerRenderer.onSurfaceChanged` always use the full display size | The resolution setting became a no-op. Every device rendered at full panel resolution (≥2.25× the pixels of the former 720p default), so FPS dropped |
| R2 | New FPS-driven `optimizeForPerformance()` / `restoreQualitySettings()` with high thresholds (e.g. Shield below 40–50 fps) | Oscillation between modes. Each flip rewrote preset duration (15–35 s), transition (2–10 s) and beat sensitivity (0.6–1.2), and called `setRenderResolution()`. That calls `projectm_set_window_size`, which per `parameters.h` *"will reset the OpenGL renderer"*, so the screen flashed black and the preset's feedback buffer was lost |
| R3 | PCM truncated to 512 values and beat sensitivity lowered to 0.6 whenever "memory optimized" | Visuals reacted less to the music |
| R4 | `applyPerformanceOptimizations()` ran after initialization; `initUI()` hard-coded `autoChangeEnabled = false` | Saved preset and transition durations were overridden; the auto-change state was inconsistent |
| R5 | Duplicated auto-change block in `onDrawFrame` | Redundant logic, two timers |

## 3. Pre-existing defects (also in 1.6)

| # | Defect | Evidence | Effect |
|---|---|---|---|
| P1 | `ProjectMApplication.extractAssets()` deleted and re-copied all presets on every launch (1 KB buffer, background priority); `MainActivity` polled for up to 15 s | Code | Slow startup; a partial playlist if the timeout hit |
| P2 | Preset switches ran on the UI thread (`onKeyDown`, menu buttons, the `postDelayed` startup preset) | Code; GL calls require a current context on the calling thread ([GLSurfaceView docs](https://developer.android.com/reference/android/opengl/GLSurfaceView#queueEvent(java.lang.Runnable))) | projectM compiles shaders while loading a preset. Without a context this fails or leaves the preset blank. **Likely main cause of "some visualizations stay black".** Not verified on a device |
| P3 | ES 2.0 context requested (`setEGLContextClientVersion(2)`) | `readelf`: `libprojectM-4.so` NEEDS `libGLESv3.so`; its built-in shaders are `#version 300 es` | Black output on drivers that honour a strict ES 2.0 request |
| P4 | Visualizer waveform decoded as 16-bit stereo | [Visualizer.getWaveForm](https://developer.android.com/reference/android/media/audiofx/Visualizer#getWaveForm(byte[])): *"8-bit (unsigned) mono PCM samples"* | Silence became a DC offset near full scale; waveform presets drew at the screen edge; weak reactivity |
| P5 | Two independent auto-switch timers (playlist `preset_duration` + Java timer) | Code | Unpredictable switching |
| P6 | Per frame: four JNI viewport calls with `Log.d`, native `LOGI`, `glGetIntegerv` read-backs | Code | Logcat flooding and wasted CPU on weak TV SoCs |
| P7 | `requestRender()` override queued a `glClear` on every audio callback | Code | Unneeded GL work |
| P8 | `ProjectMJNI.destroy()` ran on the main thread while the GL thread could still render; context loss created a second instance without freeing the first | Code | Use-after-free risk and a leak |
| P9 | `assets/presets/.DS_Store` inside the preset folder | Repo | A junk entry wherever the folder is listed blindly |
| P10 | No texture pack shipped and no texture search path set. 1,866 presets reference 71 image textures (`sampler_worms`, `sampler_clouds`, `sampler_rand00` …) | `grep sampler_` over the presets; `libprojectM-4.so` contains `TextureManager::ScanTextures` and `GetRandomTexture` | Those parts of presets render empty, so presets look dull. **Fixed after 1.8:** the projectM texture pack is bundled (it covers 46 of the 71 names; `randNN` then picks from it), copied to `files/textures` on first start, and set with `projectm_set_texture_search_paths` before the first preset |

## 4. Infrastructure findings

| # | Finding | Action in 1.8 |
|---|---|---|
| I1 | Build caches (`.gradle/`, `app/.cxx/`, 95 files including a 16 MB binary) and `.DS_Store` files committed despite `.gitignore` | Removed from the index |
| I2 | Dead code: `jni_simple.cpp` (projectM 3 API), `CMakeLists_simple.txt`, `MainActivity.java.part` | Deleted |
| I3 | Unused `appcompat` and `leanback` dependencies plus Jetifier (`Theme.Leanback` is a local framework-based style) | Removed; the app uses framework APIs only |
| I4 | `install.sh` installed the debug APK (debuggable, slower ART); the JNI layer built at `-O0` in debug | Release build signed with the debug key; `install.sh` prefers it; JNI always `-O2` |
| I5 | `proguard-rules.pro` referenced but missing | Reference removed while minify was off; R8 is now on, with `app/proguard-rules.pro` (`-dontobfuscate`) |
| I6 | projectM playlist library shipped but not needed with the new engine | Deleted (`.so` files and headers) |
| I7 | No automated tests | `core/src/test/native/run_native_tests.sh` |
| I8 | Gradle `9.0-milestone-1` (pre-release) with AGP 8.12 | **Not changed.** Moving to a stable Gradle release is recommended |
| I9 | `local.properties` (machine path) and `.idea/` tracked | **Not changed.** Untracking would delete them from your checkout on pull |

## 5. Architecture

The engine is the Android library module `core/` (package `nl.neerdael.projectm.core`): the native code, projectM build, presets, textures, `ProjectMJNI`, `VisualizerView`, `VisualizerRenderer`, `QualityController`, `DeviceProfile` and `DisplayInfo`. The app module `app/` holds the UI, audio capture, track titles and the updater. Another app embeds the engine by including `core/` as a Gradle module (for example from a git submodule of this repository): it calls `ProjectMCore.init(context)` once at startup, shows a `VisualizerView` driven by a `VisualizerRenderer`, and feeds audio and settings through `ProjectMJNI`.

```
ProjectMApplication ── ProjectMCore.init(context) ──────────► native worker thread
                                                             ├─ read presets.idx (prebuilt list; folder listing as fallback)
                                                             ├─ load skip list, shuffle
                                                             └─ prefetch next preset text
MainActivity (UI thread)
  ├─ remote keys / menu ──► ProjectMJNI.next/previous/random/settings  (atomic, any thread)
  ├─ Visualizer on the player's session ──► ProjectMJNI.addWaveform    (mutex buffer)
  └─ VisualizerView.setRenderHeight ─► SurfaceHolder.setFixedSize (hardware scaler)

VisualizerRenderer (GL thread) ─► onDrawFrame (native)
  1. apply dirty settings        5. projectm_opengl_render_frame
  2. first preset / commands     6. output measurement (black skip only if enabled)
  3. auto-switch requests        7. lightweight-transition overlay, capture outgoing frame
  4. feed buffered audio         8. transition stats, FPS → projectM
```

### Threading rules
- Only the GL thread touches the projectM handle (create, render, load, settings).
- All other entry points only write atomics or mutex-protected buffers. This removes a whole class of races and makes `queueEvent()` unnecessary for correctness.

### Preset checks
`tools/check-presets.py` (run by CI) reads every bundled `.milk` file and fails when a preset:
- **cannot react to music:** no `bass`, `mid`, `treb`, `vol` or `*_att` in any equation or shader, the main waveform hidden (`fWaveAlpha` ≤ 0.01 or `wave_a = 0` in code), and no custom waveform enabled;
- uses an **excluded texture** (text, logos or photos of people), or a **texture that isn't bundled**. A texture counts only when its sampler is declared and used, directly or through `#define sampler_x sampler_y`.

`--remove` deletes the failing presets. In 1.9 that removed 116 non-reactive and 73 excluded-texture presets (one was both), leaving 9,606.

### Preset memory (measuring)
The frame buffers of a preset depend only on the resolution. What differs per preset, read from the `.milk` files by `tools/gen-preset-index.py` following projectM's own rules:
- **Images.** projectM loads every image named by `sampler_<name>` or `texsize_<name>` in the warp/comp shaders, used or not, at width × height × 4 bytes (no mipmaps, no power-of-two rounding). Random-image slots count as the largest bundled image. Per preset: median 0.4 MB, max 12 MB.
- **Complex shaders:** the top 1 % by size (≥ 4.2 KB) or with two or more loops. They get a placeholder 32 MB for the GPU driver's compile memory, which can't be read from the file.

The weight (extra MB) is the second column of `presets.idx`: 7,799 presets 0 MB, 1,419 presets 1–4 MB, 388 presets 5 MB or more. 1.9.1 only **measures**. Every `LOAD` log line records the preset's weight, its shader size and loop count, how much the system's available memory dropped, and how much the process grew during the load. The next runs show which presets cause memory peaks at a switch, and whether shaders or images drive them. The RAM-based resolution cap stays in place as a temporary measure until then.

### Preset index
`tools/gen-preset-index.py` writes `core/src/main/assets/presets.idx`: the sorted list of bundled presets, each with a memory weight (see *Preset memory*). CI fails if it is out of date. The worker reads that one small asset. Listing ~10k assets with `AAssetManager_openDir` took 8.4 s on an NVIDIA SHIELD and held the asset-manager lock that UI inflation also needs, so cold start took 10.4 s. Without the index file, the folder is listed as before.

### Transitions
projectM's soft cut renders the outgoing and incoming preset for the whole transition, which doubles CPU (per-vertex equations) and GPU cost and keeps two presets' frame buffers. On a SHIELD at 1260p, 5-second FPS averages fell to 19–36 around every switch, even at 720p.

| Mode | What happens at an automatic switch |
|---|---|
| **Lightweight** | At the end of the frame in which projectM asks for a switch, `SnapshotFade` copies the window into a texture (`glCopyTexImage2D`). The next frame loads the new preset as a hard cut: projectM still seeds it with the old image (`DrawInitialImage`). The snapshot is then drawn over it, fading out with a slow zoom over min(transition, 3 s): one textured full-screen pass per frame. The texture exists only during the fade. |
| **Classic** | projectM's own blend (random transition shader) at the full render size. |
| **Auto** (default, since 1.9.12) | projectM's blend, adapted to keep the frame rate. It starts at 75 % of the render size (60 % on low-end devices): projectM renders into an off-screen framebuffer (`projectm_opengl_render_frame_fbo`, patch 0002) that one `glBlitFramebuffer` stretches onto the surface, and the size change keeps both presets' frames (patch 0002 scales them). Whether a slow blend is GPU- or CPU-bound is told apart by the render thread's CPU time (`CLOCK_THREAD_CPUTIME_ID`) over the blend: GPU-bound (below 80 % CPU) steps down to 60 % and 50 %, also once during a blend that starts far too slow; CPU-bound steps back up (a lower resolution only blurs) and renders the outgoing preset every second frame (`projectm_opengl_set_outgoing_preset_frame_divisor`); three blends with frames to spare step up again. |

Remote-control switches and forced hard cuts are never faded. Beat-triggered hard cuts are off unless *Cut on loud beats* is on (since 1.9.12). If the capture or the overlay shader fails, the switch uses classic. Every load is logged (`LOAD preset=… ms=… programs_cached= programs_compiled=`), and every transition too (`TRANSITION … mode= scale= fps= blend_fps= before_fps= cpu= outgoing_rate= slow_frames=`).

**Historical 4.1.7 memory-traffic measurements (patches 0009–0016).** The timings and upload descriptions in this paragraph/table describe the pre-rebase implementation. The 4.2 port uses upstream Mesh/VertexArray and instance ShaderCache APIs. Upstream Mesh supplies indexed warp drawing but uses glBufferSubData for unchanged buffer sizes, so the old unconditional warp-buffer orphan policy is not retained. These figures do not establish performance gains for 4.2; see [the current patch/value assessment](UPSTREAM_PATCH_VALUE.md).

**Pre-rebase implementation.** On an Ugoos AM6 (Amlogic S922X, Mali-G52 MP6, Android 9) the frame rate fell with the pixel count at a GPU load of 98–99%: the pre-rebase projectM 4.1.7 base never discarded a render target's old contents, so a tile-based GPU (Mali, Adreno, PowerVR) loads every target from memory before each pass, even passes that overwrite it completely, and a frame made up to four full-screen copies to y-flip images. The patches keep the output the same and remove that traffic: `glInvalidateFramebuffer` before every full overwrite (warp, composite, blur, video echo, and the flip copies while blending is off; not for warp or composite shaders that use `clip()`, whose discarded pixels keep the old contents), no first flip when the flip texture already holds the flipped previous frame, the warp and the shapes and waves on top of it in one render pass (the blur, made from the previous frame, moves before the warp; not for presets whose warp shader reads the blur textures, about a quarter, which would then see this frame's blur instead of last frame's), blur passes drawn straight into their textures instead of copied, the motion-vector u/v map written only while the preset shows motion vectors, video echo drawn upside down so the third flip goes away, and the warp mesh as one indexed draw with an orphaned buffer (no GPU stall, about 1 MB less copied per frame on the CPU). Since 0016 the active preset also draws its final image straight into the target framebuffer (the window, or the off-screen target during scaled blends) instead of into its own texture that projectM then copies: `projectm_opengl_set_direct_output`. The texture is still needed in two cases: transitions blend both presets' textures, and a new preset starts from the outgoing preset's last image (`DrawInitialImage`). So projectM stores the frame during transitions and in a frame in which it requests a switch, and the engine stores it while a remote-control command or a black-preset skip is pending: such a switch waits one frame (16–33 ms) after a direct frame. `SwitchPreset` logs a warning if a switch ever follows a direct frame; none in a test with ten instant cuts and remote presses.

**Blur framebuffer ownership (patch 0041).** `BlurTexture::Update` saves both caller framebuffer bindings before allocating its textures. Allocation calls `Framebuffer::SetSize`, which unbinds the read and draw targets. Saving them afterwards restored framebuffer zero on first use or resize. When the warp shader samples blur, the update runs after warping, so subsequent waveform and border draws lost their target. The unchanged `midgitstraights of majillaen - featy sweet.milk` reproduced error 1286 on host OpenGL; preserving the bindings removes that error. This does not establish cross-GPU appearance or a frame-rate improvement.

Measured with a pinned preset at fixed render sizes (`debug.projectmtv.preset`, profile build, music playing), all patches against none:

| Preset | 1080p | 1440p | 2160p |
|---|---|---|---|
| 390 threx … calmer less agile (heavy, composite shader) | 33.6 → 37.1 fps | 20.4 → 23.3 | 9.3 → 10.8 |
| TonyMilkdrop - Blood In Me edit1 (composite shader) | 43.8 → 53.5 | 25.4 → 32.0 | 13.1 → 15.8 |
| EoS+ Phat - magnetosphere 13 - pulsar (no composite shader) | 60 → 60 (vsync) | 52.1 → 60 (vsync) | 26.1 → 55.1 |

Both presets with a composite shader read the blur textures in their warp shader, so they do not get the merged render pass (0015). The gains are largest where memory traffic dominates (high resolutions, presets without a composite shader); presets with heavy composite shaders are limited by shader work. The only visible difference possible: when a preset turns motion vectors on, they use an older u/v map in that frame (the last one written while it showed them). Not adopted: half-precision preset shaders (up to twice the shader throughput on Mali, but texture coordinates lose precision at high resolutions).

**Lines (patch 0024).** projectM draws waveforms, custom waves, shape outlines and motion vectors as GL lines, 1 px wide, thick ones several times with an offset. A GL line is a fixed number of pixels wide, so its share of the picture changes with the render size, and so did a preset's brightness. `projectm_opengl_set_line_reference_size(W_ref, H_ref)` draws the lines as instanced quads instead: one instance per segment, miter joins (also for waveforms: round joins, which the issue suggests, would blend each joint twice), 1 px wide at the reference size and wider above it by the square root of the area ratio, `max(1, sqrt(W·H / (W_ref·H_ref)))`, so a line covers the same share of the picture at any size and aspect ratio (a suggestion of projectM's main developer). The legacy/low-resolution path uses MilkDrop's 1024×768 reference; active Native trails uses 1280×720 (or the actual integer canvas during a scaled transition). Historically the app used 1024×768 everywhere (set on every new projectM instance; there is no setting): a line covers the share of the picture it covered on the author's screen, 1.62 px at 1920×1080 and 3.25 px at 3840×2160. At and below the reference area the lines are drawn as before, MilkDrop's 1 px lines at full brightness: in testing, thinner lines faded by their width made feedback presets go dark below 1080 (`$$$ Royal - Mashup (191)` black at 480). Dots (GL points) use whole-pixel sizes, with alpha faded by the difference in area. The waveform's sample count follows the reference size too: MilkDrop's line waveforms draw a third of their samples when the render is narrower than three times the sample count (160 instead of 480 dots below 1440 px), so with a reference size that rule uses the reference-equivalent width, render width / line scale (1182 px at 1920×1080 and 3840×2160 with reference 1024×768); otherwise a large render drew three times MilkDrop's dots, and `$$$ Royal - Mashup (103)` was 2.3 times as bright as at 1024×768 (0.50 mean luma at 1080 against 0.22; now 0.21 at 1080 and 0.23 at 2160). Two more of MilkDrop's quantities tied to its render size follow the reference above it, because presets were made at that size: the fade of the spiro and hash waves (`Waveform::MaximizeColors` scales their alpha by the texture size, max(W, H): 0.11 up to 1024, 0.13 up to 2048, 0.15 above; with a reference size it uses the reference's, `MaximizeColorsTextureSize()`), and the blur levels. MilkDrop makes blur1 at a quarter of its texture size (blur2 an eighth, blur3 a sixteenth), blurred by a few of their own texels, so the blur radius is a fixed share of the picture only at one size: at 3840×2160 blur1 was 3.75 times narrower than at 1024×768, and presets that glow or smear through the blur textures looked sharper and darker. With a reference size the blur chain is built as from a source of the reference's area, the render size divided by the line scale (1182×665 at 1080 and 2160, `BlurSourceFor()`): the blur textures keep that size, and the first pass reads the previous frame through its mipmaps at log2 of the scale (a `glGenerateMipmap` per frame on the frame the blur reads), so every source pixel still counts. The mip levels stay allocated (about a third more than the frame); the texture pool counts them in its limit and reported bytes. Presets without blur are unchanged by it. Edges are hard, and the width is measured along the minor axis as for GL lines, so at the reference size a thin quad line lights the pixels MilkDrop's 1 px line lights, apart from a few at sharp turns. The quad is the band itself, so like a GL line it lights one row (or column) per step, also when it lies exactly on a pixel border. Which of the two rows such a tie lights is left to the GL implementation: on desktop GL the quads and GL lines agree, and on GLES the quads are moved by 1/64 px so that ties follow Mali's GL lines (verified on a Mali-G52; Tegra not verified). An anti-aliased edge exists (`projectm_opengl_set_line_antialiasing`) but is off: in testing, a soft edge made a feedback preset 14% darker. Thick lines are drawn as MilkDrop draws them: the thin line four times, offset by (0, 0), (+x, 0), (+x, +y) and (0, +y), a pixel for the main wave and half a pixel for custom waves and shape outlines, with the offsets scaled like the width. If the driver rejects the line shaders, the GL lines are drawn. With reference size 0 the GL lines are drawn as before, frame for frame (preset-lab compares frame hashes against a baseline).

Measured with reference 1920×1080 and `preset-lab line-compare` on every 40th bundled preset (241), rendering identical frames in both modes. 65 presets render differently from run to run and 1 fails to load, so 175 were compared (168 of them draw visible lines at 1080). At 1080 the median brightness deviation from GL lines is 0.01% and no preset differs by more than 10%; between 1080 and 1440 a preset's brightness changes by a median 2.0% with quad lines against 4.3% with GL lines (below 1080 both draw 1 px lines, so between 720 and 1440 it is 10.0% against 10.9%). On synthetic presets without feedback, thin lines and dots match GL lines to within a few pixels (0.1% of their brightness) and thick lines within 0.2%. Thick shape outlines are the exception: desktop GL smooths shape outlines (`GL_LINE_SMOOTH`, which GLES lacks), so they were checked against MilkDrop's scheme (four passes offset by half a pixel) rather than measured against desktop GL lines. Measured later against GL lines without that smoothing (as on GLES) at 1182×665, thick outlines at 1080 and 2160 are within 1.3%, with the same number of hits per pixel; custom waves, thin and thick, are within 0.7%. On a Ugoos AM6 (Mali-G52, Android 9) the line shaders compile without errors; with a preset that draws many outlined shapes (`Flexi - alien complex 03`) the frame rate at 1080 is within measurement noise of GL lines (−0.6% and −0.85% in two runs), and motion vectors at 2160, where the quads are 2 px wide, are up to 1.85% slower.

**Why 1024×768.** MilkDrop presets were made with 1 px lines at about 1024×768, so that is their authored look. On the desktop, 18 presets with lines (feedback showcases and the largest before/after differences) were rendered with identical audio, clock and seeds and compared by mean brightness against GL lines at 1024×768, and against GL lines at 1182×665: 16:9 with the area of 1024×768, where 1 px lines are what the reference draws, so it separates the change from 4:3 to 16:9 from the change in size. Changing the aspect alone changes many feedback presets a lot (with GL lines at 1182×665 against 1024×768, `Goody's Trichromatic Mind Games` is 1.35 times as bright and `suksma - bleuneycombinatoriccitensor` 0.11 times), so the 16:9 render is the fairer ground truth for a 16:9 TV. Against it, with the reference and the blur and fade rules above, the median ratio is 1.01 at 1920×1080 and 1.04 at 3840×2160, and 17 of 18 presets are within 10% at 1080 and 14 of 18 at 2160 (median deviation 4.5% and 6.3%); GL lines give 0.91 and 0.76 with 4 of 18 within 10% at either size. Against the 4:3 render the medians are 1.02 and 1.06 (GL lines 0.87 and 0.63). Between 1080 and 2160 a preset's brightness changes by a median 2.4%, against 15% with GL lines. The blur rule moved the 2160 count from 10 to 14 (`TonyMilkdrop - Nuclear [Flexi - help out + alien complex]` 0.81 → 0.96, `fat cancer tour meant t nz+` 1.14 → 0.99); the fade rule changes the frames of one preset in this set, not its brightness. Reference 1920×1080, an earlier default, gave medians of 0.85 and 0.97 against the 4:3 render. Without the virtual texsize below, presets that use `texsize` in their own shaders depended on the render size by themselves (`Serge circles005b` 1.35 at 2160 from `texsize`-scaled warp frequencies and offsets; `$$$ Royal - Mashup (191)`, a one-texel neighbour-difference recurrence seeded by the wave, 2–14 times as bright depending on aspect and size, which no uniform fixes), and the 4:3 to 16:9 change of the composition is the aspect itself. `suksma - penattrition` (0.73 at 2160) keeps MilkDrop's minimum motion-vector length in pixels; scaling it fixed that preset but made another worse, so patch 0024 left it as MilkDrop has it. Patch 0038 (diffusion) now scales that minimum only while compensation is active; the earlier measurements below do not validate that change. The blur rule makes blur-heavy presets cheaper at 2160, not dearer: the per-frame `glGenerateMipmap` on the 3840×2160 frame costs less than the full-size blur passes it replaces. On the Ugoos AM6 at render height 2160 (60 fps cap, GPU at 99% in every run, no music playing, two alternating runs each, release 2.1.4 with GL lines against this build), `TonyMilkdrop - Nuclear [Flexi - help out + alien complex]` went from 10.69 to 11.32 fps (+5.9%) and `fat cancer tour meant t nz+` from 7.34 to 9.12 fps (+24%). On the Ugoos AM6 (music playing, 60 s per run, release 2.1.4 with GL lines against reference 1024×768, alternating runs), `$$$ Royal - Mashup (191)`, `(103)` and `(162)` hold the 60 fps cap at render height 1080 with both (GPU utilization about 79% against 75%), `Flexi - alien complex 03` is 2.0% slower at 1080 (44.6 against 43.7 fps, GPU-bound), and at 2160 Mashup (191) is 0.9% and Mashup (103) 3.9% slower (32.4 against 32.2 fps and 35.4 against 33.9 fps).

**Virtual texsize and the render height cap.** Above the reference area, preset code sees a canvas of the reference's area at the render's aspect ratio, the render size divided by the line scale (1182×665 at 1080 and 2160, `ShaderCanvasSize()`, the size the blur levels are made from): `texsize` (`_c7`) and `texsize_main`, `mip_x/y/avg` (`_c12`) and the per-frame and per-pixel `pixelsx/pixelsy`. In MilkDrop `texsize` is the internal canvas the preset was tuned on (MilkDrop's own canvas stretch also reported the small canvas), and 5,284 of the 9,606 bundled presets step by `texsize.zw` texels, 4,428 turn uv into pixels with `texsize.xy`. With the real size those steps are fixed in pixels: a warp that advects by `grad*texsize.zw*6` moves the picture 3.25 times slower at 2160, so `Acid Mandala v1c` stayed small and desaturated (saturation 0.46 against 0.80). The textures, their sampling and the sizes of real textures (`texsize_<name>`) are unchanged; without a reference size and at or below its area the frames are byte-identical. That leaves one render-size effect no uniform can move: a feedback preset re-samples its canvas bilinearly every frame, which smooths it by about a sixth of a real texel² per frame, so at 2160 the smoothing is about 10 times smaller in picture units than at the reference and low-diffusion presets settle into another regime (`Acid Mandala`'s red centre, mean centre R over 12 s: 0.45 authored at 1182×665, 0.43 at render height 1260, 0.41 at 1330, 0.43 at 1400, 0.35 at 1440, 0.34 at 1530, 0.27 at 2160; 414 bundled presets use this gradient-advection warp). For these historical measurements, Auto and numeric fixed choices used a 1330 render-height cap, subject to panel and memory limits, and the display scaler upscaled the render. That policy has been retired: the current automatic controller can reach the native panel size, and all saved fixed/native modes normalize to Auto. Native trails is described below. The following desktop and TV measurements describe the cap before the diffusion patch, not gains attributable to diffusion compensation. Measured on the desktop on 24 presets (the 18 above, `Acid Mandala v1c` and five gradient-advection presets) against the authored 1182×665 render, every frame brought to 3840×2160 with bicubic upscaling as a TV scaler would, 4 s after a 4 s warm-up: the median image error (mean absolute difference of five frames) is 0.112 for the previous build at native 2160, 0.098 with the virtual texsize at 2160, and 0.074, 0.074 and 0.075 with it at 1260, 1330 and 1440; brightness is within 10% for 16, 19, 19, 20 and 20 of 24, and saturation within a median 2% throughout. 1330 is the highest height that keeps `Acid Mandala`'s centre; between 1260 and 1440 the other presets differ within run-to-run noise. Against the previous build at native 2160, 15 presets get closer to the authored render and 2 further (`$$$ Royal - Mashup (191)` 0.29 → 0.38, the recurrence above; `Hexcollie` 0.19 → 0.21, its noise-volume grain is coarser). The cost is detail: the variance of the Laplacian of the 2160 image, a sharpness measure, falls from a median 447 at native 2160 to 81 (the authored render upscaled from 1182×665: 13). It is also much faster on 4K TVs: on the Ugoos AM6 (Mali-G52) with render height 2160 chosen in both apps (60 fps cap, music playing, two alternating 60 s runs each, release 2.1.4 at native 2160 with GL lines against this build at the capped 2364×1330, confirmed in logcat), `$$$ Royal - Mashup (103)` went from 36.3 fps to the 60 fps cap (GPU 99% → 88%), `TonyMilkdrop - I Like Cartoon --- Isosceles edit` from 12.7 to 33.7 fps, `fat cancer tour meant t nz+` from 7.6 to 23.6 fps and `Flexi - alien complex 03` from 12.3 to 30.1 fps.

**Current audit repairs (0017–0033).** Built-in opacity preserves mode-adjusted alpha, volume multiplication and the faint-wave threshold. Valid custom-wave windows are centered and separated; point equations receive fresh host inputs, while per-pixel aspect inputs use inverse factors. Named constants retain original double decimals, gamma-only passes use their separate epsilon, and negative odd echo orientation retains the signed horizontal flip. Legacy oscillator Y, triangle topology, row traversal and the exact-axis angle seam follow original physical conventions. Local RGB brightening and border fan coverage retain float colour/alpha. Later authored sample/dot/circle/style/field fixes are described below. See the [patch catalog](user-guide/engine/patches.md) and [active evidence](superpowers/evidence/authored-fidelity-followup/README.md) for current numbering and qualified limits.

**Native trails (patch 0042).** The current Native core uses an authored feedback state **L**, with native-resolution new geometry and composite output. Standard is the JNI/AAR default and skips the native warp; Medium/High keep a centered, headroom-limited detail band with gain caps 0.5/1. The shader preserves each block/channel’s reconstructed-base mean before RGBA8 quantization, avoiding positive energy from clipping signed detail. Each preset owns its resources, including during transitions. Native viewport restoration and UV-map invalidation on mode changes are covered by image regressions. See [Native trails design and validation](superpowers/specs/2026-10-05-native-trails.md) for pipeline, memory, API and evidence scope.

Patch0043 draws the authored geometry into the current canvas warp target and alternates the existing authored buffers. Prepared waveform vertices and bounded shape batches are reused for native presentation; equations and shader/evaluator RNG are not reevaluated for the second destination. Shape drawing explicitly restores per-vertex inputs after instanced line draws. Native geometry is no longer center-sampled into persistent authored state. No extra authored texture or full-canvas copy is allocated by this correction; GPU work for native geometry replay must still be measured on the device.

The Android core enables trails above 1330p with a 1280×720 line reference. `S = round(sqrt(W*H/(1280*720)))`; compatible canvases require S≥2 and both dimensions divisible by S. At 3840×2160, S=3 and L is1280×720; at2560×1440, S=2. A scaled transition can use a different integer canvas; preset-local texsize/blur/geometry decisions follow that actual canvas. Smaller/incompatible sizes and driver shader/resource failures retain the legacy path. Diagnostics distinguishes active canvas, inactive render size, canvas fallback and shader/resource fallback.

**Legacy diffusion and fallback (0038).** When detail is inactive, eligible bilinear warp reads use the existing average-preserving variance filter `(scale²-1)/6`, capped1.9. Historical evidence retains earlier diffusion patch numbering. Patch0039 remains in the historical series; new builds no longer publish or support a capped-policy AAR.

One draw with two render targets writes the exact y-flipped frame (`texelFetch`) and its filtered copy. Only bilinear warp reads use the filtered copy. Warp sampler descriptors whose bound sampler is `GL_NEAREST` (`sampler_pw_main`, `sampler_pc_main` and their aliases), the composite shader and the old-school composite read the exact copy, as at the reference size. Point reads of state encoded in colour channels are therefore not averaged. The pass replaces the required end-of-frame flip, and both copies become the next frame's warp inputs; motion vectors drawn onto the previous canvas trigger a recomputation before the warp. Full-screen pass counts therefore match the uncompensated path, but each pass writes one extra colour target, and an active preset keeps one more render-size RGBA texture. Scale/reference and framebuffer changes invalidate the cached inputs. The blur levels are still made from the unfiltered previous frame, so `GetBlur` and bilinear `GetPixel` reads see different added footprints. The pass explicitly disables blending so it overwrites its target, including RGBA source colour, rather than multiplying it by alpha again. Shader uniform locations are cached; shader failure retains the ordinary copy path. No reference or a render at/below the reference area leaves compensation inactive.

Eligibility is a conservative token-pattern check at preset load: point-only feedback, recognized undisplaced `uv_orig` main reads, and the recognized peak-plus-sharpen pattern keep the ordinary path. Mixed point/bilinear feedback may remain eligible. This is not complete shader semantic analysis, and skipping a warp does not correct its resolution dependence. The minimum motion-vector length scales only with active compensation.

**Validation scope and accepted checkpoint.** Historical baseline29/candidate30 and `1b2c2663` MRT measurements retain their own source, artifact, clock and GPU identities. They are not measurements of the new dual-AAR policy. The [final merged-renderer validation](superpowers/evidence/0025-feedback-diffusion/final-merged-validation/README.md) compares baseline35 (`f435dd7c`), final MRT36 (`0e3f948e`) and a true classic35 `ref0,0` control on one Apple M4 Pro emulator stack, with fixed signal/seed and eight selected captures per job. Its 64-case sample uses successful receipts from a partial older baseline24 corpus; newly recovered translator/evaluator cases are underrepresented.

Magnitude matters more than direction counts. At Native 2160, paired thumbnail-error improvement versus baseline35 has median 17.084% relative reduction, but only 0.001482 absolute normalized-RGB error reduction. Paired native-luma error has median 0.571% relative reduction. Against the earlier overwrite-fixed `790aaa24` candidate, recent median effects are much smaller; zero-error denominators are explicitly undefined. Some presets have much larger positive or negative effects. These are sampled metrics, not a perceptual threshold or a universal fidelity result. Exact selected-frame repeats establish stability under the recorded inputs; they do not bound sensitivity to small size changes. Reference-size bands remain planned follow-up, not a gate on the user-approved research checkpoint.

**One Native core.** The APK and canonical `projectM-TV-core[-<version>].aar` use the same Native-capable `:core`. The separate capped1330 artifact and new `core-native` aliases are retired. Legacy `native` build-property spelling is accepted; `capped` is rejected. Public Java/JNI names remain compatible. The projectM C API defaults off for engine compatibility; Android JNI defaults Standard, selecting the1280×720 reference above1330p. Fixed-size workers explicitly control reference/level for validation.

**Default automatic quality.** `QualityController` chooses from its FPS ladder up to the detected panel size, using live available memory and estimated rendering growth. Advanced › Resolution exposes Auto, supported fixed heights and Native via additive `setResolutionMode`; there is no RAM-limiter control or installed-RAM height ceiling. Explicit modes bypass FPS adaptation and slow-preset skipping, retain live memory protection and restore toward the selected height after recovery. Deprecated fixed/native settings normalize to Auto. The selected trails gain contributes to the memory estimate, and enabled transitions budget two presets. Low memory lowers resolution, flushes returned texture cache and pauses prewarming; recovered headroom can permit later growth. The reserve is Android threshold + 128 MiB when kernel-visible total RAM is at least 3,584 MiB; smaller devices retain max(total RAM / 5, threshold + 128 MiB). Both retain the 64 MiB recovery margin and candidate resize allowance. Aggregate available-memory samples reflect competing use; no per-app reclaim estimate, process cleanup, root access or new setting is used. See [release artifact ownership](RELEASING.md#downloads-and-core-library).

**The load stall (solved in 1.9.12).** `projectm_load_preset_data` parses the preset, translates its HLSL shaders to GLSL and links them on the GL thread; on the SHIELD that froze the picture for 0.5–1.9 s (median 0.9 s) at every switch. Profiled with simpleperf (`docs/PROFILING.md`): 73 % was the driver linking the warp and composite programs, most of the rest the HLSL translator constructing `std::locale("C")` for every float literal. Now `PresetPrewarmer` loads the upcoming presets (`PresetLibrary::PeekNext`, and since 1.9.16 also the random pick made one step ahead, `PeekRandom`, and the previous preset, `PeekPrevious`) into a short-lived second projectM instance on a background thread with its own EGL pbuffer context (the evaluator's `rand()` state is per thread, patch 0004); the linked programs go into a process-wide program binary cache (patch 0002), from which the render thread's load takes them with `glProgramBinary`, and the translator uses `std::locale::classic()` (patch 0003). Switches now take 10–80 ms. Random and previous-preset switches are not prewarmed and still compile. Two troubleshooting switches (Settings › Advanced, on by default) can isolate GPU drivers that fail on this path: *Background compile* stops the prewarm thread and its second EGL context (`ProjectMJNI.setBackgroundCompile`, applied on the GL thread), and *Shader binary cache* makes every program compile from source with no binary export or `glProgramBinary` load (`setShaderBinaryCache`, patch 0035). Both threads record what they were last doing in a fixed-size trail file (`diagnostics_trail.h`) that *Last exit* shows next to Android's exit records.

### Preset skipping
A preset is added to `files/skipped_presets.txt` and never picked again when:
1. its file is empty or unreadable;
2. projectM reports a load failure (`projectm_set_preset_switch_failed_event_callback`), e.g. a file it cannot parse; shaders that do not compile already fall back to projectM's default warp and composite shaders. Equation code no longer fails a load (patches 0029 and 0033–0035): code the evaluator rejects is compiled again in MilkDrop's form (numbered lines joined, `//` and `\\` comments removed, a `;` inside parentheses without a following operand read as a space, as NS-EEL does), a lone `.` is the number 0, and a block that still does not compile is left out, like MilkDrop's `CState::RecompileExpressions`: failed init code leaves the q (preset) or t (custom wave/shape) variables at zero, other failed blocks do not run. Each left-out block is logged as `Preset code left out` (`projectm_set_preset_initialization_warning_event_callback`); the preset is not skipped;
3. *Skip slow presets* is on and it stays below 50 % of the target FPS at the lowest resolution; or
4. *Skip blank presets* is on (**on by default since 1.9.4**) and it has been black **twice**, in any showings: 5 samples in a row, 1 s apart, with no channel above 20/255 while music plays (samples count only after 3 s of uninterrupted music, since presets that draw from the music start from black). The first time the app only moves on to the next preset and records a strike in `files/skipped_presets.txt.blank`; a one-off (music starting late, a slow build-up) therefore never removes a preset. After 3 black verdicts in a row with no visible preset in between, nothing is struck or skipped until a preset shows output again (a rendering fault must not empty the library).

**Output measurement.** For 20 s after each transition, 5 rows and 5 columns of the window are sampled once per second while audio is present. One `OUTPUT` log line per preset records the luma range (flatness), the share of sampled pixels that changed visibly since the previous sample (luma ≥ 8/255, or hue ≥ 12° on saturated pixels), for the whole frame and for the most active of 40 regions (quarters of each line), and how many changes were luma versus hue-only. Flat and still output are **only measured**. Presets that looked dull on the SHIELD ran on a build without textures, and a wrong skip is permanent, so thresholds get chosen from real runs first. For the same reason, 1.9 clears the skip list once on first launch.

*Reset* in the menu clears the list and the strikes.

### Resolution
The GL surface buffer is resized with `SurfaceHolder.setFixedSize(w, h)`. The display composer scales it to the panel, so a 720p render fills a 1080p or 4K screen without extra GPU work ([Android Developers blog: using the hardware scaler](https://android-developers.googleblog.com/2013/09/using-hardware-scaler-for-performance.html)). projectM always renders at the surface size, so no viewport workarounds are needed.

**True 4K (`DisplayInfo`).** Android TVs commonly drive the UI at 1080p on a 4K panel, while a SurfaceView can still be shown at the panel's full physical resolution. `getRealSize()` reports the UI size, so before 1.8 "Native" was 1080p on such TVs. The physical size is now detected as AndroidX Media3 does in `Util.getCurrentDisplayModeSize`: the `vendor.display-size` / `sys.display-size` property, Sony's 4K panel feature, then `Display.Mode.getPhysicalWidth/Height()`. **Needs on-device confirmation per TV model:** *Advanced › Diagnostics* shows the panel, UI and render sizes.

**Automatic native-capable resolution (`QualityController`).** Auto is the default mode. The new `resolution_mode` preference opts into fixed height or Native; retired `render_height` values still normalize to Auto. `setResolutionMode` validates numeric choices against the detected panel; Native follows that panel. Fixed/Native keep their selection through preset changes and low FPS, but memory reviews can temporarily reduce actual size. Returning to Auto uses its separately saved automatic starting height. It targets FPS with the existing settle periods, up/down hysteresis, CPU-bound detection and per-preset probe backoff, now up to the full panel height. `NATIVE_HEIGHT`, `RENDER_HEIGHT_CAP`, fixed-mode methods and constructor signatures remain compatibility symbols; they do not impose a1330 automatic ceiling or fixed output. Old fixed-resolution/static-RAM preferences do not override Auto. Diagnostics shows actual panel/UI/render dimensions and memory constraint status.

**Automatic memory headroom.** The former installed-RAM limiter is removed. `ProjectMCore.init` initializes an application-context ActivityManager sampler; the existing once-a-second FPS callback samples `MemoryInfo` (total/available/threshold/lowMemory). Current available memory already includes this app and other apps’ usage. A pure budget estimates additional texture allocation before growth, including Native trail detail and two live presets when transitions are enabled. The reserve and footprint factors are conservative policy estimates, not measured process/GPU limits; see the design for exact values. Invalid samples prevent growth; low-memory/reserve breaches are considered before FPS settling. Healthy samples and recovery hysteresis permit later growth rather than a permanent session RAM ceiling.

On the historical2GB SHIELD, 1440p-and-above rendering caused Android’s low-memory killer to close SoundCloud and other processes. That observation motivates proactive headroom checks and cache/prewarm cleanup; it does not prove that any reserve guarantees survival under every vendor policy. Live music-process and memory validation remains necessary.

Managed hosts review trails/transition settings atomically, invalidate the old FPS generation,
then call `revalidateForAllocationChange()`. A confirmed reduction publishes its current
height before sampling memory: the next new-generation rendered-frame sample observes the
texture release and still lowers resolution if pressure persists. Growth and unconfirmed
allocations require a fresh full budget. Visibility/context resumes independently use
`revalidateForResume` and always sample current memory before rendering.
The controller captures the old allocation before changing settings or invoking a height
listener, so enabling trails or blending can become a net reduction after a height downshift.
Hosts do not recalculate both old and new topologies at the already-lowered height.

### Frame pacing
Full rate renders continuously (`RENDERMODE_CONTINUOUSLY`). Half rate switches to `RENDERMODE_WHEN_DIRTY` and a `Choreographer` callback calls `requestRender()` on every second vsync: 30 fps at 60 Hz, 25 fps at 50 Hz. A steady half rate looks smoother than an uneven 40–50 fps and leaves the GPU room for heavy presets. projectM's `time` follows the wall clock, so time-driven motion keeps its speed; feedback motion (zoom, rotation, decay) is applied once per frame and does depend on the frame rate.

### Threads
| Thread | Priority | Work |
|---|---|---|
| GL (GLSurfaceView) | `THREAD_PRIORITY_DISPLAY` | projectM render, preset loading, output measurement, transition overlay |
| AudioCapture (HandlerThread) | `THREAD_PRIORITY_AUDIO` | `Visualizer` callbacks → `addWaveform` |
| Native worker | default | Preset indexing and prefetch |
| UI | default | Overlay; status polled every 500 ms, text only updated when changed |

### Overlay UI
`OptionRow` is a focusable settings row: ↑/↓ moves between rows, ‹ › changes the value, and center cycles it or runs an action. The main panel (now playing, transport, auto change, preset mood (All / Chill / Normal / Intense), preset duration) ends with **Track display ›** (track info on/off, how long, pill style) and **Advanced ›**, which each slide a separate panel over it. Advanced holds resolution, frame rate, detail (mesh), Native trails (Standard / Medium / High), transition duration, transitions (Auto / Lightweight / Classic), cut on loud beats, skip slow presets, skip blank presets, skipped-preset reset and live diagnostics. BACK returns. Advanced scrolls vertically when its rows exceed the safe screen area; D-pad focus brings each row into view. All panels sit within the 48 dp / 27 dp overscan-safe margins. The track corner (`TrackCorner`, upper left) stays on screen while a panel is open: it is at most 60% of the screen wide, as in Milkbeat, and never reaches into the panel column; the diagnostics panel starts below it. Views fade out and are set to `GONE`, so a hidden overlay costs nothing to draw. Long preset names use a marquee, which is only restarted when the text actually changes.

### Device tiers (`DeviceProfile`)
| Tier | Rule | Auto start / floor | Frame rate | Detail (mesh) | Transition | Skip slow |
|---|---|---|---|---|---|---|
| HIGH | NVIDIA Shield / Tegra | 1440p / 720p | 30 | High 64×48 | 7 s | on |
| STANDARD | everything else | 1080p / 540p | 30 | Medium 48×32 | 7 s | on |
| LOW | `isLowRamDevice()` or <1.6 GB RAM (e.g. older Fire TV sticks) | 720p / 360p | 30 | Low 32×24 | 2 s | on |

Detail levels: Minimal 24×16, Low 32×24, Medium 48×32, High 64×48, Ultra 96×72. The per-vertex equations run on the CPU for every vertex on every frame, which is usually the bottleneck on low-end ARM boxes.

Saved fixed-resolution values, including 1440/2160 and the legacy `NATIVE_HEIGHT` sentinel, all normalize to Auto. A remembered automatic height is only a starting candidate, reviewed against live memory and adjusted for target FPS. New builds publish one Native-capable core and reject the retired `capped` policy; historical releases remain unchanged.

## 6. Verification performed

| Check | Result |
|---|---|
| Native engine compiled with `-Wall -Wextra` (host clang, projectM 4.1 headers, stub Android headers) | Clean |
| Java compiled against the Android 14 framework (`android-all` jar) with a generated `R` | Clean (deprecation warnings only) |
| All 19 JNI names and signatures cross-checked (`javac -h` header compiled against the implementation) | Match |
| Host engine tests under ASan + UBSan: indexing/filtering, first frame, settings, next/random/previous, auto-switch, forced hard cut, mesh re-apply, failure skip + persistence, audio cap, black detection (silence / visible / black / disabled), skip-current, reset, context-loss resume | all pass |
| JVM tests (`QualityControllerTest`): levels per panel, change only at preset switch, back-off, severe drop, slow-preset skip, low-tier floor | 5/5 pass |
| 1.9 host engine tests (ASan + UBSan): `presets.idx` with CRLF/blank/junk lines and folder fallback; lightweight capture → hard cut → fade; remote switch ends fade; hard cuts never faded; capture failure → classic; classic mode; Auto switches only after a slow classic blend; black skipping off by default; `OUTPUT` flat/still lines; readback from the window framebuffer | all pass |
| 1.9 `fade_gl_test` on Mesa llvmpipe (OpenGL ES 3.2, headless EGL): capture, fade curve (start / half / end), self-stop, GL state restored (blend, scissor, program, VAO, texture unit, sampler binding) | all pass |
| 1.9 JVM tests: memory limit caps Auto and fixed levels, remembered 4K clamped, memory pressure lowers once per preset, second failure blocks a level | 9/9 pass |
| GitHub Actions: Gradle build + NDK/CMake native build + APK packaging on ubuntu-24.04 | green |
| **On-device test** | **Not done yet.** Needs a run on Shield / TCL / Fire TV |

## 7. What could go wrong

| Risk | Likelihood | Mitigation |
|---|---|---|
| Black detector skips a legitimately very dark preset | Low (off by default since 1.9) | Only when enabled, only while audio plays, 5 consecutive samples; *Reset* restores all |
| Live render-footprint/reserve estimates are too conservative or miss driver resource costs | Medium | Validate actual Auto sizes, memory headroom and trails/transition workloads. Review allocation settings atomically, preserve resident credit for reductions, and lower under pressure; no manual RAM toggle remains |
| `glCopyTexImage2D` from the window is slow or unsupported on a driver | Low | Only on switch frames; any GL error falls back to classic; *Transitions › Classic* |
| Two heavy presets do not fit in a frame on the CPU even with the outgoing one at half rate | Medium (preset-dependent) | Such blends still dip (the SHIELD: 15–30 fps for the heaviest pairs). Since 1.9.16 custom shapes are drawn in batches (patch 0006, +74–93% fps on shape-heavy presets); waveform-heavy presets are limited by the projectm-eval interpreter |
| The texture pool keeps the discarded preset's frame buffer textures (patch 0007; up to 48 MB, typically 16 MB at 720p) | Low | Only while at least 20% of RAM is free and no pressure pause runs; emptied at the first `onTrimMemory`; reused textures are cleared first, so rendering is identical (verified on Mesa) |
| The background compiler's second projectM instance costs memory (textures it loads), and memory pressure makes Android take it from the music player | Low | The instance exists only for the ~0.1–1 s of each compile, at a tiny window size; no compile while less than 15 % of RAM is available, and a 20 s pause after each `onTrimMemory` signal (60 s up to 1.9.15); the program cache is capped at 8 MB including its keys |
| Visualizer returns silence (DRM apps, some vendors), so black detection never runs | Medium | Load-failure skipping still works; visuals follow projectM's idle response |
| A device without OpenGL ES 3.0 can no longer install the app | Low (projectM 4 never worked there anyway) | Manifest now states the real requirement |
| `setFixedSize` or physical-panel detection behaves oddly on specific TV firmware | Device-dependent | Inspect panel/UI/render dimensions in Diagnostics; return to Auto or a lower supported fixed choice. Native also uses `setFixedSize`, with the detected panel height, so it is not a layout-size workaround |
| Preset load still freezes the picture for a random/previous switch or when the background compile has not finished | Low | Program cache; `LOAD … programs_compiled=` shows misses |
| Pulling this change removes build caches from the index | Certain | Harmless; Gradle and CMake regenerate them |

## 8. Recommended next steps
1. Build 1.8 locally (`./gradlew assembleRelease && ./install.sh`) and test on your weakest and strongest TVs.
2. Run `tools/tv-diagnostics.sh <tv-ip>:5555 --no-install --duration 180` (see `docs/DIAGNOSTICS.md`) for startup, FPS, resolution and composition data.
3. Move Gradle to a stable release.
4. ~~Add CI~~ Done: `.github/workflows/android.yml` (see `docs/RELEASING.md`).

## Audio source

**Why the Visualizer can hear nothing.** On an NVIDIA SHIELD (Android 11) with HDMI eARC and Dolby output, media is mixed on an output of the Dolby "MSD" module (`AUDIO_DEVICE_OUT_BUS`), encoded to E-AC3 and bridged to HDMI. Android picks the output for session-0 effects in `AudioPolicyManager::selectOutputForMusicEffects()` from the outputs of the device media would normally use (HDMI), not the MSD outputs. No active output qualifies, so it falls back to the idle primary output, and the Visualizer receives silence. The 1.9 diagnostics show exactly this: the Visualizer (effect 51) sits on `AudioOut_D` with 0 tracks while SoundCloud plays on `AudioOut_1D`. The selection code is unchanged in Android 14 (see the [Android 11](https://raw.githubusercontent.com/LineageOS/android_frameworks_av/lineage-18.1/services/audiopolicy/managerdefault/AudioPolicyManager.cpp) and [Android 14](https://raw.githubusercontent.com/LineageOS/android_frameworks_av/lineage-21.0/services/audiopolicy/managerdefault/AudioPolicyManager.cpp) sources, LineageOS mirror).

**Player session search.** A Visualizer attached to the player's own audio session is placed on the output that session plays on, so it hears the music where session 0 does not. The app can't ask Android for other apps' sessions, but session IDs come from one counter (steps of 8), so `PlayerSessionFinder` probes the 128 IDs below a freshly generated one, 16 at a time with 300 ms to settle, and takes the first with a signal. While Android reports music playing and the app hears nothing (no session yet, or the player moved to a new one), `MainActivity.audioWatch` (every 2 s) searches after 4 s of silence, and right away after a launch or resume: the session found last (remembered across launches) is probed first, which takes about 0.3 s; a full search takes up to about 4 s. After an empty search the next one waits 60 s, except that each new track from the media session (`onTrack`) allows one search right away. A session that fails to attach also waits 60 s. While nothing plays, nothing is probed. On the SHIELD the visuals react about 1 s after launch (1.9.18; before, a 4 s silence wait and the 2 s ticks made it about 10 s).

**No other source.** The app never attaches to session 0, and has no playback-capture source: on the SHIELD both heard silence, the player's session works everywhere it was tried, and it needs nothing beyond `RECORD_AUDIO` (`AudioFlinger::createEffect` only asks for `MODIFY_AUDIO_SETTINGS` on session 0). While no player session is known, no Visualizer runs. Audio that an app sends to the TV already Dolby-encoded is never mixed, so it can't be visualized.

## Auto-update

`Updater` (off by default, *Settings › Advanced › Auto-update*) opens outbound network connections for updates. The separate temporary custom-pack listener accepts local HTTP uploads only while its dialog is open. While it is on, it runs on its own background thread, 10 s after each launch, then every 6 hours while the activity stays resumed (right away when switched on). Resuming without a new launch checks only once 6 hours have passed since the last completed check; a failed check is retried at the next launch or interval:

1. `HEAD github.com/johnneerdael/ProjectM-TV/releases/latest`: GitHub answers with a redirect to `/releases/tag/v<version>`, so no API call (or rate limit) is needed.
2. If that version is newer than the installed one (CI suffixes like `-ci.42` ignored), it downloads `releases/download/v<version>/projectM-TV-<version>.apk` into `no_backup/update-download` (excluded from backups).
3. The APK must be this package, have a higher version code, and carry the same signing certificate as the installed app; otherwise it is deleted. Then it moves to `no_backup/updates`, and the activity shows the *Install* row and a notice.
4. *Install* hands it to Android's installer with `ACTION_INSTALL_PACKAGE`: a `content://` URI from the non-exported `UpdateFileProvider` with a one-off read grant (Android 7+), or a world-readable file (Android 5-6, whose installer only reads files). Android asks to confirm, and on Android 8+ to allow installs from the app the first time.

Downloads that are no longer newer than the installed version are deleted at the next check. When the app was installed by an F-Droid client (installer package), the setting shows *Via F-Droid* and nothing runs. F-Droid's inclusion policy allows downloading updates only with explicit user consent, which the off-by-default setting is. For testing, `adb shell setprop debug.projectmtv.update_from 1.9.17` makes the app treat that as the installed version (and accept the same version code).

## Random texture binding invariant (2026-10-04)

Patch 0037 caches the selected image per preset slot 00–15, while each shader alias retains its own name and sampler mode. A qualified prefix such as `pc_rand00_clouds` filters the image pool by `clouds` and requests point/clamp sampling; `fw_` selects linear/wrap. The unqualified default is linear/wrap. Authored `sampler_state` fields remain ignored, as documented in patch 0032. A later stage reuses an existing slot even if its alias names another filename prefix. Within a new shader, filtered aliases take precedence over unfiltered forms; competing filters retain lexical precedence. New presets select new random images through production `std::random_device` seeding.

Images are extracted from APK `textures/` into app-private `files/textures/` before the first preset. Both live and prewarm engines receive that directory. `Texture::Name()` retains the selected base name and `SourcePath()` the loaded file path; diagnostic tools must hash that file and record shader/uniform/unit identity before asserting an association. Offline sampler declarations, compilation and a successful preset load do not establish correct appearance.

## Legacy shader global inputs

Patch 0040 preserves plain uninitialized scalar/vector float globals as external
uniform inputs. Read-only globals stay uniforms; shader writes use the initialized
per-invocation copy established by patch 0030. The GLES link-time default for unbound
uniforms is zero. This is a defined current-core policy, not a claim that legacy D3D9
registers always held zero. Locals and explicit static/const/initialized storage retain
their previous classification. Mixed comma declarations are emitted separately when
needed to preserve different storage classes. The focused source analyzer and target
policy are documented in `tools/milk-analyzer/README.md`.

### Shader literal serialization

Patch 0044 formats parsed finite float32 shader literals using the classic locale
and `std::numeric_limits<float>::max_digits10`. Decimal/exponent spelling preserves
float type and negative zero when GLSL is parsed; integer and Boolean AST literals
retain separate emission paths. This prevents the inherited six-significant-digit
formatter from changing coefficients before the driver sees them.

`GLSLGenerator` rejects nonfinite literal nodes through its existing error state.
`MilkdropShader` reports translation failure and retains its existing stage fallback;
no nonfinite literal is silently changed to zero or emitted as an authored `inf`/`nan`
identifier. Runtime arithmetic and the tokenizer’s initial decimal-to-double-to-float
conversion are outside this serialization contract. See
[the reproduction and related-code audit](superpowers/evidence/float-literal-roundtrip/README.md).

## Renderer compatibility corrections (2026-10-06)

Patches 0045–0047 keep sampling and arithmetic owned by the consuming draw.
Main-textured custom shapes bind their own repeat/linear sampler on every fill;
named images retain their descriptors. Blur upper bounds expand upward when the
interval is too narrow, retaining the legacy clamp-then-expand order. A shared
float32 coefficient producer rejects nonfinite or unrepresentable inputs and
progressive cancellation; storage and decoded getters use the same default 0–1
triplet in that case. The shared warp vertex shader uses signed negative zoom
directly when the zoom exponent is exactly one, as MilkDrop CPU `powf` does.
Positive zoom and other exponent calculations retain their previous path.
Authored custom HLSL power translation is unchanged.

These changes add no Java/JNI API and leave preset assets unchanged. Host UV,
sampler and normalization controls are separate from device appearance and
performance evidence; they do not establish identical rendering on Windows or
all TV GPUs.

## Large warp rotation

Current patch0011 (historical0051 from PR #51) computes rotation sine/cosine on the CPU after converting the final
per-frame or per-pixel equation result to float, as MilkDrop 2 does. Large-angle
GPU trig can return zero for both outputs on the observed GLES/Metal driver,
collapsing feedback UVs to the rotation centre. CPU libm handles the finite float
range, including angles for which a double remainder with a rounded `2*pi`
constant is inaccurate. Equations and their original rotation state are unchanged.

The 4.2 mesh reuses `transforms.z` for sine and adds an instance-owned four-byte
cosine VertexBuffer at attribute8. The rotation-only patch used seven active input attributes.
Resize/upload cosine with the existing buffers; the 4.1.7 interleaved 56→60-byte
layout remains historical evidence. Patch0015 adds the negative-power buffer at
attribute9, bringing the current warp shader to eight active input attributes.
With no per-pixel code the
pair is cached once per frame; otherwise it uses each vertex's final evaluated
rotation. Legacy/custom warp programs share this vertex interface, and prepared
meshes reuse the pair for authored/native draws without reevaluating equations.
There is no public C/Java/JNI API change. Other shader trig remains unchanged;
nonfinite rotation is still unsupported, with no finite identity substitution.
See [4.2 rotation synchronization](superpowers/evidence/upstream-master-4-2/rotation51-synchronization/README.md)
and the [original repair evidence](superpowers/evidence/large-rotation-trig/README.md)
for their separate observed scopes and remaining validation.

## Negative warp powers

Patch0015 computes negative effective zoom with the original nested CPU `powf`
expression after the emitted-float conversion. This restores defined integer
nested powers that GLSL does not define for a negative base. PerPixelMesh owns
the four-byte-per-vertex attribute9 buffer, resizes/uploads it with the existing
mesh buffers and reuses it for prepared replay. Raw zoom/exponent equations are
unchanged. The exact authored unit-exponent case retains its direct signed value;
other negative vertices require two CPU power calls. Positive zoom stays on the
existing GPU path. Fractional-domain NaN/Inf are retained, with no forced magnitude,
epsilon or texture-sampling fallback. Invalid-coordinate appearance and TV
performance remain outside these numerical controls. See the
[Tulip investigation](superpowers/evidence/tulip-negative-zoom-power/README.md).

## Evaluated waveform and legacy display controls

Engine policy `live-controls-v1` starts with patches 0048–0049. `Waveform` reads
evaluated `wave_mode`, `wave_usedots`, `wave_thick` and `wave_additive`. Mode
conversion truncates toward zero, then takes signed remainder over projectM's
16 modes. Negative remainders have no factory implementation; nonfinite or
unrepresentable integer inputs draw nothing. Math is rebuilt when the effective
mode changes. Authored/native targets share one generated geometry stream and
the same evaluated flags, retaining mode-specific alpha and recurrence.

`FinalComposite` passes `PerFrameContext` to legacy `VideoEcho` and `Filters`.
Every legacy composite owns filters even when all defaults are off; inactive
frames skip filter GL work. Filter order and blend formulas remain brighten,
darken, solarize, invert. Flags use nonzero truth. `PerFrameUpdate` retains the
existing gamma [0,8] and echo zoom [0.001,1000] clamps. Echo orientation truncates
toward zero and uses signed remainder modulo four; an undefined integer
conversion omits echo and draws gamma-only output. The echo branch compares narrowed float alpha to0.001f, matching the
MilkDrop3 legacy consumer (float conversion at4065, comparison at4085). Existing echo threshold,
gamma redraws, UV math and GL cleanup remain intact. Custom composite shaders
retain their existing uniform/branch policy.

Neither repair copies evaluated outputs into `PresetState`: configuration
defaults still reset each frame, and each preset instance owns its state. No
public Java/JNI/C API changes, preset edits or predictor policy changes are
included. Historical static-policy audit results remain unchanged. See
[controls and validation](superpowers/evidence/live-native-controls/README.md).

## Custom preset packs

`PresetPackUploadServer` binds one IPv4 LAN interface on a random port with a SecureRandom session URL. One listener and at most three request workers handle bounded HTTP requests; one ZIP import runs at a time. Idle speculative browser sockets close silently; the page has no external resources. Dismiss/pause closes both listener and client socket. `CustomPresetPack` uses platform `ZipFile` to import presets and engine-supported texture files while skipping unrelated compressed entries, bounds extraction, checks CRC/size, writes generated storage paths and a UTF-8 index, prepares the native index without publishing it, then atomically replaces the active-generation pointer and commits the prepared native catalog under app-private `no_backup/custom-presets/`. Failed staging is removed. The previous pack remains active until a validated import commits. Native rejection/cancellation/timeout discards preparation; failed publication restores the previous pointer. Committed-file cleanup belongs to a coalesced application worker, independent of dialog shutdown. Header and body receive deadlines are 5 seconds and one hour, in addition to socket idle limits; native preparation/restore waits are bounded at 30 seconds. Wi-Fi/Ethernet addresses take precedence over VPN interfaces.

The additive `ProjectMJNI.setCustomPresetPack` queues startup restore on the native worker and returns a request ID. Uploads use `prepareCustomPresetPack`, request-specific status, commit and discard. Category requests wait for restore, while staged imports leave the live catalog unchanged. Counts are cached and updated on skip/reset/index changes. Large replacement orders and membership maps are built off lock; publication swaps prepared containers and the worker retires old metadata. Standard UTF-8 preset names are decoded by the platform for JNI strings. Immutable generation-qualified identities keep custom skips, history and prewarm data distinct from bundled presets and replaced packs. All combines bundled/custom entries; scored category indexes remain unchanged. Presets are read individually on demand rather than retained as one 50,000-file buffer. Texture files keep unique case-insensitive basenames under the immutable generation. Main/prewarm rendering use matching per-preset ordered texture paths; packaged presets use bundled images, custom presets prefer their pack with bundled fallback. Texture managers remain owned by active/transitioning presets so a blend cannot change outgoing images. Retired generation files remain while live rendering/prewarming leases need them; the GL thread clears the outgoing lease when `projectm_is_transitioning` reports actual preset retirement; cleanup retries piggyback the foreground status loop, with no background polling. No predictive scoring occurs.

Custom archives, extracted presets and the active pointer live in `Context.getNoBackupFilesDir()` (API21+), rather than the normal files directory. Android excludes this tree from Auto Backup, so a large pack cannot crowd out preferences and skip-list backups. Normal app restarts/updates retain it; reinstall/data clearing/device restore requires uploading the pack again.

The TV dialog renders a ZXing Core QR code on a white square with an unbroken quiet zone. The code contains the full temporary session URL without requiring it to be typed or displayed as text. The device test decodes the actual screenshot region and compares the result to the current listener endpoint.

## Current authored-fidelity audit additions

The candidate ordered series now contains33 patches. Patches0029–0033 restore source line budgets with a reference-width cap, discrete custom dots, circle closure before smoothing, captured per-instance shape thickness and continuous publication of the actual previous warp field. Shape and warp replay retain prepared geometry; equations and RNG are not evaluated again. Out-of-domain thickness retains the parsed style without rewriting the raw value. UV publication uses the actual warp fragment and its discard/output behavior, not a separate analytic pass, and adds intentional bandwidth while vectors are hidden. The older pre-rebase conditional-write measurements above remain historical.

Source controls and focused Native3840x2160 evidence preserve the Standard1280x720 reference. Active-canvas JNI lifecycle checks cover resize, context recreation, pressure requests, mesh/trails changes and preserved-context resume. They do not certify Activity/audio lifecycle or physical-TV headroom. See [current qualification](superpowers/evidence/authored-fidelity-followup/README.md) for exact identities, scope, isolated combined-cost results and remaining PR gates.

Patch0034 adds compatible continuous motion-field storage on baseline GLES3.0 contexts. A context-local core/extension check and actual mixed-format probe select RG16F where renderable or RG16UI half words otherwise. Integer consumers decode texels before interpolation, and fresh/pooled integer storage uses a typed clear. Shader cache keys separate the packed variants. Primary color/dither and prepared replay remain; there is no per-frame capability polling or new exception from rendering.

## Touchscreen Android build (2026-10-11)

The default `:app` build remains the TV APK. `-PandroidTouchscreen=true` changes the application ID to `nl.neerdael.projectm`, label to ProjectM Android, manifest feature requirements and framework theme, and overlays the regular Launcher/sensor-landscape manifest plus smaller safe margins. No runtime dependency is added. The phone APK does not require Leanback or expose a Leanback launcher entry. Debug/profile test suffixes remain available for both builds.

`MainActivity` attaches framework GestureDetector input only to the visualizer surface in the touchscreen build. Completed horizontal swipes perform the same random/previous hard cuts as remote Right/Left; surface clicks open/close the menu. Framework ScrollViews and OptionRow click actions handle the menu, with 48dp touch rows and explicit close/back controls. All three menu panels scroll within their bounds; touchscreen margins include stable system-bar insets so transient phone navigation does not cover setting values. Touch events suspend auto-hide during contact and restart its timer on release. The separate TV diagnostics card stays TV-only; the phone's main menu retains the audio meter, frame/render status and engine identity.

CI builds/stages TV first and touchscreen second with their own APKs and R8 mappings, publishing one unchanged core AAR. The updater uses a build-specific asset prefix and still validates app ID and signing key. Both APKs share version allocation/signing but have separate settings and installation identity. See [build and test](user-guide/development.md#touchscreen-build) and [release artifacts](RELEASING.md#generated-artifacts).

The touchscreen build adds `PhoneAudioInput` with a persisted microphone/playback selection. Microphone uses an activity-owned `AudioRecord`; phone playback (API29+) uses a fresh Android MediaProjection consent token in a non-exported `mediaProjection` foreground service. `PhonePcmCapture` owns a blocking audio worker, reads 44.1kHz signed PCM16 mono and converts it to the existing core's unsigned mono waveform input. Pause stops capture and discards consent; projection revocation and recording failures stop the service. No video display/recording is created, and no core API changes are made. Playback must be permitted by the source player. TV retains its Visualizer session discovery and no microphone use.
