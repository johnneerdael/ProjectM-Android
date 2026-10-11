# Static behaviour and mood implementation plan

> Use subagent-driven-development for independent evidence modules and executing-
> plans for coupled integration in the existing worktree. The user approved the
> direction and activated the goal; no additional approval gate is needed.

**Goal:** Improve source-only activity classification by quantified flashing,
motion and prominence, preserving uncertainty and source semantics.
**Architecture:** Extend typed source analysis, export three evidence groups and
join them into a versioned behaviour scorer. Reuse optional proof/symbolic/compiler
facilities selectively, with no display simulation.
**Tech stack:** Existing Python analyzer, pinned ProjectM-TV readers, SymPy/Z3,
optional compiler IR; unchanged Android/AAR.

## 1. Baseline and contract
- [x] Read current activity/mood/extraction paths and save fixed2000/100 identities.
- [x] Record current quantified fields and unassigned bands; freeze new thresholds
  as preference assumptions independently of the cohort/human labels.
- [x] Define evidence groups (`flashing`, `motion`, `prominence`), physical units,
  interval/premise/provenance fields and explicit consumer signatures.

## 2. Mathematical producers (independent files)
- [x] Flash evidence: first controls for high/low contrast, unreachable gates,
  smooth high-frequency pulses, alpha/modulo crossings and shared event schedules;
  then use qualified source ranges/derivatives and predicate proofs.
- [x] Motion evidence: first translation/rotation/zoom combined cases, inverse
  map direction, zero-neutral, singular/spatial/unknown cases and explicit FPS;
  then reuse native transport and source derivative machinery.
- [x] Prominence evidence: first tiny/transparent/offscreen/viewport-covering/
  attenuated/overlapping cases; then derive clipping/material/transfer intervals
  while preserving unresolved history and contrast.
- [x] Run focused tests after each producer and repair/retest exact failures.

## 3. Consumer and preference mapping
- [x] Add `static_behaviour` to source description; preserve existing fields and
  include context/policy identities in export/cache identity.
- [x] Implement `score_static_behaviour(evidence, preferences=None)` with activity
  range, bands/reasons and missing contributions. Never fill p95 fields from
  deterministic upper bounds or promote estimates into native certification.
- [x] Test calm/mid/intense controls and transparency/disconnection/unknown
  rejection, overlap25–30/70–75 and strict no-flash Chill eligibility.
- [x] Document schema/units/assumptions and update AGENTS in the same branch.

## 4. Real source qualification and continued gap reduction
- [x] Compare baseline/new facts and scores on unchanged fixed2000; report exact
  affected filenames/hashes, unknown causes by prevalence and component visibility.
- [x] Recheck known human examples without fitting to their individual outcomes.
- [ ] Prioritize any missing frequent flash/motion/prominence calculation and
  implement/retest it before declaring completion.
- [ ] Run prepared suite, schema checks,100-source paired export and independent
  spec/correctness review; freeze source during each qualification run.
- [ ] Commit/push increments, export report/evidenceZIP in Downloads, audit full
  objective. Leave goal active when required behaviour remains incomplete.

Useful commands (prepared environment required):
```sh
MILK_SYMBOLIC_PYTHON=/Users/jneerdael/Scripts/source-analysis-evaluation/python-env/bin/python MILK_PROOF_PYTHON=/Users/jneerdael/Scripts/source-analysis-evaluation/python-env/bin/python build/preset-lab-venv/bin/python -m pytest tools/milk-analyzer/test_source_activity.py tools/milk-analyzer/test_source_vertex_motion.py tools/milk-analyzer/test_mood_scoring.py -q
```
All final adapter/environment inputs remain in the completed component
qualification JSON under build/preset-corpus; revalidate before full-suite use.

## Current ledger

- `a7523167`: source producer integration, fixed2000 qualification, prepared
  3406tests+92subtests and strict docs. Zero automatic eligible bands; goal not done.
- `85786b63`: generic unknown-activity Chill guard and independent bounded producer
  retention. Focused124 originals retain124reports and113usefulhues;152prepared
  neighboring controls pass. Mathematical prominence gaps remain.
- Candidate index/outer-fold port is being integrated separately after16new and
  12existing controls; original grind231 recovers structural captures only.
- Editable preference argument, final100 exports and successive integration
  qualification checkpoints are now implemented/verified. Broad flash/movement
  gains and useful validated whole-preset grouping remain unfinished.
- Ruling: do not turn known zero-valued partial components into calm suggestions
  when remaining activity is unresolved. Historical results are preserved.
- Ruling: producer-local bounded caches and partial failure records retain
  independent colour/flash/motion facts; no missing range is invented.

- `7a01c8f0`: original typed index/outer capture port,65focused controls, minimal
  optional schema addition; no upstream Java/source dependency.
- Final v5 fixed2000 run:2000 behaviour reports,1552 useful hue descriptions,
  367conditional activity estimates;0automatic eligible bands.100 paired exports
  pass schema/model identities and unknown-activity rejection. Goal remains active.
- Fresh review findings repaired: instance resampling multiplicity, context-domain
  propagation, optional traversal-budget isolation, output clamp and native finite
  domain guards. Native finite ranges are modeled assumptions, not driver evidence.
- `e773a0ae`: legacy/Holder final-response evidence,3552tests+92subtests,
  100source exports and fixed2000 checkpoint; source indices367→378.
- 2026-10-11 input-rate checkpoint: declared772-case profile obtains229finite
  combined geometry records across120presets; same-context scoring ablation204→217
  indices.3633tests+92subtests and100exports pass. Whole-preset eligibility remains
  empty. Uniform final-color source controls now qualify all3bands; experimental
  phase proof remains unintegrated with0first-ten corpus gains.
- Ruling: blur operator bounds remain separate from current drawing because their
  input is previous feedback; no source-age shortcut is used to fabricate scores.
- Next frequent gap to investigate: persistent/instance helper geometry state
  (ma/mx/my occurs in249 saved-v6 presets), plus wave and nonlinear shader motion.
  Review native per-instance reset/order and existing equation-domain proof support
  before implementing any new state inference. Do not fill unknown state values.
- 2026-10-11 sequential-state/colour checkpoint: 3,690 prepared tests plus
  92 subtests, 100 schema/model-valid exports and corrected fixed2000 source run
  pass. Paired shape-output axes are exported for385 presets, stochastic colour
  recipes for98 and aggregate large-group support for330. These are conditional
  descriptor counts; activity indices remain378 and automatic eligibility empty.
  False grayscale claims, embedded operand aliases, division epsilon, live-border
  union and aggregate native-corner/area-rounding bugs are repaired/reviewed.
  See `docs/superpowers/evidence/static-behaviour-2026-10-11-state-colour/README.md`.
  Goal remains unfinished; next proofs must handle visible state steps, waveform
  transport and previous-feedback evolution rather than treating bounded x/y
  positions as known movement speed.
