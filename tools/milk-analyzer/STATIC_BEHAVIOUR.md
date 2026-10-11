# Source-only behaviour and preference evidence

The experimental export now includes `analysis.visual_description.static_behaviour`.
It derives conditional component evidence from the typed program graph, without
evaluating audio/frame sequences, equations, shaders or rendered images. The patched
source reader parses the preset; compiler evidence may qualify stage selection.

## Consumer fields

| Field | Meaning and units | What it does not establish |
|---|---|---|
| `context` | Declared viewport pixels, feedback frames/second, scalar input ranges | Actual device or input trajectory |
| `flashing.records` | Component brightness delta, RGB-infinity-norm change/second, periodic cycles/second and conditional event schedules | Visible strobe timing or whole-image contrast |
| `motion.contributions` | Conditional viewport-unit/second envelopes, audio partial response, backward-sampling and forward-transport distinctions | Typical optical flow or actual trajectories from displacement alone |
| `prominence.by_component` | Clipped support, opacity, final difference gain and displayed contribution intervals | Guaranteed dominance, visible contrast or accumulated feedback coverage |
| `colour.components` | Source RGB/HSV anchors, hue-family possibilities, conditional final palette and contribution weights | A measured palette or a unique image |
| `shape_state.by_component` | Conditional private-state invariants and per-instance shape-output intervals | Native finiteness, visible speed or mood eligibility |
| `classification` | Known-source potential index, conservative interval, overlapping candidate and eligible preference bands | Calibrated human mood accuracy |

`classification.predicted_bands` uses the known component potential estimate.
Unknown contributing activity suppresses Chill suggestions even provisionally;
zero-valued partial components do not supply a calm point estimate.
`classification.eligible_bands` additionally requires complete bounded evidence;
unknown contributing activity or execution/domain gaps veto eligibility. Consumers
must not automatically classify a provisional Chill candidate as safe/calm. The
source-potential value is not a measured mean, maximum frame intensity or p95.

## Preference assumptions

The initial policy `static-activity-preference-v1` uses references of0.75 viewport
units/second for motion,1 RGB unit/second for brightness change,0.30 RGB units for
flash contrast and2 cycles/second for flash frequency. These are editable future
preference assumptions, not a human-fitted classifier. The overlapping bands remain
Chill1–30,Normal25–75,Intense70–100. Stronger partial evidence can support an intense
candidate; missing effects cannot certify absence of flashing.

Brightness deltas for materials already contain alpha. Their screen weighting uses
support and final difference gain, without multiplying alpha a second time. Motion
uses opacity-weighted displayed contribution. Tiny, offscreen, transparent and
disconnected effects have separate controls. Feedback can grow or redistribute a
source contribution, so an initial small support is not a lifetime ceiling.

The colour producer joins shape centre/perimeter/border colours, wave colours and
qualified transfer rules. It preserves unknown inherited feedback/image colours.
Hue candidates and encoded-RGB temperature tags describe possible ingredients;
they do not prove a warm/cold or psychedelic overall appearance.

## Sequential shapes and random colour

`shape_state.by_component.shape_N.state_domains` reports private variable boxes
whose initialization and complete ordered instance transition have been proved.
`instance_output_domains` reports supported output axes separately. For example,
a reflected sine/cosine walker can have both x/y bounds while its accumulated
angle remains unbounded; an independent tangent axis can remain absent. Native
instance counts and exact engine initialization policy participate in provenance.
See `SOURCE_SHAPE_STATE_DOMAINS.md` for semantics and unresolved conditions.
These nominal layout facts do not replace existing motion or finite-domain guards.

For more than256 configured shape instances, prominence uses one aggregate
polygon-area envelope over the complete instance domain. It sums unclipped area
ceilings and caps union coverage at one, without enumerating every polygon or
assuming overlap/independence. Its lower bound is zero; known invalid native
geometry still prevents transparency certification. The ideal-area upper uses
exact rational arithmetic, a rational upper bound on pi and a conservative sine
series rather than assuming one final floating-point adjustment is sufficient.

`colour.components[].source_palette.stochastic_vertex_colour` describes supported
direct or quantized native random RGB calls, encoded channel bounds, copied-draw
correlation and initialization/frame/instance invocation scope. Separate calls
are distinct values even when their syntax matches; copied values retain their
shared-grey correlation. Live constant or unknown borders remain part of the
combined material box. A refresh scope is a possible invocation source, not a
guaranteed visible flash, uniform RNG distribution or reached palette histogram.

## Reproducible reference and cohort

The default reference is1920×1080 at30 feedback frames/second. A caller may supply
`--behaviour-context context.json` with `viewport`, `feedback_fps`, optional named
`reference_profile` and finite `scalar_input_domains`. These values participate in
cache identity. No context silently changes the authored shader/audio engine.

