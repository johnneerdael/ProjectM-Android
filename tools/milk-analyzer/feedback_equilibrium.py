"""Feedback steady-state brightness and colour from source facts (no frames rendered or stepped).

Each frame the engine resamples the previous canvas through the warp (colour gain g per channel,
plus a constant offset), then draws elements on top. Where an element covers a pixel with colour c
and alpha a every frame, the stored value converges to

    additive drawing:      x* = a*c / (1 - g)              (clamped to 1)
    alpha-over drawing:    x* = a*c / (1 - (1 - a)*g)

Elsewhere the canvas converges to offset / (1 - g). Two bounds bracket how far drawn content
spreads: ``local`` keeps every element's energy where it is drawn (no transport), ``spread``
distributes the summed per-frame energy over the whole screen (complete mixing). The composite then
maps canvas colour to display colour: the legacy gamma/brighten/darken/solarize/invert transfers,
or an exported affine composite. Values are nominal: ranges use their midpoints, unknown colours a
neutral prior, and every substitution is listed. This is mathematics over the static facts, not a
simulation; it is a descriptor for understanding and calibration, never a measurement.
"""
import math

POLICY='source-feedback-equilibrium-v3'
ASPECT_Y=270/480  # reference render (engine ruler, checkpoints): short/long side
REFERENCE=(480,270)
NEUTRAL=.5


def _mid(span):
    if isinstance(span,(int,float)) and math.isfinite(span):return float(span)
    if isinstance(span,list) and len(span)==2 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in span):
        return (span[0]+span[1])/2
    return None


def _clip(value,low=0.,high=1.):
    return min(high,max(low,value))


def _luma(rgb):
    return .299*rgb[0]+.587*rgb[1]+.114*rgb[2]


def _saturation(rgb):
    high=max(rgb)
    return 0. if high<=1e-9 else (high-min(rgb))/high


# Flat canvas levels: 8-bit steps 1..32/255 (faint trails and decaying feedback, where high-gain composites
# such as x50 then solarize do all their work) plus quarters up to full.
LEVELS=(0.,1/255,2/255,4/255,8/255,16/255,32/255,.25,.5,.75,1.)
TIMES=(2.,5.,8.)


def stage_transfer(facts,stage,levels=LEVELS,times=TIMES,size=(48,27)):
    """Mean output RGB of an exported stage program for flat input colours (the stage's colour transfer).

    Each level c fills main and blur inputs with the constant colour c; the program is evaluated at a few
    declared times with neutral audio (bands 1) and averaged over the screen; 'rgb' is the mean over the
    times and 'rgb_spread' the per-channel range between them. This evaluates the exported closed-form
    shader at fixed inputs; no frames are stepped and no feedback is iterated.
    """
    import numpy as np
    import prediction_illustration as P
    program=(((facts.get('/analysis/visual_description/stage_programs') or {}).get('stages') or {}).get(stage) or {})
    if program.get('status')!='exported':return None
    width,height=size
    columns,rows=np.meshgrid((np.arange(width)+.5)/width,(np.arange(height)+.5)/height)
    uv=np.stack([columns,rows,columns,rows],axis=-1).astype(np.float32)
    bands={name:1. for name in ('bass','mid','treb','bass_att','mid_att','treb_att')}
    controls=_stage_controls(facts,bands,times)
    table,spread,nonfinite=[],[],[]
    for level in levels:
        image=np.full((height,width,3),level,np.float32)
        outputs=[]
        for time in times:
            try:
                out=P._evaluate_stage(program['program'],image,uv,time,30.,bands,controls=dict(controls[time]),stage=stage)
            except Exception:  # noqa: BLE001 - an unevaluable program leaves the transfer unknown
                return None
            nonfinite.append(float(np.mean(~np.isfinite(out))))
            out=np.where(np.isfinite(out),out,0.)
            outputs.append(np.clip(out,0,1).reshape(-1,3).mean(0))
        table.append([float(v) for v in np.mean(outputs,axis=0)])
        # How far each channel moves between the declared times (time-driven palette shifts).
        spread.append([float(v) for v in np.ptp(outputs,axis=0)])
    # Non-finite results (0/0, inf-inf) are undefined in GLSL ES: they count as 0 in rgb, and their share is reported.
    return {'levels':list(levels),'rgb':table,'rgb_spread':spread,'times':list(times),'nonfinite_share':float(np.mean(nonfinite))}


DETAIL_SATURATION=.25  # a pixel counts as coloured at this saturation and DETAIL_VALUE brightness
DETAIL_VALUE=.1


