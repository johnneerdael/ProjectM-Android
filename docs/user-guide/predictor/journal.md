# Research journal

The static Mood table is the result of twelve days of continuous research, 5–16 October 2026: about **600 commits** on the research branch, nearly **400 randomly drawn checkpoint presets** compared with real renders, and a whole-corpus analysis of all 9,606 bundled presets rerun many times as the mathematics improved. This page tells that story, including the dead ends.

| Date | Commits | Focus |
|---|---|---|
| 5–8 Oct | ~140 | A numerical forecaster: simulate the preset, compare with the engine |
| 9–10 Oct | ~125 | The turn to static analysis: describe mechanisms, bound values |
| 11 Oct | ~25 | Understanding checkpoints begin: predict, freeze, render, compare |
| 12 Oct | ~50 | The engine ruler; the first Mood panel ships (measured); calibration starts |
| 13 Oct | ~70 | "Renders validate, never decide"; knowledge pack; calibration rounds |
| 14 Oct | ~130 | Engine-exact semantics; tiny-grid simulation rejected; batch checkpoints |
| 15 Oct | ~50 | Per-option classifiers, precision floors, the static palette, all 9,606 grouped |
| 16 Oct | ~10 | Previews as a teacher; the static Mood table |

## 5–8 October: a numerical forecaster

The first approach was direct: re-implement enough of the engine in Python to **simulate** a preset (equations, shaders, feedback) under declared audio, and compare the result with the published core library rendering the same preset. Most of this work was about matching the engine exactly: custom-wave point counts, PCM resampling, quad-strip order after the Y flip, triangle rasterisation, blur precision, half-float texture filtering, the JNI audio quantisation, noise textures, and the semantics of each published core release (2.3.5 through 2.3.25).

It worked in the sense that simulations could reach a frozen 95-point agreement gate on chosen presets. It failed as a way to understand presets: a simulation that matches the engine is just a slower engine. It says *what* the picture is, not *why*, and it costs seconds to minutes per preset. The owner's verdict set the direction for everything after: the project had explicitly not wanted to rely on simulations, the gaps had to be solved mathematically, and a simulation cannot teach anything the code does not already say.

## 9–10 October: the turn to static analysis

Pull request #67 merged the first static **effect families**: named constructions recognised in the source, with parameters and evidence. The next two days added static descriptions of almost every part of a preset, each as a bounded fact rather than a simulated value:

- texture sampling geometry, native blur decoding inputs, composite hue generation;
- shape fill contributions, paired shape trajectories, compound movement bounds;
- feedback scaling envelopes and nominal warp colour transfer;
- nonlinear colour lanes, image-driven lookup offsets, tiled and mirrored coordinate maps;
- direct shader colour response to audio bands, recurrent audio ancestry, `q`-variable proofs.

## 11 October: understanding checkpoints

The checkpoint loop began: draw a preset at random with a pre-registered seed (no rerolls), describe it from the static facts, draw a [prediction image](prediction-images.md), **freeze and hash everything**, then render it in an emulator and compare. The first checkpoints set the pattern of the whole research: each miss pointed to a missing piece of mathematics, which was added for every preset.

- **Zylot – Spiral**: filled gaps and concentric rings were missing → 8-bit decay orbits and floors, persistence sweeps, bilinear spread, radius-locked colour. On an unseen 640×360 check the radial colour profile correlated 0.95–0.99.
- **Rovastar and Krash – Seas Of Tron**: banding, travelling ripples and a row of motion vectors → per-pixel mesh-field structure, motion vectors, echo and gamma, closed-form wave colour. The next version predicted the pink lines, ripples and vector row before capture.
- **Dragonfly Wings**: a black prediction against a dark-red flowing scene → scalar palette maps, flat-field steady states.
- **martin – time machine**: an overexposed glow with lobes against one round sun → float32 equation time (beat refractory ties at exactly three frames), half-pixel offsets of thick wave passes. The corrected prediction was identical to the render: brightness 0.659 against 0.660.
- **404**: a black prediction against four mirrored articulated arms → point positions over per-frame state, engine `rad`/`ang` per stage, sequential alpha compositing. Brightness 0.108 against 0.108.

## 12 October: the engine ruler and the first Mood panel

To score anything at scale, every bundled preset was rendered once by the pinned, patched engine (480×270, 300 frames, synthetic audio): the **engine ruler**. Its measurements produced the first Mood panel in the app, released on `main`: the Mood table was *measured*, not predicted. The owner made clear this was temporary: moods based on rendered measurements had to give way to moods from the source.

The same day the first **calibration** linked static facts to ruler measurements, out of fold. Feedback equilibrium (`a·c/(1−g)` per channel) entered as features. A ceiling was measured too: two real renders of the same 84 presets (emulator and ruler, different audio) agree on Energy 86%, Brightness 81%, Movement 93% and Comfort 92% of the time. No prediction can be expected to beat that.

## 13 October: renders validate, never decide

The rule that governs the shipped table was set: per-preset renders may be used purely to validate and correct a prediction, never to change it directly, only to improve the mathematics behind it; and every mathematical change has to benefit the entire corpus without causing regressions.

Every mathematical change was from then on gated with a paired measure on 200 presets: the fix had to help without regressing others beyond known noise. That day added per-frame random sites, mesh terms with frame state, video echo in the legacy composite, 3-D noise volumes, tiling, legacy hue tint, neighbourhood blur and gradient relief mechanisms, and the platform-neutral **knowledge pack** with its reader contract and golden vectors ([SDK](sdk.md)).

