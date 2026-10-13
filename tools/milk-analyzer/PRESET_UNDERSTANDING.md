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
tags (avoided possible tags also count), minimum confidence, Mood facets
(`"facets": [option ids]`, OR within a group and AND across groups, intersected
with the other filters) and limit. Every selected preset lists its reasons. These are assumption-based preferences, not
calibrated taste; explicit user feedback should replace defaults.

`preset_recipe.py` wraps the mood record with an engine-neutral render/intent
description in one versioned JSON, so later consumers need no contract change.
Its `facets` block (also copied into each preference-index entry) gives Mood
facet memberships from the bundled engine-ruler measurements for bundled
presets, otherwise from the source-calibrated display estimate with intervals,
`possible_options` and `unresolved_options` (see EXPORT_CONTRACT.md, Mood facets
block); no simulation output feeds it.

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
  declared time (native frame k renders at (k+1)/fps). When those frames cover
  the whole time since load, the canvas starts cleared (black), as projectM
  clears it at preset load; a shorter history starts from the flat-field steady
  state. Warp and composite programs are evaluated with IEEE float semantics
  (`gles300-ieee-illustration-v1`: x/0 is ±∞, 0·∞ in a compound `*=` is NaN,
  bare `*` keeps the translator's `mult0` zero guard). Non-finite outputs are
  stored as an RGBA8 target does (NaN → 0, infinities clamped), and non-finite
  sample coordinates are addressed at the edge. This is an illustration policy,
  not a proof; certified paths keep the strict numeric policy.
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

  Descriptor v2 adds the feedback-equilibrium columns (see *Feedback
  equilibrium* below). Scores of the shipped model, with the previous
  descriptor-v1 model in brackets:

  | Statistic | Out-of-fold Spearman | Held-out 90 |
  |---|---|---|
  | Luminance | 0.641 (0.583) | 0.694 (0.574) |
  | Frame difference | 0.712 (0.693) | 0.751 (0.733) |
  | Flow | 0.681 (0.665) | 0.764 (0.729) |
  | Brightness jumps | 0.765 (0.757) | 0.738 (0.734) |
  | Saturation | 0.637 (0.593) | 0.541 (0.556) |
  | Warm/cool | 0.600 (0.498) | 0.656 (0.468) |

  The shipped model is fitted on the r8c whole-pack export, which has offline
  compile evidence and stage transfers that bind the per-frame state, with
  descriptors that include the composite hue shader.

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
  - activity Spearman 0.748 (0.793 on the held-out 90; descriptor v1: 0.735
    and 0.784);
  - primary band accuracy 0.65 overall, 0.84 at high confidence (24% of
    presets), 0.76 on the held-out set (v1: 0.64, 0.85 on 22%, 0.72);
  - Chill/Intense swaps 1.3% (v1: 1.4%).

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
- **Simulation is a diagnostic only.** The simulation evaluates exported source
  formulas frame by frame. It is never a measurement and never a grouping or
  calibration feature (owner decision, 2026-10-12). Stacking it on the
  calibrated estimate in a 2,400-preset pilot raised luminance from 0.56 to
  0.68 and saturation from 0.58 to 0.69. That gain only locates gaps in the
  static model: the level the feedback loop settles at, and how colour passes
  through the warp and composite. These gaps are closed with derived formulas.
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
- **Per-point state.** Custom-wave per-point variables persist from point to
  point and from frame to frame (for example a toggle that alternates points
  between two rails). Point records carry `point_recurrence`: each variable's
  end-of-point update and its initial value. Point j reads point j−1's end value,
  and the illustrator carries the last point's value into the next frame.
- **r14 (`285.milk`) v1 → v2.** v1 was black because all four arm-like waves were
  blocked by a per-point toggle. v2 matches the emulator: a warm orange spiral of
  swept tiles, blurred correlation 0.90.
- **Named image textures.** Samplers that name a bundled image (for example
  `sampler_devboxb`) read the actual texture file. `corpus_inputs.texture_index`
  resolves it over `core/src/main/assets/textures`, with sampler prefixes
  stripped, and `texsize_<name>` takes the image's size. Unknown names keep a
  deterministic stand-in.
- **Shape state.** A custom shape's per-frame code runs once per instance, and
  its variables persist across instances and frames. Shape elements now carry
  `frame_recurrence` (plain and init-prefixed input names, initial value,
  end-of-run update, random calls kept). The illustrator steps it per instance,
  drawing only each polygon's bounding box.
- **r15 (`Spotted Blob_2 … could-scape`) v1 → v2.** v2 matches the emulator
  (blurred correlation 0.994, identical luma and colour). It shows the dark
  smoke from the blended `devboxb` image and the random-walker spotted blobs.
- **Mode-3 wave alpha.** A mode-3 built-in wave uses the reference alpha
  (`MaximizeColorsTextureSize` table) × 1.3 × treb², then the volume ramp and
  the clamp; it was previously drawn at alpha 1.
- **r16 (`BrainStain-radioactive`).** The calibrated estimate is Intense
  (certain), and v1 already matched the chaotic green/magenta field (blurred
  correlation 0.81). The centre blob is blue instead of magenta: a tinted
  textured shape copies the centre onto itself, so the first colour to reach it
  becomes a fixed point.

- **Large per-pixel terms.** Per-pixel motion terms can inline several whole
  per-frame Q blocks. The mesh field now exports each term's graph up to 1,024
  nodes (previously 256). If a control still has a term that is unknown and has
  no range, the illustrator holds the whole control at its neutral value (zoom 1,
  dx 0, …) or at the control's range midpoint. Summing only the known terms can
  invent motion: in `dx = q·x − x` the `−x` alone is a strong leftward flow.
  Mesh terms read the per-frame state at the start of the frame, like shader
  programs.
- **Motion vectors.** `MilkdropPreset::RenderFrame` draws motion vectors into
  the previous frame before the warp, using the u/v map from the previous warp.
  They therefore reach the screen only after one warp, decay and shader pass.
  GLES has no line smoothing. The illustrator draws aliased 1-pixel lines by the
  diamond-exit rule: the pixel that holds the end point is not drawn, so a
  1.25-pixel vector covers one pixel. It blends them with `mv_a` and applies the
  minimum length in texture units (`|(1.25/W, 1.25/H)|`), as
  `PresetMotionVectorsVertexShader` does.
- **r17 (`suksma - fuck alltec auto in orem…`) v1 → v2.** v1 drew a bright red
  field of long radial lines. The capture is a dark brown field of warped
  orange and white vector ticks. v2 matches its palette and structure: luma
  0.173 vs 0.155 (ruler 0.159) and saturation 0.43 vs 0.43. The canvas follows
  the native passthrough canvas within about 15%. The regression on r8–r16 is
  unchanged except r11 (blurred correlation 0.957 → 0.991).
- **Float32 time.** `RenderContext::time` is a float that is widened to
  `PRJM_EVAL_F`, so equations see float32 time. That decides ties: with a 0.1 s
  beat refractory period (`above(time, t0+.1)`), three frames at 30 fps land
  exactly on the threshold. The double value 3/30 equals 0.1, while float32(0.1)
  is larger. The frame stepper, mesh terms, waves and shapes now use float32
  time. On r18, the beat flags, beat counters and peak follow the engine on all
  150 frames, verified by a native probe that encodes the q values as colour.
- **Thick custom waves.** `CustomWaveform` offsets thick passes by 1/viewportX
  in NDC on both axes. That is half a pixel right and H/(2W) pixels up (NDC y
  grows upward). The illustrator had moved the vertical pass half a pixel down.
  A flat line at y = 0.5 therefore lit two rows instead of the engine's one, and
  additive feedback doubled the canvas.
- **r18 (`martin - time machine`) v1 → v2.** v1 was overexposed (luma 0.86 vs
  0.66) and showed side lobes. v2 is identical to the capture: luma 0.659 vs
  0.660, the same colour and a blurred correlation of 1.0. The canvas mean
  matches the native passthrough canvas within 0.001. The frozen text had
  expected a coloured disc. That disc is hidden, because its visibility needs
  64 beats, and the look comes from the composite's sun and ray terms.
- **Point positions over per-frame state.** Custom-wave positions can inline
  main per-frame Q graphs, such as an `mtime` accumulator or beat counters.
  Their records keep closed-form positions and list the per-frame inputs those
  positions read (`frame_inputs`). The illustrator resolves them by stepping the
  exported frame program, using values from the start of the frame; names that
  are never written read 0.
- **Shader rad/ang.** Both stages measure y downward from the top. The warp mesh
  uses `rad = hypot(x·aspectX, y·aspectY)` and `ang = atan2(y·aspectY,
  x·aspectX)`. The composite (`FinalComposite::UvToMathSpace`) scales rad to 1
  at the corners and wraps ang to [0, 2π). With y measured upward, polar
  composites came out mirrored.
- **Alpha-blended dots and thick passes.** GL composites overlapping
  alpha-blended points one after another. The background keeps ∏(1 − a), and
  the points' alpha-weighted colour fills the rest, so dense dots converge to
  their colour. Summing them had pushed the result toward white. Each thick line
  pass is blended on its own.
- **r19 (`404.milk`) v1 → v2.** v1 was black. v2 matches the capture: four
  articulated arms of yellow, orange and teal dots wrapped by the polar
  composite, luma 0.108 vs 0.108 and a blurred correlation of 1.0. The
  regression on r8–r18 is unchanged or better (r14: 0.928 → 0.964).

### Feedback equilibrium, EEL memory and point sampling (2026-10-12)

- **Feedback equilibrium.** `feedback_equilibrium.py` estimates the
  steady-state canvas from source. Each frame the warp maps the canvas through
  a gain g and offset per channel, and drawn elements inject colour c with
  alpha a. Additive elements converge to a·c/(1−g), alpha-blended ones to
  a·c/(1−(1−a)·g). Shapes use their area-averaged radial gradient; borders,
  waves and motion vectors are included. The gain and offset come from the
  exported warp program evaluated on flat inputs (levels 0–1, times 2/5/8,
  neutral bands), otherwise from the feedback matrix or decay. The composite
  comes from its exported transfer table, then the legacy gamma, brighten,
  darken, solarize and invert controls. A shape colour written as a formula
  uses its average over 0.25–10 s and all instances (bands held at 1); `rand`
  calls use the expectation of projectm-eval's uniform draws, estimated with a
  fixed seed. This removes about 60% of the neutral-colour substitutions; the
  calibration scores did not change measurably. `static_descriptor` exposes the local
  and spread estimates as `equilibrium:*` columns; the fit above uses them.
  Estimates are too dark when element colours are unknown (neutral colour
  priors), so they serve as model inputs, not as display values.
- **Facet agreement.** Against the bundled engine-ruler memberships, the
  out-of-fold source-derived memberships with a cross-fitted quantile remap
  agree per group: Energy 0.53, Brightness 0.57, Colour 0.47, Movement 0.63,
  Comfort 0.81 (descriptor v1: 0.53, 0.56, 0.45, 0.63, 0.81). Evidence:
  `facet-agreement-r6-eq3.json` in the calibrated-display evidence folder.
- **Agreement ceiling and switch criterion.** Two measurements of the same 84
  presets, emulator captures (other audio) and the engine ruler, agree on
  Energy 0.86, Brightness 0.81, Movement 0.93 and Comfort 0.92. No source
  estimate can be expected to beat that. Proposed criterion for building a
  facet group's bundled values from source instead of renders: whole-pack
  out-of-fold agreement with the ruler reaches 90% of this ceiling (Energy
  0.77, Brightness 0.73, Movement 0.84, Comfort 0.83). Colour has no emulator
  saturation or hue measurements yet, so its ceiling is open. Evidence:
  `facet-agreement-ceiling.json`.
- **EEL loops and memory.** `loop(n, body)` lowers to a plan (`eel_memory.py`)
  with projectm-eval semantics: n is read once, truncated and capped at
  1,048,576. `megabuf` (one buffer per preset, shared by all its equation
  blocks) and `gmegabuf` (process-wide) are versioned, zero-initialised
  buffers read through a `memory:<space>` input. Each write gives a new
  version; an index addresses item int32(index + 0.0001), valid in
  [0, 128·65536). A buffer that no block of the preset writes reads 0. The
  frame program carries the buffers as frame state, so shape and wave code
  read the frame's writes. `while` loops remain unresolved. Stims marks
  memory-dependent outputs as unresolved, because other phases can write the
  same cells.
- **Readonly render values.** The illustrator supplies `aspectx`/`aspecty`
  (RenderContext invAspectX/Y: 1 and long/short), `pixelsx`/`pixelsy` and
  `meshx`/`meshy` from the declared context.
- **Point samplers.** A sampling policy with `linear: false` (`sampler_pw_*`,
  `sampler_pc_*`) reads the GL_NEAREST texel floor(u·size). Evaluating it
  bilinearly left weights of about 1e-7 on the texel two away, which a strict
  `> 0` test turns into real output.
- **r20 (`amandio c - prime forms 2 …`) v1 → v3.** v1 was black: shape 0 draws
  1,024 instances at positions that per-frame code writes into `gmegabuf`
  inside `loop(1024*c, …)`. The loop count reads the previous frame's `c`. v2
  draws the instances, which seed a Conway-like excitable medium in the warp
  (green channel); the composite colours its edges cyan. In v2 the fronts ran
  1.67 px/frame to the right because of the point-sampling defect. An
  identity-composite variant against the native ruler located the defect
  (diagnostic only). v3 matches the capture: luma 0.532 vs 0.567, blurred
  correlation 0.85, and the canvas front extents agree within 1 px. The pixel
  phase of the stripes differs, because sub-pixel dots rasterise to slightly
  different seed pixels. Re-predicting r8–r19 gives unchanged results.

- **Stochastic wave recurrences.** Custom-wave per-point and per-frame state
  that calls `rand` is kept: the recurrence is collected with `rand`-aware
  input analysis, and `rand` is drawn from a seeded generator
  (projectm-eval: uniform on [0, max(1, floor(x))], one draw per call and
  point). Exported statistics use a fixed seed; the illustrator uses a seed per
  frame. These are draws from the authored distribution, not the engine's
  random stream. A position channel that equals a state update (`x=mx`) takes
  the state's end-of-point value, so each random step is drawn once.
- **r21 (`LuxXx - squdgesquid ii`) v1 → v2.** v1 drew smooth red-orange
  hexagonal bands. Four custom waves draw 512-point random walks, and those
  waves were dropped, so the red reaction field had no seeds. v2 draws the
  walks. The warp sharpens red against its blur; green grows where red is
  below 0.357 and blue where it is high. The composite folds local peaks into
  six fins. The field is chaotic: display luma swings between about 0.07 and
  0.23, and the emulator screenshot caught a dark moment. Over frames 60–149
  the predicted luma is 0.152 (10th–90th percentile 0.066–0.222) against the
  capture's 0.136 (0.072–0.230). Diagnostics against the native ruler: the
  canvas red coverage is 0.74 vs 0.87, and the exported composite applied to
  the ruler canvas gives red 0.53 vs 0.51. Remaining gap: decay written as
  `1 − 0.01·equal(frame%6, 0)` has a closed-form mean, but the range analysis
  leaves it unresolved. It has no effect here, because projectM does not apply
  decay to custom warp shader output.
- **r22 (`Rovastar - Cosmic Tornado - mash0000 …`) v1.** Understood on the
  first prediction: a centred audio ring, swirled and zoomed into a vortex tube
  with pastel trails (luma 0.217 vs 0.212, blurred correlation 0.996). The SDK
  text matched as well, except that it called trail persistence unresolved:
  with a custom warp shader the decay control is null. The recipe now carries
  `render.feedback.warp_transfer`, the exported warp evaluated on flat colours
  (here gain 0.977 per frame, about 30 frames to halve), and the SKILL reads
  it.
- **Custom-wave scopes.** A wave per-frame variable that its code writes but
  init does not set persists across frames from 0, so it is wave state. A wave
  per-point name that no block of the wave writes reads 0, because wave
  contexts only see q and t copies of other blocks. Point colours that read
  main per-frame state through inlined Q graphs keep their programs (status
  `frame_state_point_colours`, `frame_inputs`) for frame stepping, without
  statistics. EEL bitwise `&`/`|` evaluate as (int64)a op (int64)b. An
  undrawable point cloud is skipped with a limitation instead of stopping the
  illustration.
- **Random noise palettes.** 1,480 bundled presets redraw `mq21..mq31` with
  `rand()` when `sin(time·0.5)` passes a threshold, and use them as
  per-channel noise-subtraction windows in their shaders. projectm-eval's
  generator is a process-wide Mersenne Twister with a fixed seed, so a fresh
  process is deterministic, but in the app the stream depends on what ran
  before. The palette of these presets is a draw, and the ruler's colour
  facet for them is one draw.
- **r23 (`i poison my plants with my piss - i am for you nz+`) v1 → v4.** v1
  was pink/magenta and the capture yellow/orange/red. None of the three custom
  waves was drawn (bitwise `&`, uninitialised wave state, main-frame state in
  colours), and the inverting composite turned their missing colours into
  excess blue. Native-ruler variants with shifted random streams kept the
  engine canvas blue at 0.63–0.74, while our seeds stayed at 0.87–0.89 display
  blue: a model gap, not the draw. v4 draws all three waves. Its time-averaged
  colour over frames 60–149 is 0.84/0.47/0.43, against the capture's
  0.83/0.54/0.30 (frames 60–149) and 0.95/0.47/0.42 (frames 150–299).
- **r24 (`suksma - sac ur bozz wid da kreamz`) v1.** The frozen prediction has
  the capture's golden metallic palette and brightness (time-averaged colour
  over frames 60–149: 0.35/0.29/0.14 against 0.40/0.29/0.15). The frame layout
  differs because the warp blur radius is `sin(bass·90)·rad`: a 0.01 change in
  bass moves it by up to 0.9, so the per-frame layout depends on audio band
  precision. The SDK text expected a small figure on a dark screen. It read the
  wave footprint as coverage, while the composite maps the whole canvas
  through the `seaweed` texture: an open SDK gap.
