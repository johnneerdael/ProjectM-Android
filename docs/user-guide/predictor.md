# How ProjectM TV understands presets

ProjectM TV bundles 9,606 MilkDrop presets. Each is a small text file of equations, shader code, shapes and waves: a recipe the engine runs 30 or 60 times a second. Nothing in that file says "this one is a dark blue tunnel" or "this one strobes on the kick drum". The look only exists once the engine has run the recipe for a few seconds, through a feedback loop that keeps redrawing its own previous frame.

The **predictor** is a body of static analysis that reads a preset's source and works out mathematically what the picture will look like, without rendering it. It decides every [preset mood](predictive-collections.md) in the app.

Pages in this section:

| Page | Contents |
|---|---|
| [Reading a preset](predictor/source-reading.md) | How a `.milk` file becomes thousands of auditable facts: the native reader, equation and shader graphs, drawn elements, audio routes |
| [Feedback, brightness and motion](predictor/feedback-maths.md) | The closed-form mathematics: decay orbits, warp transfer, feedback equilibrium, trail level distributions, motion and flashing |
| [Colour and palettes](predictor/colour.md) | Hue families, the static display palette, Palette and Main colour, grey presets, warm and cool |
| [From estimates to moods](predictor/mood-table.md) | The calibration model, the per-option classifiers and their precision floors, the shipped table and its checks |
| [Accuracy](predictor/accuracy.md) | How right the moods are, per option, measured out of fold, and what the numbers mean |
| [Prediction images](predictor/prediction-images.md) | How a predicted picture is drawn from the facts, and how the real render it is compared with is captured |
| [Predictions vs renders](predictor/gallery.md) | Frozen predictions side by side with real renders, including chaotic presets the analysis gets right, and the misses |
| [The JSON output](predictor/json-output.md) | Every field of the recipe and the mood evidence, and what each value means |
| [The SDK](predictor/sdk.md) | The understanding SDK, the knowledge pack and the LLM skill that turns facts into plain-language descriptions |
| [Research journal](predictor/journal.md) | Twelve days, about 600 commits and nearly 400 checkpoints: how the analysis was built and corrected |
| [The road ahead](predictor/future.md) | Using the dataset to train MilkDrop models and to generate visuals for other frameworks |
| [Export contracts](predictor-export.md) | File formats and contracts for the exports, the mood bundle and the knowledge pack reader |

## Understanding, not recreation

The predictor is not meant to be a second renderer; the engine already is one. Its goal is understanding: being able to say from the source alone what a preset draws, how it moves, which colours it settles on, how it reacts to music and whether it flashes, in a form that both people and programs can use.

That goal sets three working principles:

- The analysis describes mechanisms. "The warp keeps red at 99.4% per frame, green at 97% and cuts blue to 85%, so the canvas drifts to yellow-orange and blue halves in about 4 frames" is understanding; a pixel-exact copy of the picture would not be.
- Every fact names its evidence: the equation, shader expression or setting it came from, and the conditions under which it holds.
- Unknowns stay explicit. When a value depends on something the analysis cannot resolve (an unbounded audio term, a random texture, a loop that does not terminate within budget), the fact says so instead of guessing.

## The rules

The project owner set these rules at the start of the research, and they held throughout:

1. **Moods come from the source.** Static analysis decides every option in the shipped Mood table. No value comes from a rendered frame.
2. **Renders validate, they never decide.** Real renders, captured in an emulator or measured by the engine ruler, are used to check and correct the mathematics. They may not change a prediction directly: there are no per-preset overrides, and no preset is fitted to its own render.
3. **Every correction must be general.** When a prediction misses, the missing mechanism is found and fixed for every preset that uses it, then gated against the whole corpus so nothing else regresses. Fixes are mathematical and never tuned to one preset.
4. **Fast enough to be static.** The analysis that feeds the moods must stay cheap, with no frame-by-frame simulation of the whole picture and no downscaled mini-renders used as features. (A downscaled 64×36 simulation was tried and rejected: MilkDrop feedback depends on pixel scale, and its rank correlation with real brightness fell from 0.92 to 0.76.)
5. **Precision over coverage.** An option is only given where it is likely right. It is better to leave a preset without a Brightness option than to call it Balanced on a coin flip.
6. **Nothing runs on the TV.** All analysis happens offline when the collection is built. The app reads a small table.

## What actually ships

The app ships one file per collection, `preset-attributes/attributes.tsv`, with one line per preset holding its mood options and eight estimated values. For all 9,606 presets it is about 400 KB compressed, roughly 42 bytes per preset. The core library's `PresetFacets` class reads it and the Mood panel shows it.

The table is built from the static evidence file, `docs/superpowers/evidence/static-mood-table-2026-10-16/static-evidence.json.gz`. It has one record per preset with its file hash, options, palette, main colour and values, plus the identity of the analysis that produced them. CI rebuilds the table from this file and fails if a single cell differs, if a preset file has changed since it was analysed, or if the table outgrows its size budget.

The evidence itself comes from the analyzer in `tools/milk-analyzer/` on the research branch `feat/predictor-static-output-bounds`. The analyzer is not merged into `main`; `main` carries its output and the checks.

[From estimates to moods](predictor/mood-table.md) follows the whole chain.

## Three kinds of result

The research produced three kinds of result that are easy to confuse:

| Result | Description | Used for moods? |
|---|---|---|
| **Static estimates and facts** | Closed-form analysis of the source plus a calibration model over static features. Milliseconds to seconds per preset. | **Yes**: this is the Mood table |
| **Prediction images** | The preset's own exported equations and shaders evaluated frame by frame by the analyzer for 150 frames, drawn as a picture | No: a validation and illustration tool for people ([details](predictor/prediction-images.md)) |
| **Real renders** | The engine itself, either the engine ruler (all 9,606 presets, used to train and score the calibration) or emulator captures (about 400 checkpoint presets) | No: ground truth for checking and calibrating the mathematics |

## Where it stands

- Out of fold, about 4 of 5 mood options the analysis gives are correct, and it gives about 2 of 5 of the options a render would ([accuracy](predictor/accuracy.md)).
- On nearly 400 randomly drawn checkpoint presets, frozen predictions were compared with emulator renders; many chaotic presets are predicted frame for frame ([gallery](predictor/gallery.md)).
- The analysis still misses some presets badly, mainly where brightness depends on how drawn content builds up in the feedback loop over time, or where colours are random per load. The [journal](predictor/journal.md) lists the open gaps.
