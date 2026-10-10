# Generated shader pattern translation

`source_shader_pattern_transport.py` provides two source-only APIs:

```python
rigid_shader_pattern_transport(analysis, stage, context=None)
generated_shader_pattern_transport(analysis, stage, context=None)
```

The first API checks a complete pure generated RGB graph. The second retains
that result as `full_pattern`, or returns `full_pattern=None` and independently
proved live generated colour subfields in `partial_patterns`. The source graph
comes from the existing typed shader lowering. No source text is interpreted by
a new parser, and no frames, shader execution or equation execution are used.

For fixed affine phases `k.x*x+k.y*y+omega*t+bias`, the producer solves every
constraint `k dot v = -omega` simultaneously. All RGB factors must share one
velocity. Pointwise outer operations such as sine, cosine and absolute value
preserve the coordinate identity `G(u,t)=F(u-v*t)` on their original defined
domains. Time-only colour modulation vetoes the complete-pattern proof. Static
spatial factors also constrain the velocity, so a fixed mask or gradient cannot
silently move with an independently animated generator.

Coefficients and consistency use rational arithmetic over the original typed
literals. Existing lane, constant-conversion, affine-admission and scalar-bound
helpers supply the source contract. The binary64 affine helper's coefficients
are never used for rank or consistency: losing the increment in
`(1e20*u+u)-1e20*u` must not erase its exact nominal spatial coefficient.
The proof is nominal real arithmetic after literal conversion; it does not
establish GPU arithmetic parity. Dynamic casts remain unresolved.

Composite shader/original UV inputs alias normalized viewport UV. Warp original
UV bypasses the native mesh. Warp shader UV requires a selected, time-independent
uniform affine native recipe and caller-supplied finite `_uv.x`/`_uv.y` domains
that include the actual mesh output and fixed texel offset. Native recipe
rotation/float conversion retain their existing qualification. Input domains
are declared premises, not observed renderer bindings.

`signed_velocity_vp_per_second` follows the inverse-feature direction. A phase
`cos(10*uv.x+time)` yields `[-0.1,0]`; no feedback-FPS multiplier applies.
Rank two gives a unique velocity. Rank one reports the minimum-norm
representative, since tangent velocity is unidentifiable. The reported speed is
an outward bound for that nominal representative. Clock resets and the wrapped
shader clock's 10,000-second seam are excluded.

Subfields use the existing live colour traversal, excluding sample coordinates,
known zero products, constant clipping and unused assignments. Each record
retains its original `source_graph_path`, projected lane, generated expression,
source/engine identity and parent-held conditions. Its role is
`live_generated_colour_subfield`; `included_in_total_motion=False` and
`full_stage_transport_proved=False` are mandatory. Parent samples/history,
masks, other factors and later passes can alter or cancel apparent motion.
Never replace unresolved full-stage motion with these partial records.

Selection, clipping/discard, execution effects, discrete casts, domain validity
and intermediate finite binary32-range guards remain separate admission gates.
The source HLSL `sqrt(abs(x))` lowering is retained. Visibility, contrast,
prominence, native precision and dominant screen motion remain unknown; this
module does not assign moods or certify content motion.

Validation on 2026-10-10: 34 focused controls pass. Together with existing
temporal and affine-sampling controls, 84 tests pass. The first ten unchanged
records from the saved v6 source inventory, parsed with exact source34 reader
SHA256 `754e4f4129db585cb4f7d5bee915d6bb24ac10ab25901ee7ef0832ce50744afc`
and validated saved compatibility, recover **zero** full or partial patterns.
The bounded replay is
`build/preset-corpus/shader-pattern-transport-smoke10-2026-10-10.json`.
No cohort improvement has been demonstrated by that check.
