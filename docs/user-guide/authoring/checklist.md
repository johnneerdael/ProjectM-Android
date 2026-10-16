# Checklist

These mistakes were all found in real presets. For each one you get what goes wrong and how to avoid it. Avoid them and your presets will load and look the same in MilkDrop 2, in projectM players and in ProjectM TV.

## The file

| Do | Why | Real example |
|---|---|---|
| Put `MILKDROP_PRESET_VERSION=201` and `PSVERSION_WARP` / `PSVERSION_COMP` first when you use shaders | Without them, shader code is ignored | 1,506 bundled presets have no version line |
| Number code lines 1, 2, 3 … without gaps | Reading stops at the first missing number | — |
| Keep each name and number on one line | MilkDrop glues lines together; other engines don't | `161.milk` splits `is_beat` across two lines |
| Write `key=value` with no space before `=` | `zoom =1` silently keeps the default | — |
| Write booleans as `0` and `1` | `-1` is true in MilkDrop, false in projectM | — |
| Always write `wave_r`, `wave_g`, `wave_b`, `wave_x`, `wave_y` | MilkDrop fills missing ones with 0, projectM with 1/1/1/0.5/0.5 | — |
| Set `PSVERSION_COMP=0` if you don't write a composite shader | projectM's empty-composite fallback skips gamma | — |
| Keep files under 1 MiB | Larger files fail to load in projectM | — |

## Equations

| Do | Why | Real example |
|---|---|---|
| End every statement with `;`, avoid `;)`, use `//` comments | Legacy forms only work in MilkDrop and ProjectM TV | `index=index+1;);` |
| Write `0`, never a lone `.` | projectM's evaluator rejects `.` | `y=if(c,.-.4,y);` |
| Use `int(rand(n))` for an integer | `rand(n)` returns a fraction | — |
| Guard divisions, `pow`, `log`, `asin` | The engines disagree on division by zero and domain errors | — |
| Copy values into `q1`–`q32` every frame you need them | q resets to its post-init value each frame | — |
| Set motion variables every frame you change them | Built-ins reset to the file value each frame | — |
| Don't pass data to the next preset through `reg`/`gmegabuf` | They are per preset in projectM | — |
| Keep `wave_mode` within 0-7 | projectM's modes 8-15 differ from MilkDrop's wrap-around | 4 bundled presets use mode 8 |
| Expect `bass` near 10 for a moment at a cold start | Audio history starts at zero | — |
| Remember `warp` defaults to 1 | Set `warp=0` for a still mesh | — |

## Shaders

| Do | Why | Real example |
|---|---|---|
| Don't name variables `sample`, `inf`, `nan` | Reserved or ambiguous in GLSL | `Flexi - madness portal.milk` turned into a red disc |
| Initialize every global you read | Uninitialized globals read 0 on GLES, anything on D3D9 | `martin - organic light.milk` (`uv3`) |
| Write one constructor per array element | Flat initializer lists can fail translation | `ORB - Stahl - Glass Ocean` |
| Copy an input before modifying it (`float t = time;`) | Writes to inputs need a per-invocation copy | `$$$ Royal - Mashup (324)` |
| Guard `pow`: `pow(max(x,1e-6), y)` | Negative or zero bases are undefined in GLSL | 7 of the 12 unforecastable presets in the 100-preset audit |
| Use float literals (`2.0`) in float expressions | GLSL ES rejects some int/float mixes | `EVET - Spiracology 2` |
| Apply decay in your warp shader | MilkDrop ignores `decay` when a warp shader runs | — |
| Implement gamma/echo yourself in a custom composite | Classic display effects don't apply to it | — |
| Read blur with `GetBlur1/2/3` | Raw blur samplers return encoded values | — |
| Test multiplicative composites with dark and bright feedback | Channel products can crush to black | A bundled preset that looked "broken" was black by design |

## Textures

| Do | Why | Real example |
|---|---|---|
| Choose filtering with `fw_`/`fc_`/`pw_`/`pc_` | `sampler_state` fields are ignored | `ORB - Arctic Chill` |
| Avoid image names like `ab_stars.png` | Any `XY_` prefix is stripped: looked up as `stars` | — |
| Keep texture names unique ignoring case | Lookup is case-insensitive | — |
| Expect premultiplied alpha | Transparent pixels sample black | `… rand tritex - inv play.milk` |
| Design `randNN` for any image, or use a name prefix | Choices change on every load | 192 bundled presets use random textures |

## Shapes, waves and blur

| Do | Why | Real example |
|---|---|---|
| Keep important shapes at least two pixels wide at 1080p | Sub-pixel shapes may not light any pixel | `amandio c - the green machine 2 … btbam covers sepultura.milk` |
| Clamp colours to 0-1 in per-point code | Custom wave colours wrap around instead of clamping | — |
| Keep blur ranges at least 0.1 wide and nested | MilkDrop collapses narrow ranges; ProjectM TV repairs them, so the two look different | `flexi - a julia fractal for hexcollie embossed (Jelly).milk` |
| Use negative `zoom` only with `zoomexp=1` | Other combinations are undefined on GPUs | `Hexcollie - This is where we begin stripped.milk` |

## Before you share

1. Copy the presets into a checkout's `core/src/main/assets/presets` and run `tools/check-presets.py` (without `--remove`).
2. Watch the preset cold and after a minute of music, at 720p and at 4K.
3. Check the TV log for `Preset code left out`.
4. If you can, compare with MilkDrop 2 on Windows.
