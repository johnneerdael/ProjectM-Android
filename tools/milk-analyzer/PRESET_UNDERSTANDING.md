# Preset understanding from static JSON

`preset_understanding.py` is a standard-library consumer of existing
`effect_family_export.py` records. It describes approximate source constructions,
colour ingredients, nominal motion/brightness facts and audio control routes for
an LLM or SDK. It neither generates effects nor requires exact image recreation.
The source-analysis producers, models and renderer are unchanged.

Load the local `skills/understand-preset/SKILL.md` for LLM interpretation. The
existing `SOURCE_APPEARANCE.md` explains field semantics in detail.

## Python and CLI

Add `tools/milk-analyzer` to the module search path, then call:

```python
import json
from preset_understanding import summarize_preset

with open("preset.json", encoding="utf-8") as handle:
    record = json.load(handle)
summary = summarize_preset(record)
print(summary["description"])
```

From the repository root:

```bash
python3 tools/milk-analyzer/preset_understanding.py INPUT_JSON --output SUMMARY_JSON
```

Omit `--output` to emit JSON to stdout. Return code0 means successful consumption;
return code2 prints an explicit error to stderr. Output cannot overwrite the input. The function raises `ValueError`
for unsupported/failed records or malformed recognized containers. Input must be
one full computed schema1 `preset-effect-families` record, not the exporter cache
wrapper or a run manifest. A schema1 appearance `status:unknown` variant is
accepted with missing facts and explicit unresolved questions. Raw equation or
shader strings are data; the consumer never interprets or executes them.

The consumer is bounded to32MiB of encoded JSON,500,000 visited JSON values and
128 nested levels. Files are read with the size limit before JSON decoding.
Nonfinite numbers and non-JSON values are rejected. Limits produce explicit
errors instead of silently dropping facts. No dependencies, native parser,
network, model import, shader compilation or device are required.

## Output contract

Schema1, policy `preset-understanding-v1`:

| Field | Interpretation |
|---|---|
| `preset` | Original exported source identity |
| `input_record_sha256` | Consumer's SHA256 of the full sorted, compact UTF-8 JSON; content identity, not a signature or producer hash verification |
| `components` | Source element IDs/paths and code-derived family labels; visible contribution remains conditional |
| `facts` | Grouped evidence: identity, context, construction, colour, geometry, shape state, motion, flashing, audio, feedback, mood and uncertainty |
| `description` | Deterministic concise approximate description derived from the retained facts |
| `mood.provisional_source_potential_bands` | Original classification `predicted_bands`; no additional scoring |
| `mood.eligible_bands` | Original classification `eligible_bands`; empty stays empty |
| `mood.intensity` | Original index/interval, preserving nulls and its source-potential scope |
| `unresolved_questions` | Visible dominance, motion/flashing and remaining automatic classification questions with source evidence paths |
| `limitations` | Interpretation boundaries |

Each facts entry contains `path`, `value` and `interpretation`. `path` is an
RFC6901 JSON pointer into the full original record; `value` is copied unchanged,
including nulls, intervals, conditions and source programs. Resolve array
positions numerically and unescape `~1`/`~0` in object keys. Selected structures
can contain substantial expression evidence; an LLM can read relevant groups on
demand instead of putting the entire summary in its context.

Facts preserve source identities and provenance as supplied. This consumer does
not validate source/parser/model digests against files or claim cryptographic
trust. `uses_rendered_images`, `uses_shader_execution` and
`uses_equation_execution` are false for this consumer;
`actual_visible_appearance_verified` and `mood.actual_visible_mood_verified`
remain false even when the producer admits conditional source eligibility.

## Interpretation and mood grouping

The ten family labels follow `SOURCE_APPEARANCE.md`. Code5 admits a tunnel
candidate,6 a symmetry candidate and7 a recognized fractal construction.
Points and repeating radial glows do not establish independent particles.
Generic radial zoom, feedback, preset names or arbitrary shader text cannot
supply these labels.

Colours come from static-behaviour component source palettes and final candidate
palettes, keeping their transfer/alpha/texture conditions. Geometry and state
intervals remain nominal and unclipped. Full-range dynamic custom-wave RGB remains a possible ingredient even when
its interval box admits every hue; no reached multicolour palette follows.
Sampling-origin displacement relations with `is_trajectory_speed:false`, backward
sampling and isolated affine-component diagnostics retain their diagnostic scopes
in the prose, rather than acquiring whole-map or trajectory speed labels.
Motion and brightness quantities retain
physical units and their exact/partial/upper-bound qualifiers. A high nominal
cycle rate or speed ceiling does not establish visible flashing or typical
movement; unknowns do not imply calmness. Audio paths identify affected controls
and conditional gains, not BPM or guaranteed visible response strength.

An LLM may use these ingredients for approximate explanations and explicitly
labelled aesthetic or mood hypotheses. The strict `mood.eligible_bands` contract retains the producer's eligibility
result. Separate automatic LLM estimated mood groups are permitted from source
understanding under explicit preferences, evidence and uncertainty; incomplete
pixel certification does not veto useful approximate interpretation. Provisional
source potential, conditional strict eligibility and LLM estimated groups remain
separate fields. A companion human/LLM interpretation may use a structure such as
`{"scope":"approximate source interpretation", "likely_look":"...",
"estimated_mood_groups":[{"group":"...", "preferences":{}, "uncertainty":["..."]}], "evidence_paths":["/..."], "unknowns":["..."]}`.
Keep it outside `mood.eligible_bands`; no calibrated confidence is established.
For example, line waves plus feedback can suggest layered flowing line activity
while later composition leaves the dominant pattern open. Empty mathematical
eligibility does not prevent this useful approximate explanation.

Applying the consumer across9,606 exports does not establish
whole-corpus appearance accuracy or assign every preset a verified mood.

## Projection and feedback operators

`static_behaviour.curve_projection.components` supplies declared-viewport geometry
facts: nominal radius in pixels, source-to-screen scales, coordinate boxes,
possible clipping and separate point/locus speed bounds. The native vertex Y
conversion and orthographic Y reversal are both included. A box can include
unreached points; clipping possibility does not prove visible clipped content.
Negative line-smoothing weights can overshoot the original coordinate box.
Growing radii require a finite declared time domain. Raster coverage, line widths,
displayed motion and whole-preset mood remain separate from these operators.

