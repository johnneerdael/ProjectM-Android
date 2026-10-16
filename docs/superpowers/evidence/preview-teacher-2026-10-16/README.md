# Previews as a teacher for the static maths (2026-10-16, owner trial)

The owner allowed a short deterministic preview (the 150-frame prediction illustration the checkpoints already render)
on a trial basis, then corrected its role: "labels against a preview does not help us improve our static analysis our
global runs without previews if we do not fix out math". Previews are not a label source. Where the static estimate
misses but the preview, our own source maths run frame by frame, is right, the static closed form is missing
something. That mechanism is fixed generally in the static analysis and gated corpus-wide.

## Value and cost

On 216–219 checkpoint presets, preview window statistics against the engine ruler (Spearman): luminance 0.897,
saturation 0.913, coloured share 0.867, frame difference 0.868. The calibrated static estimates score 0.797 / 0.825
/ 0.823 / 0.798. Shorter previews lose the gain (frames 30–59: 0.813; frames 60–119: 0.891; frames 60–149: 0.896).
Cost at full resolution under heavy shared load: median 91 s, max 292 s per preset (150 frames; 60 frames: median
42 s). The 64x36 downscale was rejected earlier.

## Never wait for the corpus

`run_previews.py` runs the corpus in a fixed random order (resumable), so any partial result is a random sample.
`gap_ledger.py` processes each finished preview at once: static OOF vs preview vs ruler, plus that preset's
mechanism facts (warp magnification, equilibrium local/spread, detail gain and, from now on, the preview canvas level
before the composite). Snapshot at 1,222 previews: 124 static underestimates and 151 static overestimates the preview
gets right, against 408 where both agree.

## Math corrections found

1. **Composite over the canvas level distribution (adopted).** For a nonlinear composite, the display is the mean of
   T(level) over the canvas, not T(mean level). 14.milk: equilibrium canvas 0.14–0.20, but the composite
   `1 - (1/blur2 - main*blur1 - 1.35*blur2)^2` maps every flat level near that to black, while feedback trails pass
   through the bright band (engine 0.51). `feedback_equilibrium._trail_histogram` derives the distribution: paint of
   area a per frame at level L leaves levels bg + (L - bg) g^k, each covering a, until the screen is covered. The new
   output `display_trail_luma` is the descriptor column `equilibrium:display_trail_luma`. Ledger set (120 presets):
   Spearman with the ruler 0.252 / 0.246 (local / spread) → 0.342. Random 1,000 presets: MAE 0.234 / 0.294 → 0.226,
   Spearman 0.364 / 0.308 → 0.323. Calibration A/B on those 1,000 (5-fold, 3 seeds): luminance OOF 0.527 → 0.532,
   better under every seed.
2. **Warp area magnification (not adopted alone).** A per-pixel zoom of about 2.5x (bmelgren – Getter Sun tweek 3)
   grows a thin wave line until it fills the screen; the spread bound assumes area-preserving transport. The forward
   Jacobian rule p·Σ g^k min(1, a m^k) fixes that preset, but overshoots on other magnifying presets, and singular maps
   (everything sampling one point) break it. Magnification is over-represented among underestimates (12% vs 5%), so it
   stays a lead.
3. **Diffuse remainder.** A fact lift scan between gap classes and agreeing presets (`gap_lift.py`, 1,222 previews)
   finds at most 2.3x lifts. The misses do not share one static fact. The preview canvas level added to the frame
   statistics now splits each miss into canvas (equilibrium) versus composite.
