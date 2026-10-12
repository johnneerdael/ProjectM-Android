# Preset moods

!!! warning "Measured, not guaranteed"
    Moods are predictions from one short measurement of each preset. They are a starting point, and they will improve. If a preset feels wrong for its mood, please [report it](https://github.com/johnneerdael/ProjectM-Android/issues).

Open the settings panel and choose **Preset mood** (Settings › Preset mood) to open the **Mood** panel.

![Mood panel with Energy, Brightness, Colour, Movement, Style and Comfort rows](images/setup/mood.png)

## Attributes

Each group is one row; each option shows the number of presets you would have if you toggled it (*→ N*).

| Group | Options | Measured from |
|---|---|---|
| **Energy** | Chill, Normal, Intense | An activity percentile combining frame-to-frame change, motion speed and brightness jumps |
| **Brightness** | Dark, Balanced, Bright | Mean luminance |
| **Colour** | Monochrome, Pastel, Vivid, Warm, Cool | Coloured share, saturation, luminance and warm/cool balance |
| **Movement** | Still, Drifting, Fast | Motion speed in screen widths per second |
| **Style** | Kaleidoscope, Tunnel, Liquid, Geometric, Particles, Fractal | Structure facts read from the preset source |
| **Comfort** | No strobe | Brightness jumps per 10 s below a threshold |

The exact thresholds are in `tools/milk-analyzer/facets/facets-v1.json`. Ranges can overlap, so a preset can be both Chill and Normal, and one preset can carry several Style options.

## How choices combine

- Options in the **same group** combine as OR: **Vivid** and **Warm** play presets that are either.
- **Different groups** combine as AND: **Chill** and **Dark** play presets that are both.
- Nothing selected plays all presets. **Clear all** returns to that.
- Options that would leave no presets are dimmed and skipped by Left and Right.
- The header shows *N presets in your mix*. Under 20 it adds *few presets: some repetition*. If every match is skipped on this TV it shows *No presets left in your mix; playing All* and plays All.
- Counts exclude presets this TV has skipped. Automatic changes, **Random** and **Previous** stay inside the mix, and your choice is saved.
- A **Chill**, **Normal** or **Intense** choice saved by an earlier version becomes the matching **Energy** option.
- Presets from a [custom pack](custom-packs.md) have no attributes, so they are not played while any option is active. The **Collection** row (*Built-in* or *Custom*) appears when a pack exists or Custom is chosen; choose *Custom* to play the pack.

## Which presets have attributes

GitHub editions bundle attributes for all 9,606 presets. F-Droid editions start with 20 starter presets that carry their own attributes, so the counts are small until you download the full collection from **Advanced › Cream of the Crop** ([collection setup](getting-started.md#optional-collection-in-f-droid-editions)). A full-collection download made before attributes existed has none, and then the Mood panel offers only the Collection choice; download the collection again to get the attributes.

## How the attributes are measured

Energy, Brightness, Colour, Movement and Comfort come from engine-ruler measurements of every bundled preset. Each preset is rendered once for 10 seconds at 480x270 and 30 fps; the statistics use frames 60-299 and one synthetic audio track, on macOS GLES under SwiftShader (see `tools/native-ruler/`). Style comes from facts read from the preset source: its equations and shapes, not a render.

## Limits

- One 10 s render per preset with one synthetic track under SwiftShader. Real music and TV GPUs differ. Emulator agreement on 83 presets was rho 0.91-0.96, which is not a per-preset guarantee.
- **Style** rests on source structure and is the least certain attribute.
- **No strobe** and **Chill** are not guarantees against flashing.
- Custom-pack presets are excluded while any option is active.

## Legacy activity scores

The Chill, Normal and Intense categories that Milkbeat and older versions use (a 1-100 activity score: Chill 1-30, Normal 25-75, Intense 70-100) are unchanged in the core library. The sections below describe that score and its example captures; the **Energy** options in the Mood panel are computed separately from the ruler measurements above.

| Chill | Normal | Intense |
|---|---|---|
| ![Legacy Chill category: 2,702 presets in rotation](images/setup/mood-chill.jpg) | ![Legacy Normal category: 4,658 presets in rotation](images/setup/mood-normal.jpg) | ![Legacy Intense category: 2,795 presets in rotation](images/setup/mood-intense.jpg) |

## What the legacy categories look like

These captures come from a 1080p Android TV emulator playing different tracks in Milkbeat, with the mood set and a random preset chosen for each. Your music and TV will produce different frames; these show the character of each mood, not a guarantee.

### Chill

| | |
|---|---|
| ![Zylot - The Collective Unconcious (Jelly 5-5)](images/gallery/chill-1.jpg) | ![EoS - pointfield 12 deep oceans](images/gallery/chill-2.jpg) |
| *Zylot – The Collective Unconcious (Jelly 5-5)* | *EoS – pointfield 12 deep oceans* |
| ![EoS + Phat - chasers 10 sentinel B](images/gallery/chill-3.jpg) | ![LuxXx - Makes Me Cry II (Lifeforms in the Clouds)](images/gallery/chill-5.jpg) |
| *EoS + Phat – chasers 10 sentinel B* | *LuxXx – Makes Me Cry II (Lifeforms in the Clouds)* |

### Normal

| | |
|---|---|
| ![Bdrv Aderrasi - Armada (Battleship)](images/gallery/normal-3.jpg) | ![flying hamster - flower borders (version 8)](images/gallery/normal-2.jpg) |
| *Bdrv Aderrasi – Armada (Battleship) bdrv etAL rolo nz* | *flying hamster – flower borders (version 8) – mash0001* |
| ![cortex meat - adm affect non](images/gallery/normal-4.jpg) | ![Geiss - Calligraphy (Jelly V3)](images/gallery/normal-5.jpg) |
| *cortex meat – adm affect non* | *Geiss – Calligraphy (Jelly V3)* |

### Intense

| | |
|---|---|
| ![figurative lesson lard](images/gallery/intense-1.jpg) | ![rce-ordinary - microscopic things (crosslinking mix)](images/gallery/intense-2.jpg) |
| *figurative lesson lard* | *rce-ordinary – microscopic things (crosslinking mix)* |
| ![suksma - coal drapes](images/gallery/intense-3.jpg) | ![negation entropy (scalar nods)](images/gallery/intense-4.jpg) |
| *suksma – coal drapes – mrt fsh behooval roam3 nz+* | *negation entropy (scalar nods)* |

A single still cannot show motion. What separates the moods is how fast and how suddenly these pictures change.

## How the legacy scores are made

The score measures **visual activity**, not musical genre or taste. Each bundled preset was run once through the published ProjectM TV core library (version 2.3.3, in its capped build, which predates the current Native engine based on projectM 4.2) with controlled input:

- 420 frames at 30 fps, at 128×72 pixels with a 48×32 mesh; the first 60 frames are warm-up.
- A synthetic test signal: quiet tones for 0–5 s, a brighter melody for 5–9 s, then melody plus kick-drum pulses for 9–14 s. No real recordings are used or shipped.

Four quantities are measured from the frames:

1. **Coherent brightness transitions per second**: changes of at least 0.1 in normalized brightness over at least 20% of the picture, with the mean brightness also changing by at least 0.1.
2. **Median motion** in screen widths per second, from optical flow sampled at 10 fps.
3. **Mean acceleration** of that motion.
4. **Peak per-pixel change**: the 95th percentile, over frame pairs, of each pair's 95th-percentile brightness change.

They are combined as `4.3673 + Σ weight × log1p(x) / scale`, with weights of about 36.97, 2.47, 50.61 and 23.40. A separate flash term, from paired up-and-down brightness flips, is computed too, and the larger of the two values is used. The raw values are ranked and rescaled so that the least active preset scores 1 and the most active 100. A score therefore places a preset relative to the others; it is not a percentage. The 382 presets that showed no visible activity in the measurement score 1, stay in All, and are left out of the three moods.

The weights were fitted to eight human judgments of real presets. In leave-one-out checks the model placed 4 of 8 in exactly the judged band and 6 of 8 within five points. That is a small calibration set, which is why moods are still beta.

## Known limits of the legacy scores

- **One short probe.** Fourteen seconds of synthetic audio cannot show how a preset reacts to every song, or how it develops over minutes.
- **Low resolution.** The probe renders at 128×72; 4K detail and Native trails are not measured.
- **Random inputs.** Random textures and noise differ from run to run.
- **Chill is not a promise.** A Chill preset can still flash on the right music.

Report a mismatch with the preset name (shown in the settings panel), the mood, the song and your TV.

## Predictor development is separate

The current [source predictor](predictor.md) is developing conditional JSON
descriptions of mathematical constructions, materials and audio controls without
rendering frames. Its [export contract](predictor-export.md) is separate from this
measurement bundle. These source traits have not replaced the shipped scores,
and no calibrated source-only Chill/Normal/Intense classifier is claimed.

## For developers

The bundle lives in `core/src/main/assets/preset-genres/`:

- `presets.jsonl` holds each preset's source hash, measurements, score and memberships;
- `manifest.json` holds the model, runtime and signal identities, render settings and checksums;
- one index file per mood.

Verify the bundle with:

```sh
python tools/milk-analyzer/beta_export.py --check --bundle core/src/main/assets/preset-genres
```

The checker recomputes every rank and membership from the recorded measurements and refuses stale source or texture hashes, a different runtime, or a wrong frame schedule. Producing new scores needs an Android emulator and the pinned core library; see the [analyzer README](https://github.com/johnneerdael/ProjectM-Android/blob/main/tools/milk-analyzer/README.md). The app never renders the library itself: it reads the prebuilt indexes.