- **Whole-pack re-export r7 (loops, memory, stochastic waves).** The refit
  on r7 summaries matches the previous fit within ±0.004 on every statistic
  and facet group. The per-preset fixes are real, but they do not move
  whole-pack averages.
- **Negative result: control time series.** Columns summarising the authored
  per-frame controls (zoom, rot, warp, dx/dy, decay and so on) over the
  declared band sequence correlate weakly with the measured motion
  (|ρ| ≤ 0.27). Adding them left every out-of-fold score within ±0.004, so
  they were removed again (evidence: `fit-report-r7-control-series-negative.json`).
- **Stage transfers.** `stage_transfer` now binds the frame clock, readonly
  render values and the stepped frame program. Before, it lost the transfer of
  about 43% of custom warps and 47% of custom composites in a sample,
  because their programs inline per-frame graphs.
- **Offline compile evidence for the whole pack.** The translator plus the
  GLSL ES 3.00 validator accept 7,745 of 7,776 custom warps and 7,800 of
  7,826 custom composites. Per-preset manifests feed `corpus_understanding.py
  --compile-manifests`, which removes the "native selection unresolved"
  conditional from about 7,800 presets.
- **Still presets.** The ruler measures 483 presets as still (frame
  difference < 0.003, no brightness jumps): 314 black, 35 white and 134
  frozen. They dominate the largest individual Energy over-estimates, but most
  are already predicted calm (median predicted activity percentile 0.10 with
  r8c). Only about 50 of the 483 are predicted above the median, so they are
  a small lever for whole-pack Energy agreement.