`facts.feedback` retains the original history-colour envelope and native sampling
recipes. A colour difference-gain ceiling or ideal perturbation half-life counts
warp evaluations, not observed trails or screen persistence. The additive
`static_behaviour.affine_radial_feedback` model accepts the pinned source34 engine
and selected default warp with central, neutral transform controls. For
`zoom(r)=a+b*r`, it exports the backward sampler `r_source=r_output/(a+b*r_output)`
and inverse fixed-feature map `r_output=a*r_source/(1-b*r_source)`, with domain,
crossover and direction records. Inward sampling can move retained features
outward; these directions must not be conflated. Custom/unknown warp paths,
unmatched engines, singular domains and unsupported effects remain unresolved.
These are nominal one-step operators before texel offsets, mesh interpolation,
storage, drawings and final composition, not executed feedback histories.

`static_behaviour.curve_feedback_relation.components` links a supported central
affine polar curve to that sampler. The exporter declares source-sample reference
0.5 and diagnostic step counts1,4,16. It supplies same-angle inter-turn pitch,
fresh radial motion and retained/fresh separation. The reference is not typical,
observed or certified as a native vertex. Growing radii need a declared finite
time domain; current, future and adjacent positive-radius branches must remain valid.

Optional n-step records use `F^n(r)=a^n*r/(1-b*r*S_n)`, with
`S_n=(a^n-1)/(a-1)` or `S_n=n` when `a=1`. No frame sequence or feedback image is
evaluated. Pole, radius, time/branch and rational-size guards can reject an optional
record while preserving local evidence. Clipping flags include retained, fresh and
selected adjacent branches. Gain^n is an independent colour-operator difference
bound, not achieved stroke brightness. Separation versus turn pitch can inform
a conditional layering hypothesis; visible overlap, thickness and density remain
unverified.

`static_behaviour.material_marker_motion.components` (policy
`source-material-marker-motion-v1`) separates raw colour-label transport from
geometric drift on the same affine polar recipe. For labels `C0+Cs*s+Ct*t`,
a common branch exists only when every channel with `Cs!=0` gives the same
`ds/dt=-Ct/Cs` and every `Cs=0` channel (including alpha) has `Ct=0`. Then
`R'=Rt+Rs*ds/dt` and `Phi'=Pt+Ps*ds/dt`, with speed ceiling
`sqrt(R'^2+(max|R|*Phi')^2)` in source units and an optional pixel ceiling only
for a matching explicit projection. Time-growing radii need a declared time
domain. The geometric locus record keeps its fixed-angle normal-drift ceiling.
Uniform labels are temporal modulation or static material, not quietness;
incompatible labels stay unresolved. Native modulo/clamps, interpolation,
sampling, feedback and composition can hide labels; no visible speed, unique
particle or mood credit follows. A producer failure is isolated in
`producer_failures` without erasing projection evidence.

`static_behaviour.feedback_persistence` (policy
`source-unorm8-decay-persistence-v2`) applies only to the fixed main-decay warp
model with zero offset and image-independent sampling. The pinned source34 warp
writes `min(decay,1)*texture(main)` at mediump into an RGBA8 main image, so a
locally uniform stored level `k` becomes the round-to-nearest conversion of the
shader product. The orbit from full white is computed under three arithmetic
profiles (exact real, float32, fp16 mediump) because levels near a rounding tie
can differ: for `d=0.95` the floor is 9 under exact real arithmetic and 10 under
float32. Results are reported per profile and as intervals
(`floor_level_interval`, `steps_to_half_interval`, `steps_to_floor_interval`,
`largest_stuck_level_interval`); `level_orbit_from_full` is the float32
reference. For `d=0.92` every profile halves in 9 steps and stalls at 6/255
after 43. Exact ties are ambiguous because GLES leaves tie direction open.
GLES only prefers round-to-nearest; truncating conversion would remove the
floor. Edges, filtering, drawing, blending and display are not modelled.

The half-level and floor horizons (every distinct profile value, at most 128)
are added to the curve/feedback step counts. `persistence_layer_sweep` compares
the closed-form retained/fresh separation at each horizon with the turn pitch;
`interturn_gap_crossed_before_floor` is true only when every floor horizon
crosses, false only when none does. Crossing supports a conditional
gap-filling hypothesis, not achieved density, overlap or thickness.

`curve_feedback_relation` components also carry `bilinear_diffusion_spread`.
Each `GL_LINEAR` warp read at sub-texel offset `f` adds variance `f(1-f)<=1/4`
per axis, and the qualified radial map stretches earlier spread by at most `J`
per step (the larger of the forward radial stretch and the zoom). After `n`
steps `Var<=(1/4)*sum_{k=1..n} J^(2k)`. Without a qualified radial map the bound is
withheld. Whole-texel offsets add nothing, so only a positive possibility is
reported: `adjacent_layer_merge_possible` is true or null, never false. An extra
diffusion pass above the engine's line-reference scale would only add spread.

`static_behaviour.radial_colour_field.components` (policy
`source-radial-colour-field-v1`): for an affine polar recipe with `Rs!=0`, each
affine raw label equals `C0+(Cs/Rs)*(R-Rc-Rt*t)+Ct*t`, a function of radius and
time but not angle. When the radius keeps one sign (a time-invariant proof, or
over a declared time domain), colour along the continuous curve is radius-locked;
only where feedback actually covers the gaps can this read as concentric rings.
Per channel it exports radial gradient `Cs/Rs`, radial modulo period
`|Rs/Cs|*period` where raw labels stay nonnegative (native signed fmod plus
clamp is not periodic across zero; `negative_raw_label_possible` flags this;
pixels need a matching isotropic projection), fixed-radius
rate `Ct-Cs*Rt/Rs` and iso-label ring drift `Rt-Ct*Rs/Cs`. A radius-locked spiral can
therefore read as rings if feedback fills its gaps; that remains a hypothesis.
Layering age, smoothing, modulo/clamps and composition remain separate; visible
ring count and contrast are not certified.

The radial colour record also carries `sweep_front`. At a fixed displayed
radius the curve's single point moves in angle at `Phi'_R=Pt-Ps*Rt/Rs`, so the
continuous curve sweeps back over every interior point of a covered radius once
per `2*pi/|Phi'_R|` seconds, whatever the number of turns. This is a rotating
refresh front: a local, spatially travelling change, not a whole-screen flash.
With the stored-level orbit,
`stored_level_from_full_before_next_crossing_interval` gives the level a
full-white deposit would reach before the next crossing if no retained content
arrived from other radii; it is a modulation ceiling, since feedback transport
can refill the point first. When `Rt!=0` a fixed radius is covered only for
`|Rs/Rt|` seconds (`revisit_within_radius_coverage`); more than one revisit per
frame aliases and withholds the level estimate.