def stage_detail_gain(facts,stage='warp',level=.1,amplitude=.02,time=5.,size=(96,54),seed=0):
    """How much one pass of an exported stage amplifies fine structure (the spatial perturbation loop gain).

    The input is a dim grey canvas (level) carrying small zero-mean grey noise (amplitude, smoothed at 1 and 2 px,
    wrapped) in every channel; one evaluation at a declared time with neutral audio. Detail is luma minus its 9x9
    local mean; gain = std(output detail) / std(input detail). A copy gives 1 and a scale its factor. Above 1, fine
    structure grows each frame until it clips (pattern-forming feedback such as ret += (ret - blur)*k), whatever the
    flat-field gain, so a canvas the equilibrium calls black can fill with bright spots. No frames are stepped.
    """
    import numpy as np
    from scipy.ndimage import gaussian_filter,uniform_filter
    import prediction_illustration as P
    program=(((facts.get('/analysis/visual_description/stage_programs') or {}).get('stages') or {}).get(stage) or {})
    if program.get('status')!='exported':return None
    width,height=size
    rng=np.random.default_rng(seed)
    noise=gaussian_filter(rng.standard_normal((height,width)),1,mode='wrap')+.5*gaussian_filter(rng.standard_normal((height,width)),2,mode='wrap')
    noise=noise/noise.std()*amplitude
    image=np.repeat((level+noise)[...,None],3,axis=2).astype(np.float32)
    columns,rows=np.meshgrid((np.arange(width)+.5)/width,(np.arange(height)+.5)/height)
    uv=np.stack([columns,rows,columns,rows],axis=-1).astype(np.float32)
    bands={name:1. for name in ('bass','mid','treb','bass_att','mid_att','treb_att')}
    controls=_stage_controls(facts,bands,(time,))
    try:
        out=P._evaluate_stage(program['program'],image,uv,time,30.,bands,controls=dict(controls[time]),stage=stage)
    except Exception:  # noqa: BLE001 - an unevaluable program leaves the gain unknown
        return None
    out=np.clip(np.where(np.isfinite(out),out,0.),0,1)
    luma=lambda a:.2126*a[...,0]+.7152*a[...,1]+.0722*a[...,2]
    detail=lambda l:l-uniform_filter(l,9,mode='wrap')
    gin=float(detail(luma(image)).std());gout=float(detail(luma(out)).std())
    if gin<=0:return None
    return {'gain':gout/gin,'flat_out':float(luma(out).mean()),
            'input':{'kind':'dim grey noise','level':level,'amplitude':amplitude,'smoothing_px':[1,2],'size':list(size),'time':time}}


def stage_detail_response(facts,stage='composite',level=.5,amplitude=.2,time=5.,size=REFERENCE,seed=0):
    """Colour an exported stage creates from structure: a grey multi-scale texture through the program.

    Flat-colour probes (stage_transfer) cannot see colour a shader derives from detail (gradients,
    blur differences, loops over offset samples). The input is deterministic grey noise at level +/-
    amplitude, smoothed at 1, 4 and 16 px and equal in every channel, at the reference size so texel
    offsets keep their meaning; one evaluation at a declared time with neutral audio. The result
    describes the program's response to texture, not any particular frame's content.
    """
    import numpy as np
    import cv2
    import prediction_illustration as P
    from time_expression import HUE_BANDS
    program=(((facts.get('/analysis/visual_description/stage_programs') or {}).get('stages') or {}).get(stage) or {})
    if program.get('status')!='exported':return None
    width,height=size
    rng=np.random.default_rng(seed)
    noise=sum(cv2.GaussianBlur(rng.standard_normal((height,width)).astype(np.float32),(0,0),sigma) for sigma in (1.,4.,16.))
    noise=noise/max(float(noise.std()),1e-9)
    image=np.repeat(np.clip(level+amplitude*noise,0,1)[...,None],3,-1).astype(np.float32)
    columns,rows=np.meshgrid((np.arange(width)+.5)/width,(np.arange(height)+.5)/height)
    uv=np.stack([columns,rows,columns,rows],axis=-1).astype(np.float32)
    bands={name:1. for name in ('bass','mid','treb','bass_att','mid_att','treb_att')}
    controls=_stage_controls(facts,bands,(time,))
    try:
        out=P._evaluate_stage(program['program'],image,uv,time,30.,bands,controls=dict(controls[time]),stage=stage)
    except Exception:  # noqa: BLE001 - an unevaluable program leaves the response unknown
        return None
    out=np.asarray(out,np.float64)
    nonfinite=float(np.mean(~np.isfinite(out)))
    out=np.clip(np.where(np.isfinite(out),out,0.),0,1).reshape(-1,3)
    high,low=out.max(1),out.min(1)
    saturation=np.where(high>1e-9,(high-low)/np.maximum(high,1e-9),0.)
    coloured=(saturation>=DETAIL_SATURATION)&(high>=DETAIL_VALUE)
    r,g,b=out[:,0],out[:,1],out[:,2];delta=np.maximum(high-low,1e-12)
    hue=np.where(high==r,((g-b)/delta)%6,np.where(high==g,(b-r)/delta+2,(r-g)/delta+4))*60
    shares={}
    if coloured.any():
        for name,spans in HUE_BANDS.items():
            inside=np.zeros(len(hue),bool)
            for a,b_ in spans:inside|=(hue>=a)&(hue<b_)
            share=float(np.mean(inside[coloured]))
            if share>=.05:shares[name]=round(share,3)
    return {'mean_rgb':[round(float(v),4) for v in out.mean(0)],'mean_luma':round(float(_luma(out.mean(0))),4),
            'mean_saturation':round(float(saturation.mean()),4),'coloured_share':round(float(coloured.mean()),4),
            'hue_shares':dict(sorted(shares.items(),key=lambda kv:-kv[1])),'nonfinite_share':nonfinite,
            'input':{'kind':'grey multi-scale noise','level':level,'amplitude':amplitude,'smoothing_px':[1,4,16],'size':list(size),'time':time},
            'coloured_rule':'saturation >= %.2f and max channel >= %.2f'%(DETAIL_SATURATION,DETAIL_VALUE)}


