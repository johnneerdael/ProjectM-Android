# Project history and decisions

## How the work changed

1. Started with genre/preset selection using audio references from
   `/Users/jneerdael/Desktop/audio` and a home-TV audience with editable preferences.
   User sought a large bass-reactive dance collection, then All/Chill/Normal/Party.
2. Native frame/corpus measurement proved too slow and did not meet the intended
   source-understanding goal. A separate baseline producer owned full-corpus
   runs on `followup/quad-line`; do not treat its frame analysis as independent
   static prediction or start a competing run. Historical baseline worktrees may
   have been removed; use this branch's evidence and current filesystem.
3. Built full language/equation/shader parsing, dependency tracking and a numerical
   predictor. Used patched projectM-eval/native semantics, not unpatched upstream.
   Native and predictor errors were attributed separately. Source audits initially
   tracked315 blockers. Subsequent engineering fixes and opt-in strict random-slot
   source contract cleared that focused language subset; that did not certify
   every preset's appearance. Major native fixes were handed to other engineers
   and merged; do not reimplement their historical handoffs.
4. Audited six pipeline areas against original MilkDrop2: parsing/EEL, frame/audio,
   warp/mesh/borders, wave/shapes, shaders/textures/noise/blur, composite/storage.
   Classified discrepancies P/I/M/U/D, with33 I/M findings delivered for engineering
   repairs. The user requires source understanding without blindly copying old
   code or damaging patched native4K/authored-canvas fidelity. PR65 addressed18
   library audit repairs; later source/native patches continued. Exact historical
   details: `docs/superpowers/evidence/six-area-audit-delivery/` and related audits.
5. Previous visual-loop targets included consecutive high-scoring predictions,
   with5% numerical tolerance but strict geometry/trajectories/flash timing.
   These are historical checkpoints, not proof of current static-only mood
   classification. The goal later shifted explicitly to approximate recognizable
   effects and source data usable by computers/LLMs, not pixel-perfect recreation.
6. Evaluated reusable open-source components, then integrated bounded capabilities
   into this predictor rather than replacing it or adopting another renderer's
   semantics. Built static flash/motion/prominence/colour evidence and preferences.
7. Added auditable source SDK/LLM skill, polar-wave recipes, curve/locus separation,
   source projection, correlated RGB, radial feedback and closed-form layer relations.
   Current pending addition separates material-labelled motion from geometric drift.

## Reuse research — do not restart broad discovery

Reports in `docs/research/` are included in the ZIP. Their earlier dated statements
may be superseded by follow-up sections/commits; read the final implementation.

- SymPy: optional pure nominal algebra/differentiation refinement. Never erase
  native casts, singularities, state or arithmetic order. Prototype+real-graph
  qualifications recorded; current adapter is implemented.
- Z3: bounded real/IEEE proof queries, predicates and state-domain checks; unknown
  and timeout preserve uncertainty. Current adapter is implemented.
- SPIR-V/glslang/SPIRV-Cross: selected def-use/control/resource machinery. Inspection
  ES310/auto-bindings are not the AAR's GLES300 runtime. Full helper inlining made
  graphs larger; retain summaries and use targeted passes.
- Naga/Slang/Crab: optional typed IR, bounded derivative and relational-state
  components. Prepared external workers are pinned in source-environment.json.
- Stims: independent dataflow/pattern fixtures and ideas; its Q/reset, random and
  arithmetic policies differ from ours and were not adopted as authoritative.
- Iris glsl-transformer: Java AST/index/wildcard experiment validated. An original
  bounded Python operator/type index and opaque-capture matcher were implemented
  (`source_field_index.py`, fold consumer); do not copy the AGPL Java framework.
- Enzyme: actual LLVM21/Slang helper derivative runtime experiment completed.
  It produced zero new production range bounds/classifications at that checkpoint;
  derivatives alone do not prove texture/history/range/flash behaviour.
- python-flint/Arb, Reachability/LazySets/TaylorModels: later sourced suggestions
  for interval/correlation/feedback work, not integrated/benchmarked gains yet.

## Recent verified increments

- e773a0ae: legacy/nonlinear colour influence,3552tests+92subtests.
- 8e6e9b18: declared input motion and blur-response bounds.
- 6cc20d92: sequential shape layout/private state, stochastic colour/aggregate
  shape support;3690tests+92subtests,100exports. Fixed2000 snapshot retained378
  conditional activity indices,0 strict eligible moods.
- a5920c37: SDK/LLM source understanding, affine polar curves and interior locus;
 3784tests+92subtests,100exports. Full9606 enabled-custom-wave source census:
 4641 wave-containing presets,11417 active waves,438 radial-construction presets,
 53 supported affine-polar recipes across42 presets (38spiral/15circle recipes).
 These are primitive coverage counts before selection/contribution/visibility.
- 2aabf283: screen projection/Y flip, palette storage ordering, radial sampling;
 3890tests+92subtests,100exports/14071exactSDKfacts.
- bada3b01: native macOS GLES source-matched screenshot/10-second evidence.
- ed1833da/6c99bb81: interruption recovery/client-retry documentation.
- 8c0bdfe6: correlated RGB, local/closed-form layer spacing, explicit UV/filter
 envelope;3985tests+92subtests,100exports/14179exactSDKfacts.

A previously quoted84.4% effect/behaviour/colour descriptor coverage was a dated
source cohort quantity, not scene/mood correctness or the current all-corpus score.
Keep all such denominators/profile/model identities explicit.