## Per-pixel warp fields, motion vectors and composite

`static_behaviour.mesh_field` (policy `source-mesh-field-structure-v1`)
decomposes each native per-pixel warp control (zoom, zoomexp, rot, warp, cx,
cy, dx, dy, sx, sy) from its source graph. Single-coordinate `select` gates
become interval regions; signed additive terms are classified as constant,
uniform (audio/time/q, bounded with declared input domains), coordinate-affine,
uniform-scaled coordinate-affine, spatial oscillators or unresolved. Oscillators
of an affine coordinate/time argument report planar wavelength and phase speed
(the pattern moves along the wavevector at `-w/|k|`), radial ring wavelength and
speed, or angular lobe count and rotation.

Engine convention (pinned source34 warp shader), in per-pixel units: zoom acts
about the screen centre as `0.5+(c-0.5)/z^(zoomexp^(2*rad-1))`; `cx`/`cy`
centre only stretch and rotation; then the warp samples `(u-dx, v-dy)`. Retained
content therefore moves `+dx` right and `+dy` down (y=0 top) per step, and
`zoom<1` contracts toward the screen centre. Zoom is uniform only when zoomexp
is 1; otherwise a `radial_zoom_profile` reports the effective range over
radius. Per-pixel `x`/`y` are aspect-corrected: both measure the long side (1
unit = `max(width,height)` pixels) and the short axis spans a centred sub-range
(at 16:9, y spans 0.219-0.781).

For a same-axis affine term `d=a+b*c`, the raw slope gives `s=1/(1-b)`. When
zoom/stretch/centre are uniform, zoomexp is 1, rotation and procedural warp are
zero, the composed backward slope is `k=1/(z*s_axis)-b`; features scale by
`1/k` per step (`composed_feature_scale_per_step_range`, with mirroring when
negative) toward the fixed line solving `c=B(c)` (`fixed_point_range`). Uniform
audio/time terms widen the offset into an interval; unbounded, time-growing or
unresolved terms withhold the behaviour. Under compression a line's integrated
intensity scales by `|s|` per step, and so does its peak once it is about a
texel wide; a fresh sharp line's phase-averaged first-step peak is `|s|` for
`|s|<=1/2` and `1-1/(4|s|)` above. Sampling aliasing leaves beaded remnants.
Patterns are per-step sampling-map facts, not visible speeds.

`static_behaviour.motion_vectors` describes the native motion-vector element:
`mv_a>=0.0001` with positive integer grid counts (legacy `bMotionVectorsOn`
maps to `mv_a=1`), the engine grid positions (rows measured from the bottom),
colour and length. Vectors point toward the previous sampling position and are
drawn into the feedback image, so they are later warped and decayed.

The legacy composite (`final_transfer.legacy_response` on prominence
components) is described from the gamma redraw weight sum and the video echo.
With echo active the engine draws each pass once and adds `int(gamma-0.0001)`
redraws, so the weight sum is about `max(1,gamma)`: gamma below 1 does not
darken. Without echo the gamma-only path sums to `gamma`. The echo blends the
image at `1-alpha` with a copy scaled by `echo_zoom` about the centre at
`alpha` (magnified above 1, shrunk with edge sampling below 1); odd orientation
mirrors horizontally and orientation `>=2` vertically (native integer
truncation). Built-in wave `wave_material` time curves are
reported as per-channel ranges, rate ceilings and periods when known, with
max-normalisation noted.

`static_behaviour.radial_uv_envelope` needs explicit `texel_offset_pixels`; optional
`main_texture_size` independently supplies sampled texture dimensions. Neither
is silently inferred by the static context. It distinguishes coordinates within
`[0,1]` from a `GL_LINEAR` footprint within the texture-centre window. Unknown
dimensions leave that footprint unresolved. Default-warp/source34 qualification,
nominal arithmetic and interpolation premises remain explicit; no observed
wrapped texel, active filter mode or native precision is certified.

## Analytic custom-wave curves

When existing `elements[i].parameters.source_curve_recipe` is present, the
consumer retains it as an exact geometry fact at
`/analysis/visual_description/elements/i/parameters/source_curve_recipe`.
A recognized `source-parametric-wave-v1` recipe can refine the approximate look
to a circle, affine-radius spiral or polar-curve candidate. Names and a generic
radial family do not supply that refinement. Unknown classes/policies retain
raw facts without new shape claims.

Nominal turns are across the normalized source sample domain. Phase cycles per
source-time second describe the analytic coordinate phase, not visible
revolutions or flashes. Fixed-sample partial-speed ceilings keep source custom-wave
x/y coordinate units; no viewport conversion is assumed. Native sample points,
aspect projection, smoothing, clipping, thickness, alpha, shaders and feedback
remain separate. Time-growing radii can leave the speed ceiling null.

An existing `source_locus_relation` is retained as its own exact geometry fact;
its `fixed_angle_colour` is a separate exact colour fact. A fixed-sample point
speed is parameter-point motion and does not measure continuous-curve drift.
The conditional interior fixed-angle radial rate and normal-speed ceiling remove
tangential reparameterization, retaining signed source-radius semantics and
source-coordinate units. A proved continuous full-circle source locus can be
stationary even while its parameter points move rapidly. Finite parameter
endpoints, sample polylines, pixels, colour interpolation and feedback remain
unresolved; this is no static-screen or calm-mood certificate.

Fixed-angle raw RGB rates and nominal modulo cycles describe source colour on
the same interior branch. Native modulo events, cadence and visible flash
frequency remain unknown. Read exact/enclosed coefficients and all source-domain
conditions before using approximate numeric displays.

`spatial_vertex_colour` is also retained as a distinct colour fact. Its affine
RGBA coefficients, raw time-zero intervals and nominal modulo cycles along the
sample domain describe spatial ingredients. They do not establish temporal flash
frequency, reached screen colour bands, native arithmetic or mood eligibility.
All source expressions remain opaque data.

`spatial_vertex_colour.joint_rgb_spatial_pattern` preserves common affine RGB
sample-phase congruence at fixed source time. Slopes25/15/5 have signed winding
5/3/1 and nominal Euclidean-modulo period equal to the colour period/5. Zero slopes
give a sample-uniform source. Unsupported/excessive coefficients leave this
optional pattern unknown and preserve geometry. Native signed fmod is not globally
periodic across zero; sign conventions, finite sample span, rounding/interpolation
and reached repetitions remain separate. These sample-unit relations are not
temporal flashes, arbitrary independent RGB boxes or verified hue counts.

