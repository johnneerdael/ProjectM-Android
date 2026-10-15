"""Source-calibrated display estimates (standard library at prediction time).

Gradient-boosted regression trees map the static summary descriptor
(``static_descriptor``) to display statistics measured by the engine ruler
(pinned patched engine rendered offline): mean luminance, frame difference,
optical-flow speed, global brightness jumps, saturation and warm/cool. The
trees are fitted offline (``fit_display_calibration.py``, optional
scikit-learn) and stored as JSON, so prediction needs no third-party packages.

Each prediction carries the out-of-fold residual interval of its target
(10th-90th percentile), the cross-validated rank correlation and the label
source. These are calibrated source estimates: no rendered frame of the preset
being described is read, and accuracy is the reported cross-validation score,
not a guarantee for an individual preset.
"""
import gzip
import json
import math
from pathlib import Path

POLICY='source-calibrated-display-v1'
DEFAULT_MODEL=Path(__file__).with_name('fixtures')/'calibrated-display-model.json.gz'
MISSING=-1e9
# Physical range of each statistic: estimates and residual intervals are clamped into it.
DOMAINS={'mean_luminance':(0.,1.),'mean_abs_frame_difference':(0.,1.),'mean_saturation':(0.,1.),'warm_cool':(-1.,1.),
         'mean_flow_screen_widths_per_s':(0.,None),'global_brightness_jumps_per_10s':(0.,None),
         'coloured_share':(0.,1.),**{'hue_share_'+h:(0.,1.) for h in ('red','orange','yellow','green','cyan','blue','purple','pink')}}
_CACHE={}


def load(path=None):
    path=Path(path or DEFAULT_MODEL)
    key=str(path)
    if key not in _CACHE:
        if not path.exists():_CACHE[key]=None
        else:
            with gzip.open(path,'rt') as handle:_CACHE[key]=json.load(handle)
    return _CACHE[key]


def _tree(nodes,x):
    i=0
    while True:
        value,feature,threshold,left,right,leaf=nodes[i]
        if leaf:return value
        i=left if x[feature]<=threshold else right


def predict(summary,model=None,render=None):
    """Return {target: {'value','interval','oof_spearman','evidence'}} or None when no model is available.
    render: an already computed recipe render whose colour probes feed the descriptor (else computed here)."""
    from static_descriptor import descriptor
    model=model or load()
    if model is None:return None
    columns=descriptor(summary,render=render)
    x=[]
    for name in model['columns']:
        value=columns.get(name)
        x.append(MISSING if value is None or not math.isfinite(value) else float(value))
    out={}
    for target,spec in model['targets'].items():
        raw=spec['baseline']+sum(_tree(tree,x) for tree in spec['trees'])
        clamp=lambda v,bounds=DOMAINS.get(target,(None,None)):min(max(v,bounds[0]) if bounds[0] is not None else v,
                                                                   bounds[1] if bounds[1] is not None else math.inf)
        value=clamp(_inverse(raw,spec.get('transform')))
        low,high=(clamp(_inverse(raw+spec['residual_p10'],spec.get('transform'))),clamp(_inverse(raw+spec['residual_p90'],spec.get('transform'))))
        out[target]={'value':value,'interval':[min(low,high),max(low,high)],'oof_spearman':spec['oof_spearman'],
                     'evidence':'source-calibrated','label_source':model.get('label_source')}
        if type(spec.get('threshold')) in (int,float):out[target]['threshold']=spec['threshold']
    return out


def _inverse(raw,transform):
    if transform=='logistic':return 1/(1+math.exp(-raw)) if raw>=0 else math.exp(raw)/(1+math.exp(raw))
    if transform=='log1p10':return max(0.,math.expm1(raw)/10)
    if transform=='log1p':return max(0.,math.expm1(raw))
    return raw