def composite_load_spread(facts,level=.5,draws=8,time=5.,size=(48,27)):
    """How much the displayed colour of a flat canvas depends on the random per-load hue tint.

    projectM draws hueRandomOffsets at every preset load; the corner tint (hue_shader / _vDiffuse) follows
    them. The exported composite is evaluated on a flat canvas at `level` under `draws` tint draws; a
    composite that raises or multiplies by the tint (pow(hue_shader, 4), dot(ret, hue_shader)) shows a
    wide brightness and hue spread, one that ignores it shows none. No frames are stepped.
    """
    import numpy as np
    import prediction_illustration as P
    from time_expression import hue_family
    program=(((facts.get('/analysis/visual_description/stage_programs') or {}).get('stages') or {}).get('composite') or {})
    if program.get('status')!='exported':return None
    width,height=size
    columns,rows=np.meshgrid((np.arange(width)+.5)/width,(np.arange(height)+.5)/height)
    uv=np.stack([columns,rows,columns,rows],axis=-1).astype(np.float32)
    bands={name:1. for name in ('bass','mid','treb','bass_att','mid_att','treb_att')}
    controls=_stage_controls(facts,bands,(time,))
    image=np.full((height,width,3),level,np.float32)
    lumas,families=[],[]
    for seed in range(draws):
        diffuse=P._hue_shader(width,height,float(time),offsets=P._hue_offsets(seed))
        try:out=P._evaluate_stage(program['program'],image,uv,time,30.,bands,diffuse=diffuse,controls=dict(controls[time]),stage='composite')
        except Exception:return None  # noqa: BLE001 - an unevaluable program leaves the spread unknown
        out=np.clip(np.where(np.isfinite(out),out,0.),0,1).reshape(-1,3).mean(0)
        lumas.append(float(_luma(out)));families.append(hue_family(out))
    return {'level':level,'draws':draws,'luma_range':[round(min(lumas),4),round(max(lumas),4)],
            'hue_families':sorted(set(families)),'per_draw_luma':[round(v,4) for v in lumas],
            'meaning':'displayed colour of a flat canvas under different random per-load hue tints'}


def composite_colour_matrix(facts,level=.5,time=5.,size=(48,27)):
    """Composite response to coloured flat canvases: mean output for black and for (l,0,0), (0,l,0), (0,0,l).

    Grey probes (stage_transfer) assume channel independence; channel swaps and mixes (ret = tex.zxy,
    dot(ret, ...)) need coloured probes. Four evaluations of the exported composite, neutral audio, one
    declared time; the result is a local linear map around black at the probe level. No frames are stepped.
    """
    import numpy as np
    import prediction_illustration as P
    program=(((facts.get('/analysis/visual_description/stage_programs') or {}).get('stages') or {}).get('composite') or {})
    if program.get('status')!='exported':return None
    width,height=size
    columns,rows=np.meshgrid((np.arange(width)+.5)/width,(np.arange(height)+.5)/height)
    uv=np.stack([columns,rows,columns,rows],axis=-1).astype(np.float32)
    bands={name:1. for name in ('bass','mid','treb','bass_att','mid_att','treb_att')}
    controls=_stage_controls(facts,bands,(time,))
    outputs=[]
    for colour in ((0.,0.,0.),(level,0.,0.),(0.,level,0.),(0.,0.,level)):
        image=np.broadcast_to(np.array(colour,np.float32),(height,width,3)).copy()
        try:out=P._evaluate_stage(program['program'],image,uv,time,30.,bands,controls=dict(controls[time]),stage='composite')
        except Exception:return None  # noqa: BLE001 - an unevaluable program leaves the matrix unknown
        outputs.append([float(v) for v in np.clip(np.where(np.isfinite(out),out,0.),0,1).reshape(-1,3).mean(0)])
    base=outputs[0]
    return {'level':level,'black_rgb':base,'columns_rgb':[[outputs[c+1][i]-base[i] for i in range(3)] for c in range(3)],
            'meaning':'displayed rgb ~= black_rgb + sum_c (input_c / level) * columns_rgb[c] near the probe level'}


