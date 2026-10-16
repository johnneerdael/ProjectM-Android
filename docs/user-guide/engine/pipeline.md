# How a frame reaches your screen

This page follows audio input through the shared ProjectM TV Engine to the screen. The TV and touchscreen apps capture audio through different APIs and then share one rendering pipeline. The sections cover audio capture, threading, preset switching without stalls, transitions, automatic quality and preset skipping.

## Audio: listening to the player, not the room

The TV build never uses the microphone. Android's `Visualizer` API attaches to an audio session, and the obvious choice, session 0 (the global mix), often hears nothing on TV hardware. On an NVIDIA SHIELD with HDMI eARC and Dolby output, media is mixed on the Dolby MSD module and encoded to E-AC3. Android places session-0 effects on the idle primary output, so the Visualizer receives silence. The selection code is unchanged in Android 14.

A Visualizer attached to the player's own session sits on the output the music actually plays through. Android does not list other apps' sessions, but session IDs come from one counter in steps of 8. `PlayerSessionFinder` therefore probes the 128 IDs below a freshly generated one, 16 at a time with 300 ms to settle, and takes the first with a signal:

- The last session found is remembered across launches and probed first, which takes about 0.3 s. A full search takes up to about 4 s.
- While Android reports music playing and the app hears nothing, the app searches after 4 s of silence, and immediately after launch or resume.
- After an empty search, the next waits 60 s. Each new track reported by the media session allows one immediate search.
- While nothing plays, nothing is probed.

The capture is 8-bit mono. Audio that a video app sends to the TV already Dolby-encoded is never mixed, so it cannot be visualized.

## Phone and tablet audio

ProjectM Android defaults to a foreground-only microphone `AudioRecord`. On Android 10+, Phone playback uses an `AudioPlaybackCaptureConfiguration` tied to a fresh Android MediaProjection consent token. A non-exported mediaProjection foreground service starts before the app obtains the token; the service creates no virtual display or video recording. Capture is limited to permitted media, game and unknown-usage playback in the same user profile.

`PhonePcmCapture` reads 44.1kHz signed PCM16 mono and converts it to the engine's existing unsigned 8-bit mono waveform input. Microphone and playback capture stop when the activity pauses, and projection revocation or a capture failure also stops the playback service. A new playback session requires new consent. The TV player-session discovery path is unchanged. See [phone setup](../getting-started.md#touchscreen-phone-or-tablet) for the user flow.

## Threads and ownership

| Thread | Priority | Work |
|---|---|---|
| GL (GLSurfaceView) | `THREAD_PRIORITY_DISPLAY` | Owns the projectM instance: create, render, load, settings, output measurement, transition overlay |
| PhoneAudioCapture (touchscreen) | `THREAD_PRIORITY_AUDIO` | Blocking microphone/playback AudioRecord reads into the same buffered engine input |
| AudioCapture (TV) | `THREAD_PRIORITY_AUDIO` | `Visualizer` callbacks into a mutex-protected buffer |
| Native worker | default | Preset index, shuffling, prefetching the next preset's text |
| Prewarm | background | Compiles upcoming presets' shaders in a second, short-lived projectM instance |
| UI | default | Overlay; status polled every 500 ms |

Only the GL thread touches the projectM handle. Every other entry point writes atomics or a locked buffer, which removes a whole class of races.

Each frame on the GL thread:

```text
1. apply changed settings          5. projectm_opengl_render_frame
2. first preset / remote commands  6. output measurement (black-preset check)
3. automatic switch requests       7. lightweight-transition overlay
4. feed buffered audio             8. transition statistics, FPS → projectM
```

## Switching presets without freezing

Loading a preset parses it, translates its HLSL shaders to GLSL and links them. On a SHIELD that froze the picture for 0.5 to 1.9 s (median 0.9 s) at every switch. Profiling showed that 73% of the time went to the driver linking the warp and composite programs. Most of the rest was the HLSL translator constructing a `std::locale("C")` for every float literal.

Four changes removed the stall:

- `PresetPrewarmer` loads upcoming presets (the next in order, the random pick made one step ahead, and the previous preset) into a second projectM instance on a background thread with its own EGL pbuffer context.
- Linked programs go into a process-wide program binary cache, and the render thread's load picks them up with `glProgramBinary`.
- The translator uses `std::locale::classic()`.
- The expression evaluator's `rand()` state is per thread, so prewarming cannot disturb the live preset's random sequence.

Switches now take 10 to 80 ms. Prewarming pauses under memory pressure.

The preset list itself comes from a prebuilt index, `presets.idx`. Before the index existed, listing about 10,000 assets took 8.4 s on a SHIELD and held a lock that UI inflation also needed, so cold start took 10.4 s.

## Transitions

projectM's soft cut renders both the outgoing and the incoming preset for the whole blend. That doubles CPU and GPU cost and keeps two presets' frame buffers in memory. On a SHIELD, frame-rate averages fell to 19 to 36 fps around every switch. **Advanced › Transitions** offers three strategies:

