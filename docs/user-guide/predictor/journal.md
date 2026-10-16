# Research journal

The static Mood table came out of twelve days of continuous research, from 5 to 16 October 2026. The work produced about 600 commits on the research branch, compared nearly 400 randomly drawn checkpoint presets with real renders, and reran a whole-corpus analysis of all 9,606 bundled presets many times as the mathematics improved. This page records how it went, including the dead ends.

| Date | Commits | Focus |
|---|---|---|
| 5-8 Oct | ~140 | A numerical forecaster: simulate the preset, compare with the engine |
| 9-10 Oct | ~125 | The turn to static analysis: describe mechanisms, bound values |
| 11 Oct | ~25 | Understanding checkpoints begin: predict, freeze, render, compare |
| 12 Oct | ~50 | The engine ruler; the first Mood panel ships (measured); calibration starts |
| 13 Oct | ~70 | "Renders validate, never decide"; knowledge pack; calibration rounds |
| 14 Oct | ~130 | Engine-exact semantics; tiny-grid simulation rejected; batch checkpoints |
| 15 Oct | ~50 | Per-option classifiers, precision floors, the static palette, all 9,606 grouped |
| 16 Oct | ~10 | Previews as a teacher; the static Mood table |

## 5–8 October: a numerical forecaster

The first approach re-implemented enough of the engine in Python to simulate a preset (equations, shaders, feedback) under declared audio, then compared the result with the published core library rendering the same preset. Most of the effort went into matching the engine exactly: custom-wave point counts, PCM resampling, quad-strip order after the Y flip, triangle rasterisation, blur precision, half-float texture filtering, the JNI audio quantisation, noise textures, and the semantics of each published core release from 2.3.5 through 2.3.25.

Simulations could reach a frozen 95-point agreement gate on chosen presets, but they did not help anyone understand a preset. A simulation that matches the engine is a slower engine: it shows what the picture is without explaining why, and it costs seconds to minutes per preset. The owner's verdict set the direction from then on. The project had explicitly not wanted to rely on simulations, the gaps had to be solved mathematically, and a simulation cannot teach anything the code does not already say.

## 9–10 October: the turn to static analysis

Pull request #67 merged the first static effect families: named constructions recognised in the source, each with parameters and evidence. Over the next two days static descriptions were added for almost every part of a preset, each stated as a bounded fact instead of a simulated value:

- texture sampling geometry, native blur decoding inputs, composite hue generation;
- shape fill contributions, paired shape trajectories, compound movement bounds;
- feedback scaling envelopes and nominal warp colour transfer;
- nonlinear colour lanes, image-driven lookup offsets, tiled and mirrored coordinate maps;
- direct shader colour response to audio bands, recurrent audio ancestry, `q`-variable proofs.

## 11 October: understanding checkpoints

The checkpoint loop began here. A checkpoint draws a preset at random with a pre-registered seed (no rerolls), describes it from the static facts, draws a [prediction image](prediction-images.md), freezes and hashes everything, then renders the preset in an emulator and compares. The first checkpoints set the pattern for the rest of the research: each miss pointed to a missing piece of mathematics, and that piece was then added for every preset.

- Zylot - Spiral: the prediction lacked the filled gaps and concentric rings. The fix added 8-bit decay orbits and floors, persistence sweeps, bilinear spread and radius-locked colour. On an unseen 640×360 check the radial colour profile correlated 0.95 to 0.99.
- Rovastar and Krash - Seas Of Tron: the prediction missed the banding, the travelling ripples and a row of motion vectors. The fix added per-pixel mesh-field structure, motion vectors, echo and gamma, and closed-form wave colour. The next version predicted the pink lines, ripples and vector row before capture.
- Dragonfly Wings: the prediction was black where the scene was dark red and flowing. Scalar palette maps and flat-field steady states were added.
- martin - time machine: the prediction showed an overexposed glow with lobes where the render had one round sun. The fixes were float32 equation time (beat refractory ties at exactly three frames) and the half-pixel offsets of thick wave passes. The corrected prediction was identical to the render, with brightness 0.659 against 0.660.
- 404: the prediction was black where the render showed four mirrored articulated arms. The fix added point positions over per-frame state, engine `rad`/`ang` per stage and sequential alpha compositing. Brightness came out at 0.108 against 0.108.

## 12 October: the engine ruler and the first Mood panel

To score anything at scale, the pinned, patched engine rendered every bundled preset once (480×270, 300 frames, synthetic audio). These measurements are the engine ruler. They also produced the first Mood panel in the app, released on `main`, so that first Mood table was measured, not predicted. The owner made clear this was temporary: moods based on rendered measurements had to give way to moods from the source.

On the same day the first calibration linked static facts to ruler measurements, out of fold, with feedback equilibrium (`a·c/(1−g)` per channel) among its features. A ceiling was measured as well. Two real renders of the same 84 presets (emulator and ruler, with different audio) agree on Energy 86% of the time, on Brightness 81%, Movement 93% and Comfort 92%, and no prediction can be expected to beat those figures.

## 13 October: renders validate, never decide

This day set the rule that governs the shipped table. Per-preset renders may be used only to validate and correct a prediction. They never change a prediction directly; they can only lead to better mathematics behind it. Every mathematical change also has to benefit the entire corpus without causing regressions.

From then on, each mathematical change had to pass a paired measure on 200 presets: the fix had to help without regressing others beyond known noise. The same day added per-frame random sites, mesh terms with frame state, video echo in the legacy composite, 3-D noise volumes, tiling, legacy hue tint, neighbourhood blur and gradient relief mechanisms. It also added the platform-neutral knowledge pack, with its reader contract and golden vectors ([SDK](sdk.md)).