## Frozen description checkpoints

Save the summary, original input file/hash and source identity before examining
a screenshot or ten-second actual-AAR clip. Record AAR/worker/device/render/audio
identities separately. Continue an authorized checkpoint capture without waiting
for human feedback. Compare afterward, retaining the original prediction and any
new observation separately. A capture can resolve a particular visible behaviour;
it does not silently certify other presets or all mood groups.

The active project workflow also requests a prediction-based illustration before
capture. Save its prompt/image identity separately from the frozen SDK output;
an image generator can itself make interpretation errors. Use an isolated emulator
for Android AAR qualification, followed by a screenshot and10-second low-resolution clip with
declared audio. Compare the general structure, colours, movement and audio response
without requiring exact pixels. Preserve both prior descriptions and subsequent
diagnoses. A failed emulator/capture attempt supplies no native appearance evidence.
The user also authorizes native execution of the matching patched engine source
as a comparison alternative. Record its macOS ABI/GLES driver/API binding separately
from Android AAR/JNI qualification. Physical devices remain excluded.

Local checkpoint files are currently retained under `build/preset-corpus/` because
this session's filesystem allows writes only in the repository/tmp, while Downloads
delivery remains requested. Artifact links and an exportable ZIP can provide the
review bundle without claiming that files were already copied into Downloads.

## Validation

```bash
build/preset-lab-venv/bin/python -m pytest tools/milk-analyzer/test_preset_understanding.py -q
```

The tests cover controlled source facts, uncertainty, malicious instruction text,
unknown/failed export handling, exact fact-path/value preservation, finite/size
limits and CLI errors. When local frozen evidence exists, they also consume all
100 records in
`build/preset-corpus/static-behaviour-final100-2026-10-11-state-colour-v8/results`
without producer imports or rendering. That evidence test skips on a checkout
without this untracked local export folder; controlled tests remain runnable.

A fresh single-preset source export can additionally exercise recipe integration:

```bash
PRESET_UNDERSTANDING_FRESH_EXPORT=FRESH_ZYLOT_JSON build/preset-lab-venv/bin/python -m pytest tools/milk-analyzer/test_preset_understanding.py -q
```

This optional integration test requires the fresh record to contain a recognized
spiral recipe; it skips when the environment variable is absent. Frozen earlier
exports retain their original facts and descriptions.

## Shader colour palettes, flat-field states and mechanisms

`nonlinear_texture_colour_bounds.stages.<stage>.scalar_palette` (policy
`source-scalar-palette-map-v1`) applies when every projected RGB path to the
sampled inputs passes through one common scalar node: the stage output is then
exactly `f(s)`. The scalar range comes from unit sample domains; 33 points across
it give raw and clamped colours with hue families, and the black-content and
white-content colours are evaluated exactly. Independent channel paths report
`multiple_independent_sample_paths`. Which scalar values occur on screen is not
claimed.

`nonlinear_texture_colour_bounds.flat_field` (policy
`source-flat-field-steady-state-v1`) models spatially uniform content: every
main/blur sample returns the same per-channel value, so the custom warp becomes a
3-D recurrence iterated from black with clamping and RGBA8 rounding each step
(up to 900 steps). It reports whether flat regions decay, saturate, settle or
cycle, the settle time, and the composite colour at that state and at a black
start. Non-feedback textures (noise, images) abstain. Quantisation stalls
within half a level of a real fixed point. Edges, drawn elements, gradients and
advection change real content.

The SDK turns `analysis.families` mechanisms into plain-language construction
sentences (for example image-driven self-advection, kaleidoscope sectors,
polar tunnel sampling, complex quadratic fractals) with their stage. These are
proven program constructions; on-screen prominence remains conditional.

## Approximate mood layer and corpus grouping

`approximate_mood.py` (policy `approximate-activity-mood-v1`) reads only a
`preset-understanding-v1` summary and returns an editable activity estimate
(1-100), its interval, Chill/Normal/Intense band candidates (overlaps 25-30 and
70-75), confidence and labelled drivers with evidence pointers. It is separate
from strict source eligibility, which it reports unchanged.

- `source` drivers carry magnitudes from source facts: per-pixel warp patterns
  (uniform zoom edge flow, rotation, translation, ripples), curve sweep-front
  cadence, bounded geometry trajectories, brightness cycles, colour rates and
  authored audio routes.
- `prior` drivers stand for mechanisms present with unresolved magnitude (a
  time-driven shader field, moving or audio-driven geometry, brightness change
  of unknown rate). Each mechanism/component counts once and priors contribute
  only their largest assumed magnitude per dimension.

Shader motion magnitudes come from two exact-pointer facts: warp/composite
`sample_value_offset_envelope` records (per-step lookup displacement bounds
driven by sampled colours, from source or declared-scenario domains) and finite
`sampling_motion` lookup speed ceilings. A warp self-advection bound `b` gives a
source motion driver `fraction*b*fps` (editable `advection_typical_fraction`,
default 0.25, because typical sample differences are far below the full
range); a lookup ceiling gives half its speed. Audio routes into brightness or
colour controls add one beat-flash prior scaled by the number of
audio-brightness elements.

Motion is measured in screen widths per second; source motion combines by
root-sum-square. The score is `base + motion_weight*m + flash_weight*f +
audio_weight*a + colour_weight*c` with each term clipped to [0,1]. Every weight,
reference and prior is editable (`--rules` JSON). Confidence is high only with
no prior or unresolved drivers, medium below half, low otherwise or without any
source motion/flash magnitude. Unrecognised records become `unresolved` drivers
that saturate the upper estimate in their dimension, low confidence assigns no
band (`abstained`, possible bands only), and audio counts once per band (bass,
mid, treble, volume), so missing evidence never becomes certified Chill. The estimate is an assumed
preference grouping, not a calibrated mood.

`corpus_understanding.py` runs the whole pack: native parse, static export (no
rendering or frame simulation), SDK summary and approximate mood per preset,
with a process pool, per-preset timeout, frozen model identity and resumable
compact results. `report.json` counts statuses, bands, confidence and the
activity histogram; `collections.json` lists presets per band by activity.

## Multi-axis features and user-preference selection