`static_behaviour_validate.py` runs an unchanged source inventory against frozen
source-bound offline compiler records and one immutable reader per worker. Optional
`--symbolic-python` and `--proof-python` enter reusable SymPy/Z3 worker sessions.
The manifest freezes model, source, reader, context, compiler-record and component
identities. Compressed per-preset rows retain errors and partial evidence. Counts
of useful descriptors or provisional bands are coverage, not appearance accuracy.

Independent producers retain their own partial results when another producer
exhausts its bounded traversal. Producer failures are exported and veto automatic
eligibility. Separate bounded caches prevent one failure from poisoning other
component calculations.

The new builder is still being qualified. See the task plan and saved cohort
results for current checkpoints; a synthetic constant-colour control passing does
not certify general feedback presets.

## Material changes when a texture sample holds fixed

A textured shape fill can now export
`flashing.records[].fixed_unit_texture_material_partial`. This bounds changes in
vertex colour and alpha when the sampled RGBA, geometry, barycentric location and
destination remain fixed. Each texture channel is a declared unit-interval input.
The calculation reuses the existing native-channel, stable-modulo and blend
calculus; over blending includes the destination term from changing alpha.

This is a partial response, not the total displayed change.
`sampling_coordinate_response_included` stays false,
`texture_history_change_rate` stays null and `total_brightness_rate_known` stays
false. Missing texture bindings remain unverified. A positive ceiling does not
prove that a flash occurs. These fields do not alter automatic mood eligibility.

The frozen809-preset descriptor recheck recovers finite partial rates for592 and
finite two-state contrast bounds for643;28 and97 have positive ceilings. Inputs
and exact source hashes are retained in the task evidence. This does not certify
809 full native visuals or replace the unknown texture/history contribution.

Motion evidence retains caller `scalar_input_domains` and reference-profile
identity. Geometry time/audio partials and uniform native transport envelopes
use the union of declared context domains and validated input-scenario domains;
a conflicting interval for the same scalar name is rejected with the same policy
as prominence. Declared amplitude intervals still supply no audio change rate.
The effective domain map and its hash are exported separately from caller context
and scenario identity.

## Declared input change rates

`context.scalar_input_maximum_rates_per_second` optionally maps exact scalar
input names to finite nonnegative change ceilings in engine-input units/second.
It defaults to an empty object. Rates for source/native shader clocks cannot
override their existing seconds basis. An audio input rate is not music BPM,
sample frequency or a value measured by this static analyzer.

For supported shape formulas, `geometry_declared_input_transport` combines the
source-time derivative with independent scalar sensitivities times these rates.
For example, `x=.5+.1*bass; y=.5+.2*mid` with bass rate3 and mid rate4 has centre
speed ceiling `hypot(.3,.8)` viewport units/second. Simultaneous independent
inputs do not cancel each other's bounds. Radius and rotation add the existing
orthogonal perimeter contribution.

The corresponding finite amplitude domains and all contributing rates must be
declared. Unknown state, missing rates, changing topology, source seams, invalid
native conversions and potentially overflowing perimeter additions retain unknown
transport. Qualified combined records exclude their constituent partial records
from total-motion aggregation, while preserving those records for inspection.
The rate map participates in context/cache identity. It does not establish
texture history, dominant screen movement or a whole-preset mood.

## Blur propagation

`prominence.blur_propagation` describes conditional RGB image-supnorm difference
gains from the image supplied to the pinned blur producer, with controls held
fixed. It reuses the existing patched safe-range producer. Each level exports
`encoded_rgb_supnorm_gain_upper`, progressive scale/bias and the separate
`getblur_rgb_supnorm_gain_upper`. An already-expanded `GetBlur` source expression
contains its decode scale; applying the decoded gain again would double-count it.

Nonnegative normalized filtering and clipping are nominally nonexpansive; range
normalization and signed edge-darkening may amplify differences. Native pair-error
bounds remain null, with separate per-pass error coefficients. No frame or image
is generated. RGB-only blur does not carry a changing main alpha lane.

This operator report does not say that current shape/wave injection has reached
the blur bank. The pinned engine updates blur from previous feedback before the
current drawing. Callers must preserve source-age/pass-timing and native storage
obligations; a finite blur operator gain alone does not close the preset's feedback
trajectory or authorize using a shader-site gain as a current drawing gain.

## Uniform final-color cycles

The flash producer identifies `uniform_rgb_over_viewport` separately from a
local color response. `periodic_attainment` states whether a declared single-clock
interval spans at least one complete nominal cycle. For a complete, unclipped,
uniform final RGB program, that attained full-cycle contrast reaches the whole
viewport; its screen weight cannot have an arbitrary zero lower endpoint.

