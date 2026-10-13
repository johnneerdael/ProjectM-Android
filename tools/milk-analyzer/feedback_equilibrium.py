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


LEVELS=(0.,.25,.5,.75,1.)
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
    table,spread=[],[]
    for level in levels:
        image=np.full((height,width,3),level,np.float32)
        outputs=[]
        for time in times:
            try:
                out=P._evaluate_stage(program['program'],image,uv,time,30.,bands,controls=dict(controls[time]),stage=stage)
            except Exception:  # noqa: BLE001 - an unevaluable program leaves the transfer unknown
                return None
            out=np.where(np.isfinite(out),out,0.)
            outputs.append(np.clip(out,0,1).reshape(-1,3).mean(0))
        table.append([float(v) for v in np.mean(outputs,axis=0)])
        # How far each channel moves between the declared times (time-driven palette shifts).
        spread.append([float(v) for v in np.ptp(outputs,axis=0)])
    return {'levels':list(levels),'rgb':table,'rgb_spread':spread,'times':list(times)}


STAGE_CONTROL_BUDGET_SECONDS=3.


def _stage_controls(facts,bands,times,fps=30.,budget_seconds=STAGE_CONTROL_BUDGET_SECONDS):
    """Inputs a stage program reads at each declared time: bands, the engine frame clock, readonly
    render values and the per-frame state (exported frame program stepped under the same bands).

    Frame k renders at time (k+1)/fps; shader programs inline per-frame graphs over the start-of-frame
    state, as the illustrator binds them. Stepping stops after budget_seconds; later times then use
    the last stepped state.
    """
    import time as clock
    import numpy as np
    import prediction_illustration as P
    deadline=clock.perf_counter()+budget_seconds
    constants=P._render_constants(facts.get('/analysis/visual_description/static_behaviour/context') or {})
    frame=(facts.get('/analysis/visual_description/stage_programs') or {}).get('frame') or {}
    stepper=P._FrameStepper(frame,constants=constants,deadline=deadline) if frame.get('status')=='exported' and (frame.get('state') or frame.get('outputs')) else None
    result={};k=0;out={}
    for time in sorted(times):
        target=max(0,int(round(time*fps))-1)
        base={**bands,**constants,'time':float(np.float32(time)),'fps':float(fps),'frame':float(target),'progress':0.}
        if stepper is not None:
            while k<=target and clock.perf_counter()<deadline:
                out=stepper.step(float(np.float32((k+1)/fps)),fps,bands,k);k+=1
            base.update({name:value for name,value in {**out,**(stepper.start or {})}.items() if isinstance(value,(int,float))})
        result[time]=base
    return result


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
        if parameters.get('textured'):notes.append(base+': textured shape copies the canvas (no new energy)');continue
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
    return terms


def _composite(rgb,facts,notes,transfer=None):
    if transfer is not None:return [_clip(v) for v in _apply_transfer(transfer,rgb)],'composite_transfer'
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
            'uses_equation_execution':False,'uses_rendered_images':False}
