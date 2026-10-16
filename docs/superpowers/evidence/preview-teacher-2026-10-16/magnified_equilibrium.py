"""Prototype: feedback equilibrium with area magnification (static).

The shipped spread bound assumes area-preserving transport: mean canvas = injected energy / (1 - g). With per-step
area magnification m (forward Jacobian of the mesh warp), an element of area a and premultiplied colour p injected k
frames ago covers min(1, a m^k) of the screen at weight g^k, so its mean contribution is p * sum_k g^k min(1, a m^k)
(reduces to p a / (1 - g) at m = 1). Background offset as before; the composite transfer maps canvas to display."""
import json, gzip, base64, sys
from pathlib import Path
W = Path('/Users/jneerdael/Scripts/Projectm-TV/.worktrees/predictor-memory-repair'); sys.path.insert(0, str(W / 'tools/milk-analyzer'))
import feedback_equilibrium as E
def magnified_display(summary, m, steps=600):
    facts = {f['path']: f['value'] for g in summary['facts'].values() for f in g}
    notes = []; gain, offset = E._gain_and_offset(facts, notes)
    terms = E._shape_terms(facts, notes) + E._border_terms(facts) + E._wave_terms(facts, notes)
    canvas = []
    for i in range(3):
        g = min(gain[i], .999)
        level = offset[i] / (1 - g) if g < 1 else (1. if offset[i] > 0 else 0.)
        for area, premultiplied, alpha, additive in terms:
            s = 0.; cov = area
            for k in range(steps):
                s += (g ** k) * min(1., cov); cov *= m
                if g ** k < 1e-4: break
            level += premultiplied[i] * s
        canvas.append(E._clip(level))
    composite = E.stage_transfer(facts, 'composite')
    shown, _ = E._composite(canvas, facts, notes, composite)
    return E._luma(shown)
