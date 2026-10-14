# No strobe: static safety gap (2026-10-15)

Rule (Comfort facet): No strobe means fewer than 1 global brightness jump per 10 s, where a jump is a
frame-to-frame change of at least 0.08 in mean grey. Labels come from the engine ruler for all 9,606 presets.

**Static estimate as a gate.** The calibrated jumps estimate is out of fold, so every prediction is static.

| Model | Estimate threshold | Admitted | False admits (≥1 jump) | Strobing admitted (≥10 jumps) |
|---|---|---|---|---|
| r11 (old) | < 1 | 4,035 | 529 (13.1%) | 117 |
| r13 (shipped 2026-10-15) | < 1 | 4,027 | 526 (13.1%) | 119 |
| r11 | < 0.25 | 1,818 | 80 (4.4%) | 19 |
| r13 | < 0.25 | 1,848 | 76 (4.1%) | 19 |

The better jump ranking (0.765 → 0.771) does not close the safety gap. `strobe-false-admits.json` lists the 19
strobing presets admitted at the strict threshold.

**Base rates.** 2,981 presets (31%) flicker at 10 or more jumps per 10 s. Legacy-composite presets do so 10% of the
time, shader-composite presets about 36%.

**Static constructs: rate among flickering vs calm presets (lift).** Over all presets, `invert`/`solarize`
per frame scores 3.0 but is rare (2% vs 1%). `frame%` scores 1.8, band thresholds 1.7, `rand(` 1.7 and
border colours per frame 1.2. Inside composite shaders, bands read directly score 5–7 but cover only 5% of
flickering presets; q-variables from audio 1.6, noise textures 1.5. Everything else is close to 1.

**Mechanisms found.**
- Huge video-echo zoom: The Logic Bomb, `fVideoEchoZoom=67`, alpha 0.5. Half the display is a 67× magnified
  patch, so it swings bright or dark as content moves through it. With zoom ≥ 8 and alpha ≥ 0.3, 4 of 7 presets
  flicker hard (median 25 jumps). The rule is exact but covers few presets.
- Frame-counter state machines: Stahlregen Crossroads, a 6-frame colour cycle. Audio-threshold colour switches:
  MegalomaGreg Ambitions. The r13 model now ranks both correctly.

**Conclusion.** Most strobing is audio-driven content pushed through feedback, not a single construct. The static
quantity needed is the audio-to-brightness gain chain: displayed brightness change per frame-to-frame band change,
through bindings, element areas and composite gain. Next step: derive it from the recipe's audio bindings and
transfers, then validate the gate against the ruler, aiming for zero strobing admitted.

## Tried and reverted: direct audio-route sensitivity

For each recipe audio route, its closed form was evaluated while the band moved over its reference 10–90%
range, giving the expected per-frame jump for the reference frame-to-frame band change. On the 200 set only
518 of 3,896 routes (13%) could be evaluated: most go through per-frame state (q-variables, accumulators,
beat detectors). The proxy carries no signal: Spearman 0.025 against ruler jumps. So the audio-to-brightness
chain needs the per-frame state recurrence (beat detectors and counters as static maps over band statistics),
not direct band formulas.
