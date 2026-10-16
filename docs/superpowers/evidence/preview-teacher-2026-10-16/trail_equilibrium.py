"""Prototype: displayed brightness as the composite averaged over the canvas level distribution (static).

The shipped equilibrium maps one canvas level (local or spread mean) through the composite transfer. For nonlinear
composites the mean of T(c) differs from T(mean c). Feedback trails give a derivable distribution: an element painting
area a per frame at level L leaves pixels at levels L g^k (age k), each covering about a of the screen, until the screen
is covered; the rest stays at the background level. Display = sum over that histogram of T(level) (composite flat-colour
transfer, interpolated), averaged over channels via luma."""
import json, gzip, base64, sys, math
from pathlib import Path
W = Path('/Users/jneerdael/Scripts/Projectm-TV/.worktrees/predictor-memory-repair'); sys.path.insert(0, str(W / 'tools/milk-analyzer'))
import feedback_equilibrium as E
def trail_display(summary, max_age=600):
    facts = {f['path']: f['value'] for g in summary['facts'].values() for f in g}
    notes = []; gain, offset = E._gain_and_offset(facts, notes)
    terms = E._shape_terms(facts, notes) + E._border_terms(facts) + E._wave_terms(facts, notes)
    composite = E.stage_transfer(facts, 'composite')
    def show(rgb):
        out, _ = E._composite([E._clip(v) for v in rgb], facts, notes, composite); return out
    bg = [E._clip(offset[i] / (1 - gain[i])) if gain[i] < 1 else (1. if offset[i] > 0 else 0.) for i in range(3)]
    hist = []; covered = 0.
    for area, premultiplied, alpha, additive in terms:
        if area <= 0 or alpha <= 0: continue
        level = [p / alpha for p in premultiplied]
        for k in range(max_age):
            if covered >= 1: break
            share = min(area, 1 - covered); covered += share
            hist.append((share, [bg[i] + (level[i] - bg[i]) * (gain[i] ** k) for i in range(3)]))
            if max(gain) ** k < 1e-3: break
    hist.append((max(0., 1 - covered), bg))
    rgb = [0., 0., 0.]
    for share, level in hist:
        shown = show(level)
        for i in range(3): rgb[i] += share * shown[i]
    return E._luma(rgb)