- **r8c whole-pack export (shipped model).** It combines offline compile
  evidence with stage transfers that bind the per-frame state. Facet
  agreement with remap rises on every group: Energy 0.537, Brightness 0.585,
  Colour 0.504, Movement 0.635 and Comfort 0.815 (r7: 0.528, 0.571, 0.475,
  0.629, 0.811). The steady-state estimate separates ruler-black presets
  (median display luma 0.013, 47% below 0.01) from random ones (0.142, 23%).
  Evidence: `fit-report-r8c.json`, `facet-agreement-r8c.json`,
  `band-eval-r8c-oof.json`.

- **Composite hue shader.** Composite evaluations now bind `hue_shader` /
  `_vDiffuse` to the engine's composite vertex colour
  (`FinalComposite::ApplyHueShaderColors`). Four corner shades cycle with
  time, are normalised to 0.5–1 and are interpolated bilinearly over the
  screen. The engine's per-load random offsets are taken as zero, so the
  cycling and range are exact and the hue placement is illustrative. 1,200
  bundled presets read `hue_shader`.
- **r25 (`suksma - pus on my cat - j4+ - cubby`) v1 → v2.** v1 was mostly grey,
  while the capture shows bright neon blocks with glossy embossed edges. The
  composite multiplies by `pow(hue_shader, ret)`, and v1 had no hue shader.
  v2 matches: luma 0.647 vs 0.628, saturation 0.41 vs 0.49.
