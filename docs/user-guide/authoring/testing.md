# Test and predict presets

A preset can fail quietly in many ways: a shader falls back to a default, an equation block is left out, a texture is missing, or the picture is black until the music gets loud. The tools below catch those failures, from a quick static check to predicting what a preset will draw before rendering a frame.

## 1. Try it on a TV

The fastest real test is your TV:

1. Zip the preset and its textures and upload them as a [custom preset pack](../custom-packs.md). **Custom** is selected automatically.
2. Play music in a verified player and watch the preset cold, then again after a minute of music. Feedback presets can take several seconds to build up.
3. Press **Center** to see the preset's name, and open **Advanced** to check the render size and Native trails state in Diagnostics.

### Watch the log on a TV

With developer options and ADB enabled on the TV:

```sh
adb logcat -s projectM-Native
```

| Line | What it tells you |
|---|---|
| `LOAD preset='…' ms=… … weight_mb=… … programs_compiled=…` | The preset loaded, how long it took, how many shader programs were compiled, its texture memory |
| `Preset code left out (<preset>): <reason> (line N, column M)` | An equation block failed to compile and was dropped, as MilkDrop would. The rest still runs |
| `Preset load failed (<preset>): <reason>` | The file could not be parsed; the preset is skipped |
| `SKIP preset='…' reason=…` | The preset was added to this TV's skip list (unreadable, failed to load, too slow, or black twice) |
| `OUTPUT …` | Brightness range and how much of the picture changed while the preset played |

A shader that fails to translate or compile does not stop the preset. Its stage silently uses projectM's default shader instead, so if a preset looks plain or "wrong", suspect its shader first and check it against the [translation table](shaders.md#what-translates-and-what-does-not).

A preset skipped as *black* or *too slow* is recorded on the TV's skip list. You can reset the list under **Advanced › Skipped presets**.

## 2. Static checks

`tools/check-presets.py` runs in CI on the bundled presets in `core/src/main/assets/presets`. It takes no path argument, so to check your own presets, copy them into that folder in a checkout. Never pass `--remove` there casually: it deletes failing presets. The script reports presets that:

- cannot react to music, meaning there is no `bass`, `mid`, `treb`, `vol` or `*_att` in any per-frame, per-pixel, wave, shape or shader code, *and* the main waveform is hidden (`fWaveAlpha` ≤ 0.01 or `wave_a = 0` in code), *and* no custom wave is enabled;
- use an excluded texture (images with text, logos or people);
- use a texture that is not bundled. A texture counts only if its sampler is declared *and* used, directly or through `#define`.

`tools/gen-preset-index.py` estimates each preset's extra memory. It counts every referenced image at its decoded size, random slots at the largest bundled image, and a 32 MB allowance for very large shaders (over 4.2 KB or with two or more loops).

## 3. Preset Lab: render and measure

