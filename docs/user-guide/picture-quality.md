# Picture quality and performance

Both builds adjust render size to the device's display, frame rate and available memory by default. This page explains what the automatic choices do and which settings to change when you want something specific. The engine section has the technical depth: [Rendering MilkDrop at 4K](engine/resolution.md) and [How a frame reaches your screen](engine/pipeline.md).

## Resolution

**Advanced › Resolution** chooses how large ProjectM TV renders. The display scales the result to fill the screen.

| Mode | Behaviour |
|---|---|
| **Auto** (default) | Starts at your device tier's height and adapts to the target frame rate and available memory, up to the panel's full physical size. A 4K panel can render at 3840×2160 even when Android's menus run at 1080p |
| **720p, 1080p, 1440p, 4K** | A fixed height, offered up to your panel's size. Low frame rates do not lower it |
| **Native (*panel*)** | The full physical panel, for example *Native (4K)* |

In Auto, resolution drops after about 3 seconds below 85% of the target frame rate, and rises again after about 15 seconds at 97% or more when memory allows. Auto remembers its last height for the next start.

**Memory protection applies in every mode.** Before raising resolution, the app estimates the extra texture memory, including Native trails and two presets during a blend, and keeps a reserve for the music player. Under memory pressure it lowers resolution, frees cached textures and pauses shader preloading, then recovers when headroom returns. On TV, Diagnostics shows *resolution reduced for memory headroom* while this is active. It protects the music app but cannot guarantee every vendor's memory policy.

In fixed sizes and Native, **Skip slow presets** has no effect (the setting is kept for Auto), so you can study a demanding preset at full size.

## Native trails

Feedback presets build each frame from the previous one. At 4K that accumulation behaves differently from the much smaller screens the presets were written on. **Native trails**, active above 1330p, keeps the feedback at an authored-scale canvas (1280×720 at 4K) and draws each frame's new waves, shapes and final image at full native resolution.

| Level | Result |
|---|---|
| **Standard** (default) | The authored feedback look, with sharp native geometry on top |
| **Medium** | Adds native-resolution detail to the trails, with a gain cap of 0.5 |
| **High** | The same passes as Medium, with a gain cap of 1 |

Medium and High cost the same; they differ in how much detail they keep. Both use more GPU time and memory than Standard, so Auto may choose a lower resolution. Near black and white the gain is limited so that detail cannot add brightness through clipping.

At 1330p or below, or when a driver rejects the shaders, the previous diffusion path is used; TV Diagnostics shows the reason. More: [Native trails](engine/resolution.md#native-trails-authored-feedback-native-geometry).

## Transitions

| Mode | What happens at an automatic change |
|---|---|
| **Auto** (default) | A full blend of both presets at a reduced scale: 75% to start (60% on low-RAM devices or below 2.6 GB of RAM), down to 50% when the GPU is the limit, back up to 100% when blends have frames to spare. When the CPU is the limit, the outgoing preset renders every second frame instead |
| **Classic** | projectM's blend at full resolution, the heaviest option |
| **Lightweight** | An instant cut with a fading snapshot of the old preset on top, for at most 3 s. The cheapest option |

**Transition** sets the length (Instant, 1–10 s). Instant cuts without blending, which also frees the memory reserved for a second preset. Remote-control switches are always instant.

## Frame rate and detail

- **Frame rate** defaults to about 30 fps: the refresh rate, half or a quarter of it, whichever is closest (30 on a 60 Hz TV, paced to every second vsync). Steady 30 fps looks smoother than an uneven 40–50. Motion driven by `time` keeps its speed at any frame rate, but feedback motion (zoom, rotation, decay) advances once per frame, so it runs faster at a higher frame rate.
- **Detail** sets the warp mesh. Each mesh point runs the preset's per-vertex equations on the CPU every frame, so on a low-end box a smaller mesh helps CPU-heavy presets more than a lower resolution does.

## Device tiers

On first start the app classifies the device and chooses defaults accordingly:

| Tier | Devices | Auto starts at | Auto lowest | Detail | Transition |
|---|---|---|---|---|---|
| High | NVIDIA SHIELD / Tegra | 1440p | 720p | High | 7 s |
| Standard | everything else | 1080p | 540p | Medium | 7 s |
| Low | Android low-RAM devices or below 1.6 GB of RAM | 720p | 360p | Low | 2 s |

TV Diagnostics shows the tier and RAM. Detail and Transition can be changed afterwards.

## When playback stutters

1. Keep **Resolution › Auto**. Fixed and Native sizes ignore frame rate.
2. Lower **Detail** if a preset's equations limit the CPU. A lower resolution does not help those presets.
3. Use **Native trails › Standard** on a 4K panel.
4. Switch **Transitions** to **Lightweight** if stutters happen only during blends.
5. Keep **Skip slow presets** on, so presets that cannot keep up on your TV are retired.

Check the main panel's render size and frame rate before and after a change. On TV, **Advanced › Diagnostics** also shows memory state.