`approximate_features.py` (policy `approximate-feature-vector-v1`) implements the
research feature contract over SDK facts: motion speed/acceleration/jerk and
discontinuities, flash transitions and contrast, brightness jumps, bass
effect, palette saturation/hue variety/warm-cool/hue rate, mean display luma,
feedback half-life and structure scores (symmetry, nonlinear warp, feedback
complexity, organic, geometric, fractal) from proven mechanisms, with
composite-stage constructions weighted 0.7. Each feature carries an evidence
label (`source-estimate`, `mechanism-estimate`, `assumed`, `unknown`). The
research equations give intensity, smoothness, psychedelic, warm and cold
scores with intervals; activity confidence depends on the intensity interval
only. Style tags whose inputs are all assumed are reported as `possible_tags`.
Profile suitability uses `mood_profiles.PROFILES` (genres, viewing contexts,
the owner-chosen 70+ gentle default) and the research fit formula.

`corpus_understanding.py` stores this record per preset and writes
`preference-index.json`. `preference_select.py` (standard library only)
ranks presets for an editable preference file: profiles, activity window,
comfort rules (`no_flashing` excludes unknown or assumed flash evidence,
`min_smoothness`, `max_speed_vp_s`), palette warm/cold, preferred and avoided
tags (avoided possible tags also count), minimum confidence and limit. Every
selected preset lists its reasons. These are assumption-based preferences, not
calibrated taste; explicit user feedback should replace defaults.

`preset_recipe.py` wraps the mood record with an engine-neutral render/intent
description in one versioned JSON, so later consumers need no contract change.

Feedback (`feedback` in the preference file) works on the feature vectors:
`liked`/`disliked` presets add a similarity bonus/penalty from standardised
feature distance (motion, flash, palette, luma, feedback and structure), and
complaints tighten comfort relative to the named preset (`too_fast` caps speed
at 0.8× its estimate, `too_flashy` enables no-flashing, `too_dark`/`too_bright`
bound display luma). Disliked or complained-about presets are excluded.
Motion driver magnitudes are capped at 10 screen widths/s (perceptually
saturated) so explosive zoom formulas cannot overflow the scores.

Held-out check (2026-10-11, 34 presets never used for tuning): rank correlation
of intensity with observed emulator activity 0.33 (0.28 for the older scorer);
2 of 8 strongly flashing presets were tagged Flashing. Automatic activity is
therefore only a rough prior; preference feedback is the intended correction.

## Point clouds, mirrors, borders and radial zoom (2026-10-12)

These general facts came from the r4 checkpoint (`Phat+fiShbRaiN_Mandala`),
where the frozen v1 prediction was black and grey although the native picture
is a bright, four-fold mirrored blue/purple particle fountain.

- `source_point_colour.py` (`source-custom-point-colour-distribution-v1`) runs
  inside the custom-wave colour model. A custom wave evaluates its per-point
  code at `sample=j/(N-1)` (MilkDrop2 and projectM agree). When r, g, b and a
  depend only on `sample`, `time` and declared scalar inputs, the module
  enumerates that finite grid at declared times (audio held at band
  midpoints) and reports mean colour, hue-family shares, saturation and
  alpha. Hashed formulas such as `((sample*5454)%100)*.01` become a measured
  spread. `time_expression.evaluate_inputs` implements projectm-eval `%`
  (C remainder of truncated integers, divisor 0 gives 0) and EEL equal.
  When x/y are also closed-form, the record keeps the serialised programs and
  source position bounds. Persistent per-point state, `rand` and waveform
  inputs stay unresolved and are listed.
- `mirror_symmetry.py` (`source-mirror-symmetry-v1`) turns a uniform negative
  stretch (`sx<0` or `sy<0`, a per-step reflection) and a mirrored composite
  echo into flip directions, a fold count and a symmetric-energy score
  `2AB/(A^2+B^2)`. Feedback uses `(1, decay)` and the echo uses `(1-a, a)`.
  The score is an upper estimate that feeds `structure.symmetry`.
- `source_borders.py` (`source-border-feedback-operators-v1`) models MilkDrop2
  `DrawSprites`, drawn after shapes and waves into the feedback canvas. Each
  border is a square annulus covering `out^2-in^2` of the viewport, blended
  "over" with its colour, so retained content there keeps `decay*(1-a)` per
  frame. The record adds the RGBA8 orbit, floor and half-life. The darken-centre
  diamond (alpha 3/32 at the centre) is also included. A border band covering
  most of the screen sets the approximate `feedback.half_life_s`.
- A `rad`-affine zoom (constant + uniform + `k*rad` terms) with a uniform
  zoomexp is sampled over the viewport as a `radial_zoom_profile`, with
  `screen_mean_percent_per_step`. Closed-form point clouds add a motion driver
  (median on-screen point speed, one-frame differences).
- Brightness controls are classified by word (`outline_opacity`, `border_a`),
  not by prefix.

Controlled emulator variants of the r4 preset, under the checkpoint's
`decay-experiment/` folder, established three engine facts used by the
illustrator:

1. The capture is upright (the frame writer reverses GL rows), and a shape at
   `y=.2` renders 80% of the way down the screen. Wave vertices follow the
   curve-projection fact: row = `H/2-(y-.5)*long`.
2. With decay 0 and only one dot wave enabled, every authored point lands on a
   lit pixel, while projectM's 4-tap smoothed midpoints hit only at chance
   level. Published-AAR dot waves therefore draw the N authored points; line
   waves keep 2N-1.
3. A header-only decay of .999 matches the original brightness, so the
   per-frame `decay` assignment is effective. Native frame `k` is rendered at
   source time `(k+1)/30`.

4. Textured fills copy the stored previous frame without mirroring and rotate it
   by `tex_ang-ang`. A quadrant control and a `tex_ang=±1` control matched the
   operator to native at mean absolute error 0.0012, and confirmed the rotation
   sign. The copy's alpha is the vertex alpha times the stored canvas alpha.
   The warp keeps alpha undecayed, and blending updates it with the same factors
   as RGB.
5. Shape outlines (`border_*`, thick: four offsets) and untextured gradient fills
   are drawn. The r4 dark central hexagram is the black outline of a textured
   triangle, rotated by its own copy.

The legacy composite also exports `tint_amount`. The illustrator applies the
fShader corner tint with zero random hue offsets, so hue placement is not a
prediction. Textured shapes redraw the previous frame through their polygon
with the exact affine fan mapping. The frozen r4 v4 illustration at frame
149 has mean luma 0.212 against 0.210 native, saturation 0.507 against 0.499
and centre luma 0.337 against 0.338. The random-spout `wave_1` ring and the
tint hue placement remain unmodelled.

