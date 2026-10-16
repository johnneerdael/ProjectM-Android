# Anatomy of a .milk file

A `.milk` file is plain text, one `key=value` pair per line, one preset per file.

## Keys and values

| Rule | MilkDrop 2.25c | projectM |
|---|---|---|
| Where the key ends | At the first `=` **or space** (`state.cpp:96–111`) | Same (`find_first_of(" =")`) |
| Key case | Case-sensitive | Lower-cased, so case-insensitive |
| Duplicate keys | — | The first occurrence wins ("to mimic Milkdrop behaviour") |
| A value that does not parse | The default is silently kept | The default is silently kept |
| Booleans (`bWaveDots`, …) | Any nonzero value is true | Only values > 0 are true |
| File size | — | Files over 1 MiB, or containing a NUL byte, fail to load |

In practice:

- Don't put a space before `=`. `zoom =1` stores key `zoom` with value `=1`, which does not parse, so zoom silently stays at its default. This happens in both programs.
- `bWaveDots=-1` is true in MilkDrop and false in projectM. Write `1`.
- `PSVERSION_comp=3` works in projectM but not in MilkDrop. Match the case MilkDrop writes.
- `[preset00]` is a leftover from MilkDrop 1. Neither parser needs it, but MilkDrop writes it, so keep it for tools that expect it.

## The version header decides which shaders run

| `MILKDROP_PRESET_VERSION` | Warp stage | Composite stage |
|---|---|---|
| missing or < 200 (default 100) | fixed-function | fixed-function |
| 200 | `PSVERSION` (default 2) | `PSVERSION` |
| > 200 (MilkDrop writes 201) | `PSVERSION_WARP` (default 2) | `PSVERSION_COMP` (default 2) |

A shader version of 0 means the classic fixed-function stage; anything above 0 enables your `warp_`/`comp_` code. MilkDrop distinguishes 2 (ps_2_0), 3 (ps_2_x) and 4 (ps_3_0) when compiling. projectM only checks "greater than 0".

Of the 9,606 bundled presets, 1,506 have no version line at all and therefore run fixed-function stages, even if they contain shader code.

!!! warning "Shader version without shader code"
    With a version of 200 or more, `PSVERSION_COMP > 0` and no `comp_` lines, MilkDrop generates a composite shader that still applies gamma, video echo and the legacy filters. projectM substitutes a plain pass-through without gamma, so with the default `fGammaAdj=2`, the image is roughly half as bright. If you want the classic composite, set `PSVERSION_COMP=0`. If you want a shader, write one.

## Code blocks

| Block | Keys | Runs |
|---|---|---|
| Preset init | `per_frame_init_1`, `per_frame_init_2`, … | Once, at load |
| Per frame | `per_frame_1`, … | Once per frame |
| Per vertex | `per_pixel_1`, … | Once per warp-mesh vertex per frame |
| Custom wave *N* (0-3) | `wave_N_init1`, `wave_N_per_frame1`, `wave_N_per_point1` | Init once; per frame; per point |
| Custom shape *N* (0-3) | `shape_N_init1`, `shape_N_per_frame1` | Init once; per frame, once per instance |
| Shaders | `warp_1`, `comp_1`, … | On the GPU, per pixel |

Wave and shape code keys have no underscore before the line number (`wave_0_per_point1`, not `wave_0_per_point_1`). A preset has at most four custom waves and four custom shapes.

Settings for waves and shapes use the `wavecode_N_` and `shapecode_N_` prefixes:

- Waves: `enabled`, `samples`, `sep`, `bSpectrum`, `bUseDots`, `bDrawThick`, `bAdditive`, `scaling`, `smoothing`, `r`, `g`, `b`, `a`.
- Shapes: `enabled`, `sides`, `additive`, `thickOutline`, `textured`, `num_inst`, `x`, `y`, `rad`, `ang`, `tex_ang`, `tex_zoom`, `r g b a`, `r2 g2 b2 a2`, `border_r g b a`.

## Numbered lines and how they are joined

Both readers start at line 1 and stop at the first missing number. If you delete `per_frame_7`, everything from `per_frame_8` onwards is silently ignored. MilkDrop also stops at 32,768 characters per block.

A leading backtick is stripped from every code line. MilkDrop's exporter adds one to shader lines so that leading spaces survive.

The two engines join the lines into one program differently:

- MilkDrop joins equation lines with no separator at all, then removes `//` and `\\` comments to the end of each line (`CState::StripLinefeedCharsAndComments`, `state.cpp:1526`). Two lines `a=1;` and `b=2;` become `a=1;b=2;`; without the `;` they would fuse into `a=1b=2`. A name split across two lines is glued back together.
- projectM joins lines with a newline, and its evaluator understands `//` and `/* */` comments.

Real presets depend on MilkDrop's rule. `161.milk` splits a variable name across lines:

```ini
per_frame_22=k1 =  is_
per_frame_23=beat*equal(index%2,0);
```

MilkDrop reads `is_beat`. Stock projectM sees two names and rejects the whole preset. ProjectM TV retries rejected code in MilkDrop's joined form, so it renders as on Windows.

Other legacy forms seen in bundled presets:

| Form | Example | Meaning in MilkDrop |
|---|---|---|
| `\\` comment | `shape_3_per_frame18=/////// Planetary system \\\\\\\` | Comment to end of line |
| Stray `;` before `)` | `shape_3_init176=index=index+1;);` | NS-EEL reads it as a space |
| Lone `.` | `y=if(c,.-.4,y);` | The number 0 |

## When code does not compile

MilkDrop never refuses a preset because of an equation error. It shows an error message for a few seconds, leaves out the block that failed, and runs the rest (`CState::RecompileExpressions`, `state.cpp:1553`):

- If `per_frame_init` fails, q1 to q32 start at zero.
- If a wave or shape `init` fails, its t1 to t8 start at zero.
- A failed per-frame, per-pixel or per-point block does not run.

projectM 4.2 fails the entire preset on any equation compile error. ProjectM TV follows MilkDrop: only a file that cannot be parsed at all fails to load. Each left-out block is logged as `Preset code left out (<preset>): <reason> (line N, column M)` (see [Test and predict](testing.md#watch-the-log-on-a-tv)).

!!! note "Portability"
    For presets that should also work in stock projectM: number lines without gaps, keep every token on one line, end every statement with `;`, use `//` comments, write `0` rather than `.`, and avoid `;)`.