- **Hue-shader descriptors (shipped).** Refitting r8c with descriptors that
  include the composite hue shader leaves facet agreement within noise
  (Brightness 0.592, others within 0.003 of r8c) and raises luminance to
  0.641. It is shipped so the model matches the descriptor code used at
  prediction time.

- **Spectrum-mode custom waves.** With `bSpectrum=1`, `value1`/`value2` read
  the engine spectrum of the declared PCM window, computed as in projectM
  `PCM::UpdateSpectrum` with `MilkdropFFT`: two-tap damping, an envelope over
  480 samples, a 1,024-point FFT and equalisation `−0.02·ln((512−i)/512)`.
  The values are resampled by (512−sep)/samples, smoothed and scaled by
  0.15·scaling·waveScale. 2,229 bundled presets have such waves. Engine
  per-point inputs (`value1`, `value2`, `sample`) are never treated as main
  per-frame state.
- **r26 (`suksma - more pathetic attempts … evil dog collar`) v1 → v2.** v1 had
  the right look but was about 40% too dark over time. Both custom waves are
  spectrum waves and were drawn as vertical lines instead of the engine's
  diverging lyre curves. The steep composite turned the thinner bright tail
  into the brightness gap. v2 matches: luma 0.476 vs 0.459, colour within
  0.02 per channel.
