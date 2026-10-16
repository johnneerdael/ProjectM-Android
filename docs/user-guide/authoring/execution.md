# The frame, step by step

Most "why doesn't my variable keep its value" surprises come down to what runs when and what is reset in between. The order below is MilkDrop 2's (`RenderFrame`, `milkdropfs.cpp:752`); projectM follows the same order.

## At load

1. Settings are read. Every user variable in every code block is cleared to 0.
2. `per_frame_init` runs once. The values of q1 to q32 at its end are saved as the preset's *post-init q values*.
3. Each custom wave's and shape's `init` runs once and sees the post-init q values. Its t1 to t8 at the end are saved as that wave's or shape's *post-init t values*.

## Every frame

```text
 1. reset built-in variables to the preset file's values
 2. reset q1 to q32 to the post-init q values
 3. run per_frame
 4. copy q into the per-vertex context; clamp gamma (0–8) and echo_zoom (0.001–1000)
 5. per-vertex code over the warp mesh → warp the previous frame (motion vectors are drawn first)
 6. compute blur levels (only if a shader uses them)
 7. custom shapes  (each instance runs shape per-frame code)
 8. custom waves   (per-frame code, then per-point code)
 9. built-in waveform
10. darken centre, then outer and inner borders
11. composite → the screen
```

Steps 5-10 draw into the *canvas*, which is the image the next frame warps. The composite (step 11) is never fed back. Shapes are drawn before waves on purpose.

### What resets and what persists

| Kind of value | Reset when | Persists |
|---|---|---|
| Built-ins: `zoom`, `rot`, `warp`, `cx`, `cy`, `dx`, `dy`, `sx`, `sy`, `decay`, `wave_*`, `ob_*`, `ib_*`, `mv_*`, `echo_*`, `gamma`, blur ranges, … | **Every frame**, to the file's value, before `per_frame` | No: set them every frame if you change them |
| q1 to q32 | **Every frame**, to the post-init values | Changes made in `per_frame` last for that frame only |
| t1 to t8 (per wave or shape) | **Every frame**, to that wave's or shape's post-init values | Writes are never carried to the next frame |
| Your own variables (`kick`, `phase`, …) | Never | Across frames, within the block that owns them |
| `monitor` (MilkDrop) | Never | Yes (projectM does not provide it) |

Because your own variables persist, envelope followers work:

```ini
per_frame_1=kick=max(.78*kick,min(1.5,max(0,(bass-.95)*1.6)));
```

`kick` is a user variable, so it keeps last frame's value and decays by 0.78 per frame unless a new bass hit lifts it. To make it visible to shaders, waves and shapes, copy it into a `q` every frame:

```ini
per_frame_3=q1=kick;
```

### Read-only inputs

| Variable | Value |
|---|---|
| `time` | Seconds since the visualizer started, not since the preset started |
| `fps` | Current frame rate |
| `frame` | Frame counter |
| `progress` | 0→1 through the preset's scheduled duration |
| `bass`, `mid`, `treb` | Band levels relative to their recent average: about 1 is "normal" |
| `bass_att`, `mid_att`, `treb_att` | Smoothed versions of the same |
| `meshx`, `meshy`, `pixelsx`, `pixelsy`, `aspectx`, `aspecty` | Mesh and canvas dimensions |

!!! warning "The first seconds of audio"
    MilkDrop's audio history starts at zero and its long-term average adapts quickly at startup, so the first non-silent frames can report `bass` and `mid` near 10. A preset that raises `bass` to a high power can flash to white or crush to black for a moment at a cold start. This behaviour was cross-checked against MilkDrop 2.25c (`plugin.cpp`).

## Per vertex (per_pixel)

`per_pixel` code runs once for every vertex of the warp mesh, not for every pixel; the image is interpolated between vertices.

- Before each vertex, only `x`, `y`, `rad`, `ang` and the motion variables (`zoom` … `sy`) are reset to their per-frame results.
- q and your own variables are not reset per vertex, so a value written at one vertex is still there at the next. You can accumulate across the mesh, but the result depends on traversal order.
- The mesh size changes the result. MilkDrop's default is 48×36 (maximum 192×144), projectM's default is 32×24, and ProjectM TV's **Detail** setting chooses 24×16 to 96×72. A per-vertex effect with sharp spatial features looks different at different mesh sizes.

## How state is shared between blocks

| Data | MilkDrop 2 | projectM |
|---|---|---|
| q1 to q32 | per_frame → per_vertex, waves, shapes, shaders | Same |
| q written inside a wave or shape | Not seen by other waves, shapes or shaders | Same |
| t1 to t8 | Private to each wave or shape | Same |
| `reg00`–`reg99` | **Process-global**: shared by every block and surviving preset changes | **Per preset**: shared by that preset's blocks only |
| `gmegabuf` | Process-global | Per preset |
| `megabuf` | Per code block | Per code block |

!!! note "Portability"
    Presets that pass data to the *next* preset through `reg` or `gmegabuf` work only in MilkDrop. In projectM each preset starts with its own registers.

## Custom waves and shapes, per frame

For a custom wave, the per-frame variables are loaded with q from the main per-frame result and t from init. The wave's per-frame code runs, and then q and t are copied into the per-point context. Per-point code receives `sample` (0→1 along the wave) and `value1`, `value2` (left/right audio or spectrum). Each point starts with `x = 0.5 + value1`, `y = 0.5 + value2`, and `r`, `g`, `b`, `a` from the per-frame results (`milkdropfs.cpp:2681`).

For a custom shape with `num_inst` above 1, the shape's per-frame code runs once per instance, with `instance` set to 0, 1, 2 …. q, t and all shape built-ins are reset for every instance, while your own variables persist across instances and frames.

## Defaults worth knowing

| Setting | Default | Note |
|---|---|---|
| `warp` | **1** | The animated sine warp is on unless you set `warp=0` |
| `fDecay` / `decay` | 0.98 | Ignored by MilkDrop when a warp shader runs (see [effects](effects.md#decay)) |
| `fGammaAdj` / `gamma` | 2.0 | Applied by the classic composite, or baked into MilkDrop's generated default composite |
| `zoom`, `zoomexp`, `sx`, `sy` | 1 | |
| `cx`, `cy`, `wave_x`, `wave_y` | 0.5 | |
| `nWaveMode` | 0 | |
| `fWaveAlpha` | 0.8 | Set `fWaveAlpha=0` to hide the built-in wave |
| `b1n`…`b3n` / `b1x`…`b3x` | 0 / 1 | Blur ranges |
| Custom wave | samples 512, scaling 1, smoothing 0.5 | |
| Custom shape | 4 sides, rad 0.1, centre red, edge transparent green, border white at alpha 0.1 | |

Some settings have a different name in the file than in equations: `fDecay` ↔ `decay`, `nWaveMode` ↔ `wave_mode`, `fZoomExponent` ↔ `zoomexp`, `fGammaAdj` ↔ `gamma`.

!!! note "Portability"
    MilkDrop fills a missing `wave_r`, `wave_g`, `wave_b`, `wave_x` or `wave_y` with the reset value of `rot`. That value is read before the file's `rot`, so it is effectively 0 (`state.cpp:1369`), which gives a black wave in the corner. projectM uses 1, 1, 1, 0.5, 0.5. Always write them.