## 14 October: engine-exact semantics, and a rejected shortcut

The busiest day (about 130 commits) was spent on fidelity to the engine's exact rules, each found by a checkpoint miss and fixed generally:

- projectm-eval's cold-start random stream, statement-order random draws, lazy `if`/`&&`/`||`, inlined EEL loops;
- noise textures that follow MilkDrop's procedural noise exactly; random textures sampled as the expected image;
- built-in waves capped at width/3 samples (MilkDrop 2.25c), mode-specific alpha, alpha-blended segments compounding like GL;
- per-point `q`/`t` variables restarting every frame, beat-switched shapes, negative shape radii, non-finite line endpoints;
- radial rays, radial streaks, shape colour over time, composite detail colour, textured frame copies that add no light.

A shortcut was tested and **rejected**. Running the source maths on a tiny 64×36 grid for about 90 frames would have been cheap, but MilkDrop feedback depends on pixel scale (texel offsets, 1-pixel lines, fixed blur kernels). Against the ruler on 197 presets, its brightness rank correlation was 0.756 (full resolution: 0.924) with a mean error of 0.130 (0.041), and it still took a median 3.9 s per preset. Downscaled simulation is not a source of moods.

Checkpoints switched to **batches of ten**, triaged in milliseconds from stored predictions and the ruler, with deep dives only for big misses.

## 15 October: classifiers, floors and the palette

The calibration grew from regression estimates to the shipped decision path ([From estimates to moods](mood-table.md)):

1. **Rounds r13–r14**: hue shares, coloured share and a No strobe classifier became targets. Estimates shrink toward the middle, so rules on point estimates admitted extremes rarely and flooded the middle options.
2. **Per-option classifiers** for Dark, Bright, Still, Chill, Intense, Warm, Cool and Monochrome; then for the middle options Balanced, Drifting and Normal, first at a 70% precision floor.
3. **No strobe** gated at probability ≥ 0.93 plus a jumps estimate below 0.05: zero strobing presets admitted out of fold.
4. **Pastel** at a 70% floor (owner: *"the floor is fine"*).
5. **The 80% middle floor** (owner: *"go ahead"*): about 2,330 wrong middle labels removed for 4,230 correct ones lost. Pooled out of fold: 79% precision, 41% recall.
6. **The static display palette** pooled every colour source; raising the calibrated hue weight lifted "leading hue in the top two" from 64% to 70%. A palette-concentration target sharpened mostly-one-colour presets. On colour the owner asked to stop focusing on one dominant colour: the analysis should be able to say there is none unless one really dominates, and the full palette of colours used matters more. Main colour became strict (65% predicted top share and 55% of the palette): claims 84% correct. Grey presets got an empty palette.

At the end of the day all 9,606 presets were grouped from static analysis alone, with the preset's identity removed so no measured row could leak in. Ten presets first failed because their per-pixel zoom read EEL memory (`megabuf`); a general fix gave memory inputs an empty buffer, and all 10 exported.

The batch checkpoint rounds (r186–r395) tracked the decisions: under the 80% floor, rounds 15–22 made 214 admissions with 12 wrong (94%), and round 23 made 25 with none wrong.

## 16 October: previews as a teacher

The owner allowed a short trial: use the frame-by-frame prediction (a "preview") as an input. The previews were clearly better than the static estimates (brightness rank correlation 0.90 against 0.80 on about 220 presets), but the owner corrected the idea within the hour: labelling against previews would not improve the static analysis that runs without previews unless the mathematics itself was fixed. Previews became a **teacher**: where the static estimate misses and the preview is right, the closed form is missing a mechanism. Every finished preview was processed immediately, never waiting for a full run.

What the teacher found:

1. **The composite must be averaged over the trail level distribution** (adopted). A nonlinear composite applied to the mean canvas level can map everything to black while trails pass through bright levels. The trail histogram fixed that generally ([feedback maths](feedback-maths.md#trails-pass-through-bright-levels)).
2. **Warps that magnify area** (a lead, not adopted alone): a per-pixel zoom of about 2.5× grows a thin line until it fills the screen, while the spread estimate assumes area-preserving transport. A forward-Jacobian rule fixed the example and overshot on others.
3. **The canvas fixed point with alpha-over mixing** (adopted): the canvas recurrence with proper compositing and the measured warp transfer, averaged over the ruler's window.
4. **The rest is diffuse**: no single static fact explains the remaining misses (lifts at most 2.3×).

Then the owner turned the research into a product: *"actually try and see how we can incorporate this in our app as the new mood presets, maybe in some sort of compressed fashion"*, chose Palette plus Main colour, and approved regenerating the whole table from static analysis, accepting unlabelled presets, because they let people give feedback on the quality of the predictions.

## Open gaps

- **Brightness of accumulating content**: magnifying warps, slow equilibria and textured frame copies still produce the largest brightness errors.
- **Random colour per load**: the analysis knows the distribution, not the draw.
- **Audio-only flashes**: flashes triggered only by real musical transients.
- **Style** has no measured ground truth.
- **Speed**: the static export takes seconds per preset; the goal is under one second.

The research continues on `feat/predictor-static-output-bounds`. When it improves the mathematics, the evidence is re-exported and the table regenerated through a normal reviewed pull request.