- **r27 (`Serge + martin - crystal palace bubble003a`) v1.** Understood on the
  first prediction: an amber log-polar composite over a ring, dot clouds and
  short smeared trails (luma 0.336 vs 0.317, saturation 0.61 vs 0.60, blurred
  correlation 0.86). The SDK text got the construction right but left the
  palette unresolved. The composite's flat transfer only reports grey levels.
- **r9 whole-pack export (spectrum waves; not shipped).** Refitting on the
  export with spectrum-mode waves leaves the calibration within noise
  (luminance 0.644, frame difference 0.711, flow 0.678, jumps 0.765,
  saturation 0.635, warm/cool 0.605). Facet agreement with remap is
  marginally lower: Energy 0.532, Brightness 0.591, Colour 0.503, Movement
  0.631, Comfort 0.813 (r8c-hue: 0.536, 0.592, 0.501, 0.634, 0.813). The
  r8c-hue model stays the fixture. Spectrum waves change how 2,229 presets
  look in the illustration, but the refit shows no measurable gain from
  them in the whole-pack statistics. Evidence: `fit-report-r9.json`,
  `facet-agreement-r9.json`.
- **Dark built-in waves cut the canvas.** Built-in wave blending took its
  coverage from the line colour, so a near-black wave never darkened the
  feedback. projectM blends the wave at its alpha whatever its colour, and
  with `bMaximizeWaveColor` a wave whose largest channel is at most 0.01 is
  drawn as authored, i.e. near black. Coverage now comes from the raster mask.
  Recipes add `effective_base_radius_model_units` (base plus `wave_mystery`)
  for circle modes, and `max_normalise_rule` with `value_at_unit_bands` for
  maximised wave colours. Custom warps that keep one channel and clear another
  now report `per_channel` persistence (`channel_selective`) instead of a
  misleading channel mean.
