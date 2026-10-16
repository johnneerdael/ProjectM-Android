# Colour and palettes

Colour was the hardest part of the analysis and the last to be finished. A preset's source rarely says "this is blue": colours come from formulas that change over time, from shaders that remap the canvas, from textures, from channels that the feedback loop keeps or kills at different rates, and sometimes from random choices made at load. This page explains how the predictor turns all of that into the **Colour**, **Palette** and **Main colour** options.

## Hue families

Colours are named by **hue family**, using hue in the HSV model (`time_expression.hue_family`). A colour is grey when its brightness (V) is below 0.02 or its saturation (S) is below 0.08. Otherwise its hue angle decides the family:

| Family | Hue range (degrees) |
|---|---|
| Red | 345–360 and 0–15 |
| Orange | 15–45 |
| Yellow | 45–75 |
| Green | 75–165 |
| Cyan | 165–195 |
| Blue | 195–255 |
| Purple | 255–285 |
| Pink | 285–345 |

Green and blue cover wide arcs because the eye distinguishes fewer shades there; cyan and purple are narrow bands between them.

## Where colour comes from in a preset

The analyzer collects colour from every source the [source reading](source-reading.md) exposes:

- **Element colours**: waves, shapes, borders and motion vectors, with their colour formulas sampled at 60 moments between 0.5 and 30 s. A shape whose colour cycles through the spectrum contributes several families.
- **The feedback steady state**: the colour the canvas settles at ([feedback equilibrium](feedback-maths.md#2-where-the-canvas-settles-feedback-equilibrium)). Channel-selective warps (keep red, cut blue) push any drawing towards particular families.
- **The warp's detail colour**: what the warp shader makes of grey texture. Some warps create colour from nothing, for example by offsetting channels against each other.
- **The composite**: its flat transfer and colour matrix say how canvas colours are remapped on screen. A composite can turn a grey canvas into a full rainbow, or a colourful canvas into grey. Element colours are passed through the composite colour matrix before they count.
- **The calibrated hue estimate**: the [calibration model](mood-table.md) predicts the share of each hue family in the final picture from all static features.

## The static display palette

`preset_recipe.display_palette` pools these sources into one palette, without stepping any frames. Each source is normalised and then weighted:

| Source | Weight | Condition |
|---|---|---|
| Calibrated hue shares | 24 | always |
| Composite detail colour | 3 | when the composite colours more than half of a grey texture |
| Feedback steady state | 1.5 | when it is coloured |
| Warp detail colour | 1 | when the warp colours more than 30% of a grey texture |
| Shape fills | 1 × area | per shape |
| Waves | 0.3 | per wave |
| Point clouds | 0.3 | per custom wave drawn as dots |

The calibrated estimate carries most of the weight because it is the only source that has been checked against real pictures across the whole corpus; the mechanistic sources refine it where they have something to say. Raising its weight to 24 lifted "leading hue in the engine's top two" from 64% to 70% out of fold.

Pooled shares below 3% are dropped and the rest renormalised. The calibrated hue shares are first **sharpened** according to the predicted share of the top colour: when the model expects one colour to dominate, the distribution is raised to a power (1, 1, 1.5 or 2 depending on the predicted top share, with bin edges at 0.378, 0.456 and 0.561), so a preset that is mostly blue is not described as a spread of five colours.

## Palette

**Palette** lists every family with a pooled share of at least **10%**. Most presets have two to five. Out of fold, a 10% palette finds about **76%** of the colours the engine's render shows, and about **71%** of the colours it names are really present.

The threshold is a trade-off. A lower threshold would find more true colours and name more false ones; 10% keeps a named colour more likely right than wrong while still listing secondary colours.

## Main colour

**Main colour** is deliberately strict. A family becomes the main colour only when both:

1. the calibration model predicts that the top colour covers at least **65%** of the coloured picture (`hue_top_share ≥ 0.65`), and
2. that family holds at least **55%** of the pooled palette.

The second condition was added after the first alone named a main colour for too many mixed presets. With both, main-colour claims name the render's top colour **84%** of the time out of fold (77% with the first condition alone), and claims cover about 10% of coloured presets. In the shipped table 1,135 presets (about one in nine) have a main colour.

## Grey presets

About 1,000 bundled presets show almost no colour (engine coloured share below 10%). A naive palette would still name hues for them, from authored colours the composite then washes out. Instead, when the **Monochrome** classifier admits a preset (93% precise out of fold), the palette is empty, there is no main colour, and the preset is marked grey. In the out-of-sample checks the monochrome classifier never admitted a coloured preset.

## Colour, Pastel, Vivid, Warm and Cool

The **Colour** group uses five estimated quantities:

- **coloured share**: the fraction of the picture that is clearly coloured rather than grey (the static probes count a pixel as coloured at saturation 0.25 or more and brightness 0.10 or more);
- **saturation**: the mean saturation of the picture;
- **luminance**: the mean brightness;
- **warm/cool balance**: from −1 (all cool hues) to +1 (all warm hues).

The rule thresholds in the definition (`tools/milk-analyzer/facets/facets-v1.json`) are:

| Option | Rule on the estimated values |
|---|---|
| Monochrome | coloured share below 0.1 |
| Pastel | luminance above 0.35, saturation below 0.3, and not Monochrome |
| Vivid | saturation at least 0.5 |
| Warm | warm/cool at least 0.25 |
| Cool | warm/cool at most −0.25 |

Monochrome, Pastel, Warm and Cool are decided by dedicated classifiers rather than by these rules on point estimates; see [From estimates to moods](mood-table.md). Pastel is the hardest: soft, light colour is easily confused with white-out or grey, so it is only given where the classifier reaches 70% precision.

## Colour that changes at load

Some presets pick their colours at random when they load: a `rand_preset` switch, random redraws of the `q` values that feed colours, a random hue offset in the composite, or a random library texture. The analysis knows the *distribution* of colours, not the draw your TV will make. The recipe marks such presets (`random_tint`, `per_load_random`, `random_redraws`), and their palettes describe the colours that are likely across loads. They account for several of the colour misses in the [gallery](gallery.md#where-it-misses).

## Example

**Various – Fire and Brimstone**: the calibrated hue shares lead with green (0.33), red (0.26) and yellow (0.19). The feedback steady state is yellow. Pooled, the palette is green, red and yellow (each above 10%); no family reaches the main-colour bar, so it has no main colour. The render shows red, yellow and green fire, as the [comparison](feedback-maths.md) shows.
