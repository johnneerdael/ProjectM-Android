# Writing presets

A MilkDrop preset is a small text file that programs a feedback loop. Each frame, the previous image is warped by a mesh of equations, darkened, and drawn over with waveforms and shapes. Then a final shader produces what you see. A few dozen lines of code can produce endless variation, and a single wrong detail can leave the screen black or stop the preset loading.

This section describes how a preset actually executes, at the level of the source code that runs it. It draws on two kinds of evidence. The first is MilkDrop 2's released source (v2.25c), the reference implementation every preset was written against; statements about MilkDrop cite the file and line, for example `milkdropfs.cpp:2852`. The second is this project's analysis of real presets: parsing all 9,606 bundled files, translating every shader, running each preset under controlled audio, and, in a randomized audit of 100 presets, comparing predictions made from source alone against rendered frames.

Most preset guides describe what each variable is *meant* to do. This one also covers the edge cases that decide whether a preset works: equation code split across lines, a division by zero, a texture name that starts with two letters and an underscore, a shape smaller than a pixel.

!!! tip "Write for MilkDrop 2"
    ProjectM TV Engine follows MilkDrop 2 wherever projectM had drifted from it (see the [patch catalog](../engine/patches.md)). Writing to MilkDrop 2's rules is therefore the best way to get the same result here, in MilkDrop on Windows and in other projectM players. Where projectM still differs from MilkDrop 2, these pages say so under **Portability**.

## Pages

| Page | What you learn |
|---|---|
| [Anatomy of a .milk file](milk-format.md) | Keys, versions, numbered code lines, and how lines are joined |
| [The frame, step by step](execution.md) | What runs when, what resets every frame, how q and t variables flow, draw order, defaults |
| [Equations](equations.md) | The expression language as NS-EEL2 and projectm-eval actually evaluate it |
| [Shaders](shaders.md) | Warp and composite HLSL: the hidden header, inputs, blur decoding, what translates to GLSL |
| [Textures](textures.md) | Sampler names, filtering prefixes, random textures, noise, transparent images |
| [Motion, waves, shapes and blur](effects.md) | The warp formula, decay, the built-in and custom waves, shapes, blur ranges, legacy filters |
| [Test and predict presets](testing.md) | Static checks, rendering tools, and what can be predicted from source alone |
| [Checklist](checklist.md) | Common mistakes, each with a real preset that made it |

## A first preset

This complete preset draws a ring that swells with the bass. It uses only a composite shader; the default warp keeps the previous frame.

```ini
MILKDROP_PRESET_VERSION=201
PSVERSION=2
PSVERSION_WARP=0
PSVERSION_COMP=2
[preset00]
fDecay=0.94
fGammaAdj=1
fWaveAlpha=0
zoom=1
rot=0
warp=0
comp_1=`shader_body
comp_2=`{
comp_3=`    float beat = saturate(0.85*(bass-0.8));
comp_4=`    float2 p = (uv-0.5)*float2(texsize.x/texsize.y,1.0);
comp_5=`    float radius = 0.22 + 0.18*beat;
comp_6=`    float thickness = 0.010 + 0.030*beat;
comp_7=`    float edge = abs(length(p)-radius);
comp_8=`    float core = 1.0-smoothstep(thickness,thickness+0.010,edge);
comp_9=`    float glow = exp(-edge*edge*130.0);
comp_10=`    float3 tint = lerp(float3(0.08,0.62,0.95),float3(0.65,0.90,1.0),beat);
comp_11=`    ret = float3(0.008,0.015,0.028) + core*tint + glow*float3(0.035,0.09,0.15);
comp_12=`}
```

What each part does:

- The version lines come first. Without `MILKDROP_PRESET_VERSION` of at least 200, the shader stages are switched off and `comp_` lines are ignored. `PSVERSION_WARP=0` keeps the classic fixed-function warp; `PSVERSION_COMP=2` enables the composite shader.
- `warp=0` turns off the animated sine warp, which is on by default.
- Shader lines start with a backtick, which the parser strips. Lines are numbered from 1 without gaps; reading stops at the first missing number.
- `bass` and `texsize` come from a header that is prepended to every shader. `texsize.x/texsize.y` corrects for aspect so the ring stays round.

To see it on your TV, put it in a ZIP and upload it as a [custom preset pack](../custom-packs.md).

## A complete, modern example

The *Aurora Ownership* test presets, written for this project, use most block types: per-frame bass envelopes exported through `q` variables, textured, additive and multi-instance shapes, a dotted waveform and a spectrum ring, plus warp and composite shaders. They were designed so their behaviour could be predicted from source before rendering, and the frozen motion, colour and flash estimates matched the render with a worst relative error of 0.076%. The source is in the [predictor branch](https://github.com/johnneerdael/ProjectM-TV/tree/feat/predictor-visual-loop/tools/milk-analyzer/witnesses/patch-0010-aurora); [Test and predict presets](testing.md#aurora-a-preset-designed-to-be-predicted) walks through it.

## Other references

- The projectM team's [preset authoring guide](https://github.com/projectM-visualizer/projectm-visualizer.org/tree/preset-authoring-guide/content/1.docs/3.preset-authoring), in progress, has per-effect setting tables and the full expression-language reference. This section concentrates on execution semantics, shaders and textures, and testing.
- MilkDrop 2's own *preset authoring* HTML guide ships with MilkDrop and remains the original description of every variable.
