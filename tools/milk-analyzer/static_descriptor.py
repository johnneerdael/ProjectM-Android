"""Generic numeric descriptor of a preset-understanding summary (source facts only).

Every fact value is walked; numeric and boolean leaves become columns keyed by
their path with element/list indices collapsed to ``*`` (aggregated by max,
mean and count), and short categorical strings become one-hot ``key=value``
columns. The descriptor is a faithful, lossy flattening of the static analysis
for calibration and model fitting: it reads no rendered frames and executes no
preset code. Columns that are rare across a corpus should be pruned by the
caller.

v2 adds derived ``equilibrium:*`` columns from feedback_equilibrium: the feedback steady-state
canvas and display colour (local and fully spread bounds), warp gain/offset and per-frame drawn
energy, computed from the same facts by closed-form transfer evaluation (no frames stepped).
"""
import math
import re

POLICY='static-summary-descriptor-v3'
SKIP_GROUPS={'identity'}
SKIP_KEYS={'conditions','unknown_reasons','evidence','limitations','scope','note','policy','source_locations',
           'source_keys','expression','expressions','programs','nodes','representative_points','lane_expressions_rgb',
           'coordinate_expression','offset_expressions','channel_expressions','flag_expressions','tex_zoom_expression','tex_angle_expression',
           'level_orbit_from_full','profiles','series','samples','reference_table','program','plans','declared_audio_sha256'}
INDEX=re.compile(r'/\d+(?=/|$)')
MAX_DEPTH=8
MAX_STRING=40


def _walk(value,path,depth,out):
    if depth>MAX_DEPTH:return
    if isinstance(value,bool):
        out.setdefault(path,[]).append(1. if value else 0.)
    elif isinstance(value,(int,float)):
        if math.isfinite(value):out.setdefault(path,[]).append(float(value))
    elif isinstance(value,str):
        if 0<len(value)<=MAX_STRING:out.setdefault(path+'='+value,[]).append(1.)
    elif isinstance(value,dict):
        for key,child in value.items():
            if key in SKIP_KEYS:continue
            _walk(child,path+'/'+str(key),depth+1,out)
    elif isinstance(value,list):
        if len(value)<=64 and all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in value) and value:
            finite=[float(v) for v in value if math.isfinite(v)]
            if finite:
                out.setdefault(path+'/min',[]).append(min(finite));out.setdefault(path+'/max',[]).append(max(finite))
            return
        for child in value[:256]:
            _walk(child,path+'/*',depth+1,out)


def descriptor(summary):
    """Return {column: value} for one preset-understanding summary."""
    leaves={}
    for group,rows in summary.get('facts',{}).items():
        if group in SKIP_GROUPS:continue
        for row in rows:
            path=INDEX.sub('/*',str(row.get('path','')))
            _walk(row.get('value'),group+':'+path,0,leaves)
    columns=_equilibrium_columns(summary)
    for key,values in leaves.items():
        if key.endswith('=') or not values:continue
        if '=' in key.rsplit('/',1)[-1]:
            columns[key+'#count']=float(len(values))
            continue
        columns[key+'#max']=max(values)
        if len(values)>1:
            columns[key+'#mean']=sum(values)/len(values)
            columns[key+'#count']=float(len(values))
    return columns


EQUILIBRIUM_MODELS=('identity','legacy','composite_transfer','affine_composite')


def _equilibrium_columns(summary):
    """Derived steady-state columns; empty when the equilibrium cannot be formed."""
    try:
        from feedback_equilibrium import equilibrium
        e=equilibrium(summary)
    except Exception:  # noqa: BLE001 - a descriptor never fails on one derived group
        return {}
    out={'equilibrium:display_local_luma':e['display_local_luma'],'equilibrium:display_spread_luma':e['display_spread_luma'],
         'equilibrium:display_local_saturation':e['display_local_saturation'],'equilibrium:display_spread_saturation':e['display_spread_saturation'],
         'equilibrium:drawn_area_fraction':e['drawn_area_fraction'],'equilibrium:elements':float(e['elements']),
         'equilibrium:substitution_count':float(e['substitution_count'])}
    for name in ('display_local_rgb','display_spread_rgb','canvas_local_rgb','gain_rgb','offset_rgb','energy_rgb_per_frame'):
        for channel,value in zip('rgb',e[name]):out['equilibrium:'+name+'/'+channel]=float(value)
    out['equilibrium:display_local_warm']=e['display_local_rgb'][0]-e['display_local_rgb'][2]
    out['equilibrium:display_spread_warm']=e['display_spread_rgb'][0]-e['display_spread_rgb'][2]
    for model in EQUILIBRIUM_MODELS:out['equilibrium:composite='+model]=1. if e['composite_model']==model else 0.
    # Composite transfer shape: threshold level (1.1 when it never reaches 0.5), time spread, undefined share.
    level=e.get('composite_threshold_level')
    out['equilibrium:composite_threshold_level']=1.1 if level is None else float(level)
    out['equilibrium:composite_spread_max']=float(e.get('composite_spread_max') or 0.)
    out['equilibrium:composite_nonfinite_share']=float(e.get('composite_nonfinite_share') or 0.)
    return out