### Custom warp shaders as feedback operators (r5 checkpoint, `144.milk`)

- `feedback_transfer` keeps an affine previous-image transfer when a custom warp
  adds terms that never read an image directly. These include spatial/time
  fields such as `.1/length(sin(uv*6))` and terms that read images only
  nonlinearly or through coordinates. Main and blur sample sites both
  contribute matrices (`affine_previous_image_samples`). `uniform_content_gain`
  sums the diagonal gains of every site. The injected part is exported per RGB
  lane (`image_independent_injection.lane_expressions_rgb`) and is not counted
  as gain or as a constant offset. Image-dependent injections set
  `coordinate_feedback_dependency`.
- Nonlinear per-pixel mesh terms keep their bounded source graph, and a
  stretch that is negative everywhere is reported as a mirror even when its
  magnitude varies.
- The illustrator rebuilds exported graphs as `shader_fields.Field` and
  evaluates them with `grid_math.evaluate_grid`, the same numerical semantics
  as the predictor. This covers injected warp lanes and the exported coordinate
  expression of the main sample site (so image-driven displacement steers the
  remap). `_uv.xy` is the mesh-warped coordinate, `_uv.zw` the pixel position,
  and `rand_frame` is a seeded stand-in. Custom warp shaders store alpha 1
  (projectM `MilkdropShader`: `float4(ret.xyz, 1.0)`). Thick line waves are
  four additive half-pixel passes (projectM 4.1.7 `CustomWaveform::Draw`).
  Legacy darken/brighten/solarize/invert filters are applied after the
  gamma/echo draws.
- The r5 v3 frozen illustration reproduces the magenta line arcs, the glowing
  spots of the injected field, the central blue column and the curved smear.
  Its mean luma is 0.006 against 0.017 native. The wide blue haze comes from a
  shape whose opacity is cubic in the mid band (`mid_att^2*mid*0.002`), so
  band midpoints understate it. That sensitivity is audio-dependent rather
  than a source error.
- Audio-driven controls are evaluated per frame. `prediction_illustration.py
  --audio <milk-audio-inputs report>` takes declared per-frame bands (native
  frame k at source time (k+1)/fps) instead of band midpoints. Engine bands are
  heavy-tailed (r5 audio: mid mean 1.01, median 0.57, p90 2.23), so a nonlinear
  response such as `mid_att^2*mid*0.002` averages 0.020, ten times its midpoint
  value. Through a 0.97 feedback gain that becomes a saturating haze. The
  frozen r5 v4 illustration with the declared audio reproduces the haze, the
  glow spots and the blue/green colour cycle. At frame 60 its mean RGB is
  0.028/0.085/0.110 against 0.035/0.079/0.079 native. Saturation is
  0.94 against 0.80 because display gamma still uses its range midpoint.
- `audio_series.py` (`source-audio-drawing-series-v1`) evaluates closed-form
  audio-driven drawing over a declared reference band sequence
  (`fixtures/reference-band-sequence-2026-10-12.json`: the checkpoint audio
  after JNI U8 ingress, continuous 300 frames from the source34 audio
  adapter). Covered drawing is untextured and textured custom shapes (textured
  ones use a declared nominal content luma of 0.25 and are flagged) plus
  closed-form point clouds. The result is the screen-mean fresh-drawing
  contribution per frame, its mean, its p95 jump and the transitions above
  0.03 per second. These feed `brightness.audio_drawing_mean`,
  `brightness.audio_drawing_jump_p95` and, when nonzero,
  `flash.coherent_transitions_hz` (evidence `source-estimate+declared-audio`).
  Feedback accumulation and the composite are excluded, and the sequence is a
  declared input, not music statistics.

### Stochastic shapes and custom composites (r6 checkpoint)

- The illustrator samples projectm-eval `rand(x)` (uniform on
  `[0, max(1, floor(x)))`) with a seeded per-frame generator. This is a Monte
  Carlo draw of the authored distribution, not the engine's random stream.
  It also draws instanced shapes, binding `instance` from 0 to num_inst-1.
- Mesh terms the export leaves unresolved are held at their range midpoint (or
  zero), and the illustration continues instead of stopping.
- Affine custom composites (`texture_colour_transfer.stages.composite`, now in
  the summary) are applied as the sum of matrix x texture(coordinates) plus
  offset lanes. They are evaluated with the grid evaluator using the shader
  low-level uniforms (`_c0`/`_c5`/`_c6`/`_c7`/`_c13`, `texsize_main`) and
  per-pixel `_rad_ang`. Blur levels come from the engine blur bank (see
  below) and noise textures are deterministic stand-ins.
- Whole-pack run r5 (analyzer `72b11bea`): all 9,606 presets computed.
  Approximate bands are Chill 1,194, Normal 6,953 and Intense 1,498, with 843
  abstentions (8.8%).

### Stage programs and built-in waveforms (r7 checkpoint)

- `source_stage_program.py` (`source-stage-program-v1`) exports each authored
  warp/composite stage's returned RGB as a typed graph with texture-sample nodes
  inline and loop plans as a table (`visual_description.stage_programs`, also in
  the SDK summary). The illustrator rebuilds the graph (`shader_fields.Field`,
  `LoopPlan`) and evaluates it per pixel with `grid_math.evaluate_grid`, binding
  the `shader_uniforms` layout from a declared render state (Q values 0), `_uv`,
  `_rad_ang`, engine blur levels and noise stand-ins. Any
  translated shader — nonlinear, image-dependent or looping — now drives the
  feedback and display instead of falling back to a gain model.
- `builtin_wave_geometry.py` implements projectM 4.1.7 built-in waveform modes
  0-9 (excluding the spectrum mode 8) from declared PCM: wave_scale/smoothing
  IIR, mode geometry, edge clipping and the 4-tap midpoint insertion.
  `fixtures/reference-waveform-windows-2026-10-12.npy` holds the declared
  checkpoint PCM windows (576 U8 samples per frame). Built-in vertices use the
  same screen mapping as custom waves (column (1+x)/2·W, row (1+y)/2·H).
- r7 (`The Waving Shaker`): v1 black → v2 grayscale web of blurred streaking
  lines around a moving horizontal waveform, luma 0.185 against native 0.31–0.34
  (Q uniforms held at 0 explain part of the gap).
- `stage_programs.frame` exports the per-frame recurrence: every persistent
  per-frame variable's initial (per_frame_init or 0) and end-of-frame update
  graphs, plus Q1..Q32 and the native controls as outputs. The illustrator steps
  it under the declared bands, so Q uniforms, smoothed audio accumulators,
  zoom/rot/cx and the like follow the authored equations instead of midpoints.