- **r28 (`Flexi - splatter effects 22`) v1 → v2.** A red-only warp (`x +
  blur1 − blur3`) grows splatter from seeds, shown through an amber composite.
  The wave colour `(treb+bass)·0.005` sits on the 0.01 maximise gate, so the
  small centre ring flips between orange and black. In v1 the black ring never
  reached the canvas, the central hole never grew and the display stayed too
  dark over time (luma 0.20 vs 0.27). The native-ruler canvas located the
  miss: red coverage matched to frame 30 and then ran 0.06–0.10 high. v2
  tracks the ruler canvas (0.509 vs 0.506 at frame 100) and the capture
  (frames 60–149: luma 0.257 vs 0.267, saturation 0.458 vs 0.460, blurred
  correlation 0.86). Other checkpoints are unchanged except r21's chaotic
  frame-150 snapshot (its time average is unchanged). Open: the SDK text still
  calls the screen mostly dark, because no mechanism names the
  difference-of-blurs pattern term.
- **Band-pass feedback (`blur_difference_feedback`).** A warp lane that adds a
  finer level of the fed-back image (main or blur1) and subtracts a coarser
  blur sharpens features between the two scales every frame, so seeds grow
  into splatter, cells or edges that cover the canvas. The detector reads
  signed coefficients per sampled surface through component selections and
  constant blur decodes. It fires on 80 of a 600-preset random sample (477
  with warp code), mostly main against blur1, blur2 or blur3. It does not see
  band-pass terms behind `if` branches. With it and per-channel persistence,
  the r28 v3 SDK text describes the splatter spreading from the seed ring.
  Its brightness ("dim", from `display_estimate` 0.15, interval 0–0.39 against
  a measured 0.27) waits for a whole-pack refit that includes the mechanism.
- **r29 (`phledge lasso blaq wholes …`) v1.** Understood on the first
  prediction. Four instanced shape layers and two waves seed channel-selective,
  self-advecting warp and composite shaders, so the field churns and strobes.
  Single frames differ (luma swings 0.3–0.65 within a few frames). Over frames
  60–149 the prediction matches: luma 0.490 vs 0.474, RGB within 0.02 per
  channel, saturation 0.122 vs 0.126, frame difference 0.41 vs 0.34. The SDK
  text gave a dense churning, washed, grey-based bright field with possible
  flicker.
- **r30 (`TonyMilkdrop - Tricolors … Isosceles edit`) v1.** Understood on the
  first prediction: a glowing rounded triangle with a streak over a dark,
  finely advected field (single-frame blurred correlation 0.986; frames 60–149
  luma 0.067 vs 0.069, correlation 0.998). The only difference is the inner
  tint: the composite multiplies by `pow(hue_shader, 6)`, and projectM draws the
  hue phases from `std::random_device` at every load, so the placement is
  random by construction. The recipe now carries `render.composite.hue_shader`
  (periods, range, random phase) from the export's `native_colour_generators`,
  which `preset_understanding.py` had dropped. The SDK brightness (estimate
  0.26 vs measured 0.07) waits for the refit.
- **Large per-point programs and wrapping warps.** Custom waves whose
  per-point code projects 3D Lissajous points in perspective produce 234–334
  graph nodes, over the 256-node control export, so their positions and
  colours were dropped and the waves never drawn. Per-point programs now
  export up to 1,024 nodes. A record whose colours stay unresolved keeps its
  closed-form positions (`positions_only`, drawn in the wave's
  `authored_rgba`), and recipes show frame-state point clouds. A warp taking
  `frac(ret − k)` wraps levels around the range: `warp_transfer.wrap` reports
  the shift per frame and the cycle length (intent `level_cycling`) instead of
  a halving time.
- **r31 (`shifter - lattice (eclipse) … aa bb`) v1 → v2.** v1 drew a calm red
  field; the capture is a multicoloured cellular liquid texture with a red
  radial burst (frame difference 0.18). The native-ruler canvas showed
  hundreds of radial coloured lines from three custom waves that v1 dropped
  (export budget). v2 matches: screenshot luma 0.302 vs 0.286, saturation
  0.80 vs 0.82; frames 60–149 luma 0.250 vs 0.235, blurred correlation 0.87,
  frame difference 0.20 vs 0.18. The v2 SDK text describes a full-screen
  flowing field whose colours cycle every 6.6 s. r21's chaotic time average
  moved to 0.139 (capture 0.123).
- **r32 (`A Bit Storm … dancing petals`) v1.** Understood on the first
  prediction: the same mirror-symmetric fan of white stripes, central column
  and bottom speckle (frames 60–149 luma 0.550 vs 0.535, saturation 0.037 vs
  0.038, frame difference 0.13 vs 0.14). The snapshot tint differs (lilac vs
  yellow-green). A full-screen additive quad draws `int(rand(4))/3` colours
  every frame and shape colours follow beat-triggered random seeds, so the
  per-frame tint is a draw from projectm-eval's process-wide random stream.
- **r10 whole-pack export (dark-wave fix and band-pass mechanism; not
  shipped).** Refit within noise (luminance 0.644, frame difference 0.712,
  flow 0.677, jumps 0.765, saturation 0.636, warm/cool 0.605). Facet agreement
  with remap is marginally higher: Energy 0.537, Brightness 0.596, Colour
  0.502, Movement 0.635, Comfort 0.812 (mean 0.6164 vs 0.6152). Later
  descriptor changes (r31–r33) make an r11 export the consistent candidate.
  Evidence: `fit-report-r10.json`, `facet-agreement-r10.json`.
