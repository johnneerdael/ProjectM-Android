# Interval and recurrent feedback library follow-up

Research date: 2026-10-11. Scope: additional source-only bounds for temporal
colour changes, movement controls and feedback, using the existing typed graphs.
This is a research proposal; no component was installed, no new adapter was run,
and no prediction, renderer, device or production dependency was changed.
The historical exact-recreation objective has been replaced by the active goal
of understanding effects and automatically assigning moods across all 9,606
presets. Static analysis plus LLM interpretation should decode and describe
effects, with SDK/skill access and intermediate frozen descriptions paired with
actual-AAR screenshots at 10 seconds under declared audio for human feedback.
Exact pixel recreation is not an acceptance requirement. The [previous component evaluation](2026-10-10-component-reuse-evaluation.md)
and [current adopted components](../../tools/milk-analyzer/SOURCE_COMPONENTS.md)
remain the implementation baseline; their historical goal-status wording does
not define the current objective.

## Recommendation

Evaluate **python-flint/Arb as an optional nominal range backend**, coupled to a
small bounded two-frame/state experiment. Port selected set-recurrence methods
when they carry actual frame relations that independent scalar boxes lose.
Do not adopt an ODE reachability framework as the first implementation.

Arb supplies difficult numerical enclosure work. It does not supply MilkDrop
phase/storage semantics, relational invariants, evolving texture fields or a
flashing classifier. Feed useful bounds and explicit unknowns into effect
descriptions and mood interpretation; preserve the distinction between a
nominal mathematical bound, an actual-AAR observation and a human judgment.
These calculations can improve the evidence used for interpretation without
requiring pixel equivalence or a complete native image/time certificate.

## Existing capabilities and concrete gaps

| Current implementation | Already available | Additional work worth testing |
|---|---|---|
| `source_control_bounds.py` | Independent scalar boxes; nominal time/selected-input rate calculus; fixed-exponent nonnegative powers; clamp/min/max; finite original-argument checks | Restricted-domain trig ranges and derivative ranges; log/exp; variable-exponent positive powers; paired time/state relations rather than holding all predecessor state fixed |
| `source_colour_modulus.py` | Independent two-state input-lane moduli, including Hölder powers below one at zero; finite native scalar limits and original-domain guards | Compose these moduli with declared frame-to-frame input/state differences; retain the distinction between independently changing samples and a common scalar audio direction |
| `source_feedback_envelopes.py` | Affine previous-main RGB coefficient matrices, sum-of-absolute-coefficient gain, conditional contraction and ideal half-life | Forced perturbation recurrences, certified weighted channel bounds, finite-horizon nonlinear modulus propagation, and explicit treatment of changing coordinates/coefficient inputs |

Current trig calculus mostly returns `[-1,1]`, even for a small declared argument
range. Fixed powers use Python `math.pow` plus outward endpoint steps. There is
no documented target-libm error contract here; outward `nextafter` alone is not
a substitute for a library's proved transcendental enclosure. These observations
identify a nominal numerical backend opportunity, not a demonstrated defect in
native output or a measured classification improvement.

Current feedback conditions deliberately exclude drawing, clipping/storage,
blur/history qualification, changing non-image inputs and image-driven sampling.
Any frame recurrence must model these obligations rather than quietly extending
the existing affine colour gain into a whole-frame claim.

## python-flint / Arb: what can be reused

