# r161 v2: per-pixel warp controls bounded from the source

v1 recipe: `sx`/`sy` (per pixel) and `cx`/`cy` (per frame) had `value_range: null`. The reader fell back on
the 0.9995 base zoom and called the motion a slow uniform contraction.

The source (`per_pixel`) is `sx = sy = zm*rd`. Here `rd` is the distance from a centre
`(cx, cy) = (0.5 + 0.6 cos(0.6 m), 0.5 - 0.6 sin(0.4 m))`, and `m += mid^3 * 0.02 * (75/fps)` each frame.
So the warp is a per-pixel lens around a travelling centre. Three general gaps in the value bounder hid this:

1. `eel_divide` with an unproved denominator failed the whole expression. projectm-eval returns 0 for
   |divisor| < 1e-5, so the quotient of finite operands is an arbitrary finite value, and cos() of it stays
   in [-1, 1]. GLSL `divide` stays unknown.
2. `atan` had no rule. It maps every finite value monotonically into (-pi/2, pi/2); `atan2` maps into [-pi, pi].
3. The outward rounding step moved a 0 lower bound of `sqr(...)+sqr(...)` to -5e-324, which made `sqrt`
   unprovable. Squares, and sums or products of same-signed operands, are exactly >= 0 under IEEE rounding.

v2 recipe: `sx`/`sy` range [0, 2.66] (non-uniform) and `cx`/`cy` range [-0.1, 1.1]. SKILL.md now explains
`warp_controls`: the engine samples `(p - c)/s + c`, a non-uniform stretch far from 1 is a lens, and a wide
centre range means it travels. The v2 reading (`llm-look-description-v2.txt`) describes the lens and the
moving centre. It still opens with the base contraction.
