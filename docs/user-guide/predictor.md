# Predicting presets from source

The predictor's current priority is **describing a preset's constructions and audio
controls directly from its `.milk` source**. The aim is machine-readable JSON that
helps another program understand its characteristic look, match user preferences
and eventually create a recognizable adaptation or generate a new effect.

This work is experimental. It does not change the app's
[shipped preset moods](predictive-collections.md), which still use the historical
frame-measurement bundle. **A source-only JSON description that reliably reconstructs
the whole preset's look has not yet been validated.**

!!! note "Implementation checkpoint"
    This page describes the committed source work at `9c8ff632` (2026-10-10) on
    [`feat/predictor-static-output-bounds`](https://github.com/johnneerdael/ProjectM-TV/tree/feat/predictor-static-output-bounds).
    It follows the static mechanism work merged by PR #67 into the experimental
    predictor parent branch. Publishing these docs separately does not merge that
    implementation into `main` or replace the released mood indexes.

## Three different kinds of result

| Path | What it does | What its result means |
|---|---|---|
| Shipped mood collections | Measures frames from the historical controlled native render and stores rankings. | A beta activity ranking for that short input window. |
| Numerical source forecast | Executes source equations and simulates shader/feedback fields under declared audio, time, assets and render settings. | The existing 47-field statistical export. It consumes no native reference frames, but still performs simulation. |
| Static source description | Parses the file, follows contributing equation/shader expressions and recognizes supported mathematical constructions. | Conditional forms, parameters, colour ingredients, coordinate mappings and audio-to-control relationships without executing equations, shaders or display frames. |

The [export reference](predictor-export.md) keeps these contracts separate. The
47 numerical fields have not all become static. Removing retained frame arrays
from a forecast does not remove its simulation cost.

## Approximate grouping for the whole pack

An approximate grouping layer reads the source description and gives every
preset an editable activity estimate from 1 to 100, with Chill, Normal and
Intense candidates. Each estimate lists its drivers: measured source facts (for
example a zoom of 2–7% per step driven by bass, a ripple travelling at 64 px/s,
a brightness cycle rate) and assumed priors for mechanisms whose strength the
analysis cannot yet bound. When assumed or unresolved drivers dominate, the
preset gets no group, only possible groups, so a preset is never placed in
Chill just because evidence is missing. These groups are assumption-based
preferences, not calibrated moods; all weights can be edited and the whole pack
can be rescored without re-running the analysis. The strict source eligibility
described below remains separate.

## Source behaviour work in progress

The experimental branch now joins conditional flashing, movement-speed, prominence
and hue-candidate information into a separate `static_behaviour` report. It also
exports an initial source-potential activity index. This is progress toward automatic
Chill / Normal / Intense grouping; it is not yet a calibrated mood or visual-accuracy
claim. Known partial evidence and automatic eligibility are exported separately.
Read the [source behaviour contract](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-static-output-bounds/tools/milk-analyzer/STATIC_BEHAVIOUR.md).

Response bounds can describe changes without pretending to know the input's
history. For example, a square-root colour operation has a bounded response to
a declared texture-value change even though its derivative is infinite at zero.
The JSON keeps that two-state response separate from per-second motion or flashing.
Legacy gamma and echo use the patched engine's actual redraw and blending rules.
These conditional bounds help quantify possible effect strength; they do not
by themselves establish a preset's mood.

Callers can also declare maximum changes per second for exact scalar input names.
This lets the predictor combine time, bass, mids and other supported input responses
into conditional shape movement bounds. An amplitude range alone does not supply
a change rate, and those declared rates are not measurements of a song or its BPM.

Private shape-state proofs now report where supported walkers can remain across
their sequential instances. Random colour recipes distinguish separately drawn
RGB values from a copied grayscale value and preserve live borders. These facts
make the source description more informative; they do not yet close feedback,
visible speed or whole-preset mood uncertainty.

The experimental branch now provides a standard-library SDK and local LLM skill
for reading these facts into recognizable effect descriptions. A source spiral
can have rapidly moving parameter points but much slower curve drift, so the
description preserves both. Approximate LLM mood estimates stay separate from the
strict physical model's eligibility result.
Uniform final-color cycles have integrated calm/moderate/intense source controls;
feedback presets still retain their unresolved movement and flashing contributions.

Recent general additions (2026-10-12): custom waves whose per-point colour
and position formulas depend only on the sample index, time and audio are now
evaluated over their authored points. This turns hashed "random-looking"
formulas into colour shares, a point cloud and a point speed. A negative
feedback stretch and a mirrored echo are reported as mirror symmetry, with a
fold count. Inner and outer borders and the darken-centre spot are treated as
per-frame fades of the picture. A screen-wide inner border, for example, can
make trails fade in about a second even when the decay is 0.999.

The prediction illustrator now follows the engine's own rendering rules. They
were checked one at a time against the pinned engine with small probe presets:
motion and rotation, the two procedural-warp formulas, the 48×32 motion mesh,
the engine blur filter and its one-frame delay, wrap modes that depend on a
per-frame value, wave and shape placement, and noise texture sizes. Custom waves
whose points depend on the wave's own per-frame counters (for example a star
field that advances with the bass) are now stepped frame by frame. On the r8
checkpoint (`River of Petals`), the illustrated picture matches the emulator
capture: the same bright, mirrored green/yellow/red pattern, with brightness
0.608 vs 0.602. On r7 (`The Waving Shaker`) the brightness is 0.342 vs 0.314, and
on r9 (`Our Destiny`) the zooming ring tunnel and central star appear, slightly
less green than the engine.
This describes how presets move and blend; it is not a renderer, and fine
detail in chaotic feedback still differs.