The inspected Python documentation identifies itself as **python-flint 0.9.0**.
The existing separate component environment reports `flint_available False`.
Official install docs list prebuilt macOS Intel/ARM packages and CPython
3.10–3.14 support; this makes a separate evaluation environment plausible, but
no wheel or installed FLINT version was qualified here. Record wheel/library
hashes and actual linked versions in the experiment. [Install documentation](https://python-flint.readthedocs.io/en/latest/install.html)

`arb` represents a real interval by midpoint and radius; the midpoint precision
is configurable and the radius has fixed 30-bit precision. It exposes
sin/cos/log/exp/sqrt, interval union/intersection, finite checks and directed
`lower()`/`upper()` bounds. Exact endpoint binary mantissa/exponent pairs can be
exported with `man_exp()` instead of silently converting bounds to nearest
Python floats. [Python Arb API](https://python-flint.readthedocs.io/en/latest/arb.html)

The general API promises rigorous error enclosures for real/complex operations.
It also documents a global precision context, predicates whose false result may
mean uncertainty, and potentially process-fatal excessive/invalid allocations.
Use the existing bounded subprocess pattern, explicit precision and input-size
budgets. Preserve existing native binary literals as binary values; use rational
or decimal construction only for a separately labelled nominal source literal.
[General concepts](https://python-flint.readthedocs.io/en/latest/general.html)

Python `**` calls FLINT `arb_pow`. The inspected C implementation treats exact
integer and half-integer exponents specially, including integer powers of
negative bases; otherwise it uses log/multiply/exp and contains a special
nonnegative-base interval case touching zero. Pin and test the actual version:
master source is inspection evidence, not the behaviour of a yet-uninstalled
wheel. [Python power binding](https://github.com/flintlib/python-flint/blob/master/src/flint/types/arb.pyx),
[FLINT power implementation](https://raw.githubusercontent.com/flintlib/flint/master/src/arb/pow.c)

Proposed initial operator adapter:

- Evaluate arithmetic, sin/cos, positive-domain log/exp and powers on bounded
  boxes. Feed supported symbolic derivatives into the same enclosure backend.
  For `x**y` with `x>0`, enclose both `y*x**(y-1)` and `x**y*log(x)` only under
  declared domains. Bound all original intermediates before cancellation.
- Treat division through zero, tan poles, fractional negative-base powers and
  unknown branches as unresolved or split their domains with an explicit budget.
  An uncertain Arb comparison cannot select the false branch.
- Retain the current Hölder model at zero. For `0<p<1`, a finite value range does
  not establish a finite derivative. Exact integer negative-base nominal powers
  require a separate source-language/native-domain qualification.
- Preserve externally proved nonnegative domains when an enclosing ball expands
  slightly below zero. Use monotone endpoint enclosures or a qualified domain
  intersection; never drop authored negative possibilities to obtain a result.

The C square-root implementation returns indeterminate for intervals containing
negative values. This cannot replace EEL's `sqrt(abs(x))` policy or introduce a
complex-valued escape for real native shaders. [FLINT square-root source](https://raw.githubusercontent.com/flintlib/flint/master/src/arb/sqrt.c)

**Arb does not preserve correlations merely because two graph nodes refer to
the same ball.** Its author documents dependency overestimation and iterative
blow-up. Higher precision reduces arithmetic error, not the actual declared
input width. Preserve shared variables symbolically or relationally and subdivide
only where useful. [Arb ball semantics and dependency discussion](https://fredrikj.net/arb/using.html)

`arb_series` supplies truncated formal series and derivatives. Its `O(x**n)` is
not automatically a numerical remainder bound over a finite interval; do not
mistake this interface for a validated Taylor model. Its root helper is explicitly
described as a test implementation. [Series API](https://python-flint.readthedocs.io/en/latest/arb_series.html)

The Python wrapper is MIT-licensed; the inspected FLINT sources use LGPL-3.0-or-later.
Keep their identities separate when importing code or distributing binaries.
[Wrapper license](https://github.com/flintlib/python-flint/blob/master/LICENSE),
[FLINT source license](https://raw.githubusercontent.com/flintlib/flint/master/src/arb/pow.c)

## Open-source recurrence methods to port or compare

| Component/method | Concrete reuse | Boundary and adoption decision |
|---|---|---|
| JuliaReach `BOX` recurrence | Compare recursive boxes with an unwrapped affine recurrence, retaining the initial set and each forcing set until the final projection | Port the small fixed-matrix method first. Recursive boxing introduces wrapping. Constant-matrix powers cannot represent arbitrary varying matrices. [BOX method](https://juliareach.github.io/ReachabilityAnalysis.jl/stable/lib/algorithms/BOX/) |
| LazySets zonotopes | Carry joint linear correlations using centre/generators; linear maps and Minkowski sums for private state blocks | Useful after boxes demonstrably lose a relation. Set geometry using ordinary floating-point matrices still needs a rounding-enclosure audit; a set-theoretic overapproximation is not by itself native numeric certification. [Discrete-time tutorial](https://juliareach.github.io/ReachabilityAnalysis.jl/dev/tutorials/linear_methods/discrete_time/), [Zonotope API](https://juliareach.github.io/LazySets.jl/dev/lib/sets/Zonotope/) |
| TaylorModels.jl | Polynomial plus validated remainder for smooth repeated-input formulas; `TaylorModel1`/`TaylorModelN`, domain mincing, range bounding | Compare a small worker only if Arb plus existing symbolic/relational refinement stays too loose. Use interval polynomial coefficients; the official example distinguishes them from Float64 coefficients. Singularities/branches need domain treatment; order/dimension and remainder growth need budgets. [Range-bounding guide](https://juliaintervals.github.io/TaylorModels.jl/dev/range_bounding/) |
| IBEX forward/backward / HC4 contractors | Contract two-frame equations, branch guards and output constraints without removing feasible nominal solutions | Secondary comparison for nonlinear feasibility gaps. Contractor convergence does not prove an inductive invariant. Retain init/transition proof obligations and native language adapters. [Contractor and HC4 documentation](https://ibex-team.github.io/ibex-lib/contractor.html) |

For a fixed affine state map, the unwrapped set formula is
`S_n = A**n S_0 + sum(A**(n-1-j) B_j)` using Minkowski sums. Fresh independent
inputs may be represented independently; a fixed uncertain parameter must keep
its identity across frames. Turning the latter into independent per-frame
uncertainty is conservative in supported cases but loses precision.

A useful small feedback extension is a componentwise nonnegative gain matrix
`M_ij = sum_sites sup(abs(A_site[i,j]))`. Check a candidate positive weight
vector with rigorous arithmetic: `M*w <= g*w`, `g<1`. This can prove contraction
in a weighted sup norm even when the unweighted maximum row sum fails.
The inequality is the certificate; approximate eigenvalues or candidate spectral
radii are insufficient. Same-frame independent sample sites cannot cancel just
because their coefficients have opposite signs.

For varying inputs/coordinates, the proposed perturbation recurrence is
`delta_next <= m(delta) + e`, where `m` is the supported colour modulus and `e`
encloses coefficient/input/coordinate changes. In the affine case this reduces
to `delta_next <= g*delta + e`. For constant `g<1`, derive a finite-horizon
geometric sum and a conditional forcing floor. For Hölder `m`, propagate the
monotone bound directly: `sqrt(delta)` on `[0,1]` can enlarge a perturbation and
does not justify an exponential half-life.

Changing UVs require an image spatial modulus, qualified interpolation/addressing
and seam rules. A UV displacement bound alone cannot supply `e`. Drawing and
feedback storage add separate forcing/quantization terms. The composite display
stage must not be assumed to be the next frame's feedback state without tracing
the actual pipeline.

## Priority supported by existing evidence

These are checkpoint counts, not a new census or expected library gains.
Their sample sizes and scopes differ, so they do not support a common benefit
percentage. Current module hashes differ from some saved manifests.

1. **State/input relations before broader numeric coverage.** The adopted
   dependency component exposes additional possible predecessor audio ancestry
   in 470/9,606 presets ([component contract](../../tools/milk-analyzer/SOURCE_COMPONENTS.md)).
   This establishes recurring state relevance, not 470 bounded recurrences.
   The fixed 2,000 dynamic-affine census records 237 uniform cases missing a
   domain, including 639 missing zoom-domain records overall. Missing domains
   overlap and may arise from unsupported code; neither is an Arb-resolvable count.
2. **Arb on existing bounded-domain nonlinear calculations.** The saved fixed100
   time-component census has 2,325 bounded records out of 2,618 and 113 distinct
   positive curves. The difference, 293, is not a trig/power-only gap count.
   The fixed100 direct-colour census has 142 band routes, six fully bounded under
   its scenario and 37 presets with direct routes. These warrant an operator-level
   failure inventory before extending the backend.
3. **Relational feedback and Taylor models after a targeted census.** No inspected
   count establishes how many feedback failures are caused by wrapping,
   channel correlation or a nonlinear modulus. Keep this experimentally ranked
   after the first two; do not invent whole-pack prevalence.

Local evidence identities read in this research:

| Artifact | SHA256 |
|---|---|
| `build/source-field-index-port/dynamic-affine-gap-census-v2.json` | `a647123602bf6d61c27faf63794058287639f8c408584bbe05e4d8edd68555da` |
| `build/preset-corpus/source-time-component-2026-10-10/census.json` (100 presets) | `9620569101d212ffdcc3b250017adaf60078490e15134525684172f9473c6129` |
| `build/preset-corpus/source-colour-response-nonlinear-2026-10-10/census.json` (100 presets) | `f87935702b2fe81bb7a0e6d901c24c184412d833cfb1b476e6891e1b557ef4d4` |

## Small next experiment on real source

Use a separate repository-local optional environment and a research worker;
keep production default-off. Export exact existing graphs and source hashes,
not a replacement parser or hand-transcribed graph presented as native analysis.
Begin with two identified witnesses:

- **`19.milk`**, SHA256 `0236113a9ed840ed9dc8892fb1b0f7894af2c0ff45585a8ba29c93973b206c1d`:
  source lines320–321 contain nested sin/cos time/audio scale formulas. Compare
  ordinary boxes, Arb restricted ranges and symbolic-derivative Arb enclosures
  for caller-declared `time=[0,1/30]`, `x,y=[0,1]`, `treb_att=[0,2]`.
  Preserve a shared `t` and paired `t+dt` when testing finite differences.
  The saved census already gives partial rate bounds near 0.2 for sx/sy; a new
  adapter must report a tighter or more rigorously enclosed calculation, not
  claim this old supported result as new coverage. Holding audio fixed is a
  partial response; vary it only under explicit paired-input constraints.
- **`Hexcollie - Melodic pulsing leds - mash0000 - vegas doesn't make life less pointless.milk`**,
  SHA256 `01441976437b273b2648d9cf754e6214134b0fe471d849248e278bb497bfdb30`:
  source lines389–390 update private residuals with a common boolean gate and
  decay 0.9. Under an independently established initial domain, nominal candidate
  bounds `abs(dx_residual)<=0.0144`, `abs(dy_residual)<=0.0108` follow by splitting
  gate 0/gate 1 and using `abs(sin)<=1`. Retain ordered writes: dx/dy consume the
  predecessor residual before its update. Establish actual initialization,
  persistence and phase identity from the current host graph; otherwise report
  only conditional transition invariance. A generic interval gate `[0,1]`
  multiplied independently at each occurrence loses the boolean correlation.
  This is a useful recurrence/branch negative control for plain Arb.

The second source also forms `ret=4*GetBlur1(uv)-4*main(uv)` before channel powers
0.5/0.5/0.7 (lines417–426). Independent unit sample premises allow negative ret.
The experiment must keep those fractional-power domains unresolved. A bound
obtained by clamping the base to zero is unacceptable. A separate positive-base
synthetic control can qualify power operators but cannot resolve this source.

Measure supported operations, newly bounded or tightened calculations, preserved
unknowns, exact affected source names, enclosure width, worst-case worker time,
and backend/cache identities. Include underflow/overflow, threshold seam,
zero-touching Hölder, negative fractional power, uninitialized state and
cross-phase alias controls. Fixed-horizon set propagation is a bound computation;
pointwise sampled trajectories are not a proof.

Arb can rigorously enclose nominal mathematics. A native result additionally
needs EEL double policies, float uploads, GPU transcendental/conversion contracts,
overflow/denormal handling, storage, interpolation, drawing and audio/frame
contracts. Report source temporal RGB upper bounds separately from visible
flashing, movement prominence, persistence or mood; none is established here.
This research does not block intermediate descriptions or mood feedback while
those mathematical gaps remain. Freeze each description's source/model/audio
identity and compare it with the actual-AAR 10-second screenshot and human
feedback as part of the active workflow. A single screenshot supplies appearance
evidence at that time, not a temporal flashing or movement measurement.
