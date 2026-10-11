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
