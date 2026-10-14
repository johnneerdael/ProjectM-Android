"""Machine-readable visual recipe and mood record for one preset.

``build_recipe(summary, source=None)`` turns an understanding-SDK summary (and
optionally the native reader's parsed source) into one JSON document:

- ``render``: an engine-neutral description of the effect - feedback loop
  (decay, persistence floor, warp patterns, shader mechanisms, flat-field
  colour), drawn layers (waves, custom curves, shapes, motion vectors) with
  their constant parameters and control formulas, and the composite (echo,
  gamma, scalar palette). It is meant for building a similar effect in another
  engine (WebGL, for example) without reference visuals; it is not a
  pixel-exact specification.
- ``mood``: the approximate feature vector, research scores, tags and editable
  profile suitability (approximate_features.describe).
- ``intent``: the generic effect list and music-reactivity map - the primary
  input for an 'alike' rebuild in a newer engine at higher fidelity.
- ``program`` (optional, off by default): parsed equation ASTs and authored
  shader source, only for users who want an exact port.

Expressions use the exporter's serialised graph form {root, nodes[op, args,
detail]}; inputs named time/bass/mid/treb/... are runtime inputs, other inputs
are persistent preset variables whose update equations live in ``program``.
Every record keeps ``evidence`` JSON pointers into the source export.
"""
import bisect
import copy
import hashlib
import json
import math
from pathlib import Path

POLICY='preset-visual-recipe-v1'
BASE='/analysis/visual_description'
STATIC=BASE+'/static_behaviour'
CONVENTIONS={
    'coordinates':'per-pixel x/y in [0,1] measured along the long viewport side (y=0 top); short axis spans a centred sub-range',
    'feedback':'each frame the previous image is resampled through the warp map, multiplied by decay, then layers are drawn on top; the composite displays the result',
    'warp_map':'source = 0.5+(p-0.5)/zoom^(zoomexp^(2*rad-1)), stretched/rotated about (cx,cy), minus (dx,dy); content therefore moves +dx right, +dy down',
    'time':'seconds since preset start; audio inputs bass/mid/treb are ~1 on average (attenuated *_att variants are smoothed)',
    'expressions':'serialised graphs {root,nodes}; EEL semantics follow projectm-eval (int=floor, x/0=0 when |d|<1e-5)',
    'fidelity':'approximate recipe for a similar effect, not a pixel-exact specification',
}



UNIT_BANDS={name:1. for name in ('bass','mid','treb','bass_att','mid_att','treb_att','vol','vol_att')}


def _value_at_unit_bands(expression):
    """Value of a band-only frame expression when every band reads 1 (projectM's bands hover around 1,
    their long-run normalisation). None when the expression reads anything else."""
    from time_expression import evaluate_inputs
    try:value=float(evaluate_inputs(expression,UNIT_BANDS))
    except (ValueError,KeyError,TypeError,ZeroDivisionError):return None
    return value if value==value and abs(value)!=float('inf') else None


def _facts(summary):
    out={}
    for group,rows in summary.get('facts',{}).items():
        for row in rows:out[row['path']]=row['value']
    return out


def _element_indices(facts):
    indices=set()
    for path in facts:
        if path.startswith(BASE+'/elements/'):
            part=path[len(BASE+'/elements/'):].split('/')[0]
            if part.isdigit():indices.add(int(part))
    return sorted(indices)


def _control(row):
    keep=('control','control_unit','curve_kind','constant_value','offset_value','amplitude_value','period_seconds',
          'frequency_hz','nominal_value_range','signed_linear_rate_per_second','maximum_absolute_control_rate_per_second','expression')
    return {k:copy.deepcopy(row.get(k)) for k in keep if row.get(k) is not None}


def _curve(recipe):
    if not isinstance(recipe,dict):return None
    keep=('curve_class','centre_source_xy','radius_affine_coefficients','phase_affine_coefficients','axis_trig_functions',
          'nominal_turns_across_sample_domain','nominal_phase_cycles_per_source_second')
    out={k:copy.deepcopy(recipe.get(k)) for k in keep if recipe.get(k) is not None}
    colours=(recipe.get('spatial_vertex_colour') or {}).get('channels') or {}
    out['vertex_colour_affine']={name:(colours.get(name) or {}).get('affine_coefficients') for name in 'rgba' if colours.get(name)}
    domain=recipe.get('sample_domain') or {}
    if domain.get('effective_samples'):out['samples']=domain['effective_samples']
    return out


def _layer(facts,index):
    path=BASE+'/elements/%d'%index
    identity=facts.get(path+'/id')
    stage=facts.get(path+'/stage')
    parameters=copy.deepcopy(facts.get(path+'/parameters') or {})
    layer={'id':identity,'stage':stage,'mechanisms':copy.deepcopy(facts.get(path+'/mechanisms') or []),
           'evidence':[path]}
    curve=parameters.pop('source_curve_recipe',None)
    layer['constants']={k:v for k,v in parameters.items() if isinstance(v,(int,float,str,bool)) and v is not None}
    if curve is not None:layer['analytic_curve']=_curve(curve)
    controls=[_control(v) for p,v in sorted(facts.items()) if p.startswith(path+'/motion_controls/') and isinstance(v,dict)]
    if controls:layer['controls']=controls
    texture=((facts.get(path+'/material') or {}).get('texture') or {}) if isinstance(facts.get(path+'/material'),dict) else {}
    if texture.get('role') and texture['role']!='untextured_vertex_gradient':
        # Textured shapes draw an image into the polygon: previous_main is the last frame (a feedback copy).
        layer['texture']={'role':texture['role'],**{out:texture[key] for key,out in (('tex_zoom_source','tex_zoom'),('tex_angle_source_rad','tex_angle_rad'))
                                                     if type(texture.get(key)) in (int,float)}}
    geometry=facts.get(path+'/geometry')
    if isinstance(geometry,dict):
        layer['geometry']={k:geometry.get(k) for k in ('radius_ndc','effective_sides','configured_instances','center_source_xy') if geometry.get(k) is not None}
    trajectory=facts.get(path+'/center_trajectory')
    if isinstance(trajectory,dict):
        layer['centre_path']={k:copy.deepcopy(trajectory.get(k)) for k in ('path_kind','center_source_xy','period_seconds',
            'semiaxis_lengths_source_units','angular_rate_rad_per_second','maximum_source_speed_units_per_second') if trajectory.get(k) is not None}
        axes=[_control(axis) for axis in trajectory.get('axis_curves') or [] if isinstance(axis,dict)]
        if axes:layer['centre_axes']=axes
    waveform=facts.get(path+'/waveform_recipe')
    if isinstance(waveform,dict):
        layer['builtin_wave']={k:copy.deepcopy(waveform.get(k)) for k in ('form_name','effective_mode','audio_inputs','wave_x','wave_y',
            'line_angle_rad','separation_normal_offset','base_radius_model_units','sample_radial_gain','nominal_rotation_rad_per_second',
            'dots','thick','additive','path_topology') if waveform.get(k) is not None}
        mystery=waveform.get('normalized_mystery');base=waveform.get('base_radius_model_units')
        if waveform.get('effective_mode') in (0,1) and type(mystery) in (int,float) and type(base) in (int,float):
            # Circle.cpp / XYOscillationSpiral.cpp: radius = base + gain*pcm + mystery (normalised); a
            # negative radius draws the same ring through the opposite side of the centre.
            layer['builtin_wave']['effective_base_radius_model_units']=base+mystery
    material=facts.get(path+'/wave_material')
    if isinstance(material,dict):
        channels={}
        for name,channel in (material.get('channels') or {}).items():
            curve_row=(channel or {}).get('raw_time_curve') or {}
            channels[name]={'time_expression':copy.deepcopy(channel.get('time_only_expression')),
                            **{k:curve_row.get(k) for k in ('curve_kind','constant_value','nominal_value_range','period_seconds') if curve_row.get(k) is not None}}
        expressions=(waveform.get('control_expressions') if isinstance(waveform,dict) else None) or {}
        for name,channel in channels.items():
            if channel.get('time_expression') is None and (expressions.get(name) or {}).get('complete'):
                channel['frame_expression']=copy.deepcopy(expressions[name])
                value=_value_at_unit_bands(expressions[name])
                if value is not None:channel['value_at_unit_bands']=value
        layer['colour']={'channels':channels,'max_normalised':bool(material.get('normalization_enabled')),
                         'blend':material.get('blend_mode')}
        if layer['colour']['max_normalised']:
            # Waveform.cpp (bMaximizeWaveColor): only a largest channel above 0.01 is scaled to 1.
            layer['colour']['max_normalise_rule']={'threshold':.01,
                'above':'every channel is divided by the largest, so the largest becomes 1',
                'at_or_below':'channels are drawn as authored (near black for small values)'}
    elif isinstance(facts.get(path+'/colour'),dict):
        layer['colour']=copy.deepcopy(facts[path+'/colour'])
    shape_material=facts.get(path+'/material')
    if isinstance(shape_material,dict) and shape_material.get('channel_expressions'):
        try:over_time=shape_colour_over_time(shape_material)
        except (ValueError,TypeError,KeyError,ArithmeticError):over_time=None
        if over_time:
            if (shape_material.get('texture') or {}).get('role')=='previous_main':
                # A textured shape draws the previous frame: its colours multiply the copied image (CustomShape
                # vertex colour times the texture), so they are a tint, never a fill colour.
                over_time['role']='tint multiplying the copied previous frame (not a fill colour)'
            layer['colour_over_time']=over_time
    for colour_path,colour_row in facts.items():
        if not colour_path.startswith(STATIC+'/colour/components/') or not isinstance(colour_row,dict):continue
        if colour_row.get('component_id')!=identity:continue
        points=(colour_row.get('source_palette') or {}).get('point_colour_distribution') or {}
        if points.get('status') in ('closed_form_point_colours','frame_state_point_colours') or points.get('positions_only'):
            layer['point_cloud']={'points_per_frame':points.get('sample_count'),'sample_grid':'sample=j/(N-1)',
                'colour_resolved':not points.get('positions_only'),'authored_rgba':points.get('authored_rgba'),
                **{k:copy.deepcopy(points.get(k)) for k in ('hue_family_shares','mean_rgb','mean_alpha','mean_saturation',
                   'held_inputs','positions_closed_form','position_bounds','frame_inputs','programs')},
                'coordinates':'MilkDrop source x right, y down, nominal [0,1]; colours native modulo 256/255 then clamp',
                'evidence':colour_path}
        break
    routes=[{'input_code':v.get('input_code'),'target':v.get('control'),'linear_gain':v.get('linear_gain'),
             'threshold_or_clamp':v.get('has_threshold_or_clamp'),'expression':copy.deepcopy(v.get('expression'))}
            for p,v in sorted(facts.items()) if p.startswith(path+'/audio_routes/') and isinstance(v,dict)]
    if routes:layer['audio']=routes
    return layer