[Preset Lab](https://github.com/johnneerdael/ProjectM-TV/tree/main/tools/preset-lab) renders presets offline with a private copy of the patched engine, a synthetic clock and fixed seeds.

- `preset-lab trace <preset>` follows the preset's code statically through numbered-line rules, overwrites, conditions, persistent state and q/t transfers, and shows which outputs can depend on which audio inputs. An input that reaches an output may still have a weak effect: a bass term can be overwritten, saturate or affect something invisible.
- `preset-lab bass-screen` renders an identical carrier signal twice, then adds bass bursts at three strengths and measures the per-pixel difference against the control. If the control does not repeat, the result is *unknown*, not "not bass-reactive".

Desktop rendering timings do not predict TV performance.

## 4. Source analysis

The [milk-analyzer](https://github.com/johnneerdael/ProjectM-TV/tree/main/tools/milk-analyzer) tools read a preset with the engine's own parser and shader translator, without rendering. They check four things.

Stage selection works out which warp and composite stages actually run, from the version keys. Many surprises turn out to be a shader that never runs because `MILKDROP_PRESET_VERSION` is missing, or a legacy stage requested by `PSVERSION_WARP=0`.

Q proofs are conservative interval proofs of the values a q variable can take. For `martin - ludicrous speed.milk`, the analyzer proves that `q29` stays within 0…7 after initialization, frame resets and its bounded increment, so a composite branch on `int(q29)%4` covers exactly four cases. A q variable that no code ever writes is proven to be exactly 0 in the shader.

The analyzer also finds implicit globals (uninitialized shader globals, which read 0 on GLES) and checks shader lowering, that is, whether each shader section translates and compiles as GLSL ES 3.00.

A preset that passes all of these will *run*. The checks do not certify how it will *look*.

## 5. Predicting a preset from its source

ProjectM TV's predictor reads a preset's source and works out, without rendering it, how bright, colourful, fast and flashy it will look. Its results decide the app's [preset moods](../predictive-collections.md). The [Predictor](../predictor.md) section explains how it reads a preset, covers the feedback and colour mathematics and its accuracy, and shows [predictions next to real renders](../predictor/gallery.md).

As a preset author, you can use it in two ways. First, to check your preset's mood: once a preset is bundled, its moods come from the analysis. A preset whose brightness depends on how drawn content builds up over many frames, or whose colours are random per load, is harder to predict and may get fewer mood options.

Second, to write predictable presets. Bounded audio envelopes, palettes set in `per_frame_init`, explicit motion variables and composites without undefined arithmetic make a preset's look follow from its source. The Aurora example below was written that way.

### What source analysis cannot settle

The analysis abstains on things the source cannot predict:

- Undefined GPU arithmetic, such as `pow` of a negative base or of zero to a non-positive power, division by zero, and coordinates that become infinite or NaN. GLSL leaves the result to the driver (`TonyMilkdrop - RGB.milk`, `141 nz.milk`, `$$$ Royal - Mashup (452).milk`).
- Random choices. The selected `randNN` images and noise realization must be supplied as declared inputs, because shader text alone does not identify an arbitrary production load's choices.
- Future audio. A preset that reacts to a breakdown cannot be predicted without the music.
- Chaotic feedback. Some presets amplify tiny differences until two runs diverge.

Be careful when explaining a prediction. `325.milk` was predicted numerically correctly, but the written *explanation* was wrong: the q32 variable is never written, so it is 0, which removes the main feedback term, and the result clamps to black. Check the proof of which q variables are untouched before explaining an effect.

## Aurora: a preset designed to be predicted

The *Aurora Ownership* SOL and LUNA presets were written for this project to test one engine feature, and designed so that their behaviour could be forecast before rendering. They make a good template for modern presets.

```ini
MILKDROP_PRESET_VERSION=201
PSVERSION_WARP=2
PSVERSION_COMP=2
[preset00]
fDecay=.90
fGammaAdj=1
fWaveAlpha=0
warp=0
per_frame_init_1=env=0;kick=0;q8=1.0;q9=0.4;q10=0.055;q11=0.3;
per_frame_1=kick=max(.78*kick,min(1.5,max(0,(bass-.95)*1.6)));
per_frame_2=env=.92*env+.08*min(2,max(0,bass_att));
per_frame_3=q1=kick;q2=env;q3=min(1.5,max(0,mid));q4=min(1.5,max(0,treb));
per_frame_4=q5=min(1,max(0,bass-bass_att+.08)*2.4);q6=time*.65;
per_frame_5=zoom=1;rot=0;warp=0;dx=0;dy=0;decay=.90;
```

It is predictable because every audio input passes through `min`/`max`, so `kick` stays within 0…1.5 and `env` within 0…2 whatever the music does. The palette, `q8`–`q10`, is set once in `per_frame_init`, so it is the same every frame (q resets to its post-init value). `per_frame_5` sets every motion variable each frame, including `warp=0`, so nothing depends on defaults.

The core's size can then be forecast. Shape 0's per-frame code is `rad=.74+.12*q1`, so the core's radius ranges from 0.74 to 0.92: a 24.3% larger diameter and 54.6% larger area at full kick. On the test audio, the computed `kick` spans 0.152871 to 1.5. The render matched the forecast with a worst relative error of 0.076%, including exact timing of flash events.

The rest of the preset uses most block types (it has no per-pixel or wave/shape init code):

- shape 0 shows a named image, a projectM extension;
- shapes 1-2 are additive halo rings with thick outlines;
- shape 3 has 12 instances orbiting by `instance`;
- wave 0 is a 256-point dotted ring with per-point colour;
- wave 1 is a spectrum ring;
- the warp shader rotates and zooms the feedback, and clears a box under the core so stale history cannot hide a wrong texture;
- the composite adds rays, blur glow, mist and a vignette.

[Full source](https://github.com/johnneerdael/ProjectM-TV/tree/feat/predictor-visual-loop/tools/milk-analyzer/witnesses/patch-0010-aurora).
