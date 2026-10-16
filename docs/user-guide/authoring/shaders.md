# Shaders

MilkDrop 2 added two pixel shaders to every preset:

- the warp shader replaces the fixed-function warp: it reads the previous frame and produces the new canvas;
- the composite shader replaces the fixed-function composite: it turns the canvas into what is displayed, and is never fed back.

Both are written in Direct3D 9-era HLSL (shader model 2 or 3). projectM translates them to GLSL with a vendored HLSL parser and compiles them as GLSL ES 3.00 on ProjectM TV. When translation or compilation fails, the stage silently falls back to a simple built-in shader: the preset loads but looks nothing like itself. A portable shader has to stay within what translates.

## Shader lines in the file

```ini
warp_1=`shader_body
warp_2=`{
warp_3=`    ret = tex2D(sampler_main, uv).xyz * 0.97;
warp_4=`}
```

Each line starts with a backtick, and the lines are numbered from 1 without gaps. Your code may declare samplers, constants and functions before `shader_body`. `ret` (`float3`) is the output colour and starts at zero.

## The hidden header

Before your code, the engine prepends a header that defines the inputs. Your code uses the names; the storage column shows where each value is held.

| Name | Meaning | Storage |
|---|---|---|
| `uv` | Texture coordinate of this pixel (warp: after the mesh warp) | `_uv.xy` |
| `uv_orig` | Coordinate before warping (warp shader) | `_uv.zw` |
| `rad`, `ang` | Distance from centre and angle, interpolated from the mesh | `_rad_ang` |
| `hue_shader` | Per-vertex colour (composite) | `_vDiffuse.xyz` |
| `aspect` | Aspect correction: `.xy` multiply, `.zw` inverse | `_c0` |
| `time`, `fps`, `frame`, `progress` | | `_c2` |
| `bass`, `mid`, `treb`, `vol` | | `_c3` |
| `bass_att`, `mid_att`, `treb_att`, `vol_att` | | `_c4` |
| `blur1_min` … `blur3_max` | Blur ranges | `_c5`, `_c6`, `_c13` |
| `texsize` | `(width, height, 1/width, 1/height)` of the canvas | `_c7` |
| `roam_cos`, `roam_sin` | 0.5+0.5·cos/sin of time at about 0.3, 1.3, 5 and 20 rad/s | `_c8`, `_c9` |
| `slow_roam_cos`, `slow_roam_sin` | The same at about 0.005-0.022 rad/s | `_c10`, `_c11` |
| `mip_x`, `mip_y`, `mip_avg` | Mip-level helpers | `_c12` |
| `q1` … `q32` | The per-frame q values, after per_frame code | `_qa.x` … `_qh.w` |
| `rand_frame`, `rand_preset` | Random `float4`: new every frame / once per preset | |
| `rot_s1`…`rot_s4`, `rot_d1`…, `rot_f1`…, `rot_vf1`…, `rot_uf1`…, `rot_rand1`… | 4×3 matrices (rotation plus translation): static, slow, fast, very fast, ultra fast, random per frame | |

Helper functions:

| Function | Does |
|---|---|
| `GetMain(uv)`, `GetPixel(uv)` | `tex2D(sampler_main, uv).xyz` |
| `GetBlur1(uv)`, `GetBlur2(uv)`, `GetBlur3(uv)` | A blur level, **decoded** back to normal colour (see below) |
| `lum(c)` | `dot(c, float3(0.32, 0.49, 0.29))` |

`tex2d` and `tex3d` are accepted as `tex2D` and `tex3D`.

!!! note "Portability"
    - MilkDrop's `time` *inside shaders* counts from the preset start (wrapped at 10,000 s). projectM's counts from program start. The per-frame equation variable `time` is program time in both.
    - In MilkDrop, `rand_frame`, `rand_preset` and the `rot_s`…`rot_uf` matrices are shared by the warp and composite shaders (`rot_rand1`–`4` are drawn anew for each). projectM generates them separately per shader, so the two stages see different values.
    - MilkDrop's `vol` and `vol_att` in shaders actually hold one third of `treb` and `treb_att`, because of a comma-operator bug in its source (`milkdropfs.cpp:3970`). projectM passes the real average volume.
    - MilkDrop writes the composite's alpha from the vertex colour; projectM writes 1.0.

## Blur levels must be decoded

Each blur level stores colours normalized to its range, `(c − min) / (max − min)`, with each level's range nested inside the previous level's. `GetBlur1(uv)` undoes this: it returns `tex2D(sampler_blur1, uv).xyz * (max1−min1) + min1`. Reading `sampler_blur1` directly returns the *encoded* value, which looks washed out or too dark whenever the range is not 0-1, so use `GetBlurN`.