- The mesh field record carries `procedural_warp_parameters` (fWarpAnimSpeed,
  fWarpScale), and the illustrator applies projectM's procedural warp
  displacement. Uniform-scaled coordinate-affine terms also export their graphs.
- r7 v3: swirl and streak structure now matches. A controlled passthrough-
  composite variant shows the remaining 4x darkness is in the feedback canvas
  (0.029 vs native 0.08), not the composite gain (×3.0 vs ×4.1).

### Engine conventions verified with native-ruler probes (r7, r8)

Each convention below was checked on the pinned engine (native ruler) with an
isolated probe preset. Each probe seeds texture, isolates one term, then applies
the illustrator's map to native frame 6 and compares the result with native
frame 7. Native-ruler frames are stored top-down: the harness reverses the
`glReadPixels` rows, and a full r8 render matches the emulator screenshot at
correlation 0.969 as stored. An earlier pass (commit `e45e6959`) flipped these
frames by mistake, which inverted its vertical conclusions; every probe was
repeated on correctly oriented frames. Probes and results:
`docs/superpowers/evidence/motion-convention-probes-2026-10-12/`.

- **Motion frame.** Per-pixel `x`/`y` and the warp's `u`/`v` use long-side
  units with y pointing down (MilkDrop's y = 0 at the top). Rotation, `cx`/`cy`,
  `dx`/`dy`, stretch, and the per-pixel `y`/`ang` inputs follow
  `PresetWarpVertexShader` in this frame. All 8 motion probes reach single-step
  correlation 1.000 (unchanged from the earlier map).
- **Procedural warp.** The vertex `pos.y` grows downward like `v`, and the
  displacement adds to `v`. Presets without a warp shader compile
  `PROJECTM_LEGACY_WARP`, which enters `pos.y` with the opposite sign. Each path
  reaches 0.9987 with its own formula and about 0.46 with the other; the earlier
  map reached 0.53 and 0.41.
- **Mesh.** Motion is evaluated at the production 48×32 mesh vertices
  (`native-lib` defaults; ruler `SetMeshSize`), with mesh row 0 at the top, and
  interpolated over the engine triangulation (one diagonal with a warp shader,
  the legacy diagonal without). A context `mesh_grid` overrides the size.
- **Blur bank.** `blur.blur_bank` (8-tap passes at engine pass sizes, unorm
  storage, range normalisation, blur1 edge darkening) replaces the Gaussian
  stand-ins in warp, composite and injection evaluation. Because the engine's
  first pass flips vertically, the illustrator uses `flipud(blur_bank(image))`;
  a `GetBlur1` probe matches to 6e-5 mean absolute error.
- **Blur timing.** Blur textures are built from the previous frame's buffer.
  The composite therefore blurs the previous canvas, and a warp shader that
  samples blur reads last frame's update, made from the canvas two frames back.
- **Waves and shapes.** Built-in wave NDC y points up on screen
  (`row = (1 - y)/2·H`; a `wave_y` probe matches to the pixel). Custom-wave
  points and shapes use y = 1 at the top: the r8 star field correlates 0.961
  with this mapping and 0.058 mirrored.
- **Conditional wrap.** A main sampler exported as `wrap: null` with
  `wrap_condition: frame_wrap > 0.0001` follows the per-frame `wrap` value. It
  used to clamp, which wiped the canvas on high-amplitude warp frames.
- **Textures and randomness.** `texsize_<name>` uniforms are supplied for noise
  (engine sizes: `noise_lq` 256 with random texels, `noise_lq_lite` 32,
  `noise_mq`/`noise_hq` 256 interpolated every 4th/8th texel), blur levels and
  stand-in images. The noise seed is deterministic, so illustrations repeat.
  `rand_frame` is a seeded new vector every frame.
- **Thick lines and history.** Thick main-wave and outline passes are blended
  one at a time. The loop renders exactly `history_steps` frames ending at the
  declared time (native frame k renders at (k+1)/fps).
- **Custom-wave state.** When per-point graphs read a wave's persistent
  per-frame variables (`state:<wave>_per_frame:<name>`), the point record carries
  `frame_recurrence`: initial and end-of-frame update graphs. The analyzer steps
  it from t = 0 at 30 fps under the held inputs for the colour distribution,
  and the illustrator steps it per frame under the declared audio.
- **r7 (`The Waving Shaker`) v6.** The waveform and streaks sit at the engine's
  rows, luma is 0.342 against the emulator's 0.314, and the percentiles are
  within 0.04. The canvas brightness follows the ruler frame by frame. Strand
  placement drifts because the feedback is chaotic and the waveform aligner is
  not modelled.
- **r8 (`River of Petals`) v1 → v2.** v1 was nearly black: the star-field seeds
  were blocked by their wave state. v2 matches the emulator: luma 0.608 vs
  0.602, mean RGB within 0.05, blurred correlation 0.951. It shows the same
  left-right symmetric green/yellow/red reaction-diffusion strands, and the
  canvas follows the ruler in all three channels within about 3%.
- **Waveform-driven custom waves.** Per-point `value1`/`value2` are resolved from
  the declared reference PCM windows, prepared as `CustomWaveform` does: the
  first 480 samples, a centred window shifted by ±sep/2 (or resampled when more
  than 480 points are requested), forward-then-backward IIR smoothing with
  `mix1 = sqrt(0.98·smoothing)`, then scaling by `scaling·fWaveScale·0.004`.
  Spectrum waves stay unresolved. The point record carries `waveform_inputs`.
- **Illustrator order.** The CLI runs the per-pixel field simulation first. The
  closed-form orbit illustrator is used only when the field or decay is not
  described.
- **r9 (`Our Destiny`) v1 → v2.** v1 drew only the fresh ring. v2 shows the
  zooming tunnel of concentric rings, the blue disc and the magenta star
  (flipped textured triangle). Luma is 0.396 against 0.459, display correlation
  0.89, and the canvas follows the ruler at 0.92–0.98. The rings and the disc
  centre are less green than native (display green 0.41 vs 0.51); this is still
  being investigated.
- **Points and outlines.** Dots follow GL point coverage: a size-s point at
  window position w lights pixels whose centres lie in [w - s/2, w + s/2). A
  native probe confirms that a point at x = 0 is not drawn and one at x = 0.5
  lands on column 239. Built-in wave dots are single 2×2 passes. Thick shape
  outlines are offset by half a pixel (`1/viewport` in strip units).
- **r9 v3.** It matches the emulator capture: the green-cyan glow at the disc
  centre, the pale star and the greenish ring tunnel, blurred correlation 0.96,
  about 15% brighter. The remaining difference is line rasterisation.
- **Inlined per-frame graphs.** Stage programs inline Q graphs over start-of-frame
  per-frame state (beat counters, accumulators) and per-frame base inputs (`fps`,
  `frame`, `time`). The illustrator records the stepper's start-of-frame state and
  supplies it to warp, composite and injected-field programs. The grid evaluator
  implements the projectm-eval operations those graphs use: `eel_divide`,
  `eel_equal`, `bnot`/`band`/`bor` (close factor 1e-5), `negate`, `sqr` and `int`.
- **Built-in wave alpha and colour per frame.** Alpha comes from the recipe: the
  authored or stepped `wave_a` times the mode gain, times the volume ramp on
  `vol = 0.333·(bass+mid+treb)`, clamped and gated at 0.004. Colour comes from the
  stepped `wave_r/g/b`, maximised when `bMaximizeWaveColor` is set.
- **r10 (`Violet Lights in The Sky`) v1 → v2.** v1 was a single bright ring. v2
  shows the dark scene of wobbly overlapping rings with violet beat sparks. The
  ring layout differs from the emulator frame because the preset's init code
  draws `rand()` for its beat counters, so even two native runs differ.

### Source-calibrated display estimates (2026-10-12)

- **Labels.** The engine ruler (pinned patched projectM-TV rendered offline,
  macOS GLES + SwiftShader, 480×270, 300 frames at 30 fps, checkpoint audio,
  statistics over frames 60–299) measured all 9,606 bundled presets. These
  measurements are calibration targets only, never classification inputs.
- **Model.** `fit_display_calibration.py` fits gradient-boosted trees from the
  `static_descriptor` columns of the r6 whole-pack summaries (analyzer
  `ad44ce53`) to six display statistics. The 90 emulator-validated presets are
  excluded from fitting. `fixtures/calibrated-display-model.json.gz` holds the
  trees; `calibrated_display.predict` needs only the standard library.

  | Statistic | Out-of-fold Spearman | Held-out 90 |
  |---|---|---|
  | Luminance | 0.583 | 0.574 |
  | Frame difference | 0.693 | 0.733 |
  | Flow | 0.665 | 0.729 |
  | Brightness jumps | 0.757 | 0.734 |
  | Saturation | 0.593 | 0.556 |
  | Warm/cool | 0.498 | 0.468 |

- **Activity.** `display_activity.py` takes the percentile of the mean
  percentile rank of frame difference, flow and brightness jumps, measured
  against frozen ruler quantiles (`fixtures/display-activity-reference-v1.json`).
  Source-calibrated estimates are first remapped through the frozen out-of-fold
  calibrated-activity distribution, a monotone map that keeps the band shares.
  Bands follow the Mood facets definition: Chill ≤ 0.35, Normal 0.25–0.75,
  Intense ≥ 0.70.
- **Grouping.** `approximate_mood(summary, display=...)` assigns bands from the
  calibrated activity, with confidence from the interval width: high ≤ 0.6,
  medium ≤ 0.8. Out-of-fold, against measured activity:
  - activity Spearman 0.735 (0.784 on the held-out 90);
  - primary band accuracy 0.64 overall, 0.85 at high confidence, 0.72 on the
    held-out set;
  - Chill/Intense swaps 1.4%.

  The whole-pack rescore (`corpus_understanding.py --rescore --display-model`)
  gives no abstentions (previously 839): Chill 3,480, Normal 4,503, Intense
  2,971. Recipes gain an additive `display_estimate` block. Evidence:
  `docs/superpowers/evidence/source-calibrated-display-2026-10-12/`.
- **Never-written variables.** projectm-eval reads a variable that is never
  written as 0. The frame stepper does the same: for example `cyyspeed`, which
  MilkDrop's joining of a line split across numbered records produces. It also
  exposes these variables to mesh terms.
- **r11 (`Starover (Semicolon Mix)`) v1 → v3.** v1 was black: a `log()` zoom term
  aborted the field. v2 and v3 show the dense red/yellow/green nested-swirl field
  with its bright border (luma 0.546 vs 0.465, saturation 0.98 vs 0.97), and in v3
  it drifts asymmetrically as in the engine. The rendering is still redder than
  native (red 0.76 vs 0.56).
- **Default custom-wave positions.** Each point starts at x = 0.5 + value1,
  y = 0.5 + value2 (projectM `LoadPerPointEvaluationVariables`, as in MilkDrop),
  so a wave without position code is a stereo X-Y trace of the declared PCM.
- **r12 (`Altars of Eckshak (green)`) v1 → v2.** v2 matches the emulator: an X of
  green-edged rays meeting at a centre glow (blurred correlation 0.965, luma
  0.057 vs 0.053). The calibrated estimate placed it in Chill.
- **Simulation versus the engine.** On 150 random presets, the source-only
  simulation now correlates with the ruler at 0.54 (luminance), 0.49 (frame
  difference), 0.51 (jumps) and 0.45 (saturation). Before today's fixes it was
  0.20 / 0.17 / 0.34 / 0.08. The calibrated model on the same presets reaches
  0.66 / 0.71 / 0.71 / 0.58.
- **Frame counter.** The per-frame `frame` variable is projectM's `m_frameCount`:
  0 on the first rendered frame, which renders at time 1/fps. Frame k therefore
  has `frame = k` at time (k+1)/fps; the illustrator had passed k+1. On r11,
  where `frame % 15` gates the targets of the dx/dy springs, the fix raises
  single-step motion correlation at frame 12 from 0.13 to 0.76.
- **r11 v4.** It matches the emulator: luma 0.468 vs 0.466, colour within 0.01,
  canvas correlation 0.82–0.96. Applying our composite to the native canvas
  reproduces the native display, so the composite model is exact.
- **Random terms in shaders.** The grid evaluator implements projectm-eval's
  `rand(x)` (uniform on [0, max(1, floor(x)))) for inlined per-frame graphs,
  with one seeded draw per evaluation.
- **r13 (`i am only here to die slowly…`).** The calibrated estimate (Intense,
  about 69 brightness jumps per 10 s) matched the capture before any fix. v2 also
  reproduces the strobe: white flashes at the same frames as the engine and
  pastel blob edges (frame luma 0.904 vs 0.885).

