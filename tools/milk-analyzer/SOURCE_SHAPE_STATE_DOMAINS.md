# Conditional private shape state domains

`source_shape_state_domains.shape_state_domain_evidence` proves sufficient
nominal real interval boxes from accepted native equation trees. It checks an
initializer and a complete ordered custom-shape instance transition. It does not
execute equations, advance frames, sample audio, or inspect images.

```python
report = shape_state_domain_evidence(
    source, policy='projectmtv-core-2.2.8-v1', shape_index=0,
    initial_variable_policy='native-new-private-locals-zero-v1')
```

Use `state_domains` for proved private state boxes and
`instance_output_domains` for supported shape output intervals. A proved unrelated
private local does not establish a bounded x/y output. Every state box carries
separate proved initialization and transition obligations. Missing axes and
unsupported recurrences remain absent, with `unknown_state_reasons`.

Pass `candidate_domains` to request checks of explicit boxes. Candidates are
obligations, never assumed bounds. Pass `initial_local_domains` only for declared
pre-initializer storage domains. An explicit initializer overwrites these values
in source order. `input_domains` names fresh reset inputs; their domains are
premises and do not certify actual audio or main-frame Q behavior.

## Native boundaries

The zero-allocation policy is opt-in and requires exact `CORE_2334_ENGINE`
identity. It applies only to newly registered private variables in this shape
context. It never resets persistent locals at the next frame or instance, and
does not fill missing main-frame Q values. Without this policy, infer init values
from source assignments or explicit initial local domains.

The pinned source34 implementation supports these boundaries:

- `ShapePerFrameContext.cpp`, `LoadStateVariables`, lines 87–143 reloads shape
  configuration, current frame/audio inputs, post-main Q and post-init T values.
  It does not overwrite arbitrary private locals.
- `CustomShape.cpp`, lines 195–198 performs sequential instance loads and
  evaluations using that same context.
- `vendor/projectm-eval/projectm-eval/TreeVariables.c`, lines 31–68 allocates a
  newly registered private variable with `calloc` and explicitly stores zero.
  Its `reg00`–`reg99` path instead exposes global variable storage.
- Original MilkDrop2 2.25c `vis_milk2/milkdropfs.cpp`, lines 2347–2354 and
  2483–2524 has the corresponding sequential shape loop and reload list.

Shared register use in any equation phase prevents this local proof. Missing
cross-phase trees cannot hide register effects. Memory, loop and unknown control
effects also prevent proof. Unsupported numerical operations taint their own
data dependencies; independent bounded shape axes can still be proved.

## Proof and limits

Reuse the existing exact-rational literal conversion, interval operators and
outward bound export from `source_proofs_worker.py`. Partition `above`/`below`
branches at variable/constant comparisons, conservatively retaining strict
boundary equality. Merge values and every modified branch variable. Preserve
source order and lazy branch evaluation. Reject numerical/comparison operands
containing any embedded write using the existing `_EEL.assignment_targets`
inventory. Native evaluation can retain pointers to variable storage across
operands, so substituting an earlier value snapshot would be unsound. Explicit
ordered sequence and if-branch effects remain supported separately.

Model source34 division's native guard: return zero when the complete declared
divisor interval lies strictly inside `(-.00001,.00001)`, including zero. Use
ordinary real division only when the complete interval lies beyond either
threshold, including equality. Keep intervals crossing this seam unknown. This
guard does not change source34 if truth: every exact nonzero value selects the
true branch. These facts come from `TreeFunctions.c`, lines 296–310 and 567–586;
original MilkDrop2 truth conventions do not override this target implementation.

Source literals and proved init endpoints propose boxes. A bounded abstract
enclosure search operates on arbitrary points throughout those boxes, rather
than concrete state samples. Independently execute one full abstract transition
from the final proposed box and check containment. Remove failed candidates and
recheck survivors, so a successful coordinate cannot depend on a failed helper
box. Init-only private locals can also have constant invariants.

Nominal sin/cos of real arguments supplies `[-1,1]` even when the angle itself
has no bounded invariant. Tan and unproved denominator domains stay unknown.
The authored reflection `.9-x`, then `.9+x` below `.1`, can reach the unit upper
boundary; its interval is not simply `.1..9`. Exact reader-literal arithmetic
exports the sufficient upper enclosure `1.0000000000000002` rather than silently
rounding it down to one.

`native_numeric_certified` and `visible_motion_certified` remain false. Preserve
all finite-input, intermediate overflow, conversion and transcendental library
conditions when consuming this evidence. A nominal invariant does not prove
native arithmetic remains finite forever, continuous movement, a speed bound,
on-screen coverage or mood accuracy. Any future per-frame motion bound must
handle the configured sequential instance count and reflection/wrap jumps.

`source_static_behaviour.static_behaviour` exports this evidence independently as
`shape_state.components` and `shape_state.by_component`, keyed by `shape_N`.
Only native-enabled shapes with positive saved `num_inst` are included. Declared
scalar domains are filtered to fresh reset inputs; the `instance` range is always
`[0, num_inst - 1]` from native configuration, overriding caller declarations.
The private-local zero policy applies only to exact source34 engine identity;
missing main-frame Q domains remain unknown. Model hashes include the shape-state
producer and its rational proof helper. Producer failures stay separate, and
these conditional nominal state/output boxes never clear motion/native finite
guards or certify prominence, appearance, or automatic mood eligibility.

## Qualification checkpoint, 2026-10-11

Prepared controls: 33 new state-domain tests plus 8 equation-domain and 27
optional pinned-Z3 proof neighbors pass (68 total). Controls include generic
reflection/clamp/wrap, bad initialization, oversized steps, unbounded growth,
branch side effects, reset names, init-only locals, failed coupled-box removal,
missing cross-phase trees, configuration identity, unproved divisor domains,
cancelled tan and overflowing intermediates. Native shared-scope controls
reproduce pointer-aliasing writes; dynamic divisor controls cover zero, both
signs inside the guard, both exact threshold boundaries, an outside divisor,
and a seam-crossing interval. Use dynamic inputs because native constant folding
can hide the original division modeling defect.

The saved selection `geometry-helper-state-249-2026-10-11.json` actually contains
253 substring cases, including 249 explicit reflection cases. Every source hash
and saved shader compatibility record was validated using the exact source34
reader and `static_behaviour_validate.bind_compatibility`. The frozen standalone
proof report is `build/preset-corpus/shape-state-domains-253-2026-10-11.json`.
Model, reader and selection hashes are recorded inside it.
The earlier pre-review report is preserved as
`shape-state-domains-253-pre-review-2026-10-11.json`; its producer did not yet
reject operand aliases or model the division guard and must not be used as the
reviewed checkpoint.

Across 797 active shapes in the 253 cases, 450 have proved `mx`, 297 have proved
`my`, and 250 have paired x/y output intervals. Across presets the corresponding
counts are 247, 171 and 127. A tan-containing preset can gain paired bounds from
a different independent shape; these counts do not claim that its tan-dependent
axis became bounded. This checkpoint establishes source metadata coverage, not
image fidelity, native finite arithmetic, activity-score growth or grouping
accuracy. No baseline report or renderer was changed by this producer.
