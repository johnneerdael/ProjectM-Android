# Accuracy

How often is a mood right? This page gives the numbers, explains how they were measured, and says what they do and do not promise.

## What "right" means

The reference is the **engine ruler**: every bundled preset rendered by the pinned, patched engine at 480×270 for 10 seconds (300 frames at 30 fps) with one synthetic audio track, measured over frames 60–299. Applying the mood rules to the ruler's measurements gives each preset's **true** options. A predicted option is right when the ruler agrees.

Two numbers describe each option:

- **Precision**: of the presets the analysis put in the option, the share that truly belong. This is what you experience when you select it: "if I pick Dark, how many of the presets I get are dark?"
- **Recall**: of the presets that truly belong, the share the analysis found. This is how complete the pool is.

The analysis is tuned for precision. Low recall means smaller pools, not wrong presets.

## Out of fold: the honest numbers

The calibration model was trained on the ruler measurements of the bundled presets. Scoring it on those same presets would flatter it. Every number in this section is therefore **out of fold**: the presets were split into five groups, and each preset was predicted by a model trained only on the other four. These are the numbers to expect for presets the analysis has never seen.

Shipped decision path (value rules, option classifiers with their precision floors, the No strobe gate), 9,516 presets with complete ruler measurements:

| Group | Option | Precision | Recall | Admitted | True members |
|---|---|---|---|---|---|
| Energy | Chill | 87% | 46% | 1,765 | 3,361 |
| Energy | Normal | 80% | 30% | 1,799 | 4,807 |
| Energy | Intense | 75% | 72% | 2,757 | 2,882 |
| Brightness | Dark | 81% | 44% | 1,424 | 2,605 |
| Brightness | Balanced | 78% | 18% | 979 | 4,301 |
| Brightness | Bright | 72% | 62% | 2,344 | 2,700 |
| Colour | Monochrome | 93% | 27% | 288 | 1,002 |
| Colour | Pastel | 70% | 13% | 126 | 692 |
| Colour | Vivid | 79% | 74% | 4,641 | 4,948 |
| Colour | Warm | 82% | 59% | 1,703 | 2,381 |
| Colour | Cool | 76% | 47% | 1,054 | 1,695 |
| Movement | Still | 82% | 40% | 993 | 2,018 |
| Movement | Drifting | 79% | 23% | 1,404 | 4,751 |
| Movement | Fast | 77% | 49% | 1,814 | 2,837 |
| Comfort | No strobe | 98% | 13% | 641 | 4,969 |
| **All options** | | **79.1%** | **40.9%** | | |

### Palette and Main colour

- **Palette** (families with at least 10% of the static palette): finds about **76%** of the colours in the render, and about **71%** of the colours it names are present.
- **Leading colour**: the palette's leading family is among the render's two most common families **72%** of the time.
- **Main colour**: when a main colour is claimed, it is the render's top colour **84%** of the time.
- **Monochrome** (grey presets get no palette): 93% precise.

### No strobe in detail

No strobe is the option where a wrong answer matters most. Out of fold, the gate admitted 641 presets. Ten of them showed one or more brightness jumps per 10 s in the ruler render (at most 7), and **none** showed 10 or more, the level the classifier treats as strobing. The highest score any strobing preset reached was 0.906, below the 0.93 gate. The cost of that strictness is recall: only 13% of calm presets are admitted.

This is measured with one synthetic audio track. Music with hard transients can trigger flashes the test track did not. **No strobe is a starting point, not a guarantee.**

## In sample: what the shipped table contains

The shipped table is built by the final model, trained on all bundled presets, so for the bundled presets themselves agreement with the ruler is higher than out of fold:

Agreement of the shipped table with the ruler on the 9,606 measured bundled presets:

| Group | Option | Precision | Recall | In the table |
|---|---|---|---|---|
| Energy | Chill | 98% | 60% | 2,068 |
| Energy | Normal | 98% | 42% | 2,072 |
| Energy | Intense | 90% | 88% | 2,828 |
| Brightness | Dark | 97% | 66% | 1,780 |
| Brightness | Balanced | 98% | 28% | 1,236 |
| Brightness | Bright | 90% | 83% | 2,469 |
| Colour | Monochrome | 100% | 47% | 473 |
| Colour | Pastel | 99% | 46% | 318 |
| Colour | Vivid | 86% | 81% | 4,663 |
| Colour | Warm | 96% | 76% | 1,888 |
| Colour | Cool | 97% | 73% | 1,271 |
| Movement | Still | 97% | 61% | 1,276 |
| Movement | Drifting | 98% | 35% | 1,711 |
| Movement | Fast | 88% | 60% | 1,936 |
| Comfort | No strobe | 100% | 14% | 712 |
| **All options** | | **93.3%** | **54.2%** | |

These figures describe how the shipped table relates to the ruler; the out-of-fold figures above describe how reliable the analysis is.

## How good can it get?

Two independent measurements of the same presets do not agree perfectly either. Emulator captures (different audio) and the engine ruler, on 84 presets, agreed on Energy 86% of the time, Brightness 81%, Movement 93% and Comfort 92%. Music, randomness and timing change a preset's look from run to run. No prediction can be expected to beat the agreement of two real renders, so these are the practical ceilings.

## Checkpoints: predictions next to real renders

The table numbers come from statistics. To see whether the analysis *understands* presets, about 400 presets were drawn at random (pre-registered seeds, no rerolling) and checked one by one:

1. the analysis described the preset and drew a [prediction image](prediction-images.md), all frozen and hashed before anything was rendered;
2. the preset was rendered in an emulator with the published core library;
3. prediction and render were compared: brightness, colour, motion and layout over frames 60–149, plus the description's claims.

Highlights:

- On checkpoints r129–r156, 93% of predictions were within 0.05 of the render's brightness, and the median layout correlation was 0.92.
- In the batch rounds 15–22 (80 presets), the static Mood options made 214 admissions, 12 of them wrong (94%), and recalled 202 of 378 ruler options (53%). Round 23 made 25 admissions, none wrong. These presets were drawn from the bundle, so the calibration had seen their ruler measurements; read them as a consistency check of the shipped decisions rather than an out-of-fold result.
- Many chaotic presets are predicted frame for frame; see the [gallery](gallery.md).

## Where the analysis is weak

- **Brightness that builds up over time.** When drawn content accumulates in the feedback loop (magnifying warps that grow a thin line until it fills the screen, slow equilibria), the closed forms can be far off. Out of fold, brightness ranks presets with a correlation of about 0.70: good for ordering, loose for any single preset.
- **Random colour.** Presets that pick colours or textures at load get a palette of likely colours; the colour you see depends on the draw.
- **Audio-driven flashes.** Flashing triggered only by loud transients in real music is under-represented in a synthetic test track.
- **Style.** Style options come from source structure and have no ruler measurement to score against; they are the least certain group.
- **The middle.** In-between options (Balanced, Drifting, Normal) have the lowest recall: a preset needs strong evidence to be called "in the middle", so most uncertain presets get no option in that group.

## Report a wrong mood

If a preset is in the wrong mood, or has no option where it clearly should, please [report it](../predictive-collections.md#report-a-wrong-mood). Reports become checkpoints: the miss is analysed, the missing mechanism fixed for all presets, and the whole corpus re-checked.
