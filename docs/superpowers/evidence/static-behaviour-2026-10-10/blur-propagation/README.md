# Source blur propagation handback

The standalone producer `tools/milk-analyzer/source_blur_propagation.py` bounds
nominal RGB supnorm input differences through the source34 target blur bank.
It constructs no RGB fields, renders no images and executes no shader or preset
equations. A source parsing adapter is used only by one control proving that the
analyzer's live post-main-frame values, rather than authored configuration/init
values, supply the bound. No native source, preset, AAR or device was changed.

## API and consumer contract

```python
from source_blur_propagation import blur_propagation_evidence
report = blur_propagation_evidence(analysis.main, input_domains=scalar_domains)
```

`status == "bounded"` supplies `levels[0:3]`. Each level exports:

- `encoded_rgb_supnorm_gain_upper`: main RGB to `sampler_blurN` RGB.
- `getblur_rgb_supnorm_gain_upper`: main RGB to an unexpanded `GetBlurN` RGB.
- `progressive_scale`, `progressive_bias`, separate decode scale/bias, and
  encoded/decoded RGB difference ceilings.
- `encoded_per_pass_pair_error_gains` and decoded equivalents: coefficients
  for independent additive two-state errors introduced after each pass.

Existing source graphs expand `GetBlurN` to sampled RGB times `_c5`/`_c6` decode
constants. Multiply their sampled-site contributions by **encoded** level gains;
using decoded gain there would apply decode twice. Raw blur samples' alpha is1
and its input-difference gain is0. Blur RGB ignores incoming main alpha, and
GetBlur macros return only RGB. Preserve this distinction when composing a
four-lane sampled-RGBA modulus.

All seven live controls hold the same values in the compared states. Exact
source constants resolve through existing `source_uniforms.blur_decode_bindings`
and `blur._coefficients`; the former already uses `blur.native_ranges` with
`CORE_2315_BLUR`. Bounded dynamic edge controls require explicit scalar domains
and finite original expression/intermediate bounds. Unsupported/dynamic six-range
triplets remain unresolved, including a bounded dynamic triplet: ordinary real
intervals do not tightly bound progressive float32 cancellation. Missing state or
domains remain unknown. Original argument traversal precedes clamp/zero-product
pruning and has its own512-node budget.

## Bound and numeric obligations

For level `i`, let `s_i` be the actual float32 progressive scale promoted to a
nominal real coefficient. The nonnegative normalized horizontal/vertical kernels,
fixed bilinear clamp-to-edge samples and normalized storage clamps have nominal
RGB supnorm gain at most1. Horizontal pass applies `s_i`; its constant bias
cancels in the difference. The first vertical pass multiplies by
`(1-e)+e*t`, `t in [0,1]`, so its global absolute gain is
`E=max(1,abs(1-e))`. Later vertical passes use1. Therefore encoded level gains
are `E*s_1`, `E*s_1*s_2`, `E*s_1*s_2*s_3`; the decoded gains additionally
multiply the corresponding native float32 safe-range gap. Products and extreme
edge coefficients round outward for the report's binary64 numeric representation.

Do not replace progressive native coefficients by ideal exact telescoping:
their float32 intermediate arithmetic is preserved, so decoded gain need not be
exactly1. Negative edge controls can amplify; controls are not clamped to[0,1].
The report's global edge coefficient uses nominal `1-e`; target CPU rounding of
that subtraction remains an explicit error obligation.

Normalized pass clamps cap encoded two-state RGB differences at1; GetBlur's
nominal decoded difference ceiling is the corresponding safe-range gap. Actual
native differences additionally require per-pass sampling/arithmetic/storage
pair-error bounds and a separate decode error. The report supplies no target
error bound and keeps `native_numeric_certified=false`. The optional outward
rounded1/255 storage pair term applies only to ideal nondithered nearest-unorm8
conversion; it does not certify target storage or include native arithmetic,
filter rounding, FMA/precision or dither. Quantization alone is not globally
Lipschitz at thresholds, so it cannot silently join a nominal derivative.

The input must be the actual RGB texture supplied to `BlurTexture::Update`.
Consumers still need matching source34 lineage, dimensions, allocation, blur age,
pass schedule and coordinate/control bindings. The module does not prove that
current shapes/waves already occur in that bank. Global supnorm propagation does
not preserve local source support/area, supply temporal trajectories or certify
whole-loop contraction, appearance or mood.

## Source references

The hash-identified source34 production export is authoritative for this module;
paths and SHA256s are in `source-identities.json`.

- `BlurTexture.cpp:167-178`: live edge/range inputs and shared normalization
  producer; `:253-302`: nonnegative weights, normalization and first-pass-only
  edge coefficients; `:354-453`: patched safe-range fallback and progressive
  coefficient domains.
- `Shaders/Blur1FragmentShaderGlsl330.frag:32-53`: RGB-only weighted samples,
  normalization, scale/bias and fixed output alpha.
- `Shaders/Blur2FragmentShaderGlsl330.frag:27-49`: RGB-only vertical samples,
  normalized sum, edge factor and fixed output alpha.
- `Shaders/PresetShaderHeaderGlsl330.inc:149-151`: GetBlur RGB decode macros.
- Committed historical target correction:
  `tools/projectm-patches/0046-blur-range-interval.patch`.

Original MilkDrop2 source comparison:
`/Users/jneerdael/Scripts/milkdrop2_v2.25c_OPEN_SOURCED_20130514_orig_code/vis_milk2/milkdropfs.cpp:1551-1580`
contains the same clamp-then-expand order and collapsed upper-bound typo.
`:1647-1667` defines the same weights/progressive normalization;
`:1692-1740` defines pass uniforms and first-pass edge darkening. Reuse the
patched target's upward expansion and coherent fallback rather than importing
the original collapsed interval. This is a comparison of source intent and
target semantics, not a Windows-pixel equivalence claim.

## Validation and saved-v6 census

The first20 controls failed with the missing-producer assertion before the
implementation. Added exact rational controls then exposed two outward-rounding
failures; both pass after repair. Final focused verification:

```sh
build/preset-lab-venv/bin/python -m pytest tools/milk-analyzer/test_source_blur_propagation.py tools/milk-analyzer/test_source_uniforms.py tools/milk-analyzer/test_blur.py -q
```

Result:36 passed (21 new,15 neighboring) in0.42seconds. Controls cover default,
progressive and close ranges, clamp-then-expand ordering, coherent fallback,
dynamic/missing triplet refusal, bounded/unknown edge inputs, negative/extreme
edge coefficients, invalid expressions before clamps/zero products, native edge
upload overflow, RGB/alpha distinction, additive pair-error propagation and
post-main-frame source34 binding. No renderer/full-corpus/device test was run.

`saved-v6-census.json` and `saved-v6-candidates.jsonl` inspect unchanged saved
transfer-v6 rows one at a time. Among2000 rows,1698 have constant six-range
bindings. All589 rows with the main-to-blur veto have that prerequisite;226
also have finite sample-site gains, and35 have bounded sampled-colour moduli.
Edge source controls/domains are not separately exported there, so these counts
are candidates, not complete producer applicability or improved mood coverage.

Production producer and tests are frozen at the identities recorded in
`source-identities.json`; root owns coupled integration and final qualification.