Only the blur levels a shader needs are computed. MilkDrop decides from the blur samplers the compiled shader actually uses, upstream projectM searches the text for `GetBlurN` and `sampler_blurN`, and ProjectM TV also counts `blurN_min`/`blurN_max`. Blur ranges and their safe values are covered under [effects](effects.md#blur).

## Writing to inputs

`q1`, `time`, `bass` and the others are macros onto uniform components, so an assignment like `q18 = 1;` or `time *= 0.4;` writes into a uniform. Microsoft's compiler gave each shader invocation a writable copy that started from the input. Some projectM builds produced an *uninitialized* copy instead, so other components and other functions read garbage (`$$$ Royal - Mashup (324)`). ProjectM TV reproduces Microsoft's behaviour. For portability, copy an input into your own local before modifying it.

## What translates, and what does not

All 15,576 authored warp and composite shaders in the bundled library were translated in an earlier pass. Real presets failed on these constructs:

| Construct | Status in ProjectM TV | Advice for portable presets |
|---|---|---|
| A local variable named `sample` (reserved in GLSL ES) | Renamed automatically | Avoid the name |
| `#define` macros, including ones that expand to declarations or statements | Token replacement, keeping your spacing and parentheses | Put grouping parentheses inside the macro if precedence matters |
| Swizzle or index after a parenthesized constructor, `(float3(a,b,c)).x` | Supported | — |
| Flat array initializers, `const float4 s[5] = { …20 values… }` | Grouped into elements; an ambiguous layout fails the stage | Write one constructor per element |
| `= sampler_state { … }` | Accepted, but the fields are **ignored** | Choose filtering with a [sampler name prefix](textures.md#sampler-names-and-filtering) |
| Plain globals without initializer (`float3 mus;`) | Become external inputs that read **0** | Initialize every global you read; on Windows its value was whatever the register held |
| Float literals with many digits (`1.00000011920928955078125`, `4194304.0`) | Exact float32 | Some projectM builds round to 6 digits; avoid relying on the 7th |
| Literals that overflow float (`1e40`) or a variable named `inf`/`nan` | The stage fails | Don't |
| Mixing `int` and `float` in some expressions | GLSL ES can reject them (`EVET - Spiracology 2`) | Write float literals (`2.0`, not `2`) |
| `pow(x, y)` with negative `x`, or zero `x` and `y` ≤ 0 | **Undefined in GLSL**: any result, including NaN, on a given GPU | Guard: `pow(max(x, 1e-6), y)` or `pow(abs(x), y)` |
| Large arguments to `sin`/`cos` in shader code | Precision is driver-dependent | Wrap angles with `frac` or `fmod` first |

Undefined `pow` is the largest source of unpredictable output found by this project's [source predictor](testing.md#what-source-analysis-cannot-settle). Twelve of 100 randomly chosen presets could not be forecast because of unresolved numeric domains; seven of them involve powers of negative or zero bases, the rest nonfinite warp coordinates, a division and a dot product.

## Warp shader responsibilities

When the warp stage is a shader, MilkDrop ignores the per-frame `decay` variable and the shader decides the fade. MilkDrop's auto-generated default warp shader bakes in the *file's* decay value:

```hlsl
shader_body {
    ret = tex2D(sampler_main, uv).xyz;
    ret *= 0.98;  // the file's fDecay; or try: ret -= 0.004;
}
```

projectM also exposes the decay to warp shaders through the vertex colour, but do not rely on that for MilkDrop compatibility: apply the fade yourself.

In MilkDrop 2, the preset's `wrap` setting only affects the fixed-function warp. A warp *shader*'s `sampler_main` uses its name prefix, and without one it wraps and filters bilinearly (`plugin.cpp` sampler binding, `milkdropfs.cpp:972`). projectM, including ProjectM TV Engine, instead applies the preset's `wrap` setting to the unqualified `sampler_main` in the warp pass. To get the same result everywhere, name the mode explicitly: `sampler_fw_main`, `sampler_fc_main`, `sampler_pw_main` or `sampler_pc_main`.

## Composite shader responsibilities

With a custom composite, the classic display effects do not apply: gamma, video echo, brighten, darken, solarize and invert are yours to implement (MilkDrop 2 behaves the same way). A typical composite:

```hlsl
shader_body {
    float3 c = tex2D(sampler_main, uv).xyz;
    c += GetBlur1(uv) * 0.4;                 // glow
    c *= 1.0 + 0.3 * saturate(bass - 1.0);   // pump with the bass
    ret = pow(saturate(c), 0.92);            // safe pow: base clamped to 0..1
}
```

!!! warning "Multiplying channels can crush to black"
    A composite that multiplies colour channels together, for example `ret = c.x * c.x * c * GetMain(uv)`, turns a feedback buffer with little red into a black screen. One bundled preset investigated for "being black" did exactly this; it is not a bug. Test with both bright and dark feedback.

## Resolution and `texsize`

`texsize.xy` is the canvas size, and stepping by `texsize.zw` moves exactly one texel. On a 1024×768 screen one texel was a visible step; at 3840×2160 it is 3.75× smaller in picture terms. When rendering larger, ProjectM TV reports a canvas with the area of its line reference size (about 1182×665 for a 16:9 render with the 1024×768 reference), so texel-stepping effects keep their authored size. Other projectM builds report the real render size. If you design texel steps for canvases of roughly 1024×768, they behave well everywhere. [Details](../engine/resolution.md#virtual-texsize).