- **r33 (`undulant safe preyre --- Isosceles edit`) v1 → v2.** The capture is
  solid white. The warp divides by a canvas sample
  (`mscale = 1/tex2D(sampler_pw_main, (q20, .004)).z`, `q20` never set). The
  canvas is cleared at load, so this is 1/0 = ∞, the compound `i *= mscale`
  gives NaN, and the RGBA8 target stores 0: black is absorbing, and the
  inverting composite shows white. v1 started from the flat-field state
  (white, another fixed point) and refused the non-finite division. v2 starts
  from the cleared canvas and uses IEEE semantics: solid white for the whole
  clip. The recipe's steady state and flat transfers now carry the absorbing
  black canvas, and the v2 SDK text describes a light, pale, inverted screen.
  Earlier checkpoints are unchanged (r21 is chaotic).
- **Per-load shader switches.** `rand_preset` is four `floatRand()` values
  drawn when a shader is built, i.e. once per preset load. Recipes report
  comparisons of a component with a constant as `per_load_random` switches
  with their probability, add a `per_load_variant` intent effect and append a
  sentence to the description. The illustration holds `rand_preset` at 0.5.
- **r34 (`suksma - … painterly oil reflection - flacc spher`) v1.** Brightness
  over time, layout and motion match (frames 60–149 luma 0.41 vs 0.40,
  correlation 0.835), but the capture is a soft mirrored glow while the
  prediction shows sharp tunnel streaks. The composite branches on
  `rand_preset.x >= .4` (tunnel distortion and doubled blur in 60% of loads).
  Rendering the other branch as a diagnostic reproduces the capture (luma
  0.736 vs 0.762, edge energy 0.0027 vs 0.0028, correlation 0.76). The v4
  SDK text states the 60/40 split; what each branch changes is not yet in
  the recipe.
- **r35 (`amandio c - green machinery 2 …`) v1.** The prediction matches on
  the first attempt: a cyan/blue spiral vortex with bright filaments (frames
  60–149 luma 0.344 vs 0.380, saturation 0.60 vs 0.57, correlation 0.66). The
  SDK text gets the self-advecting texture and long persistence but calls the
  palette grey. Audio-driven shader colour channels leave the recipe without
  a hue, and the spiral form is not named. Open SDK gap: a hue summary for
  shader colour that the illustration resolves.
- **Random redraws.** Per-frame state updated as `select(condition, …rand…,
  itself)` (the random-palette template, about 1,480 bundled presets) is
  reported as `render.random_redraws`: the q values it feeds, the event times
  of the condition (first 60 s, bands at 1) and the period. r35's colour bands
  are redrawn at 3.1 s and every 12.6 s; the v2 SDK text now says the palette
  is a random draw that changes at those moments.
- **Noise volumes.** `tex3D(sampler_noisevol_lq/hq, …)` reads 32³ volumes
  (`MilkdropNoise::generate3D`: lq random per texel, hq random every 4th texel
  with cubic interpolation, seeded from the clock, so their content is a draw
  per process). The illustration used a 2D stand-in and ignored z; it now
  samples deterministic stand-in volumes trilinearly with wrap.
- **r36 (`Flexi - emergencey 2 --- Isosceles edit10h rings`) v1 → v2.** The
  magenta lace frame matched from v1. The composite subtracts volume noise
  wherever the inverted canvas is bright, which gives the capture its moving
  multicoloured patches. With volumes, frame difference rose from 0.009 to
  0.024 (capture 0.033) and the time-averaged correlation from 0.13 to 0.46.
  The interior hue remains a draw. Elsewhere r13 and r35 improved and r23's
  time-averaged luma moved from 0.548 to 0.633 (capture 0.584).
- **r37 (`fiShbRaiN - molecule mind`) v1.** Understood on the first
  prediction: a dim grey concentric tunnel with a translucent central panel
  (single-frame blurred correlation 0.956; frames 60–149 luma 0.139 vs 0.145,
  correlation 0.985, frame difference 0.0078 vs 0.0079). The SDK text matches.
- **r38 (`suksma - martin - neon space ps3 …`) v1.** Understood on the first
  prediction. It strobes (luma 0.02–0.34 within a few frames), so single
  frames differ. Over frames 60–149: luma 0.117 vs 0.133, RGB within 0.04,
  saturation 0.70 vs 0.69, correlation 0.82. The SDK text gave a neon field on
  deep blue with magenta mid-tones, cyan peaks and pronounced flashing.
- **r39 (`suksma - more Martinik theft`) v1.** Understood on the first
  prediction: a bright cyan/blue/white tiled grid with a white cross
  (single-frame correlation 0.991; frames 60–149 luma 0.687 vs 0.723,
  correlation 0.996). The SDK text gave a bright, cool point-dust scene.
