# Preset moods

!!! warning "Predicted, not guaranteed"
    Every mood is a prediction worked out from the preset's source code, without rendering the preset. An option is only given where the analysis is confident, so some presets deliberately carry no option in a group. If a preset feels wrong for its mood, please [report it](#report-a-wrong-mood): reports on unlabelled and mislabelled presets are how the predictions improve.

The Mood panel lets you choose what kind of presets play: calm or busy, dark or bright, which colours, how much movement, which visual style, and whether to avoid flashing. You can combine options freely, and the panel always shows how many presets your choice leaves.

ProjectM TV decides these moods by reading each preset's equations, shaders, shapes and waves and working out mathematically what the picture will look like. The [Predictor](predictor.md) section explains how that works in detail, how accurate it is, and shows [predictions next to real renders](predictor/gallery.md).

## Open the Mood panel

Open the settings panel and choose **Preset mood** (Settings › Preset mood).

![Mood panel with Energy, Brightness, Colour, Palette, Main colour, Movement, Style and Comfort rows](images/setup/mood.png)

Each row is one group of options. Up and Down move between rows; Left and Right move between options; Center switches the focused option on or off. Every option shows the number of presets you would have if you toggled it (*→ N*; for a selected option, the mix without it). **Clear all** at the bottom switches everything off again. Back returns to the main panel.

## The groups

| Group | Options | What it means |
|---|---|---|
| **Energy** | Chill, Normal, Intense | How much the picture changes from frame to frame, how fast it moves and how often its overall brightness jumps, combined into one activity level. Chill presets drift and breathe; Intense presets churn, cut and pulse |
| **Brightness** | Dark, Balanced, Bright | The expected average brightness of the picture once the preset has settled |
| **Colour** | Monochrome, Pastel, Vivid, Warm, Cool | The colour character: grey or near-grey (Monochrome), soft and light (Pastel), strongly saturated (Vivid), leaning to red/orange/yellow (Warm) or to blue/cyan/purple (Cool) |
| **Palette** | Red, Orange, Yellow, Green, Cyan, Blue, Purple, Pink | Every colour family that makes up at least 10% of the preset's predicted colours. Most presets have two to five |
| **Main colour** | Red, Orange, Yellow, Green, Cyan, Blue, Purple, Pink | One colour, only when it clearly dominates the whole picture. Most presets have none |
| **Movement** | Still, Drifting, Fast | How fast the picture moves across the screen |
| **Style** | Kaleidoscope, Tunnel, Liquid, Geometric, Particles, Fractal | The construction read from the preset's equations and shapes: mirrored folds, zooming tunnels, fluid smearing, polygons, point clouds, self-similar maps |
| **Comfort** | No strobe | Presets the analysis expects not to flash. Admission is deliberately strict |

A preset can carry several options in one group (for example both Chill and Normal, several Style options, several Palette colours) or none. Grey presets (**Monochrome**) never carry a Palette or Main colour option.

### Palette or Main colour?

The two colour groups answer different questions:

- **Palette › Blue** plays every preset in which blue is one of the colours, even if it shares the screen with pink and green.
- **Main colour › Blue** plays only presets that are mostly blue.

Choose Palette when you want a colour to be present, and Main colour when you want the whole screen in that colour. Because a main colour needs the picture to be dominated by one family, Main colour pools are much smaller than Palette pools.

### Presets per option

The numbers below are for the 9,606 bundled presets. Ranges overlap, so the counts in a group can add up to more or less than 9,606.

<!-- option-counts -->

## How choices combine