def apply_colour_matrix(matrix,rgb):
    """Displayed colour of a canvas colour through a composite_colour_matrix (clamped to [0, 1])."""
    level=matrix['level'];base=matrix['black_rgb'];columns=matrix['columns_rgb']
    return [min(1.,max(0.,base[i]+sum(rgb[c]/level*columns[c][i] for c in range(3)))) for i in range(3)]


# Work units (eel_memory.WorkBudget) for stepping a frame program: frame-program nodes per step plus loop body
# nodes per iteration. Deterministic, unlike the earlier 3 s wall-clock budget that made ~1% of presets' probes
# depend on machine load. Typical stepping runs ~0.5M units/s; at 2M, 97% of presets (300-preset sample) step to
# t=5 s fully, and the rest stop at the same point on every machine (at most ~4 s).
STAGE_CONTROL_BUDGET_UNITS=2e6


_STAGE_CONTROL_CACHE=[]  # [(facts, key, result)]: the few most recent presets


def _stage_controls(facts,bands,times,fps=30.,budget_units=None):
    """Cached _stage_controls_uncached: one recipe build probes the same frame program many times (16 calls took 4.8
    of 6.4 s). Entries hold the facts object itself and match it by identity, so another preset never reuses them;
    callers receive copies, so mutating a result cannot leak into the next probe."""
    import copy
    key=(tuple(sorted(bands.items())),tuple(times),fps,budget_units)
    for cached_facts,cached_key,result in _STAGE_CONTROL_CACHE:
        if cached_facts is facts and cached_key==key:return copy.deepcopy(result)
    result=_stage_controls_uncached(facts,bands,times,fps=fps,budget_units=budget_units)
    _STAGE_CONTROL_CACHE.insert(0,(facts,key,result));del _STAGE_CONTROL_CACHE[8:]
    return copy.deepcopy(result)


def _stage_controls_uncached(facts,bands,times,fps=30.,budget_units=None):
    """Inputs a stage program reads at each declared time: bands, the engine frame clock, readonly
    render values and the per-frame state (exported frame program stepped under the same bands).

    Frame k renders at time (k+1)/fps; shader programs inline per-frame graphs over the start-of-frame
    state, as the illustrator binds them. Stepping stops when the work budget is spent; later times then use
    the last stepped state.
    """
    import numpy as np
    import prediction_illustration as P
    from eel_memory import WorkBudget
    budget=WorkBudget(STAGE_CONTROL_BUDGET_UNITS if budget_units is None else budget_units)
    constants=P._render_constants(facts.get('/analysis/visual_description/static_behaviour/context') or {})
    frame=(facts.get('/analysis/visual_description/stage_programs') or {}).get('frame') or {}
    stepper=P._FrameStepper(frame,constants=constants,deadline=budget) if frame.get('status')=='exported' and (frame.get('state') or frame.get('outputs')) else None
    step_cost=max(1,_program_nodes(frame.get('state'))+_program_nodes(frame.get('outputs')))
    result={};k=0;out={}
    for time in sorted(times):
        target=max(0,int(round(time*fps))-1)
        base={**bands,**constants,'time':float(np.float32(time)),'fps':float(fps),'frame':float(target),'progress':0.}
        if stepper is not None:
            while k<=target and budget.left>=step_cost:
                budget.left-=step_cost
                out=stepper.step(float(np.float32((k+1)/fps)),fps,bands,k);k+=1
            base.update({name:value for name,value in {**out,**(stepper.start or {})}.items() if isinstance(value,(int,float))})
        result[time]=base
    return result


def _program_nodes(value):
    """Serialised graph nodes under a frame-program block (state initial/update programs, outputs)."""
    if isinstance(value,dict):
        return (len(value['nodes']) if isinstance(value.get('nodes'),list) else 0)+sum(_program_nodes(v) for k,v in value.items() if k!='nodes')
    if isinstance(value,list):return sum(_program_nodes(v) for v in value)
    return 0


def _apply_transfer(transfer,rgb):
    """Piecewise-linear per-channel interpolation of a flat-colour transfer table."""
    levels=transfer['levels'];out=[]
    for i in range(3):
        value=_clip(rgb[i]);k=1
        while k<len(levels)-1 and value>levels[k]:k+=1
        a,b=levels[k-1],levels[k];t=(value-a)/(b-a) if b>a else 0.
        out.append(transfer['rgb'][k-1][i]*(1-t)+transfer['rgb'][k][i]*t)
    return out