- **Additive line waves accumulate.** GL adds every segment of an additive
  wave, so self-crossing or retraced strokes build up. Line waves were drawn
  into one layer per thick pass, so overlaps were not counted. They now add
  each segment's pixels (`_gl_line_pixels` with segment indices; a segment's
  end pixel belongs to the next one). Alpha-blended waves keep the per-pass
  blend.
- **r40 (`Phat+EoS 3way=)`) v1 → v2.** Three additive 512-point Lissajous
  loops in orange, magenta and blue overlap until they saturate to white,
  over yellow textured shapes. v1 drew tinted rings at half the brightness.
  v2 matches the capture: screenshot luma 0.587 vs 0.579, RGB within 0.012,
  per-frame luma within about 0.01. Frame difference is still low (0.048 vs
  0.110); the video echo orientation follows the audio sum every frame.
- **r11 whole-pack export (fe62a985).** Refit within noise (luminance 0.646,
  frame difference 0.710, flow 0.681, jumps 0.765, saturation 0.638,
  warm/cool 0.602). Facet agreement with remap: Energy 0.532, Brightness
  0.598, Colour 0.502, Movement 0.639, Comfort 0.812 (mean 0.6166 vs r8c-hue
  0.6152). Most of the r28–r40 fixes change the prediction image and the
  recipe, which the whole-pack calibration does not read, so pack-wide
  agreement stays flat. Evidence: `fit-report-r11.json`,
  `facet-agreement-r11.json`.
- **r11 shipped.** The fixture model is now r11 (fe62a985 descriptors) and
  the activity reference was refreshed from its out-of-fold predictions. Band
  results are within noise of r8c-hue: main group 64.7% overall, 76.7% on the
  90 capture-checked presets (r8c-hue 75.6%), 84.3% at high confidence on 24%
  of presets (unchanged); calm/intense swaps 1.4% (held-out 2 of 90 vs 1). It
  is shipped because it matches the descriptor code used at prediction time.
  Evidence: `band-eval-r11-oof.json`.
- **Per-frame video echo.** Patch 0008 makes the engine apply this frame's
  `echo_orient` (truncated, mod 4), `echo_zoom` and `echo_alpha`. The legacy
  composite in the illustration used the midpoint of each range; it now uses
  the stepped per-frame values. r40 v3: single-frame correlation 0.984 (v2
  0.605), frame difference 0.112 vs 0.110, because its echo mirror flips with
  `int(bass_att+mid_att+treb_att) % 4`.
- **r41 (`Stahlregen - Eckshack's Eyeball (floater mix) (Plastic)`) v1.**
  Understood on the first prediction: the same dark swirling tunnel with grey
  ribbons and blue/green accents (single-frame correlation 0.85, frames 60–149
  0.89), about 20% darker late in the clip.
- **r42 (`suksma - staining aethers of lovegrudge barfpain`) v1.** Everything
  drawn matches (correlation 0.996; red and blue channels equal), but the
  background is solid green in the prediction and black in the capture. q5–q8
  are never written, so the warp's `uv = mul(uv, float2x2(_qb))` collapses to
  a constant and the background samples a single `noise_lq` texel, keeping
  channels ≥ 0.9. projectM seeds that texture from the clock, so the
  background is black in about 73% of processes and a saturated colour
  otherwise; our stand-in texel has green ≥ 0.9. Open: a recipe note when
  noise is sampled at constant coordinates.
- **r43 (`EoS - glowsticks v2 03 … [roaming]`) v1.** Understood on the first
  prediction: a tiled kaleidoscope of glowstick arcs (single-frame correlation
  0.979; frames 60–149 luma 0.157 vs 0.166, correlation 0.998, frame
  difference 0.042 vs 0.043). The SDK text misses the tiling.
- **r44 (`ORB - Comic Book Curves 2 …`) v1.** Understood on the first
  prediction: smeared blue-violet strokes with dark arcs (frames 60–149 luma
  0.272 vs 0.285, correlation 0.982, frame difference 0.133 vs 0.130).
- **r45 (`LuxXx - The Feeder II`) v1.** Brightness matches until about frame
  105, then the capture darkens while the prediction stays white. A q-probe
  (diagnostic) shows the beat state agrees but `q8` is offset by a constant
  from frame 0. `q8` accumulates `pow(1.2·bass + 0.4·bass_att + …, 6)/fps`,
  about 3,700 on the loud first frame, so a 0.1% band difference moves it by
  tens of units. The warp centres are `sin(k·q8)`, so the layout is chaotic
  with respect to tiny audio differences: unpredictable by construction.
  Open: an SDK note for amplitude-sensitive accumulators.
- **r46 (`amandio c - the green machine 4 - radial nature sludge …`) v1.**
  Understood on the first prediction: a strobing green field whose per-frame
  luma follows the capture (0.68/0.67 at frame 15, near 0 at frames 45 and
  105). Frames 60–149: luma 0.139 vs 0.127, correlation 0.78, frame
  difference 0.109 vs 0.112.