AUDIO_NAMES={1:'bass',2:'mid',3:'treb',4:'bass_att',5:'mid_att',6:'treb_att',7:'vol',8:'vol_att'}


def _warp_transfer(facts):
    """Per-frame persistence of a custom warp shader, which the decay control does not reach.

    projectM returns the warp shader's ret unchanged (decay only feeds _vDiffuse), so trails follow
    the shader itself: its flat-colour transfer W(c) (feedback_equilibrium.stage_transfer) gives
    gain W(1)-W(0) and offset W(0) per channel, and uniform content halves in ln 0.5 / ln gain frames.
    """
    from feedback_equilibrium import stage_transfer
    table=stage_transfer(facts,'warp')
    if table is None:return None
    levels=table['levels'];rgb=table['rgb']
    low,high=rgb[0],rgb[-1]
    gain=[round(high[i]-low[i],6) for i in range(3)];offset=[round(low[i],6) for i in range(3)]
    mean=[sum(row)/3 for row in rgb]
    per_channel={name:_iterated_persistence(levels,[row[i] for row in rgb]) for i,name in enumerate('rgb')}
    # A warp that keeps one channel and clears another has no single persistence: its channel mean
    # would describe neither (ret.x = main.x on flat content keeps red whole and clears green/blue).
    selective=max(gain)-min(gain)>.1
    summary=_iterated_persistence(levels,mean)
    wrap=_wrap_cycle(levels,mean)
    return {'gain_rgb':gain,'offset_rgb':offset,'linear':summary['linear'] and wrap is None,
            'halving_frames':None if selective or wrap else summary['halving_frames'],
            'steady_level_from_full':None if selective or wrap else summary['steady_level_from_full'],
            'channel_selective':selective,'per_channel':per_channel,'wrap':wrap,
            'retention_by_level':[{'level':level,'retention':round(value/level,3)} for level,value in zip(levels,mean) if level>0],
            'levels':levels,'rgb':rgb,'source':'exported warp shader evaluated on flat colours'}


def _wrap_cycle(levels,values):
    """A modulo (frac/fmod) warp: interior levels move by a constant shift while the end the shift runs
    into jumps to the other end. Content then cycles through the whole range every 1/|shift| frames
    instead of fading. None when the transfer does not wrap."""
    interior=[(level,value) for level,value in zip(levels,values) if 0<level<1]
    if len(interior)<2:return None
    shifts=[value-level for level,value in interior];shift=sum(shifts)/len(shifts)
    if not 1e-4<abs(shift)<.1 or max(shifts)-min(shifts)>.01:return None
    wrapped=values[0]-levels[0]>.5 if shift<0 else levels[-1]-values[-1]>.5
    if not wrapped:return None
    return {'shift_per_frame':shift,'cycle_frames':1/abs(shift),
            'description':'levels step by the shift each frame and wrap around the range (colour cycling), not a fade'}


def _iterated_persistence(levels,values):
    """Uniform-content persistence of one transfer curve W (levels -> values): gain W(1)-W(0), whether
    W is affine within 0.02, frames for full level to fall to half (closed form ln .5/ln gain when
    affine; None if it never halves) and the level the iteration settles at (None within 600 frames)."""
    affine=[values[0]+(values[-1]-values[0])*level for level in levels]
    linear=max(abs(a-b) for a,b in zip(values,affine))<.02
    def step(x):
        # Piecewise-linear transfer of a uniform level.
        k=1
        while k<len(levels)-1 and x>levels[k]:k+=1
        a,b=levels[k-1],levels[k];t=(x-a)/(b-a) if b>a else 0.
        return values[k-1]*(1-t)+values[k]*t
    x=float(levels[-1]);halving=None;steady=None
    for frame in range(1,601):
        nxt=step(x)
        if halving is None and nxt<=.5*levels[-1]:halving=frame
        if abs(nxt-x)<1e-5:steady=round(nxt,3);break
        x=nxt
    g=values[-1]-values[0]
    if linear and halving is not None and 0<g<1:halving=math.log(.5)/math.log(g)
    return {'gain':round(g,6),'linear':linear,'halving_frames':halving,'steady_level_from_full':steady}


COMPARISONS={'greater':'>','greater_equal':'>=','less':'<','less_equal':'<='}


def _per_load_random(program):
    """Branches on MilkdropShader's rand_preset: four floatRand() values drawn when the shader is built,
    i.e. once per preset load. A comparison of one component with a constant is a per-load switch whose
    probability follows from the uniform draw; other reads use the component continuously."""
    if not isinstance(program,dict):return None
    nodes=program.get('nodes') or []
    components={i:n['detail'].get('field') for i,n in enumerate(nodes) if n.get('op')=='member' and n.get('args')
                and nodes[n['args'][0]].get('op')=='input' and nodes[n['args'][0]]['detail'].get('name')=='rand_preset'}
    if not components:return None
    switches=[];switched=set()
    for node in nodes:
        op=COMPARISONS.get(node.get('op'))
        args=node.get('args') or []
        if op is None or len(args)!=2:continue
        a,b=args
        if a in components and nodes[b].get('op')=='constant':index,constant,flip=a,nodes[b]['detail'].get('value'),False
        elif b in components and nodes[a].get('op')=='constant':index,constant,flip=b,nodes[a]['detail'].get('value'),True
        else:continue
        if type(constant) not in (int,float):continue
        if flip:op={'>':'<','>=':'<=','<':'>','<=':'>='}[op]
        c=min(1.,max(0.,float(constant)))
        probability=1-c if op in ('>','>=') else c
        switches.append({'component':components[index],'condition':op+' '+format(float(constant),'.6g'),'probability_true':round(probability,6)})
        switched.add(index)
    continuous=sorted({field for index,field in components.items() if index not in switched})
    return {'switches':switches,'continuous_components':continuous,
            'source':'rand_preset: four uniform values drawn per preset load (MilkdropShader floatRand)'}