- Options in the **same group** combine as OR: **Palette › Red** and **Palette › Blue** play presets with either colour.
- **Different groups** combine as AND: **Chill** and **Dark** play presets that are both.
- Nothing selected plays all presets, including those without any mood option. **Clear all** returns to that (it rests while Custom plays, keeping your options).
- Options that would leave no presets are dimmed and skipped by Left and Right.
- The header always shows a count: *N presets in your mix*, all available presets when nothing is selected, or *Custom pack: N presets* while Custom plays. Under 20 it adds *few presets: some repetition*. If no preset is left, because every match is skipped on this TV or a deselection leaves no preset that fits every group, it shows *No presets match your mix; playing All* and plays All.
- Counts exclude presets this TV has skipped. Automatic changes, **Random** and **Previous** stay inside the mix, and your choice is saved.
- A **Chill**, **Normal** or **Intense** choice saved by an earlier version becomes the matching **Energy** option.
- Presets from a [custom pack](custom-packs.md) have no attributes, so they are not played while any option is active. The **Collection** row (*Built-in* or *Custom*) appears when a pack exists or Custom is chosen; choose *Custom* to play the pack.

## Presets without an option

The analysis only gives an option when it is confident. A preset whose brightness could be either Dark or Balanced gets neither, rather than a guess. This keeps the options precise, at the cost of smaller pools: an option you select plays presets that very likely belong there, but not every preset that would.

Unlabelled presets are not hidden. They play whenever the group they lack has nothing selected, and always when nothing is selected at all. Of the 9,606 bundled presets, <!-- style-only --> carry no option apart from Style. They are deliberately left that way so that people can say what they actually look like.

## Which presets have attributes

GitHub editions bundle attributes for all 9,606 presets. F-Droid editions start with 20 starter presets that carry their own attributes, so the counts are small until you download the full collection from **Advanced › Cream of the Crop** ([collection setup](getting-started.md#optional-collection-in-f-droid-editions)). A full-collection download made before attributes existed has none: the Mood header then reads *Download the full collection again to choose moods (Settings › Advanced › Cream of the Crop)* and only the Collection choice is offered. Downloading, replacing or removing the collection updates the Mood panel and the mix immediately; no restart is needed.

## How accurate are moods?

The predictions were checked against real renders of presets, out of fold: the analysis was always scored on presets it had not been tuned on.

- About **4 of 5** options it gives are correct, and it gives about **2 of every 5** options a render would show.
- In-between options (**Balanced**, **Drifting**, **Normal**) are only given where they reach **80%** precision in those checks, **Pastel** where it reaches **70%**.
- **Palette** finds about three quarters of the colours a render shows, and about 7 of 10 colours it names are present.
- **Main colour** names the render's top colour about **84%** of the time.

The [accuracy page](predictor/accuracy.md) has the numbers per option and explains how they were measured.

## Report a wrong mood

Open an [issue on GitHub](https://github.com/johnneerdael/ProjectM-Android/issues) with:

- the preset name (shown at the top of the settings panel);
- the option that is wrong or missing (for example "tagged Chill but strobes", "no Brightness option but clearly Dark", "Palette says blue, I see orange");
- the song or kind of music, and your TV model.

Reports on presets without an option are just as useful as reports on wrong ones.

## Limits

- Moods are predictions, not measurements of your screen: a preset can look different with your music, especially where it reacts strongly to audio, uses random textures or picks random colours at load.
- **No strobe** and **Chill** are not guarantees against flashing. Use them as a starting point if you are sensitive to flashing light.
- **Style** rests on source structure and is the least certain group.
- Some presets have no option in a group; they play only while that group has nothing selected.
- Custom-pack presets are excluded while any option is active.

## Where moods come from

- [How ProjectM TV understands presets](predictor.md): the idea, the rules and what ships.
- [Reading a preset](predictor/source-reading.md): from `.milk` text to facts.
- [Feedback, brightness and motion](predictor/feedback-maths.md): the closed-form maths.
- [Colour and palettes](predictor/colour.md): hue families, Palette and Main colour.
- [From estimates to moods](predictor/mood-table.md): calibration, precision floors and the shipped table.
- [Accuracy](predictor/accuracy.md), [prediction images](predictor/prediction-images.md), [predictions vs renders](predictor/gallery.md), [the SDK](predictor/sdk.md) and the [research journal](predictor/journal.md).