The scorer uses this fact only with a complete source model and qualified final
storage. Spatial patterns, sampled images, clipping, unknown native domains and
short/absent clock intervals cannot use it to qualify strong activity. The result
remains a source preference decision over a nominal cycle, not verified frame
sampling, native precision or a human-calibrated mood. Integrated source controls
now cover Chill, Normal and Intense rather than testing only fabricated input
evidence or constant-color calm output.

`SOURCE_SHADER_PATTERN_TRANSPORT.md` describes a separate experimental exact
phase-translation proof. Its 34 controls pass, but a pinned first-ten corpus
check recovered zero full or partial patterns. It is not integrated into the
primary motion/scoring path and must not be counted as recovered corpus motion.

## Final-output storage and finite shader domains

The default declared home-TV reference uses `output_storage: normalized-unorm`,
matching the app's RGB888 surface choice. Set `output_storage: unknown` for a
consumer whose output storage is not established; that context cannot qualify
automatic activity bands. The storage policy participates in cache identity.

`displayed_output` preserves raw channel intervals and separately applies the
normalized output clamp. Temporal RGB entirely above1 can become constant white;
RGB entirely below0 can become constant black. Raw modulation records remain
unchanged. Partially clipped RGB retains its remaining contrast. A nominal clamp
result alone is insufficient to qualify calm behaviour.

The bounded `native_finite_guard` checks a restricted declared binary32 model:
constants, declared scalar inputs, basic arithmetic, constant casts and finite
sin/cos. It propagates outward enclosures and includes possible subnormal flushing.
Unknown inputs, unsupported operations, overflowing intermediates or exhausted
work remain unresolved. The shader clock domain must be declared with its actual
source input name (for example `_c2.x`); no clock range is silently invented.
Native-model output bounds must also remain consistent with the nominal bounds
within the stated5%width+1e-6 allowance. This rejects tight nominal formulas whose
loss of significance permits much wider native-model values.

These guards retain source assumptions and do not certify driver transcendental
precision or rendered pixels. Repeated overlapping shapes and possible borders
also retain their aggregate local influence when a composite resamples them;
source-area integrals cannot replace that per-texel bound.

## Conditional potential and editable preferences

The scorer now consumes the separate fixed-texture material partial in
`classification.partial_contributions`. It can inform the known-source potential
index after spatial support and final transfer are accounted for. Its lower bound
never becomes total activity, and excluded texture/history trajectories keep
automatic eligibility unresolved. Tiny, invisible and unknown-transfer controls
remain guarded. A source response ceiling can be canceled by other effects; it is
not a guaranteed visible reaction.

A declared behaviour context may include `activity_preferences`, an object of
finite validated overrides for the references in `classification.preference_rules`.
For example `{"motion_reference_vp_s":1.5}` changes the preference mapping while
leaving the underlying physical evidence unchanged. The resolved rules participate
in export/cache identity; unknown names, nonfinite values and invalid thresholds
reject. Bands stay Chill1–30,Normal25–75,Intense70–100.

The first derived scoring-only check on the frozen2000 v5 records retained367
indices and changed0. Subsequent review found two obstacles: many final transfers
were unresolved, and the scorer rejected the producer's `piecewise_lipschitz`
continuity tag. The consumer now accepts that tag for the conditional partial,
while retaining unknown total activity. The original rows and derived snapshot
remain unchanged; they do not measure the corrected consumer's coverage.

## Final color-transfer responses

Legacy gamma is a weighted series of redraws, not a shader power. Its conditional
image-response gain includes the native post-equation gamma/zoom clamps,
unclamped echo alpha, hue multiplication and ordered brighten/darken/solarize/
invert filters. Scalar controls hold fixed across the two compared images.
Echo and portrait aspect expansion can redistribute support across the display.
Finite gain does not resolve the controls' own time or audio response.

Some authored shaders have a finite two-state response but no finite derivative
at zero. For example, `sqrt(x)` changes by at most `sqrt(delta)` for nonnegative
inputs separated by at most `delta`. The optional
`prominence.by_component.*.final_transfer.sampled_colour_modulus` exports one
formula per RGB channel, using terms `coefficient * delta ** exponent` with
`0 < exponent <= 1`. `delta` is the maximum change in the declared sampled RGBA
lanes at fixed sites; masks, uniforms and other inputs hold fixed. It is not
elapsed time or a texture-history change inferred from source.

Contribution bounds use the local encoded-RGBA change ceiling. They apply source
area only when pointwise support preservation is established; arbitrary lookup
keeps full-display support. A blur-site modulus remains useful shader evidence,
but is not joined to an incoming drawing without a qualified main-to-blur
propagation bound: blur normalization can amplify the change. A fractional-power modulus does not acquire
a finite per-second gain. Sample-driven branch seams, unknown or invalid domains,
history-driven lookup coordinates and unresolved shader selection remain guarded.
Nominal modulus bounds exclude native rounding and storage quantization; they
do not certify appearance or remove the unknown accumulated-feedback trajectory.