## What the static JSON can describe

The static producer is `effect_family_export.py`. Its `analysis.visual_description`
adds structured appearance and control traits alongside the effect-family record:

| Source-derived evidence | What a consumer can learn | What remains conditional |
|---|---|---|
| Component IDs and family codes | Wave/point/shape primitives, polar-depth layouts, mirror constructions, recognized fractal recurrences, feedback transforms and repeating radial glow fields. | Which constructions dominate the displayed picture. Points do not establish independent particles. |
| Shape geometry and material | Nominal size, polygon area, centre-to-edge vertex colour, borders, blending and texture requests. | Clipping, overlap, opacity, actual image binding and later shading. |
| Texture-coordinate mappings | Supported scaling, reflection, shear, translation, polar angle/depth layouts and image-driven displacement coefficients. | Actual sampled image contents, visible copy count and screen motion. |
| Colour expressions and mixtures | Supported generated colour formulas, signed sample-channel weights, tone operations and native colour inputs. | The complete final palette after masks, texture history, storage and composition. |
| Time and audio control routes | Which source control responds to bass, mids or highs; supported gains, switches, thresholds and time curves. | Perceived response strength, flash frequency and motion intensity for arbitrary music. |
| Logical feedback/display flow | Drawing order, contributing texture reads and supported nominal colour transfer. | Full recurrence, actual trail persistence and context-dependent native detail. |

For example, a radius expression `rad=.2+.05*bass` can explain that the shape's
radius changes with bass, including a source gain of `.05` radius units per bass
unit. That gain is not the percentage of the screen that moves. A nominal colour
oscillator can supply its period without establishing that it creates a visible
flash.

Recognition traces live outputs and consumed vector lanes, not names or a list of
functions. Unsupported state, branches, domains, resources and excessive symbolic
complexity remain explicit unknowns. A detected fractal plus varied generated
colour can be a psychedelic candidate; neither label proves a particular mood.

Read the [machine contract and numeric dictionaries](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-static-output-bounds/tools/milk-analyzer/SOURCE_APPEARANCE.md)
and the [mechanism reference](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-static-output-bounds/tools/milk-analyzer/EFFECT_FAMILIES.md)
for exact fields, units, conditions and source evidence.

## Current evidence

The committed checkpoint's prepared analyzer suite passed **2,301 tests and 92
subtests**. These are language, numerical and descriptor controls, not 2,301
presets with verified visual matches. The fixed 100-preset source sample provides
coverage evidence for individual ingredients:

| Ingredient supported in that sample | Presets | Evidence |
|---|---:|---|
| Nonidentity constant-affine sample maps | 61 | [Sampling geometry](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-static-output-bounds/docs/superpowers/evidence/source-sampling-geometry-2026-10-09/README.md) |
| Direct sampled-colour coordinate response | 23 | [Blur bindings and 64 response maps](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-static-output-bounds/docs/superpowers/evidence/source-blur-bindings-2026-10-09/README.md) |
| Raw RGB mixture models | 35 | [36 supported shader stages](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-static-output-bounds/docs/superpowers/evidence/source-colour-mix-2026-10-09/README.md) |
| Consumed native time formulas | 15 | [Native clock inputs](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-static-output-bounds/docs/superpowers/evidence/source-native-time-2026-10-09/README.md) |
| Consumed native hue recipes | 14 | [Four-corner colour ingredient](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-static-output-bounds/docs/superpowers/evidence/source-composite-hue-2026-10-10/README.md) |
| Mixed polar maps | 2 | [Four angle/depth maps](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-static-output-bounds/docs/superpowers/evidence/source-polar-mixed-2026-10-09/README.md) |
| Repeating radial glow generators | 2 | [Four distinct generators](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-static-output-bounds/docs/superpowers/evidence/source-radial-grid-2026-10-09/README.md) |

