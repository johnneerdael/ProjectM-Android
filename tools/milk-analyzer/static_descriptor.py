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

v4 adds ``recipe:*`` columns from the recipe colour probes (warp/composite detail responses, the composite
colour matrix with its singular-value ratios, and the static-only pooled palette).
"""
import math
import re

POLICY='static-summary-descriptor-v4'
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


BRIGHTNESS_OUTPUTS={'decay','gamma','echo_alpha','echo_zoom','invert','solarize','brighten','darken','wave_brighten','mv_a',
                    *('%s_%s'%(p,c) for p in ('wave','ob','ib') for c in 'rgba')}
BANDS={'bass','mid','treb','bass_att','mid_att','treb_att','vol','vol_att'}
COMPARISONS={'greater','less','greater_equal','less_equal','eel_equal','equal','not_equal','above','below'}


def _frame_program_columns(summary,steps=128):
    """Static columns from the exported per-frame program graphs (no frames stepped, no audio).

    periodic_state: state variables whose update reads only themselves and constants (an autonomous recurrence,
    e.g. a counter wrapping every N frames); the orbit from the initial value is a property of the formula,
    and its period is reported. Brightness-related outputs (decay, wave/border colour and alpha, gamma, echo,
    invert, ...) that read such a state, or that compare an audio band with a threshold, are counted, as is
    any frame-counter modulo.
    """
    from time_expression import evaluate_inputs,input_names
    frame={}
    for rows in (summary.get('facts') or {}).values():
        for row in rows:
            if row.get('path')=='/analysis/visual_description/stage_programs':frame=(row.get('value') or {}).get('frame') or {}
    if frame.get('status')!='exported':return {}
    names=lambda g:{n for n in (input_names(g) or ()) if isinstance(n,str)} if isinstance(g,dict) else set()
    ops=lambda g:{node.get('op') for node in (g.get('nodes') or [])} if isinstance(g,dict) else set()
    periodic={};periods=[]
    for name,record in (frame.get('state') or {}).items():
        update,initial=(record or {}).get('update'),(record or {}).get('initial')
        if not isinstance(update,dict) or names(update)-{name} or names(initial):continue
        try:
            value=float(evaluate_inputs(initial,{}));seen={value:0}
            for k in range(1,steps+1):
                value=float(evaluate_inputs(update,{name:value}))
                if value in seen:
                    period=k-seen[value]
                    if period>=2:periodic[name]=period;periods.append(period)
                    break
                seen[value]=k
        except (ValueError,TypeError,KeyError,ZeroDivisionError,OverflowError):continue
    outputs=frame.get('outputs') or {}
    bright=[g for out,g in outputs.items() if out in BRIGHTNESS_OUTPUTS]
    graphs=list(outputs.values())+[r.get('update') for r in (frame.get('state') or {}).values() if isinstance(r,dict)]
    columns={'frameprog:periodic_state#count':float(len(periodic)),
             'frameprog:brightness_outputs_from_periodic_state#count':float(sum(1 for g in bright if names(g)&set(periodic))),
             'frameprog:brightness_outputs_band_threshold#count':float(sum(1 for g in bright if ops(g)&COMPARISONS and names(g)&BANDS)),
             'frameprog:frame_modulo#count':float(sum(1 for g in graphs if isinstance(g,dict) and ops(g)&{'mod','eel_mod','fmod','modulo','remainder'} and 'frame' in names(g)))}
    if periods:columns['frameprog:periodic_state_period#min']=float(min(periods))
    return columns


def descriptor(summary,render=None):
    """Return {column: value} for one preset-understanding summary. render: the recipe render whose colour probes
    become ``recipe:*`` columns (computed from the summary when not given)."""
    leaves={}
    for group,rows in summary.get('facts',{}).items():
        if group in SKIP_GROUPS:continue
        for row in rows:
            path=INDEX.sub('/*',str(row.get('path','')))
            _walk(row.get('value'),group+':'+path,0,leaves)
    columns=_equilibrium_columns(summary)
    columns.update(_frame_program_columns(summary))
    columns.update(_recipe_probe_columns(summary,render))
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


def _recipe_probe_columns(summary,render=None):
    """``recipe:*`` columns from the recipe colour probes (preset_recipe.probe_columns); empty on failure."""
    try:
        from preset_recipe import probe_columns,probe_render
        return probe_columns(render if render is not None else probe_render(summary))
    except Exception:  # noqa: BLE001 - a descriptor never fails on one derived group
        return {}


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
