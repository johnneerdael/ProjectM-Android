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
only, followed by an actual-AAR screenshot and10-second low-resolution clip with
declared audio. Compare the general structure, colours, movement and audio response
without requiring exact pixels. Preserve both prior descriptions and subsequent
diagnoses. A failed emulator/capture attempt supplies no native appearance evidence.

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