These groups overlap. The counts are neither a whole-pack success rate nor an
appearance-accuracy percentage; even a computed record can have major unknowns.
Each linked checkpoint retains its original source/model hashes and scope.

The declared reference is the **full published ProjectM TV core 2.3.33 AAR**,
verified byte-equivalent to 2.3.32 and the earlier qualified source31 target.
Source CPU parser/model identities remain separate from AAR/JNI runtime identities.
The runtime qualification contains three small 30-frame, 128×72 JNI controls;
it does not certify all authored presets or 4K appearance. The
[published profile](https://github.com/johnneerdael/ProjectM-TV/blob/feat/predictor-static-output-bounds/tools/milk-analyzer/profiles/published-core-v2.3.33.json)
records hashes and the exact scope. This is the latest locally verified profile
for this documentation checkpoint, not a claim that no newer release exists.

## Open work and pending validation

The following are open questions or unfinished work, not proven ceilings on what
static analysis can ultimately describe:

- Whole-preset recognizable reconstruction and a calibrated appearance score.
- Final element dominance, visible coverage and complete colour palette.
- Perceived movement intensity, actual flash events and whole-feedback evolution.
- Actual random phases, selected images and bindings when no matching runtime inputs are supplied.
- Reliable automatic mood, musical-genre or audience assignments.

The current export keeps `appearance_match_accuracy` null, activity values unknown and
Chill eligibility null when the required support is absent. An empty mechanism
list does not prove that the picture is plain; an unknown flash value does not
mean no flashing.

## Current implementation constraints

The implementation deliberately supports a bounded vocabulary. For example,
constant-affine sample maps can be described while unsupported dynamic scales
remain unknown. Direct sample-response analysis has 64-sample/4,096-node budgets;
exported control programs have a 256-node budget. These are extendable
implementation choices, not theoretical limits on predicting presets.

For an exact frame, selected images, random phases, initial feedback, audio and
clock values are additional inputs. Their absence does not rule out a useful
approximate baseline description; it prevents claiming that exact instance
without declaring those inputs.

## From source traits to preferences

The intended next consumer separates the preset's evidence from the viewer's
preferences. It could favor supported smooth control curves, warm colour
ingredients or strong bass-linked geometry, and penalize supported abrupt
opacity changes. Preference weights and audience assumptions should be editable.

The shipped overlapping activity ranges are Chill 1–30, Normal 25–75 and Intense
70–100. They are rank bands, not accuracy percentages. Existing experimental
preference formulas are assumptions; the new static export does not produce a
calibrated replacement score. A family name alone cannot justify a Chill
recommendation. Age or genre can supply a user-editable default preference,
not a claim about every listener in that group.

Once sufficient traits are supported, changing a preference profile should
rescore saved evidence without repeating expensive simulation. Where support is
missing, the program must retain uncertainty rather than invent a calm or intense
result.

## Adaptation and generation

A Rust/wgpu consumer can already use supported constructions and parameters as
inputs to an original effect template. It must record its choices for unknown
colours, resources and behaviors separately. The JSON is not a complete scene
graph or shader program, and no native-4K performance result follows from it.

The longer-term goal is a description detailed enough to generate a recognizable
approximation of a particular preset, including which elements move or change
colour with each audio band. Another route is generating new programs from a
restricted vocabulary of understood forms, materials, motion and audio controls,
then analyzing them against a user's brief. Complete reconstruction and a
production generator remain future validation work.

## What historical accuracy scores mean

Earlier 95, 97.5 or 100 scores graded **frozen predictions against native renders
under a particular behavioral rubric and input protocol**. They were not the
accuracy of this newer static JSON export, and they cannot be transferred to a
new library version or renderer without matching evidence.

The historical 2.3.11 audit had 85 of 100 presets at or above its 95-point gate,
with a 98.8 mean among the 88 completed cases. Those are different quantities:
pass rate answers how many met the gate, while average agreement measures the
scored predictions' closeness. The 12 incomplete cases stay incomplete in that
historical record even after later fixes. See
[how “97% accurate” was measured](authoring/testing.md#how-are-you-measuring-97-accurate)
for the rubric, tolerances, denominators and limits. No current static appearance
percentage is established by that historical audit.