## 14 October: engine-exact semantics, and a rejected shortcut

The busiest day, with about 130 commits, went on matching the engine's exact rules. A checkpoint miss exposed each one, and each was fixed generally:

- projectm-eval's cold-start random stream, statement-order random draws, lazy `if`/`&&`/`||`, inlined EEL loops;
- noise textures that follow MilkDrop's procedural noise exactly; random textures sampled as the expected image;
- built-in waves capped at width/3 samples (MilkDrop 2.25c), mode-specific alpha, alpha-blended segments compounding like GL;
- per-point `q`/`t` variables restarting every frame, beat-switched shapes, negative shape radii, non-finite line endpoints;
- radial rays, radial streaks, shape colour over time, composite detail colour, textured frame copies that add no light.

A shortcut was tested and rejected. Running the source maths on a tiny 64×36 grid for about 90 frames would have been cheap, but MilkDrop feedback depends on pixel scale (texel offsets, 1-pixel lines, fixed blur kernels). Against the ruler on 197 presets, the small grid's brightness rank correlation was 0.756 (0.924 at full resolution) and its mean error 0.130 (0.041 at full resolution). It still took a median 3.9 s per preset, so downscaled simulation is not a source of moods.

Checkpoints then switched to batches of ten, triaged in milliseconds from stored predictions and the ruler, with deep dives only for big misses.

## 15 October: classifiers, floors and the palette

The calibration grew from regression estimates into the shipped decision path ([From estimates to moods](mood-table.md)):

1. In rounds r13 and r14, hue shares, coloured share and a No strobe classifier became targets. Estimates shrink toward the middle, so rules applied to point estimates rarely admitted extremes and flooded the middle options.
2. Per-option classifiers followed for Dark, Bright, Still, Chill, Intense, Warm, Cool and Monochrome, then for the middle options Balanced, Drifting and Normal, at first with a 70% precision floor.
3. No strobe was gated at probability ≥ 0.93 plus a jumps estimate below 0.05, which admitted zero strobing presets out of fold.
4. Pastel got a 70% floor (owner: *"the floor is fine"*).
5. The middle options moved to an 80% floor (owner: *"go ahead"*). This removed about 2,330 wrong middle labels at the cost of 4,230 correct ones. Pooled out of fold, precision was 79% and recall 41%.
6. The static display palette pooled every colour source. Raising the calibrated hue weight lifted "leading hue in the top two" from 64% to 70%, and a palette-concentration target sharpened mostly-one-colour presets. On colour, the owner asked to stop focusing on one dominant colour: the analysis should be able to say there is none unless one really dominates, and the full palette of colours used matters more. Main colour became strict (65% predicted top share and 55% of the palette), and its claims are 84% correct. Grey presets got an empty palette.

By the end of the day all 9,606 presets had been grouped from static analysis alone, with each preset's identity removed so that no measured row could leak in. Ten presets failed at first because their per-pixel zoom read EEL memory (`megabuf`). A general fix gave memory inputs an empty buffer, and all 10 exported.

The batch checkpoint rounds (r186 to r395) tracked the decisions. Under the 80% floor, rounds 15 to 22 made 214 admissions with 12 wrong (94%), and round 23 made 25 with none wrong.

## 16 October: previews as a teacher

The owner allowed a short trial of the frame-by-frame prediction (a "preview") as an input. Previews were clearly better than the static estimates, with a brightness rank correlation of 0.90 against 0.80 on about 220 presets. Within the hour the owner corrected the idea: labelling against previews would not improve the static analysis, which runs without previews, unless the mathematics itself was fixed. Previews were used as a teacher instead. Where the static estimate misses and the preview is right, the closed form is missing a mechanism. Each preview was processed as soon as it finished, without waiting for a full run.

The teacher found four things:

1. The composite must be averaged over the trail level distribution (adopted). Applying a nonlinear composite to the mean canvas level can map everything to black while trails pass through bright levels. The trail histogram fixed this generally ([feedback maths](feedback-maths.md#trails-pass-through-bright-levels)).
2. Warps that magnify area (a lead, not adopted on its own). A per-pixel zoom of about 2.5× grows a thin line until it fills the screen, while the spread estimate assumes area-preserving transport. A forward-Jacobian rule fixed the example and overshot on others.
3. The canvas fixed point with alpha-over mixing (adopted): the canvas recurrence with proper compositing and the measured warp transfer, averaged over the ruler's window.
4. The remaining misses are diffuse. No single static fact explains them (lifts at most 2.3×).

The owner then asked for the results in the app: *"actually try and see how we can incorporate this in our app as the new mood presets, maybe in some sort of compressed fashion"*. The owner chose Palette plus Main colour and approved regenerating the whole table from static analysis. Unlabelled presets were accepted because they let people give feedback on the quality of the predictions.

## Open gaps

- Magnifying warps, slow equilibria and textured frame copies (accumulating content) still produce the largest brightness errors.
- When colour is drawn at random per load, the analysis knows the distribution but not the draw.
- Audio-only flashes, triggered only by real musical transients, remain open.
- Style has no measured ground truth.
- The static export takes seconds per preset; the goal is under one second.

The research continues on `feat/predictor-static-output-bounds`. When it improves the mathematics, the evidence is re-exported and the table regenerated through a normal reviewed pull request.