def _gain_and_offset(facts,notes):
    transfer=facts.get('/analysis/visual_description/feedback_transfer') or {}
    warp=stage_transfer(facts,'warp')
    if warp is not None:
        # Affine fit of the warp's flat-colour transfer: gain = W(1) - W(0), offset = W(0).
        low,high=warp['rgb'][0],warp['rgb'][-1]
        return [_clip(high[i]-low[i],0.,1.5) for i in range(3)],[low[i] for i in range(3)]
    gain=None
    matrix=transfer.get('matrix_rgb')
    if isinstance(matrix,list) and len(matrix)==3 and all(isinstance(r,list) and len(r)==3 for r in matrix) \
            and all(isinstance(v,(int,float)) for r in matrix for v in r):
        gain=[float(sum(matrix[i]))  for i in range(3)]  # uniform-colour gain per output channel
    if gain is None and isinstance(transfer.get('uniform_diagonal_gain'),(int,float)):
        gain=[float(transfer['uniform_diagonal_gain'])]*3
    if gain is None and isinstance(transfer.get('uniform_content_gain'),(int,float)):
        gain=[float(transfer['uniform_content_gain'])]*3
    if gain is None:
        decay=(facts.get('/analysis/visual_description/static_behaviour/feedback_persistence') or {}).get('decay_gain')
        if isinstance(decay,(int,float)):gain=[float(decay)]*3
    if gain is None:
        notes.append('feedback gain unknown: neutral 0.95 used');gain=[.95]*3
    offset=transfer.get('constant_offset_rgb') or transfer.get('constant_offset_rgb_excluding_injection')
    offset=[float(v) for v in offset] if isinstance(offset,list) and len(offset)==3 and all(isinstance(v,(int,float)) for v in offset) else [0.,0.,0.]
    return [_clip(g,0.,1.5) for g in gain],offset


def _rgb(values,notes,label):
    out=[]
    for value in values:
        mid=_mid(value)
        if mid is None:notes.append(label+' colour unknown: neutral prior');mid=NEUTRAL
        out.append(_clip(mid))
    return out


# Inputs a colour formula may read for a time average without executing frames: source time, the
# engine's frame clock, neutral bands (1.0, the band midpoint) and the instance index.
_AVERAGE_INPUTS={'time','frame','fps','progress','instance','bass','mid','treb','bass_att','mid_att','treb_att'}
_AVERAGE_TIMES=tuple(.25*k for k in range(1,41))