| Mode | What happens |
|---|---|
| **Auto** (default) | projectM's blend, adapted to keep the frame rate. It starts at 75% of the render size (60% on low-RAM devices or below 2.6 GB of RAM) in an off-screen framebuffer that one blit stretches to the surface. The engine measures the render thread's CPU time during the blend. When a blend falls below 85% of the previous frame rate and is **GPU-bound** (render thread below 80% CPU) it steps down to 60%, then 50%. When it is **CPU-bound** it steps back up, because a lower resolution only blurs, and renders the outgoing preset every second frame. Three blends with frames to spare step back up. |
| **Classic** | projectM's own blend at full render size. |
| **Lightweight** | The last frame is copied into a texture, the new preset starts as a hard cut, and the snapshot fades out over it with a slow zoom, for at most 3 s. One extra full-screen pass, and the texture exists only during the fade. |

Manual switches from remote keys, touchscreen swipes or transport buttons are always instant cuts. Beat-triggered cuts happen only when **Cut on loud beats** is on.

## Tile-based GPUs

Most TV boxes use tile-based GPUs (Mali, Adreno, PowerVR). These GPUs load every render target from memory before a pass unless told the old contents can be discarded. The engine invalidates framebuffers before full overwrites (warp, composite, blur, video echo). Where the preset allows, it merges the warp and the shapes and waves on top of it into one render pass. It draws blur passes straight into their textures and draws the active preset's final image directly into the output framebuffer.

On a Ugoos AM6 with the pre-4.2 engine this took `EoS+ Phat - magnetosphere 13 - pulsar` from 26.1 to 55.1 fps at 2160p. Those figures predate the projectM 4.2 rebase. The 4.2 port keeps the invalidation and pass controls but uses upstream's Mesh/VertexBuffer updates, and the gains have not been re-measured.

## Automatic quality

`QualityController` picks the render height:

- **Auto** (default) works up to the detected *physical* panel. Android TVs commonly run the UI at 1080p on a 4K panel, so the panel size comes from the display mode's physical size, the same way AndroidX Media3 detects it. A 720p render fills a 4K screen through the display's hardware scaler at no extra GPU cost.
- It aims for the target frame rate with settle periods, up/down hysteresis, CPU-bound detection (a lower resolution doesn't help an equation-bound preset) and per-preset probe backoff.
- Memory headroom is sampled live from Android's `ActivityManager`. Before raising resolution, the controller estimates the extra texture memory, including Native trails detail and two live presets during a transition. The reserve is Android's pressure threshold + 128 MiB on devices with at least 3,584 MiB of visible RAM, and max(total ÷ 5, threshold + 128 MiB) on smaller devices.
- When memory is low, the controller lowers resolution, flushes the texture cache and pauses prewarming. Recovered headroom allows growth again.
- Fixed sizes and Native keep the chosen size regardless of frame rate, but memory protection still applies.

This protects the music player's memory. It cannot guarantee that every vendor's memory policy keeps every background process alive.

Device tiers set the starting points:

| Tier | Rule | Auto start / floor | Mesh detail | Transition |
|---|---|---|---|---|
| High | NVIDIA SHIELD / Tegra | 1440p / 720p | High 64×48 | 7 s |
| Standard | everything else | 1080p / 540p | Medium 48×32 | 7 s |
| Low | `isLowRamDevice()` or < 1.6 GB RAM | 720p / 360p | Low 32×24 | 2 s |

Per-vertex equations run on the CPU for every mesh vertex on every frame, so on low-end ARM boxes mesh detail is often the real bottleneck.

### Frame pacing

The default target is about 30 fps: the divisor of the refresh rate closest to 30 (30 fps at 60 Hz, 25 fps at 50 Hz), paced by `Choreographer`. A steady half rate looks smoother than an uneven 40 to 50 fps and leaves the GPU room for heavy presets. projectM animates on wall-clock time, so motion speed doesn't change with frame rate.

## Skipping presets that cannot work here

A preset is added to this TV's skip list when:

1. its file is empty or unreadable;
2. projectM reports a load failure, meaning a parse error. Shader compile failures fall back to default shaders, and equation blocks that will not compile are left out MilkDrop-style (see [Equations](../authoring/equations.md)), so neither causes a skip;
3. **Skip slow presets** is on (Auto resolution only) and the preset stays below 50% of the target frame rate even at the lowest resolution, or a lower resolution does not help it;
4. **Skip blank presets** is on and the preset is black twice, in any showings. Black means 5 samples in a row, 1 s apart, with no channel above 20/255 while music plays, counted only after 3 s of uninterrupted music. After 3 black verdicts in a row with nothing visible in between, the engine assumes a rendering fault and strikes nothing, so a broken driver cannot empty your library.

**Advanced › Skipped presets** shows the count and resets the list.

The engine also logs output measurements for each preset (luma range, share of changing pixels, the most active region). They are only recorded and are not used for skipping, because a wrong skip is permanent.

## Logs for the curious

With `adb logcat`, the native tag `projectM-Native` prints one line per event: `LOAD` (preset, time, programs cached or compiled, memory change), `PREWARM`, `TRANSITION` (mode, scale, frame rates, CPU share, outgoing rate) and `OUTPUT`. `Preset code left out (<preset>): <reason>` lines list equation blocks dropped MilkDrop-style. `VisualizerRenderer` prints `STATS fps=… surface=… audio=…` every 5 s.