def _subgraph(nodes,root):
    """The nodes reachable from root, reindexed (root first)."""
    order=[];index={}
    def visit(i):
        if i in index:return
        index[i]=len(order);order.append(i)
        for j in nodes[i].get('args') or []:visit(j)
    visit(root)
    return {'root':0,'nodes':[{**nodes[i],'args':[index[j] for j in nodes[i].get('args') or []]} for i in order]}


def _random_redraws(frame):
    """Per-frame state written as select(condition, ...rand..., itself): a random redraw whenever the
    condition holds (the random-palette template: mq2x = if(above(chng,cthr), rand(n), mq2x)). The
    condition is evaluated per frame (time = (k+1)/30 s, bands at 1) over the first 60 s."""
    from time_expression import evaluate_inputs,input_names
    states=[]
    for name,entry in ((frame or {}).get('state') or {}).items():
        graph=(entry or {}).get('update') or {};nodes=graph.get('nodes') or []
        if not nodes or nodes[graph.get('root',0)].get('op')!='select':continue
        condition,a,b=nodes[graph.get('root',0)]['args']
        def has_rand(i,seen=None):
            seen=seen if seen is not None else set()
            if i in seen:return False
            seen.add(i);return nodes[i].get('op')=='rand' or any(has_rand(j,seen) for j in nodes[i].get('args') or [])
        own=lambda i:nodes[i].get('op')=='input' and nodes[i]['detail'].get('name') in (name,'state:per_frame_:'+name)
        if (has_rand(a) and own(b)) or (has_rand(b) and own(a)):states.append((name,_subgraph(nodes,condition),has_rand(a)))
    if not states:return None
    name,condition,on_true=states[0]
    times=[]
    try:
        names=input_names(condition) or set()
        if names-{'time','bass','mid','treb','bass_att','mid_att','treb_att'}:raise ValueError('condition reads other state')
        previous=False
        for k in range(1800):
            t=(k+1)/30;value=bool(evaluate_inputs(condition,{'time':t,**{n:1. for n in ('bass','mid','treb','bass_att','mid_att','treb_att')}}))
            fired=value if on_true else not value
            if fired and not previous:times.append(round(t,4))
            previous=fired
    except (ValueError,KeyError,TypeError,ZeroDivisionError):times=None
    redrawn={n for n,_,_ in states}
    feeds=sorted(out for out,graph in ((frame or {}).get('outputs') or {}).items()
                 if any(node.get('op')=='input' and node['detail'].get('name') in redrawn|{'state:per_frame_:'+n for n in redrawn}
                        for node in (graph or {}).get('nodes') or []))
    gaps=[b-a for a,b in zip(times,times[1:])] if times else []
    return {'states':sorted(redrawn),'feeds':feeds,'event_times_s':times[:8] if times is not None else None,
            'period_s':sorted(gaps)[len(gaps)//2] if gaps else None,
            'note':'values are redrawn with projectm-eval rand (one process-wide stream): each draw is a random outcome'}


COLOUR_TIMES=tuple(.5*k for k in range(1,61))  # 0.5..30 s


def shape_colour_over_time(material,times=COLOUR_TIMES):
    """Shape fill colours over time from closed-form channel expressions (neutral audio, bands 1).

    Each sample applies projectM's colour modulo (256/255) and clamps, as CustomShape draws them; centre and
    edge colours are reported separately and pooled for hue shares (time-weighted, coloured samples only:
    saturation >= 0.25 and largest channel >= 0.1). None unless every RGB channel evaluates.
    """
    import colorsys
    import prediction_illustration as P
    from time_expression import HUE_BANDS
    channels=(material or {}).get('channel_expressions') or {}
    groups={'centre':('r','g','b'),'perimeter':('r2','g2','b2')}
    held={b:1. for b in ('bass','mid','treb','bass_att','mid_att','treb_att')}
    period=256/255
    samples={}
    for group,names in groups.items():
        rows=[]
        for time in times:
            rgb=[]
            for name in names:
                expression=(channels.get(group) or {}).get(name)
                value=P._value_at({'expression':expression},'none','expression',held,time,None) if expression else None
                if value is None or not math.isfinite(value):return None
                rgb.append(min(1.,max(0.,math.fmod(math.fmod(value,period)+period,period))))
            rows.append(rgb)
        samples[group]=rows
    pooled=samples['centre']+samples['perimeter'];hues=[];sats=[]
    for rgb in pooled:
        h,sat,v=colorsys.rgb_to_hsv(*rgb);sats.append(sat)
        if sat>=.25 and v>=.1:hues.append(h*360)
    shares={}
    for name,spans in HUE_BANDS.items():
        count=sum(1 for h in hues if any(a<=h<b for a,b in spans))
        if hues and count/len(pooled)>=.05:shares[name]=round(count/len(pooled),3)
    span=lambda rows:[[round(min(r[i] for r in rows),4),round(max(r[i] for r in rows),4)] for i in range(3)]
    return {'centre_rgb_range':span(samples['centre']),'edge_rgb_range':span(samples['perimeter']),
            'mean_saturation':round(sum(sats)/len(sats),4),'coloured_share':round(len(hues)/len(pooled),4),
            'hue_shares':dict(sorted(shares.items(),key=lambda kv:-kv[1])),
            'samples_rgb':{g:[[round(c,3) for c in rows[k]] for k in range(0,len(rows),10)] for g,rows in samples.items()},
            'times_s':[times[0],times[-1]],'audio':'bands held at 1'}


RAY_MIN_SHARE=.5  # screen share reading one point per ray for the radial_rays effect
RAY_GAIN=.15  # |d r_source / d r_screen| below this: a pixel's ray reads (nearly) one source point


def ray_sampling(mesh,size=(96,54),draws=3):
    """How much of the screen samples one source point per ray through the warp centre.

    The engine samples c + (p - c)/s (zoom about the screen centre, stretch about (cx, cy)). When the
    effective scale grows in proportion to the distance from c (for example s = k*|p - c|), the source
    radius no longer depends on the screen radius: every pixel on a ray reads the same point and each
    frame becomes rays converging on c. The share is the fraction of pixels with |d r_src/d r_dst| <
    RAY_GAIN, from the closed-form backward map evaluated with frame-state inputs drawn arbitrarily
    (the minimum over draws, so it holds whatever the state); no frames are stepped.
    """
    import numpy as np
    import prediction_illustration as P
    from eel_memory import input_names
    controls=(mesh or {}).get('controls') or {}
    names=set()
    for row in controls.values():
        for term in row.get('terms') or []:
            if term.get('expression'):names|={n for n in (input_names(term['expression']) or ()) if isinstance(n,str)}
    names-={'x','y','rad','ang','time','bass','mid','treb','bass_att','mid_att','treb_att'}
    width,height=size;long=max(width,height)
    columns,rows=np.meshgrid(np.arange(width,dtype=np.float64),np.arange(height,dtype=np.float64))
    saved,unresolved=dict(P._TERM_CONTEXT),set(P._UNRESOLVED_TERMS)
    shares,centres=[],[]
    try:
        for draw in range(draws):
            rng=np.random.default_rng(draw)
            P._TERM_CONTEXT.clear()
            P._TERM_CONTEXT.update(stage={n:float(rng.uniform(-3,3)) for n in sorted(names)},rng=np.random.default_rng(draw),
                                   bands={b:1. for b in ('bass','mid','treb','bass_att','mid_att','treb_att')})
            sample=P._backward_map(mesh,width,height,grid=None)
            if sample is None:return None
            time=2.+1.7*draw
            with np.errstate(all='ignore'):
                map_x,map_y=(np.asarray(m,np.float64) for m in sample(time))
                probe=np.array([[.5]])
                cx=float(P._control_field(controls['cx'],'cx',probe,probe,time).ravel()[0])
                cy=float(P._control_field(controls['cy'],'cy',probe,probe,time).ravel()[0])
                # Rays through the stretch centre (the zoom centre when there is no stretch field).
                px,py=(cx-.5)*long+width/2-.5,(cy-.5)*long+height/2-.5
                dxdy,dxdx=np.gradient(map_x);dydy,dydx=np.gradient(map_y)
                rx,ry=columns-px,rows-py;rd=np.hypot(rx,ry);ux,uy=rx/rd,ry/rd
                sx,sy=map_x-px,map_y-py;rs=np.hypot(sx,sy)
                gain=(sx*(dxdx*ux+dxdy*uy)+sy*(dydx*ux+dydy*uy))/rs
            valid=(rd>3)&(rs>1e-9)&np.isfinite(gain)
            shares.append(float(np.mean(np.abs(gain[valid])<RAY_GAIN)) if valid.any() else 0.)
            centres.append((cx,cy))
    finally:
        P._TERM_CONTEXT.clear();P._TERM_CONTEXT.update(saved)
        P._UNRESOLVED_TERMS.clear();P._UNRESOLVED_TERMS.update(unresolved)
    xs,ys=[c[0] for c in centres],[c[1] for c in centres]
    return {'ray_constant_share':round(min(shares),4),'centre_xy':[round(sum(xs)/len(xs),4),round(sum(ys)/len(ys),4)],
            'centre_range_xy':[[round(min(xs),4),round(max(xs),4)],[round(min(ys),4),round(max(ys),4)]],'state_draws':draws,
            'method':'closed-form backward map, frame-state inputs drawn in [-3, 3]; minimum share over draws'}


def _ray_sampling_if_spatial(mesh):
    # A uniform scale has d r_src/d r_dst = 1/s everywhere: only a scale that varies over the screen can be ray-constant.
    controls=(mesh or {}).get('controls') or {}
    if not any(controls.get(n,{}).get('uniform_across_mesh') is False for n in ('zoom','sx','sy')):return None
    try:return ray_sampling(mesh)
    except (ValueError,TypeError,KeyError,ArithmeticError):return None


def _render(facts):
    persistence=facts.get(STATIC+'/feedback_persistence') or {}
    mesh=facts.get(STATIC+'/mesh_field') or {}
    flat=facts.get(BASE+'/nonlinear_texture_colour_bounds/flat_field') or {}
    advection=[{'stage':p.split('/stages/')[1].split('/')[0],'offset_range_uv':v.get('offset_range_uv'),'evidence':p}
               for p,v in facts.items() if '/sample_value_offset_envelope' in p and isinstance(v,dict)]
    mechanisms=[{'mechanism':v.get('mechanism'),'stage':v.get('stage'),'parameters':copy.deepcopy(v.get('parameters')),'evidence':p}
                for p,v in sorted(facts.items()) if p.startswith('/analysis/families/') and isinstance(v,dict)]
    feedback={'decay':persistence.get('decay_gain'),
        'stored_level_halving_steps':persistence.get('steps_to_half_interval'),
        'stored_level_floor':persistence.get('floor_level_interval'),
        'warp_patterns':copy.deepcopy(mesh.get('patterns') or []),
        'warp_controls':{name:{'uniform':row.get('uniform_across_mesh'),'value_range':row.get('value_range'),'terms':copy.deepcopy(row.get('terms'))}
                         for name,row in (mesh.get('controls') or {}).items() if row.get('status')=='described'},
        'shader_advection':advection,
        'ray_sampling':_ray_sampling_if_spatial(mesh),
        'flat_field':{k:flat.get(k) for k in ('state_rgb','flat_region_behaviour','settle_seconds','composite_rgb_at_state') if flat.get(k) is not None} or None,
        'warp_transfer':_warp_transfer(facts) if persistence.get('decay_gain') is None else None,
        'evidence':[p for p in (STATIC+'/feedback_persistence',STATIC+'/mesh_field',BASE+'/nonlinear_texture_colour_bounds/flat_field') if p in facts]}
    composite={};feedback_random=[None]
    for path,value in facts.items():
        if path.endswith('/legacy_response') and isinstance(value,dict):
            ranges=value.get('native_control_ranges') or {}
            composite['gamma_weight']=value.get('gamma_absolute_weight_sum_upper')
            tint=value.get('tint_amount')
            if type(tint) in (int,float) and tint>.001:
                # Legacy composite corner hue tint (fShader): PresetState::hueRandomOffsets per preset load.
                composite['legacy_hue_tint']={'amount':float(tint),
                    'phase':'random per preset load: which hue shows where is not fixed by the source'}
            composite['echo']={'active':value.get('echo_selection')=='active or possible native echo',
                               'alpha':ranges.get('echo_alpha'),'zoom':ranges.get('echo_zoom'),'orientation':ranges.get('echo_orient')}
            composite.setdefault('evidence',[]).append(path)
            break
    stages=(facts.get(BASE+'/stage_programs') or {}).get('stages') or {}
    for stage,target in (('composite',composite),('warp',None)):
        record=stages.get(stage) or {}
        switches=_per_load_random(record.get('program')) if record.get('status')=='exported' else None
        if switches:
            if target is None:feedback_random[0]=switches
            else:target['per_load_random']=switches
    for path,value in sorted(facts.items()):
        if not path.endswith('/native_colour_generators') or not isinstance(value,list):continue
        hue=next((row for row in value if isinstance(row,dict) and row.get('policy')=='source31-native-composite-hue-v1'),None)
        rates=((hue or {}).get('raw_corner') or {}).get('angular_rate_rad_per_second_rgb')
        if not hue or not rates:continue
        # FinalComposite::ApplyHueShaderColors: four corner shades cycle at fixed rates; their phases
        # add PresetState::hueRandomOffsets, drawn from std::random_device at every preset load.
        composite['hue_shader']={'channels':['rgb'[i] for i in hue.get('consumed_rgb_components') or [] if i in (0,1,2)],
            'cycle_periods_seconds_rgb':[2*math.pi/rate if rate else None for rate in rates],
            'range_rgb':hue.get('nominal_input_range_rgb'),
            'spatial':'four corner shades blended over the screen, each normalised so its largest channel is 1',
            'phase':'random per preset load: which hue shows where is not fixed by the source','evidence':path}
        break
    from feedback_equilibrium import stage_transfer
    flat=stage_transfer(facts,'composite')
    if flat is not None:
        # Displayed colour for each flat canvas level: the custom composite's palette (texture lookups included).
        composite['flat_transfer']={**flat,'source':'exported composite shader evaluated on flat canvas colours'}
        spread=max((v for row in flat.get('rgb_spread') or [] for v in row),default=0.)
        # A palette that moves by more than 0.05 between the sample times shifts colour over time.
        composite['flat_transfer']['time_varying']=bool(spread>TIME_VARYING_SPREAD)
        # A relief composite shows slopes: flat input gives this level, textured content differs.
        # Mostly NaN/inf output (e.g. 0/0 from never-written q values): GLSL ES leaves the displayed result undefined.
        composite['flat_transfer']['output_undefined']=bool((flat.get('nonfinite_share') or 0.)>.5)
        composite['flat_transfer']['flat_areas_only']=any(m['mechanism']=='gradient_relief' and m['stage']=='composite' for m in mechanisms)
        from feedback_equilibrium import stage_detail_response
        detail=stage_detail_response(facts,'composite')
        if detail is not None:composite['detail_response']={**detail,'source':'exported composite shader evaluated on a grey multi-scale texture'}
        from feedback_equilibrium import composite_load_spread
        rows=[composite_load_spread(facts,level=level) for level in (.05,.1,.2)]
        rows=[r for r in rows if r]
        # Only material dependence is reported: brightness varying by >15% or more than one hue family across loads.
        if any(r['luma_range'][1]>1.15*max(r['luma_range'][0],1e-4) or len(r['hue_families'])>1 for r in rows):
            composite['load_spread']=[{k:r[k] for k in ('level','luma_range','hue_families')} for r in rows]
    palette=facts.get(BASE+'/nonlinear_texture_colour_bounds/stages/composite/scalar_palette')
    if isinstance(palette,dict):
        composite['scalar_palette']={'ramp':[{'scalar':row['scalar'],'rgb':row['clamped_rgb']} for row in palette.get('samples') or []],
            'black_content_rgb':palette.get('black_content_rgb'),'white_content_rgb':palette.get('white_content_rgb')}
        composite.setdefault('evidence',[]).append(BASE+'/nonlinear_texture_colour_bounds/stages/composite/scalar_palette')
    vectors=facts.get(STATIC+'/motion_vectors')
    layers=[_layer(facts,index) for index in _element_indices(facts)]
    if isinstance(vectors,dict) and vectors.get('vector_count'):
        layers.append({'id':'motion_vectors','stage':'drawing','columns':vectors.get('columns_screen_fraction'),
                       'rows_from_top':vectors.get('rows_screen_fraction_from_top'),'colour_rgba':vectors.get('colour_rgba'),
                       'length_scale':vectors.get('length_scale'),'evidence':[STATIC+'/motion_vectors']})
    bindings=[{'layer':layer['id'],'input':AUDIO_NAMES.get(route['input_code'],route['input_code']),'target':route['target'],
               'linear_gain':route['linear_gain']} for layer in layers for route in layer.get('audio',[])]
    from mirror_symmetry import mirror_operators
    if feedback_random[0]:feedback['warp_per_load_random']=feedback_random[0]
    redraws=_random_redraws(((facts.get(BASE+'/stage_programs') or {}).get('frame')))
    return {'feedback':feedback,'layers':layers,'composite':composite,'mechanisms':mechanisms,'audio_bindings':bindings,'random_redraws':redraws,
            'mirrors':mirror_operators(facts),'random_textures':_random_textures(stages)}


def _random_textures(stages):
    """randNN samplers per stage: projectM picks one bundled image per slot at every preset load
    (randNN_prefix limits the choice to names starting with prefix), so their colours are a random draw."""
    import re
    rows=[]
    for stage in ('warp','composite'):
        record=stages.get(stage) or {}
        if record.get('status')!='exported':continue
        seen=set()
        for node in (record.get('program') or {}).get('nodes') or []:
            if not isinstance(node,dict) or node.get('op')!='sample':continue
            match=re.fullmatch(r'rand(\d{2})(?:_(\w+))?',str((node.get('detail') or {}).get('canonical_texture','')).lower())
            if match and (match.group(1),match.group(2)) not in seen:
                seen.add((match.group(1),match.group(2)))
                rows.append({'stage':stage,'slot':match.group(1),'name_filter':match.group(2)})
    return rows


TIME_VARYING_SPREAD=.05

def _program(source):
    sections={}
    for name,section in (source or {}).get('sections',{}).items():
        if not isinstance(section,dict) or not section.get('active'):continue
        sections[name]={'source':section.get('source'),'ast':section.get('tree'),'status':section.get('status')}
    return {'sections':sections,'settings':copy.deepcopy((source or {}).get('values') or {}),
            'dialect':'MilkDrop 2.25c equations (projectm-eval semantics) and HLSL shader bodies as authored'}


def _display_is_exact(e,flat):
    """True when nothing feeds the canvas (no drawn elements, no injected energy or offset, no substituted
    priors) and the composite's flat transfer is constant: no spatial spread and no time variation. The
    canvas then stays at its cleared level and the display is exactly the composite of that level."""
    if not isinstance(flat,dict) or flat.get('time_varying') or flat.get('output_undefined'):return False
    if e.get('elements') or e.get('substitution_count'):return False
    if any(abs(v)>0 for v in (e.get('energy_rgb_per_frame') or [1])+(e.get('offset_rgb') or [1])):return False
    spread=flat.get('rgb_spread') or []
    return bool(spread) and all(max(abs(v) for v in row)==0 for row in spread)


def _steady_state(summary,flat=None):
    """Settled canvas/display colour from feedback_equilibrium: a hue cue, not a brightness measure.

    The local estimate keeps each element's energy where it is drawn and the spread estimate mixes it over
    the screen; unknown element colours use neutral priors (substitution_count). The level is a lower bound
    for bright presets (transport, blur and self-advection are not iterated), so brightness comes from
    display_estimate; hue_family is reported only when the estimate is visibly above black.
    """
    try:
        from feedback_equilibrium import equilibrium
        from time_expression import hue_family
        e=equilibrium(summary)
    except Exception:  # noqa: BLE001 - an optional derived block never fails the recipe
        return None
    local=e.get('display_local_rgb') or [0.,0.,0.];spread=e.get('display_spread_rgb') or [0.,0.,0.]
    rgb=local if max(local)>=.02 else spread
    return {'display_local_rgb':[round(v,4) for v in local],'display_spread_rgb':[round(v,4) for v in spread],
            'canvas_local_rgb':[round(v,4) for v in e.get('canvas_local_rgb') or [0.,0.,0.]],
            'hue_family':hue_family(rgb) if max(rgb)>=.02 else None,'composite_model':e.get('composite_model'),
            'substitution_count':e.get('substitution_count'),
            'level_note':'a lower bound for bright presets; use display_estimate for brightness',
            'source':'feedback_equilibrium steady state (source facts, no frames stepped)',
            **({'exact':True,'level_note':'exact: nothing feeds the canvas, so it stays at canvas_local_rgb, and the composite '
                'maps that level to display_local_rgb everywhere at every sampled time; the whole display is this colour '
                'and display_estimate does not apply'} if _display_is_exact(e,flat) else {})}


SIMULATED_KEYS=('mean_luminance','mean_abs_frame_difference','mean_flow_screen_widths_per_s',
                'global_brightness_jumps_per_10s','mean_saturation','warm_cool')


def _simulated_display(record):
    """Offline display statistics of the static prediction (facet_precompute record), or None.

    The prediction steps the exported source programs (no engine, no rendered frames) for 300 frames at
    480x270 under the declared reference audio; the engine ruler's statistics measure frames 60-299.
    """
    if not isinstance(record,dict) or record.get('status')!='predicted':return None
    values=record.get('statistics') or {}
    number=lambda v:round(float(v),4) if type(v) in (int,float) and math.isfinite(v) else None
    runs=[r for r in record.get('runs') or [] if isinstance(r,dict)]
    # Hue families over coloured pixels (the ruler's hue names), averaged over the per-load seeds.
    totals={}
    for run in runs:
        for name,share in (run.get('hue_shares') or {}).items():
            if type(share) in (int,float):totals[name]=totals.get(name,0.)+share/len(runs)
    shares={k:round(v,3) for k,v in sorted(totals.items(),key=lambda kv:-kv[1])}
    coloured=[r['coloured_share'] for r in runs if type(r.get('coloured_share')) in (int,float)]
    # Each load draws its own random values: list each seed's outcome so a reader can describe the variety.
    per_load=[{'seed':r.get('seed'),**{k:number(r.get(k)) for k in ('mean_luminance','mean_saturation','warm_cool')},
               'top_hues':[k for k,_ in sorted((r.get('hue_shares') or {}).items(),key=lambda kv:-kv[1])][:3]}
              for r in runs] if record.get('depends_on_seed') else None
    return {'policy':'static-prediction-display-statistics-v1','source_policy':record.get('policy'),
            'hue_shares':shares or None,'coloured_share':number(sum(coloured)/len(coloured)) if coloured else None,'per_load':per_load,
            'statistics':{k:number(values.get(k)) for k in SIMULATED_KEYS},
            'peak_brightness_change':number(values.get('peak_brightness_change')),
            'depends_on_seed':bool(record.get('depends_on_seed')),'seeds':record.get('seeds'),
            'random_flash':record.get('random_flash'),'random_texture_dependent':record.get('random_texture_dependent'),
            'reference':'static prediction (source programs stepped, 300 frames at 480x270, declared reference audio), '
                        'measured with the engine ruler statistics over frames 60-299; per-load random presets average their seeds, '
                        'peak_brightness_change is the worst seed',
            'uses_rendered_images':False,'uses_engine_execution':False}


def build_recipe(summary,source=None,*,rules=None,profiles=None,include_program=False,display_statistics=None):
    from approximate_features import describe
    facts=_facts(summary)
    recipe={'policy':POLICY,'preset':copy.deepcopy(summary.get('preset')),'conventions':CONVENTIONS,
        'description':summary.get('description'),'render':_render(facts),
        'mood':describe(summary,rules,profiles),'uses_rendered_images':False,
        'limitations':['Engine-neutral approximate recipe; drawn content, audio and native rounding make real frames differ',
                       'Mood values are editable research assumptions, not calibrated preferences']}
    recipe['render']['feedback']['steady_state']=_steady_state(summary,(recipe['render'].get('composite') or {}).get('flat_transfer'))
    display=_display_estimate(summary)
    if display is not None:recipe['display_estimate']=display
    recipe['facets']=facets_block(summary,display)
    simulated=_simulated_display(display_statistics)
    if simulated is not None:recipe.setdefault('display_estimate',{})['simulated']=simulated
    recipe['intent']=intent(recipe)
    redraw=recipe['render'].get('random_redraws')
    if redraw and redraw.get('feeds') and isinstance(recipe['description'],str):
        when=(' first at about '+format(redraw['event_times_s'][0],'.3g')+' s' if redraw.get('event_times_s') else '')+(
             ' and then every '+format(redraw['period_s'],'.3g')+' s' if redraw.get('period_s') else '')
        recipe['description']+=' Random redraws: '+', '.join(redraw['feeds'])+' are redrawn at random'+when+\
            ', so colours or shapes that depend on them are a random draw that changes at those moments.'
    variants=[e for e in recipe['intent']['effects'] if e['effect']=='per_load_variant']
    if variants and isinstance(recipe['description'],str):
        recipe['description']+=' Per-load variants: '+'; '.join(
            f"the {e['stage']} shader branches on {e['condition']} (true in {round(100*e['probability_true'])}% of preset loads)"
            for e in variants)+'. Each branch is a real outcome; describe both looks.'
    if source is not None and include_program:recipe['program']=_program(source)
    return recipe


def _display_estimate(summary):
    """Source-calibrated display statistics and activity bands (additive; None without a model)."""
    from calibrated_display import load,predict
    model=load()
    if model is None:return None
    values=predict(summary,model)
    from display_activity import classify
    activity=classify({k:{'value':v['value'],'interval':v['interval']} for k,v in values.items()},remap=True)
    return {'policy':'source-calibrated-display-estimate-v1','statistics':values,'activity':activity,
            'reference':'engine ruler: pinned patched projectM-TV, 480x270, 300 frames at 30 fps, checkpoint audio, frames 60-299',
            'note':'Calibrated from static source facts; intervals are the 10th-90th percentile out-of-fold residuals; not a rendered measurement of this preset'}


FACETS_POLICY='preset-facets-v1'
ROOT=Path(__file__).resolve().parents[2]
ATTRIBUTES=ROOT/'core/src/main/assets/preset-attributes/attributes.tsv'
BUNDLED_PRESETS=ROOT/'core/src/main/assets/presets'
# facet metric -> calibrated display statistic (the same engine-ruler fields the attribute bundle stores)
FACET_STATISTICS={'luminance':'mean_luminance','saturation':'mean_saturation','warm_cool':'warm_cool',
                  'flow':'mean_flow_screen_widths_per_s','frame_difference':'mean_abs_frame_difference',
                  'jumps':'global_brightness_jumps_per_10s'}
ATTRIBUTE_COLUMNS=('luminance','saturation','coloured_share','warm_cool','flow','frame_difference','jumps','activity')
ACTIVITY_METRICS=(('frame_difference','mean_abs_frame_difference'),('flow','mean_flow_screen_widths_per_s'),
                  ('jumps','global_brightness_jumps_per_10s'))
_FACET_CACHE={}


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _definition(definition_path=None):
    import preset_facets
    path=Path(definition_path or preset_facets.DEFINITION)
    key=('definition',str(path))
    if key not in _FACET_CACHE:
        data=path.read_bytes();definition=json.loads(data)
        reference=(path.parent/definition['activity_reference']['file']).read_bytes()
        if _sha256(reference)!=definition['activity_reference']['sha256']:
            raise ValueError('facet activity reference differs from the hash in the definition')
        _FACET_CACHE[key]=(definition,_sha256(data),json.loads(reference))
    return _FACET_CACHE[key]


def _attributes(path=None):
    """Measured bundle rows {name: (options, {column: value or None})}; empty when the bundle is absent."""
    path=Path(path or ATTRIBUTES)
    key=('attributes',str(path))
    if key not in _FACET_CACHE:
        rows={};digest=None
        if path.exists():
            data=path.read_bytes();digest=_sha256(data)
            for line in data.decode().splitlines():
                if line.startswith('#') or not line:continue
                fields=line.split('\t')
                values=dict(zip(ATTRIBUTE_COLUMNS,(None if v=='-' else float(v) for v in fields[2:])))
                if all(v is None for v in values.values()):continue  # unmeasured preset: no row to use
                rows[fields[0]]=([o for o in fields[1].split(',') if o],values)
        _FACET_CACHE[key]=(rows,digest)
    return _FACET_CACHE[key]


def _mid_rank(sorted_values,value):
    low=bisect.bisect_left(sorted_values,value);high=bisect.bisect_right(sorted_values,value)
    return (low+high)/2/len(sorted_values)


def facet_activity(values,definition_path=None):
    """Facet activity of {frame_difference, flow, jumps} against the frozen facet activity reference.

    Same mid-rank lookups as the attribute bundle (attribute_bundle.activity_values): the mean of the
    three metric mid-ranks, placed in the frozen mean-rank table. None when a metric is missing."""
    _,_,reference=_definition(definition_path)
    if any(type(values.get(name)) not in (int,float) for name,_ in ACTIVITY_METRICS):return None
    mean=sum(_mid_rank(reference['metrics'][field],float(values[name])) for name,field in ACTIVITY_METRICS)/len(ACTIVITY_METRICS)
    return _mid_rank(reference['mean_rank'],mean)


_BOUNDS={'<':('upper',False),'<=':('upper',True),'>':('lower',False),'>=':('lower',True)}


def _accepted(conditions):
    """Acceptable value set of a conjunction of threshold conditions on one metric: (lower, upper) bounds."""
    lower=(-math.inf,True);upper=(math.inf,True)
    for condition in conditions:
        side,inclusive=_BOUNDS[condition['op']];value=float(condition['value'])
        if side=='lower' and (value>lower[0] or (value==lower[0] and not inclusive)):lower=(value,inclusive)
        if side=='upper' and (value<upper[0] or (value==upper[0] and not inclusive)):upper=(value,inclusive)
    return lower,upper


def _metric_state(conditions,span):
    """'always', 'never' or 'maybe' for the conditions over the closed interval span."""
    (lv,li),(uv,ui)=_accepted(conditions);lo,hi=span
    low=(lv,li) if lv>lo else (lo,True);high=(uv,ui) if uv<hi else (hi,True)
    if low[0]>high[0] or (low[0]==high[0] and not (low[1] and high[1])):return 'never'
    inside_low=lo>lv or (lo==lv and li);inside_high=hi<uv or (hi==uv and ui)
    return 'always' if inside_low and inside_high else 'maybe'


def facet_options(values,style,definition):
    """(options, possible_options, unresolved_options) for facet values {metric: {'value','interval'?}}.

    options: memberships of the point values (preset_facets.memberships), minus unresolved options.
    possible_options: options whose rule is not constant across the reported intervals (it holds for
    some values inside them and fails for others), members and non-members alike.
    unresolved_options: options whose rule needs a value that is not available (directly or through
    not_option), never guessed."""
    import preset_facets
    point={k:v.get('value') for k,v in values.items() if type(v.get('value')) in (int,float)}
    spans={k:sorted([min(list(v.get('interval') or [point[k]])+[point[k]]),max(list(v.get('interval') or [point[k]])+[point[k]])])
           for k,v in values.items() if k in point}
    states={};unresolved=[]
    for group in definition['groups']:
        for option in group['options']:
            metrics={}
            for condition in option['all']:
                if 'metric' in condition:metrics.setdefault(condition['metric'],[]).append(condition)
            missing=[m for m in metrics if m not in point]
            dependencies=[c['not_option'] for c in option['all'] if 'not_option' in c]
            if missing or any(d in unresolved for d in dependencies):
                unresolved.append(option['id']);continue
            parts=[_metric_state(conditions,spans[name]) for name,conditions in metrics.items()]
            parts+=['always' if c['style'] in style else 'never' for c in option['all'] if 'style' in c]
            parts+=[{'always':'never','never':'always'}.get(states[d],'maybe') for d in dependencies]
            states[option['id']]='never' if 'never' in parts else 'always' if all(p=='always' for p in parts) else 'maybe'
    members=[o for o in preset_facets.memberships(point,set(style),definition) if o not in unresolved]
    possible=[o for o,state in states.items() if state=='maybe']
    return members,possible,unresolved


def facets_block(summary,display=None,*,attributes_path=None,definition_path=None,presets_dir=None):
    """Mood facet memberships for one preset (policy preset-facets-v1).

    A bundled preset whose name has a measured row in the facet attribute bundle (and whose bytes
    match the bundled preset when a hash is known) uses the engine-ruler measured values and the
    bundle's options unchanged. Any other preset uses the source-calibrated display estimate
    (display_estimate statistics) with intervals and source style facts. No simulation output or
    rendered image is read."""
    from facet_style_facts import style_facts
    definition,definition_sha,_=_definition(definition_path)
    preset=summary.get('preset') or {}
    name=preset.get('name');digest=preset.get('sha256')
    rows,attributes_sha=_attributes(attributes_path)
    block={'policy':FACETS_POLICY,'definition_sha256':definition_sha}
    note=None
    if name in rows:
        bundled=Path(presets_dir or BUNDLED_PRESETS)/name
        if digest and bundled.exists() and _sha256(bundled.read_bytes())!=digest:
            note='bundled preset bytes differ from this preset; the measured bundle row is not used'
        else:
            options,measured=rows[name]
            style_ids={o['id'] for g in definition['groups'] if g['id']=='style' for o in g['options']}
            block.update(evidence='engine-ruler-measured',style_evidence='source-structure-facts',options=list(options),
                possible_options=[],unresolved_options=[],style=[o for o in options if o in style_ids],
                values={k:{'value':v,'evidence':'engine-ruler-measured'} for k,v in measured.items()},
                activity_source='engine-ruler-measured-bundle',
                bundle={'file':'core/src/main/assets/preset-attributes/attributes.tsv','sha256':attributes_sha},
                measurement=definition.get('measurement'))
            return block
    statistics=((display if display is not None else _display_estimate(summary)) or {}).get('statistics')
    style=style_facts(summary)
    values={}
    for metric,field in FACET_STATISTICS.items():
        row=(statistics or {}).get(field)
        if row is not None and type(row.get('value')) in (int,float):
            values[metric]={'value':row['value'],'interval':list(row['interval']),'evidence':'source-calibrated'}
    if all(m in values for m,_ in ACTIVITY_METRICS):
        ends=[facet_activity({m:values[m]['interval'][i] for m,_ in ACTIVITY_METRICS},definition_path) for i in (0,1)]
        point=facet_activity({m:values[m]['value'] for m,_ in ACTIVITY_METRICS},definition_path)
        values['activity']={'value':round(point,4),'interval':[round(min(ends+[point]),4),round(max(ends+[point]),4)],
                            'evidence':'source-calibrated'}
    values['coloured_share']={'value':None,'evidence':'not-estimated'}
    options,possible,unresolved=facet_options(values,style,definition)
    block.update(evidence='source-calibrated' if statistics else 'unavailable',style_evidence='source-structure-facts',
        options=options,possible_options=possible,unresolved_options=unresolved,style=style,values=values,
        activity_source='frozen-facet-reference-from-calibrated-statistics' if 'activity' in values else None)
    if note:block['note']=note
    return block


def main(argv=None):
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('summary',type=Path,help='preset-understanding-v1 summary JSON')
    parser.add_argument('--source',type=Path,help='native reader source JSON for the program section')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--include-program',action='store_true',help='also embed parsed equations/shaders (exact port; optional)')
    parser.add_argument('--display-statistics',type=Path,help='facet_precompute record for this preset (offline simulated display statistics)')
    args=parser.parse_args(argv)
    recipe=build_recipe(json.loads(args.summary.read_text()),json.loads(args.source.read_text()) if args.source else None,
                        include_program=args.include_program,
                        display_statistics=json.loads(args.display_statistics.read_text()) if args.display_statistics else None)
    text=json.dumps(recipe,indent=1,allow_nan=False)
    if args.output:args.output.write_text(text+'\n')
    else:print(text)



SHADER_EFFECTS={
    'angular_mirror_fold':('kaleidoscope',{'sectors':'sector_count'}),
    'cartesian_mirror_fold':('mirror',{}),
    'repeat_tiling':('tiling',{'mirrored':'mirrored'}),
    'gradient_relief':('relief',{'directions':'directions'}),
    'neighbourhood_blur':('blur',{'taps':'taps','radius_spatial':'radius_spatial','radius_audio':'radius_audio','radius_time':'radius_time','offsets':'offsets'}),
    'polar_radial_sampling':('polar_tunnel',{'radial_mapping':'radial_mapping'}),
    'radial_twist':('swirl',{}),
    'global_rotation':('rotation',{}),
    'spatial_rotation':('spatial_rotation',{}),
    'image_driven_advection':('self_advection',{}),
    'gradient_driven_advection':('reaction_diffusion_flow',{}),
    'noise_driven_advection':('noise_turbulence',{}),
    'blur_difference_feedback':('pattern_growth',{'channels':'lanes','fine_levels':'fine_levels','coarse_levels':'coarse_levels'}),
    'uv_advection':('periodic_wobble',{}),
    'multi_copy_feedback_recursion':('recursive_copies',{'copies':'copies','scales':'sampling_scales'}),
    'nonlinear_feedback_map':('fractal_feedback',{'construction':'construction'}),
    'complex_quadratic_recurrence':('julia_fractal',{}),
    'mandelbox_recurrence':('mandelbox_fractal',{}),
    'radial_feedback_transform':('feedback_scale',{'scale':'sampling_scale'}),
    'periodic_radial_glow':('glow_spots',{}),
    'spatial_oscillatory_bands':('stripes',{}),
    'angular_periodic_warp':('angular_warp',{}),
}


def _reactivity(render):
    """Band -> effect parameter map; strengths are relative classes, not calibrated gains."""
    from approximate_mood import is_brightness_control
    rows={}
    for binding in render['audio_bindings']:
        band=str(binding['input']);smoothed=band.endswith('_att');base=band.replace('_att','')
        target=str(binding['target'])
        kind='brightness' if is_brightness_control(target) else 'motion'
        key=(base,binding['layer'],target)
        row=rows.setdefault(key,{'band':base,'layer':binding['layer'],'target':target,'kind':kind,
                                 'smoothed':smoothed,'linear_gain':binding.get('linear_gain'),'response':'continuous'})
        row['smoothed']=row['smoothed'] and smoothed
    for layer in render['layers']:
        for route in layer.get('audio',[]):
            band=AUDIO_NAMES.get(route['input_code'],'').replace('_att','')
            row=rows.get((band,layer['id'],route['target']))
            if row is not None and route.get('threshold_or_clamp'):row['response']='threshold_or_clamped'
    for pattern in render['feedback']['warp_patterns']:
        for name in (pattern.get('audio_inputs') or [])+(pattern.get('amplitude_dependencies') or []):
            base=str(name).replace('_att','')
            if base in ('bass','mid','treb','vol'):
                rows.setdefault((base,'feedback',pattern['pattern']),{'band':base,'layer':'feedback','target':pattern['pattern'],
                    'kind':'motion','smoothed':str(name).endswith('_att'),'linear_gain':None,'response':'continuous'})
    for layer in render['layers']:
        wave=layer.get('builtin_wave') or {}
        if wave.get('audio_inputs'):
            rows[('waveform',layer['id'],'shape')]={'band':'waveform','layer':layer['id'],'target':'line shape follows the audio waveform',
                'kind':'shape','smoothed':False,'linear_gain':None,'response':'continuous','inputs':wave['audio_inputs']}
    return sorted(rows.values(),key=lambda r:(r['band'],r['layer'],r['target']))


STREAK_MIN_PERCENT=1.     # whole-screen zoom per frame, one direction throughout
STREAK_MIN_HALF_FRAMES=10 # retained copies must last this long to overlap into streaks


def _radial_streaks(effects,half_life_s):
    """Strong one-way zoom with slow trails: every frame keeps a copy of the last one scaled by the zoom,
    so drawn detail is smeared along rays through the zoom centre. radial_scale_over_half_life is the
    scale a retained copy reaches (median zoom compounded over one half-life): far from 1 means long
    streaks. Rotation in the same feedback bends them into spirals."""
    if not half_life_s:return None
    frames=round(half_life_s*30)
    if frames<STREAK_MIN_HALF_FRAMES:return None
    for row in effects:
        span=row.get('percent_per_frame') if row['effect']=='zoom_flow' and not row.get('region') else None
        if not isinstance(span,list) or len(span)!=2 or not all(type(v) in (int,float) and math.isfinite(v) for v in span):continue
        if min(abs(v) for v in span)<STREAK_MIN_PERCENT or span[0]*span[1]<=0:continue
        median=(span[0]+span[1])/2
        spin=any(e['effect']=='rotation_flow' and isinstance(e.get('radians_per_frame'),list) and
                 max(abs(v) for v in e['radians_per_frame'] if type(v) in (int,float))>.01 for e in effects)
        return {'effect':'radial_streaks','direction':'inward' if median<0 else 'outward','half_life_frames':frames,
                'radial_scale_over_half_life':(1+median/100)**frames,'spiral':spin,
                'condition':'drawn or textured detail smears along rays through the zoom centre; smooth content shows no streaks'}
    return None


def intent(recipe):
    """Generic, engine-neutral effect list plus music-reactivity map for an 'alike' rebuild."""
    render=recipe['render'];mood=recipe['mood'];features=mood['features']
    effects=[]
    fb=render['feedback']
    half=features.get('feedback.half_life_s',{}).get('value')
    warp=fb.get('warp_transfer') or {}
    decay=fb.get('decay') if fb.get('decay') is not None else (sum(warp['gain_rgb'])/3 if warp.get('gain_rgb') else None)
    if warp.get('channel_selective'):
        # The longest-lived channel carries the trails; one that is never halved has no half-life.
        channels=[row for row in (warp.get('per_channel') or {}).values() if row.get('gain',0)>0]
        decay=max((row['gain'] for row in channels),default=0.)
        lives=[row.get('halving_frames') for row in channels]
        if half is None and lives and None not in lives:half=max(lives)/30
    elif half is None and warp.get('halving_frames'):half=warp['halving_frames']/30
    if warp.get('wrap'):
        # A wrapping warp cycles levels through the range instead of fading them.
        decay=None
        effects.append({'effect':'level_cycling','cycle_s':warp['wrap']['cycle_frames']/30,'shift_per_frame':warp['wrap']['shift_per_frame']})
    effects.append({'effect':'trails','half_life_s':half,'decay_per_frame':decay,
                    'faint_residue':bool(fb.get('stored_level_floor') and max(fb['stored_level_floor'])>0)})
    for pattern in fb['warp_patterns']:
        kind=pattern.get('pattern');row={'effect':None,'region':pattern.get('region') or None}
        if kind in ('uniform_zoom','radial_zoom_profile'):
            row.update(effect='zoom_flow',percent_per_frame=pattern.get('percent_per_step_range'),direction=pattern.get('content_motion'))
        elif kind in ('uniform_rotation','spatially_varying_rotation'):row.update(effect='rotation_flow',radians_per_frame=pattern.get('value_range_radians_per_step'))
        elif kind in ('uniform_translation','translation_component'):row.update(effect='drift',axis=pattern.get('control'),pixels_per_second=pattern.get('translation_pixels_per_second_range'))
        elif kind and kind.startswith(('compression','expansion')):
            row.update(effect='squeeze' if kind.startswith('compression') else 'stretch',axis=pattern.get('control'),
                       scale_per_frame=pattern.get('composed_feature_scale_per_step_range'),toward=pattern.get('fixed_point_range'))
        elif kind in ('planar_travelling_wave','radial_ring_wave','angular_lobes','angular_modulation_with_seam'):
            osc=pattern.get('oscillator') or {}
            row.update(effect={'planar_travelling_wave':'ripple','radial_ring_wave':'ring_ripple'}.get(kind,'angular_lobes'),
                       wavelength_px=osc.get('planar_wavelength_pixels') or osc.get('radial_wavelength_pixels'),
                       speed_px_s=osc.get('phase_speed_pixels_per_second') or osc.get('radial_phase_speed_pixels_per_second'),
                       direction=osc.get('travel_direction_xy'),lobes=osc.get('angular_lobes'),amplitude_px=pattern.get('amplitude_pixels_range'))
        if row['effect']:effects.append({k:v for k,v in row.items() if v is not None})
    streaks=_radial_streaks(effects,half)
    if streaks:effects.append(streaks)
    rays=fb.get('ray_sampling')
    if rays and rays['ray_constant_share']>=RAY_MIN_SHARE:
        spread=max(b-a for a,b in rays['centre_range_xy'])
        effects.append({'effect':'radial_rays','screen_share':rays['ray_constant_share'],'centre_xy':rays['centre_xy'],
                        'centre_moves':spread>.02,'centre_range_xy':rays['centre_range_xy'],
                        'condition':'the warp reads one source point per ray through the centre: every frame becomes rays '
                                    'converging on it, colour varying with angle only; drawn content is smeared into streaks'})
    redraw=render.get('random_redraws')
    if redraw:
        effects.append({'effect':'random_redraw','feeds':redraw['feeds'],'first_s':(redraw['event_times_s'] or [None])[0],'period_s':redraw['period_s']})
    for stage,switches in (('composite',render['composite'].get('per_load_random')),('warp',fb.get('warp_per_load_random'))):
        for switch in (switches or {}).get('switches') or []:
            # The look branches once per preset load: both variants are real outcomes.
            effects.append({'effect':'per_load_variant','stage':stage,'condition':'rand_preset.'+switch['component']+' '+switch['condition'],
                            'probability_true':switch['probability_true']})
    for item in render['mechanisms']:
        mapped=SHADER_EFFECTS.get(item['mechanism'])
        if mapped and item.get('stage') in ('warp','composite'):
            name,params=mapped;values=item.get('parameters') or {}
            effects.append({'effect':name,'stage':item['stage'],**{k:values.get(v) for k,v in params.items() if values.get(v) is not None}})
    for layer in render['layers']:
        if layer['id']=='motion_vectors':
            effects.append({'effect':'vector_grid','columns':len(layer.get('columns') or []),'rows':len(layer.get('rows_from_top') or [])});continue
        if layer.get('builtin_wave'):
            wave=layer['builtin_wave'];effects.append({'effect':'audio_waveform','form':wave.get('form_name'),
                'position':[wave.get('wave_x'),wave.get('wave_y')],'colour_cycles':bool(layer.get('colour',{}).get('channels'))})
        elif layer.get('analytic_curve'):effects.append({'effect':'parametric_curve',**layer['analytic_curve']})
        elif str(layer['id']).startswith('shape'):
            geometry=layer.get('geometry') or {}
            effects.append({'effect':'shapes','sides':geometry.get('effective_sides') or layer['constants'].get('sides'),
                            'instances':geometry.get('configured_instances') or layer['constants'].get('instances'),
                            'radius':geometry.get('radius_ndc'),'moving':bool(layer.get('controls') or layer.get('centre_axes'))})
            texture=layer.get('texture') or {}
            if texture.get('role')=='previous_main' and (texture.get('tex_zoom',1)!=1 or texture.get('tex_angle_rad',0)!=0):
                # Every frame the polygon shows the previous frame zoomed by tex_zoom and turned by tex_angle: the copies
                # nest recursively (spiral tunnels, droste effects) with no mesh zoom or rotation.
                effects.append({'effect':'frame_copy','layer':layer['id'],'tex_zoom':texture.get('tex_zoom'),'tex_angle_rad':texture.get('tex_angle_rad'),
                                'condition':'recursive while the copy is drawn with enough alpha; static values (per-frame expressions may change them)'})
        elif str(layer['id']).startswith('wave_'):
            cloud=layer.get('point_cloud') or {}
            effects.append({'effect':'custom_waveform','layer':layer['id'],
                **({'points_per_frame':cloud.get('points_per_frame'),'hue_family_shares':cloud.get('hue_family_shares'),
                    'mean_alpha':cloud.get('mean_alpha'),'closed_form_positions':cloud.get('positions_closed_form'),
                    'position_bounds':cloud.get('position_bounds')} if cloud else {})})
    composite=render['composite']
    if composite.get('echo',{}).get('active'):effects.append({'effect':'echo_double','alpha':composite['echo'].get('alpha'),'zoom':composite['echo'].get('zoom')})
    if composite.get('scalar_palette'):effects.append({'effect':'palette_map','ramp':composite['scalar_palette']['ramp'][::4]})
    mirrors=render.get('mirrors') or {}
    if mirrors.get('operators'):
        effects.append({'effect':'mirror_symmetry','fold':mirrors.get('fold'),'flips':mirrors.get('flip_directions'),
                        'score_upper':mirrors.get('symmetry_score'),'operators':[r['operator']+':'+r['flip'] for r in mirrors['operators']]})
    palette={'warm_cool':features.get('palette.warm_cool',{}).get('value'),'saturation':features.get('palette.mean_saturation',{}).get('value'),
             'hue_variety_bins':features.get('palette.effective_hue_bins',{}).get('value'),
             'hue_cycle_per_s':features.get('palette.hue_rate_p95_cycles_s',{}).get('value'),
             'background_rgb':(fb.get('flat_field') or {}).get('composite_rgb_at_state')}
    return {'effects':effects,'reactivity':_reactivity(render),'palette':palette,
            'energy':{'intensity':mood['scores']['intensity']['value'],'smoothness':mood['scores']['smoothness']['value'],
                      'tags':[t['tag'] for t in mood['tags']]},
            'guidance':'Rebuild the listed effects at any resolution and frame rate in a modern engine; keep the reactivity map (which band drives which parameter, continuous or thresholded, smoothed or raw) and the palette/energy character. Exact pixels are not a goal.'}


if __name__=='__main__':
    main()