def _formula_mean(expression,instances=1):
    """Time- and instance-averaged value of an authored colour formula over 0.25..10 s, or None.

    The value passes through projectM's colour modulo (period 256/255) and [0, 1] clamp first.
    Formulas that read per-frame state, memory or other inputs return None.
    """
    import numpy as np
    from eel_memory import evaluate_np,input_names
    names=input_names(expression,stochastic=True)
    if names is None or not names<=_AVERAGE_INPUTS:return None
    count=max(1,min(1024,int(instances or 1)))
    # rand calls: the expectation of projectm-eval's uniform draws, estimated with a fixed seed and
    # about 2048 draws per formula (replicates along a third axis).
    stochastic=any(node.get('op')=='rand' for node in expression['nodes'])
    replicates=max(1,-(-2048//(len(_AVERAGE_TIMES)*count))) if stochastic else 1
    shape=(len(_AVERAGE_TIMES),count,replicates)
    times=np.array(_AVERAGE_TIMES)[:,None,None]
    inputs={'time':times,'frame':times*30-1,'fps':30.,'progress':0.,'instance':np.arange(count,dtype=float)[None,:,None],
            **{band:1. for band in ('bass','mid','treb','bass_att','mid_att','treb_att')}}
    rng=np.random.default_rng(20261012) if stochastic else None
    try:value=np.broadcast_to(np.asarray(evaluate_np(expression,inputs,rng,batch_shape=shape if stochastic else None),float),shape)
    except (ValueError,KeyError,TypeError):return None
    period=256/255
    value=np.clip(np.fmod(np.fmod(value,period)+period,period),0,1)
    return float(value.mean()) if np.isfinite(value).all() else None


def _shape_terms(facts,notes):
    """(area fraction, premultiplied mean rgb, mean alpha, additive) per custom shape."""
    terms=[]
    for path,value in facts.items():
        if not path.endswith('/geometry') or not isinstance(value,dict) or value.get('policy')!='source-custom-shape-footprint-v1':continue
        base=path.rsplit('/',1)[0]
        material=facts.get(base+'/material') or {};parameters=facts.get(base+'/parameters') or {}
        outline=_outline_term(material,parameters)
        if outline is not None:terms.append(outline)
        if parameters.get('textured') or (material.get('texture') or {}).get('role')=='previous_main':
            notes.append(base+': textured shape copies the canvas (no new energy)');continue
        area=value.get('summed_nominal_area_fraction_per_aspect_y')
        if not isinstance(area,(int,float)):
            sides=parameters.get('instances') or 1
            area=sides*math.pi*.1**2/4;notes.append(base+': area unknown, nominal radius 0.1')
        area=min(1.,float(area)*ASPECT_Y)
        centre=list(material.get('centre_vertex_rgba') or [None]*4);edge=list(material.get('perimeter_vertex_rgba') or [None]*4)
        # Dynamic channels: the time average of the authored formula instead of the neutral prior.
        channels=material.get('channel_expressions') or {}
        for values,group,keys in ((centre,'centre','rgba'),(edge,'perimeter',('r2','g2','b2','a2'))):
            for index,key in enumerate(keys):
                if _mid(values[index]) is None and isinstance((channels.get(group) or {}).get(key),dict):
                    values[index]=_formula_mean(channels[group][key],parameters.get('instances') or 1)
        c0=_rgb(centre[:3],notes,base+' centre');c1=_rgb(edge[:3],notes,base+' perimeter')
        a0=_clip(_mid(centre[3]) if _mid(centre[3]) is not None else NEUTRAL);a1=_clip(_mid(edge[3]) if _mid(edge[3]) is not None else NEUTRAL)
        # Triangle-fan radial gradient, area-averaged over a disc: E[c*a] and E[a] with weight 2r dr.
        premultiplied=[c0[i]*a0/6+(c0[i]*a1+c1[i]*a0)/6+c1[i]*a1/2 for i in range(3)]
        alpha=a0/3+2*a1/3
        terms.append((area,premultiplied,alpha,bool(parameters.get('additive') or material.get('additive'))))
    return terms


OUTLINE_SAMPLES_PER_EDGE=32


def _outline_term(material,parameters):
    """A custom shape's outline as an element: (area fraction, premultiplied rgb, alpha, additive) or None.

    The engine draws the outline (border_a > 0.0001) as a line strip through the polygon corners in the border
    colour with the untextured shader, so it adds new light even when the fill samples the canvas. Corners sit at
    x + rad*cos(t)*aspectY, y + rad*sin(t) in normalized device coordinates, so on screen the polygon has a circumradius
    of rad*H/2 pixels. A line is 1 px wide; a thick outline is four 1-px passes offset by a pixel (2 px).
    The covered area is the on-screen part of the perimeter times the width, over the reference frame.
    """
    rgba=material.get('border_vertex_rgba')
    if material.get('border_draw_enabled') is False or not isinstance(rgba,list) or len(rgba)!=4:return None
    alpha=_mid(rgba[3])
    threshold=material.get('border_enable_threshold') if isinstance(material.get('border_enable_threshold'),(int,float)) else 1e-4
    if alpha is None or alpha<=threshold:return None
    values={k:_mid(parameters.get(k)) if isinstance(parameters.get(k),list) else parameters.get(k) for k in ('sides','rad','x','y','ang')}
    if any(not isinstance(values[k],(int,float)) for k in ('sides','rad','x','y')):return None
    sides=int(max(3,min(100,values['sides'])));angle=float(values['ang']) if isinstance(values['ang'],(int,float)) else 0.
    width,height=REFERENCE;radius=abs(float(values['rad']))*height/2
    cx=float(values['x'])*width;cy=(1-float(values['y']))*height
    corners=[(cx+radius*math.cos(angle+2*math.pi*k/sides),cy+radius*math.sin(angle+2*math.pi*k/sides)) for k in range(sides+1)]
    visible=0.
    for (x0,y0),(x1,y1) in zip(corners,corners[1:]):
        length=math.hypot(x1-x0,y1-y0);inside=0
        for i in range(OUTLINE_SAMPLES_PER_EDGE):
            t=(i+.5)/OUTLINE_SAMPLES_PER_EDGE;x=x0+(x1-x0)*t;y=y0+(y1-y0)*t
            inside+=0<=x<=width and 0<=y<=height
        visible+=length*inside/OUTLINE_SAMPLES_PER_EDGE
    thickness=2. if material.get('thick_outline') else 1.
    instances=parameters.get('instances') if isinstance(parameters.get('instances'),(int,float)) and parameters.get('instances')>0 else 1
    area=min(1.,instances*visible*thickness/(width*height))
    if area<=0:return None
    rgb=[_clip(_mid(c)) if _mid(c) is not None else NEUTRAL for c in rgba[:3]];alpha=_clip(alpha)
    return (area,[c*alpha for c in rgb],alpha,bool(parameters.get('additive') or material.get('additive')))


def _border_terms(facts):
    terms=[]
    borders=(facts.get('/analysis/visual_description/static_behaviour/borders') or {}).get('borders') or []
    for border in borders:
        if not border.get('active'):continue
        area=border.get('screen_area_fraction');alpha=_mid(border.get('alpha_range'))
        if not isinstance(area,(int,float)) or alpha is None:continue
        rgb=[_clip(_mid(r)) if _mid(r) is not None else NEUTRAL for r in (border.get('rgb_ranges') or [None]*3)]
        terms.append((float(area),[c*alpha for c in rgb],_clip(alpha),False))
    return terms


def _wave_terms(facts,notes):
    width,height=REFERENCE;terms=[]
    for path,value in facts.items():
        if not path.endswith('/waveform_recipe') or not isinstance(value,dict):continue
        base=path.rsplit('/',1)[0];material=facts.get(base+'/wave_material') or {}
        rgb=material.get('constant_vertex_rgb') or [_mid(e) for e in (material.get('rgb_component_envelopes') or [None]*3)]
        rgb=_rgb(rgb,notes,base)
        recipe=material.get('alpha_recipe') or {}
        alpha=_mid(recipe.get('alpha_envelope_without_volume_modulation'))
        if alpha is None:alpha=.5;notes.append(base+': wave alpha unknown, 0.5')
        alpha=_clip(alpha*float(recipe.get('mode_gain') or 1.))
        paths=value.get('path_count') or 1
        if value.get('dots'):coverage=paths*(width/3)*(4 if value.get('thick') else 1)/(width*height)
        else:coverage=paths*width*(2 if value.get('thick') else 1)/(width*height)
        terms.append((min(1.,coverage),[c*alpha for c in rgb],alpha,bool(value.get('additive'))))
    for path,value in facts.items():
        if '/colour/components/' not in path or not isinstance(value,dict):continue
        record=(value.get('source_palette') or {}).get('point_colour_distribution') or {}
        if record.get('status')!='closed_form_point_colours':continue
        flags=record.get('draw_flags') or {};count=int(record.get('sample_count') or 512)
        alpha=_clip(record.get('mean_alpha') or 0.)
        rgb=record.get('alpha_weighted_mean_rgb') or record.get('mean_rgb') or [NEUTRAL]*3
        if flags.get('dots'):coverage=count*(4 if flags.get('thick') else 1)/(width*height)
        else:
            bounds=record.get('position_bounds') or {}
            span=(max(.05,bounds['x'][1]-bounds['x'][0])*width+max(.05,bounds['y'][1]-bounds['y'][0])*height) if bounds.get('x') and bounds.get('y') else width
            coverage=span*(2 if flags.get('thick') else 1)/(width*height)
        terms.append((min(1.,coverage),[_clip(c)*alpha for c in rgb],alpha,flags.get('additive',True) is not False))
    vectors=facts.get('/analysis/visual_description/static_behaviour/motion_vectors') or {}
    if vectors.get('status')=='described' and vectors.get('vector_count'):
        colour=vectors.get('colour_rgba') or [1,1,1,1]
        alpha=_clip(colour[3] if len(colour)>3 and isinstance(colour[3],(int,float)) else 1.)
        rgb=[_clip(c) if isinstance(c,(int,float)) else NEUTRAL for c in colour[:3]]
        terms.append((min(1.,vectors['vector_count']*1.5/(width*height)),[c*alpha for c in rgb],alpha,False))
    elif vectors.get('status')=='partial' and vectors.get('activation') in ('active','possible'):
        # A grid sized per frame (mv_x, mv_y written by the frame program) has no constant count; its declared
        # control ranges still bound it, so the range midpoints stand in rather than dropping the grid.
        ranges=vectors.get('control_ranges') or {}
        mid=lambda name,default:_mid(ranges.get(name)) if _mid(ranges.get(name)) is not None else default
        count=max(0.,mid('mv_x',0.))*max(0.,mid('mv_y',0.));alpha=_clip(mid('mv_a',1.))
        if count>0 and alpha>0:
            rgb=[_clip(mid(name,NEUTRAL)) for name in ('mv_r','mv_g','mv_b')]
            terms.append((min(1.,count*1.5/(width*height)),[c*alpha for c in rgb],alpha,False))
            notes.append('motion vectors: grid counted at its control-range midpoints (%d vectors)'%round(count))
    return terms


def stage_output_at(facts,stage,rgb,times=TIMES,size=(48,27)):
    """Mean output RGB of an exported stage program for one flat input colour, averaged over the declared
    times (None when unevaluable). A program can mix channels (output red read from input green), so this
    is the transfer at the colour itself, not three per-channel grey-ramp lookups."""
    import numpy as np
    import prediction_illustration as P
    program=(((facts.get('/analysis/visual_description/stage_programs') or {}).get('stages') or {}).get(stage) or {})
    if program.get('status')!='exported':return None
    width,height=size
    columns,rows=np.meshgrid((np.arange(width)+.5)/width,(np.arange(height)+.5)/height)
    uv=np.stack([columns,rows,columns,rows],axis=-1).astype(np.float32)
    bands={name:1. for name in ('bass','mid','treb','bass_att','mid_att','treb_att')}
    controls=_stage_controls(facts,bands,times)
    image=np.broadcast_to(np.array([_clip(v) for v in rgb],np.float32),(height,width,3)).copy()
    outputs=[]
    for time in times:
        try:out=P._evaluate_stage(program['program'],image,uv,time,30.,bands,controls=dict(controls[time]),stage=stage)
        except Exception:return None  # noqa: BLE001
        out=np.where(np.isfinite(out),out,0.)
        outputs.append(np.clip(out,0,1).reshape(-1,3).mean(0))
    return [float(v) for v in np.mean(outputs,axis=0)]


def _composite(rgb,facts,notes,transfer=None):
    if transfer is not None:
        exact=stage_output_at(facts,'composite',rgb,times=tuple(transfer.get('times') or TIMES))
        if exact is not None:return [_clip(v) for v in exact],'composite_transfer'
        return [_clip(v) for v in _apply_transfer(transfer,rgb)],'composite_transfer'
    stage=((facts.get('/analysis/visual_description/texture_colour_transfer') or {}).get('stages') or {}).get('composite') or {}
    if stage.get('source_model')=='affine_sample_colour':
        matrix=stage.get('base_uv_matrix_rgb');offset=stage.get('constant_offset_rgb') or [0,0,0]
        if isinstance(matrix,list) and len(matrix)==3:
            try:return [_clip(sum(float(matrix[i][j])*rgb[j] for j in range(3))+float(offset[i])) for i in range(3)],'affine_composite'
            except (TypeError,ValueError,IndexError):pass
    legacy=None
    for path,value in facts.items():
        if path.endswith('/legacy_response') and isinstance(value,dict):legacy=value;break
    if legacy is None:
        notes.append('composite transfer unknown: identity');return rgb,'identity'
    controls=legacy.get('native_control_ranges') or {}
    gamma=_mid(controls.get('gamma'));gamma=1. if gamma is None else gamma
    out=[_clip(c*gamma) for c in rgb]
    if (_mid(controls.get('brighten')) or 0)>.5:out=[2*c-c*c for c in out]
    if (_mid(controls.get('darken')) or 0)>.5:out=[c*c for c in out]
    if (_mid(controls.get('solarize')) or 0)>.5:out=[2*c*(1-c) for c in out]
    if (_mid(controls.get('invert')) or 0)>.5:out=[1-c for c in out]
    return out,'legacy'


def _composite_shape(composite):
    """Descriptor facts of the composite's flat transfer: the canvas level where displayed luma first
    crosses 0.5 (None if never), the largest per-channel spread between sample times, and the share of
    non-finite outputs."""
    if not composite:return {'composite_threshold_level':None,'composite_spread_max':0.,'composite_nonfinite_share':0.}
    levels,lumas=composite['levels'],[_luma(row) for row in composite['rgb']]
    threshold=None
    if lumas and lumas[0]>=.5:threshold=levels[0]
    else:
        for (a,la),(b,lb) in zip(zip(levels,lumas),zip(levels[1:],lumas[1:])):
            if la<.5<=lb:threshold=a+(b-a)*(.5-la)/(lb-la);break
    spread=max((v for row in composite.get('rgb_spread') or [] for v in row),default=0.)
    return {'composite_threshold_level':threshold,'composite_spread_max':float(spread),
            'composite_nonfinite_share':float(composite.get('nonfinite_share') or 0.)}


def equilibrium(summary):
    """Steady-state canvas/display brightness and colour bounds from the summary facts."""
    facts={fact['path']:fact['value'] for group in summary['facts'].values() for fact in group}
    notes=[]
    gain,offset=_gain_and_offset(facts,notes)
    terms=_shape_terms(facts,notes)+_border_terms(facts)+_wave_terms(facts,notes)
    background=[_clip(offset[i]/(1-gain[i])) if gain[i]<1 else (1. if offset[i]>0 else 0.) for i in range(3)]
    local=list(background);covered=0.;energy=[0.,0.,0.]
    for area,premultiplied,alpha,additive in terms:
        area=min(area,max(0.,1-covered));covered+=area
        for i in range(3):
            if additive:value=premultiplied[i]/(1-gain[i]) if gain[i]<1 else (1. if premultiplied[i]>0 else 0.)
            else:
                denominator=1-(1-alpha)*gain[i]
                value=premultiplied[i]/denominator if denominator>1e-6 else (1. if premultiplied[i]>0 else 0.)
            local[i]+=area*(_clip(value)-background[i])
            energy[i]+=area*premultiplied[i]
    spread=[_clip((energy[i]+offset[i])/(1-gain[i])) if gain[i]<1 else (1. if energy[i]+offset[i]>0 else 0.) for i in range(3)]
    composite=stage_transfer(facts,'composite')
    shown_local,model=_composite(local,facts,notes,composite);shown_spread,_=_composite(spread,facts,notes,composite)
    return {'policy':POLICY,'gain_rgb':gain,'offset_rgb':offset,'elements':len(terms),'drawn_area_fraction':covered,
            'energy_rgb_per_frame':energy,'canvas_local_rgb':local,'canvas_spread_rgb':spread,
            'display_local_rgb':shown_local,'display_spread_rgb':shown_spread,
            'display_local_luma':_luma(shown_local),'display_spread_luma':_luma(shown_spread),
            'display_local_saturation':_saturation(shown_local),'display_spread_saturation':_saturation(shown_spread),
            'composite_model':model,'substitutions':notes[:20],'substitution_count':len(notes),
            **_composite_shape(composite),
            'uses_equation_execution':False,'uses_rendered_images':False}
