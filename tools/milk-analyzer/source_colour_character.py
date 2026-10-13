"""General source colour character, never an image palette prediction.

Known native vertex colours, correlated grey and conditional RGB boxes supply
candidate hue families. Their prominence orders possible accents; unknown
feedback and draw/composition history do not acquire invented colours.
"""
import colorsys
from functools import lru_cache
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np

POLICY='source-colour-character-v1'
MODEL_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
FAMILIES=('grayscale','red','orange','yellow','green','cyan','blue','purple','pink')
HUE_BANDS={'red':((0,15),(345,360)),'orange':((15,45),),'yellow':((45,75),),
           'green':((75,165),),'cyan':((165,195),),'blue':((195,255),),
           'purple':((255,285),),'pink':((285,345),)}
TEMPERATURE={'grayscale':'neutral','red':'warm','orange':'warm','yellow':'warm',
             'green':'mixed','cyan':'cool','blue':'cool','purple':'mixed','pink':'warm'}
SATURATION_FLOOR=.08
VALUE_FLOOR=.02
ORDERS=((0,1,2,0,1),(1,0,2,120,-1),(1,2,0,120,1),
        (2,1,0,240,-1),(2,0,1,240,1),(0,2,1,360,-1))


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _clamp(value):return min(1.,max(0.,float(value)))


def _family(rgb):
    h,s,v=colorsys.rgb_to_hsv(*rgb)
    if s<SATURATION_FLOOR or v<=VALUE_FLOOR:return 'grayscale',[h,s,v]
    degrees=h*360
    for family,bands in HUE_BANDS.items():
        if any(low<=degrees<high for low,high in bands):return family,[h,s,v]
    return 'red',[h,s,v]


def _anchor(rgb,role):
    if len(rgb)!=3 or any(value is None or not math.isfinite(value) for value in rgb):return None
    clipped=list(map(_clamp,rgb));family,hsv=_family(clipped)
    return {'rgb':clipped,'raw_source_rgb':list(rgb),'hsv':hsv,'hue_family':family,
            'temperature':TEMPERATURE[family],'role':role}


@lru_cache(maxsize=64)
def _polytope_layout(constraints):
    """Precompute bounded RGB halfspace vertices with NumPy linear algebra.

    SciPy is an optional calibration dependency, so ordinary source exports must
    not require its LP solver. Every nonempty bounded polytope has a vertex;
    enumerate triples of boundary planes in this fixed three-dimensional problem.
    """
    eye=np.eye(3);matrix=np.vstack((eye,-eye,np.asarray(constraints,float)))
    choices=np.asarray(list(itertools.combinations(range(len(matrix)),3)),int)
    systems=matrix[choices];valid=np.abs(np.linalg.det(systems))>1e-12
    choices=choices[valid];inverse=np.linalg.inv(systems[valid])
    return matrix,choices,inverse


def _feasible(box,constraints,rhs):
    matrix,choices,inverse=_polytope_layout(tuple(tuple(row) for row in constraints))
    bounds=np.asarray([span[1] for span in box]+[-span[0] for span in box]+list(rhs),float)
    vertices=np.einsum('nij,nj->ni',inverse,bounds[choices])
    return bool(np.any(np.all(vertices@matrix.T<=bounds+1e-10,axis=1)))


@lru_cache(maxsize=2048)
def _box_families_cached(box):
    box=[list(pair) for pair in box]
    if all(low==high for low,high in box):return (_family([pair[0] for pair in box])[0],)
    # HSV sectors are linear cones once maximum/middle/minimum RGB order is
    # selected. Hue bounds become inequalities on (middle-min)/(maximum-min).
    possible=[];eye=np.eye(3)
    dark=all(pair[0]<=VALUE_FLOOR for pair in box)
    grey=dark or any(_feasible(box,[(1-SATURATION_FLOOR)*eye[maxi]-eye[i] for i in range(3)]+
                              [eye[i]-eye[maxi] for i in range(3)], [0]*6) for maxi in range(3))
    if grey:possible.append('grayscale')
    for family,bands in HUE_BANDS.items():
        found=False
        for maximum,middle,minimum,base,direction in ORDERS:
            sector=sorted((base,base+direction*60))
            for low,high in bands:
                low=max(low,sector[0]);high=min(high,sector[1])
                if low>=high:continue
                tl,th=sorted(((low-base)/(direction*60),(high-base)/(direction*60)))
                difference=eye[maximum]-eye[minimum];mid=eye[middle]-eye[minimum]
                constraints=[eye[middle]-eye[maximum],eye[minimum]-eye[middle],
                    eye[minimum]-(1-SATURATION_FLOOR)*eye[maximum],-eye[maximum],
                    tl*difference-mid,mid-th*difference]
                if _feasible(box,constraints,[0,0,0,-VALUE_FLOOR-1e-7,0,0]):found=True;break
            if found:break
        if found:possible.append(family)
    return tuple(possible)


def _box_families(box):
    if box is None or len(box)!=3 or any(pair is None or len(pair)!=2 or
            not all(math.isfinite(v) for v in pair) or pair[0]>pair[1] for pair in box):return []
    clipped=tuple(tuple(_clamp(v) for v in pair) for pair in box)
    return list(_box_families_cached(clipped))


def _palette(anchors=(),box=None,*,model='unknown',forced_families=None):
    known=[];seen=set()
    for rgb,role in anchors:
        anchor=_anchor(rgb,role)
        if anchor is not None and tuple(anchor['rgb']) not in seen:
            known.append(anchor);seen.add(tuple(anchor['rgb']))
    families=_box_families(box) if forced_families is None else list(forced_families)
    if box is None:families=[family for family in FAMILIES if any(a['hue_family']==family for a in known)]
    return {'anchors':known,'rgb_component_intervals':box,'hue_families_possible':families,
            'temperature_candidates':sorted({TEMPERATURE[f] for f in families}),
            'model':model,'reached_palette_verified':False,
            'scope':'source anchors and conditional independent RGB box; no reached hue histogram or displayed dominance'}


def _material_palette(element,group_boxes=None):
    from source_fill_envelopes import native_channel_envelope
    material=element['material'];temporal=element.get('scenario_material_envelope') or element.get('material_temporal',{})
    groups=[];reasons=[]
    center=material['centre_vertex_rgba'];edge=material['perimeter_vertex_rgba']
    if center[3]!=0 or edge[3]!=0:groups=[('centre',center,('r','g','b')),('perimeter',edge,('r2','g2','b2'))]
    border=material.get('border_vertex_rgba',[None]*4)
    if material.get('border_draw_enabled') is not False and border[3]!=0:groups.append(('border',border,('border_r','border_g','border_b')))
    anchors=[];boxes=[];partial=False
    for role,rgba,names in groups:
        if any(v is None for v in rgba[:3]):partial=True
        anchors.append((rgba[:3],role))
        box=[]
        for value,name in zip(rgba[:3],names):
            if value is not None and math.isfinite(value):box.append([_clamp(value)]*2)
            else:
                channel=temporal.get('channels',{}).get(name)
                envelope=None if channel is None else native_channel_envelope(channel)
                box.append([0.,1.] if envelope is None else [_clamp(v) for v in envelope])
                reasons.append(name+' has an interval rather than a constant native colour')
        boxes.append((group_boxes or {}).get(role,box))
    box=None if not boxes else [[min(b[i][0] for b in boxes),max(b[i][1] for b in boxes)] for i in range(3)]
    textured=material.get('texture',{}).get('role') not in {None,'untextured_vertex_gradient'}
    if textured and box is not None:
        vertex_box=box;box=[[0.,span[1]] for span in box]
        palette=_palette((),box,model='sampled_RGBA_times_native_vertex_tint')
        palette['vertex_tint_anchors']=_palette(anchors,vertex_box,model='native_vertex_tint')['anchors']
        if set(palette['hue_families_possible'])==set(FAMILIES):
            palette['hue_families_possible']=[];palette['temperature_candidates']=[]
            status='inherited_colour'
        else:status='inherited_tinted_colour'
        reasons.append('sampled texture/feedback supplies unknown RGBA; vertex tint is not the actual image palette')
    else:
        palette=_palette(anchors,box,model='native_vertex_gradient_box')
        status='partial_source_colour' if partial else 'known_source_colour'
    return palette,status,reasons


def _assemble(analysis,prefix,environment):
    from effect_families import _EEL,Field,select_equation
    selected=select_equation(analysis.sections.get(prefix),prefix,policy=analysis.policy)
    model=_EEL(environment,equation_phase=prefix)
    if selected['compile_status']=='accepted' and selected['tree_status']=='parsed':model.lower(selected['tree'])
    elif selected['compile_status']!='omitted':
        model.environment={name:Field('unknown',detail={'reason':'active equation tree/loading unresolved'}) for name in environment}
    return model


def _custom_wave_palette(analysis,identity):
    from effect_families import Field,_constant,_EEL,select_equation
    from scene_equations import _scalar,READONLY
    from source_material_temporal import _channel_from_curve
    from source_control_bounds import scalar_value_envelope
    from source_fill_envelopes import native_channel_envelope
    from source_appearance import _phase_literal
    index=identity.removeprefix('wave_');prefix='wavecode_'+index+'_'
    defaults={name:_constant(_scalar(analysis.values,prefix+name,1,'float')) for name in 'rgba'}
    init_prefix=identity+'_init'
    init=_assemble(analysis,init_prefix,{**defaults,**{name:Field('input',detail={'name':'init:'+init_prefix+':'+name}) for name in READONLY}})
    reset={**defaults,**{name:Field('input',detail={'name':name}) for name in READONLY},
        **{f'q{i}':analysis.main.get(f'q{i}',Field('unknown')) for i in range(1,33)},
        **{f't{i}':init.environment.get(f't{i}',_constant(0)) for i in range(1,9)}}
    frame_prefix=identity+'_per_frame'
    frame=_assemble(analysis,frame_prefix,analysis.frame_environment(frame_prefix,init.environment,reset,uninitialized_state=True))
    point_prefix=identity+'_per_point';selected=select_equation(analysis.sections.get(point_prefix),point_prefix,policy=analysis.policy)
    written=_EEL.assignment_targets(selected.get('tree'))
    point={name:frame.environment.get(name,Field('unknown')) for name in (*'rgba',*READONLY,*(f'q{i}' for i in range(1,33)),*(f't{i}' for i in range(1,9)))}
    # Wave contexts see only q/t copies of other blocks: a per-point name no wave block writes reads 0.
    from scene_equations import _variables
    for name in {n.lower() for n in _variables(selected.get('tree') or {})}-written-point.keys()-set('xy')-{'sample','value1','value2'}:
        point[name]=_constant(0)
    for name in written-set('rgbaxy')-{'sample','value1','value2'}:
        point[name]=Field('input',detail={'name':'state:'+point_prefix+':'+name})
    point.update({name:Field('input',detail={'name':name}) for name in ('sample','value1','value2')})
    # projectM CustomWaveform::LoadPerPointEvaluationVariables (MilkDrop2 alike): each point starts at
    # x = 0.5 + value1, y = 0.5 + value2, so a wave without position code is a stereo X-Y trace.
    for name,value in (('x','value1'),('y','value2')):
        point[name]=Field('add',(_constant(.5),Field('input',detail={'name':value})),'float')
    controls=_assemble(analysis,point_prefix,point).environment
    scenario=getattr(analysis,'input_scenario',None) or {};domains={**scenario.get('scalar_input_domains',{}),'sample':[0.,1.]}
    box=[];values=[];reasons=[];reports={};invalid=False;alpha=None
    for name in 'rgba':
        report=scalar_value_envelope(controls.get(name,Field('unknown')),input_domains=domains);reports[name]=report
        channel=_channel_from_curve({'curve_kind':'unknown','nominal_value_range':report['nominal_value_range'],
            'maximum_absolute_control_rate_per_second':None,'nominal_continuity':'unknown','unknown_reasons':report['unknown_reasons']},'centre')
        pair=native_channel_envelope(channel);value=_phase_literal(controls.get(name,Field('unknown')))
        if report['nominal_value_range'] is not None and channel['native_float32_endpoint_domain'] is None:invalid=True
        native=channel['native_value_if_singleton']
        if name=='a':alpha=pair
        else:
            values.append(native);box.append([0.,1.] if pair is None else [_clamp(v) for v in pair])
        if pair is None:reasons.extend(report['unknown_reasons'] or [name+' native colour domain unresolved'])
    palette=_palette([(values,'custom_wave_native_point')],box,model='native_custom_wave_source_box')
    from source_appearance import _colour
    if not invalid and _colour(Field('components',tuple(controls[name] for name in 'rgb'),'float3')).get('mode_code')==1:
        palette.update(hue_families_possible=['grayscale'],temperature_candidates=['neutral'],model='correlated_native_shared_scalar_rgb')
    palette['channel_domain_evidence']=reports
    palette['point_colour_distribution']=_point_distribution(analysis,prefix,frame,controls,domains,init)
    palette['known_invalid_native_domain']=invalid
    palette['provably_inactive']=not invalid and alpha is not None and alpha[1]==0
    status='known_source_colour' if all(v is not None for v in values) else 'dynamic_source_colour'
    return palette,status,reasons


def _wave_recurrence(frame_prefix,init,frame,programs):
    """Persistent per-frame variables of one custom wave read by its per-point graphs.

    A variable the per-frame code reads before writing appears in point graphs as
    'state:<wave>_per_frame:<name>' (its start-of-frame value). Each such variable gets its
    initial graph (wave init code, else 0) and end-of-frame update graph; update graphs may read
    further state of the same wave, which is collected transitively. Returns None when no state
    is read or a graph cannot be serialised.
    """
    from effect_families import Field
    from source_appearance import _expression
    from eel_memory import input_names
    marker='state:'+frame_prefix+':'
    def states_of(expression):
        names=input_names(expression,stochastic=True) if expression else None
        return {n[len(marker):] for n in (names or ()) if isinstance(n,str) and n.startswith(marker)}
    pending=set()
    for expression in programs.values():pending|=states_of(expression)
    if not pending:return None
    state={};done=set()
    while pending:
        name=pending.pop()
        if name in done:continue
        done.add(name)
        update=_expression(frame.environment.get(name,Field('unknown')))
        initial=_expression(init.environment.get(name,Field('constant',detail={'value':0.})))
        if update is None or initial is None:return None
        state[name]={'initial':initial,'update':update}
        pending|=states_of(update)-done
    return {'policy':'source-custom-wave-frame-recurrence-v1','state_input_prefix':marker,'state':state,
            'conditions':['update graphs give the end-of-frame value; point graphs read the start-of-frame value',
                          'initial graphs read init-time inputs; stepping evaluates authored equations over declared inputs']}


def _point_recurrence(point_prefix,init,controls,programs):
    """Per-point persistent variables read by the point graphs ('state:<wave>_per_point:<name>').

    MilkDrop keeps per-point variables from point to point (and frame to frame): a point graph
    reads the previous point's end value. Each variable gets its end-of-point update graph (in
    terms of its start value and the point inputs) and its initial value (wave init code, else 0).
    """
    from effect_families import Field
    from source_appearance import _expression
    from eel_memory import input_names
    marker='state:'+point_prefix+':'
    def states_of(expression):
        names=input_names(expression,stochastic=True) if expression else None
        return {n[len(marker):] for n in (names or ()) if isinstance(n,str) and n.startswith(marker)}
    pending=set()
    for expression in programs.values():pending|=states_of(expression)
    if not pending:return None
    state={};done=set()
    while pending:
        name=pending.pop()
        if name in done:continue
        done.add(name)
        update=_expression(controls.get(name,Field('unknown')))
        initial=_expression(init.environment.get(name,Field('constant',detail={'value':0.})))
        if update is None or initial is None:return None
        state[name]={'initial':initial,'update':update}
        pending|=states_of(update)-done
    return {'policy':'source-custom-wave-point-recurrence-v1','state_input_prefix':marker,'state':state,
            'conditions':['points are evaluated in order; point j reads the end value of point j-1',
                          'the value carries from the last point of one frame to the first point of the next']}


def _point_distribution(analysis,prefix,frame,controls,domains,init=None):
    """Closed-form per-point colour distribution over the authored sample grid."""
    from effect_families import Field
    from scene_equations import _scalar
    from source_appearance import _expression,_phase_literal
    from source_point_colour import point_colour_distribution
    samples=frame.environment.get('samples')
    count=_phase_literal(samples) if samples is not None else _scalar(analysis.values,prefix+'samples',512,'float')
    if count is not None:count=min(512,math.trunc(count))
    programs={name:_expression(controls.get(name,Field('unknown'))) for name in 'rgba'}
    held={name:span for name,span in domains.items() if name!='sample'}
    positions={name:_expression(controls.get(name,Field('unknown'))) for name in 'xy'}
    recurrence=None;point_recurrence=None
    if init is not None:
        identity='wave_'+prefix.removeprefix('wavecode_').rstrip('_')
        recurrence=_wave_recurrence(identity+'_per_frame',init,frame,{**programs,**positions})
        point_recurrence=_point_recurrence(identity+'_per_point',init,controls,{**programs,**positions})
    waveform=None
    spectrum_mode=_scalar(analysis.values,prefix+'bSpectrum',0,'float')
    params={'scaling':_scalar(analysis.values,prefix+'scaling',1,'float'),'smoothing':_scalar(analysis.values,prefix+'smoothing',.5,'float'),
            'sep':_scalar(analysis.values,prefix+'sep',0,'float'),'wave_scale':_scalar(analysis.values,'fWaveScale',1,'float')}
    if type(spectrum_mode) in (int,float) and all(type(v) in (int,float) and math.isfinite(v) for v in params.values()):
        waveform={'params':{**{k:float(v) for k,v in params.items()},'sep':int(params['sep']),'spectrum':bool(spectrum_mode)}}
    record=point_colour_distribution(programs,count,held,positions=positions,recurrence=recurrence,waveform=waveform,
                                     point_recurrence=point_recurrence)
    flags={}
    for name,key in (('dots','bUseDots'),('thick','bDrawThick'),('additive','bAdditive'),('spectrum','bSpectrum')):
        value=_scalar(analysis.values,prefix+key,0,'float')
        flags[name]=None if value is None else bool(value)
    record['draw_flags']=flags
    return record


def _random_vertex_palette(controls):
    """Bound direct native random channels; infer no RNG distribution/visibility."""
    from source_appearance import _phase_literal
    from primitives import colour_modulo
    def channel(field):
        denominator=1.
        if field.op=='divide' and len(field.args)==2:
            denominator=_phase_literal(field.args[1]);field=field.args[0]
        if denominator is None or not math.isfinite(denominator) or denominator<=0:return None
        quantized=field.op in {'int','floor'} and len(field.args)==1
        if quantized:field=field.args[0]
        if field.op!='rand' or len(field.args)!=1 or field.detail.get('value_binding')!='stateful_random_call':return None
        maximum=_phase_literal(field.args[0])
        if maximum is None or not math.isfinite(maximum):return None
        maximum=max(1,math.floor(maximum))
        upper=maximum/denominator
        # This exact simple scope avoids modulo seams/out-of-range upload.
        if not math.isfinite(upper) or not 0<upper<=1:return None
        phase=field.detail.get('equation_phase')
        if not isinstance(phase,str):return None
        refresh='preset_initialization' if phase.endswith('_init') or phase=='per_frame_init_' else \
            'shape_instance_invocation' if phase.startswith('shape_') and phase.endswith('_per_frame') else \
            'main_frame_invocation' if phase=='per_frame_' else 'unresolved_execution_scope'
        return {'site':{'equation_phase':phase,'site_index':field.detail['site_index']},
            'encoded_channel_interval':[0.,float(colour_modulo(upper))],
            'maximum_random_argument':maximum,'division_denominator':denominator,
            'integer_projection':quantized,'refresh_scope':refresh}
    groups={}
    for group,names in [('centre',('r','g','b')),('perimeter',('r2','g2','b2')),('border',('border_r','border_g','border_b'))]:
        channels=[channel(controls[name]) for name in names]
        if any(c is None for c in channels):continue
        sites={_digest(c['site']):c['site'] for c in channels}
        scopes={c['refresh_scope'] for c in channels}
        groups[group]={'encoded_rgb_component_intervals':[c['encoded_channel_interval'] for c in channels],
            'channels':channels,'distinct_source_sites':list(sites.values()),
            'shared_random_draw':len(sites)==1,'refresh_scope':next(iter(scopes)) if len(scopes)==1 else 'mixed_execution_scopes'}
    if not groups:return None
    return {**groups,'actual_palette_verified':False,'native_rng_distribution_certified':False,
        'conditions':['Separate live call sites are not proved equal; copied results retain their source identity',
            'Native rand uses floor(maximum), clamped to at least1, and may reach its upper endpoint',
            'Bounded channel values describe source ingredients, not reached hue frequencies or perceptual flashing',
            'Initialization, frame and instance execution scopes remain separate; no source program/frames are executed']}


def _source_palette(analysis,description,element):
    if 'material' in element:
        palette,status,reasons=_material_palette(element)
        controls=getattr(analysis,'component_controls',{}).get(element['id'])
        if controls is not None and element['material'].get('texture',{}).get('role')=='untextured_vertex_gradient':
            from shader_fields import Field
            from source_appearance import _colour
            groups=[('r','g','b'),('r2','g2','b2')]
            if element['material'].get('border_draw_enabled') is not False:groups.append(('border_r','border_g','border_b'))
            mono=True
            for names in groups:
                colour=_colour(Field('components',tuple(controls[name] for name in names),'float3'))
                constant=colour.get('constant_rgb')
                if colour.get('mode_code')!=1 and not (constant is not None and constant[0]==constant[1]==constant[2]):mono=False;break
            if mono:
                palette.update(hue_families_possible=['grayscale'],temperature_candidates=['neutral'],model='correlated_native_shared_scalar_rgb')
                status='dynamic_source_colour' if not palette['anchors'] else status
            stochastic=_random_vertex_palette(controls)
            if stochastic:
                bounded,status,reasons=_material_palette(element,{name:stochastic[name]['encoded_rgb_component_intervals']
                    for name in ('centre','perimeter','border') if name in stochastic})
                palette['rgb_component_intervals']=bounded['rgb_component_intervals']
                palette['stochastic_vertex_colour']=stochastic
                if not mono:
                    palette['model']='bounded_stochastic_native_vertex_rgb'
                    palette['hue_families_possible']=_box_families(palette['rgb_component_intervals'])
                    palette['temperature_candidates']=sorted({TEMPERATURE[f] for f in palette['hue_families_possible']})
        return palette,status,reasons
    wave=element.get('wave_material')
    if wave is not None:
        constant=wave.get('constant_vertex_rgb');box=wave.get('rgb_component_envelopes')
        return _palette([] if constant is None else [(constant,'native_builtin_wave')],box,
            model='native_builtin_wave_clamp_and_normalization'),('known_source_colour' if constant is not None else 'dynamic_source_colour'),[]
    identity=element['id']
    if identity.startswith('wave_') and hasattr(analysis,'sections'):
        return _custom_wave_palette(analysis,identity)
    colour=element.get('colour') or {};mode=colour.get('mode_code')
    if mode==0:
        rgb=colour.get('constant_rgb')
        if rgb is not None:return _palette([(rgb,'shader_constant_rgb')],[[v,v] for v in rgb],model='selected_source_constant_rgb'),'known_source_colour',[]
    if mode==1:
        return _palette((),[[0.,1.]]*3,model='correlated_shared_scalar_rgb',forced_families=['grayscale']),'dynamic_source_colour',[]
    stage=element.get('stage')
    box=description.get('nonlinear_texture_colour_bounds',{}).get('stages',{}).get(stage,{}).get('raw_rgb_bounds_if_samples_unit_interval')
    if box is None:box=description.get('texture_colour_envelopes',{}).get('stages',{}).get(stage,{}).get('raw_rgb_bounds_if_samples_unit_interval')
    if mode in {3,5}:
        if box is None and colour.get('bias_rgb') is not None and colour.get('amplitude_rgb') is not None:
            box=[[_clamp(b-abs(a)),_clamp(b+abs(a))] for b,a in zip(colour['bias_rgb'],colour['amplitude_rgb'])]
        return _palette((),box,model='conditional_phase_generated_rgb_box'),'dynamic_source_colour',[]
    if mode==4 or stage in {'warp','mesh_warp'}:
        constrained=box is not None and set(_box_families(box))!=set(FAMILIES)
        if constrained:return _palette((),box,model='conditional_inherited_RGB_box'),'inherited_tinted_colour',[]
        return _palette(model='unresolved_feedback_palette'),'inherited_colour',['feedback/image colour is unresolved']
    if box is not None:return _palette((),box,model='conditional_shader_RGB_box'),'dynamic_source_colour',[]
    return _palette(),'unknown_colour',['no qualified native vertex or selected RGB source colour model']


def _suffix_value(value,steps):
    for step in steps:
        operation=step['operation']
        if operation=='domain_guard':continue
        if operation=='multiply_constant':value*=step['value']
        elif operation=='divide_constant':value/=step['value']
        elif operation=='add_constant':value+=step['value']
        elif operation=='constant_minus':value=step['value']-value
        elif operation=='one_minus':value=1-value
        elif operation=='abs':value=abs(value)
        elif operation=='power':
            if value==0 and step['value']<=0:raise ValueError('zero power base with nonpositive exponent is not a qualified shader domain')
            value=value**step['value']
        elif operation=='saturate':value=_clamp(value)
        elif operation=='clamp':value=min(step['upper'],max(step['lower'],value))
        else:raise ValueError('unsupported RGB processing operation '+str(operation))
        if isinstance(value,complex) or not math.isfinite(value):raise ValueError('nonfinite or complex RGB transfer')
    return _clamp(value)


def _suffix_interval(pair,steps):
    """Reuse the generic scalar range/proof producer for the ordered suffix."""
    from shader_fields import Field
    from source_control_bounds import scalar_value_envelope
    from effect_families import _constant
    name='colour_character_source_component';node=Field('input',detail={'name':name})
    for step in steps:
        op=step['operation']
        if op=='domain_guard':continue
        if op in {'abs','saturate'}:node=Field(op,(node,))
        elif op=='power':node=Field('pow',(node,_constant(step['value'])))
        elif op=='clamp':node=Field('clamp',(node,_constant(step['lower']),_constant(step['upper'])))
        elif op=='one_minus':node=Field('subtract',(_constant(1),node))
        elif op=='constant_minus':node=Field('subtract',(_constant(step['value']),node))
        elif op in {'multiply_constant','divide_constant','add_constant'}:
            node=Field({'multiply_constant':'multiply','divide_constant':'divide','add_constant':'add'}[op],(node,_constant(step['value'])))
        else:raise ValueError('unsupported RGB suffix interval '+op)
    report=scalar_value_envelope(node,input_domains={name:pair});span=report['nominal_value_range']
    if span is None:raise ValueError('RGB suffix has no finite qualified scalar envelope')
    return [_clamp(v) for v in span]


def _final_palette(analysis,description,element,source):
    if element.get('stage')=='composite':
        return {**source,'transfer_model':'already selected composite RGB'},[]
    selected=analysis.stages.get('composite',{})
    if selected.get('kind')=='unknown':return {**_palette(),'transfer_model':'unresolved custom stage selection'},['final composite selection/fallback is unresolved']
    if selected.get('kind')=='legacy_composite':
        from source_appearance import _phase_literal
        from legacy_composite import source_tint_amount,gamma_weights
        from engine_profiles import CORE_2331_DISPLAY
        names=('gamma','echo_alpha','brighten','darken','solarize','invert')
        values={name:_phase_literal(analysis.main[name]) if name in analysis.main else None for name in names}
        box=source.get('rgb_component_intervals');gamma=values['gamma']
        tint=source_tint_amount(analysis.source)
        if box is not None and all(v is not None and math.isfinite(v) for v in values.values()) and tint is not None and math.isfinite(tint) and values['echo_alpha']==0:
            gamma=float(np.float32(min(8.,max(0.,gamma))))
            gain=sum(gamma_weights(gamma,echo=False,control_policy=CORE_2331_DISPLAY))
            untinted=tint<=float(np.float32(.001))
            shade=[1.,1.] if untinted else [1.-tint/3.,1.]
            # The main image supplied to legacy composition is stored UNORM,
            # even when the generating warp's raw RGB exceeded that range.
            box=[[_clamp(v) for v in span] for span in box]
            box=[[_clamp(min(v*gain*s for v in span for s in shade)),
                  _clamp(max(v*gain*s for v in span for s in shade))] for span in box]
            for name in ('brighten','darken','solarize','invert'):
                if not values[name]:continue
                if name=='brighten':box=[[1-(1-a)**2,1-(1-b)**2] for a,b in box]
                elif name=='darken':box=[[a*a,b*b] for a,b in box]
                elif name=='solarize':box=[[min(2*a*(1-a),2*b*(1-b)),.5 if a<=.5<=b else max(2*a*(1-a),2*b*(1-b))] for a,b in box]
                else:box=[[1-b,1-a] for a,b in box]
            shared_gray=untinted and source.get('model') in {'correlated_native_shared_scalar_rgb','correlated_shared_scalar_rgb'}
            palette=_palette((),box,model='conditional_native_legacy_hue_gamma_filter_box',
                             forced_families=['grayscale'] if shared_gray else None)
            palette['legacy_tint_amount']=tint
            palette['legacy_tint_disabled']=untinted
            palette['gamma_redraw_gain']=gain
            palette['transfer_model']='native_legacy_gamma_hue_and_ordered_filters'
            return palette,[]
    transfer=description.get('texture_colour_transfer',{}).get('stages',{}).get('composite',{})
    transform=None;model=None
    if transfer.get('source_model')=='affine_sample_colour' and transfer.get('coordinate_sample_dependency') is False:
        samples=transfer.get('sample_contributions',[]);offset=transfer.get('constant_offset_rgb');uv=transfer.get('base_uv_matrix_rgb')
        if samples and all(s.get('canonical_texture')=='main' and all(row[3]==0 for row in s['matrix_rgb_rgba']) for s in samples) and offset is not None and all(v is not None and math.isfinite(v) for v in offset) and uv is not None and not np.any(uv):
            matrix=np.sum([np.asarray(s['matrix_rgb_rgba'])[:,:3] for s in samples],axis=0)
            transform=lambda rgb:np.clip(matrix@np.asarray(rgb)+offset,0,1).tolist()
            model='conditional_affine_main_rgb'
    channels=description.get('colour_processing',{}).get('stages',{}).get('composite',{}).get('channels')
    if transform is None and channels is not None and len(channels)==3 and all(c.get('base',{}).get('kind')=='sample_channel' and c['base'].get('canonical_texture')=='main' and c['base'].get('sample_channel',4)<3 for c in channels):
        transform=lambda rgb:[_suffix_value(rgb[c['base']['sample_channel']],c['steps_from_base']) for c in channels]
        model='conditional_ordered_main_rgb_suffix'
    if transform is None and selected.get('kind')=='default_composite':
        transform=lambda rgb:list(rgb);model='native_default_main_copy'
    if transform is None:
        return {**_palette(),'transfer_model':'unresolved final RGB transfer'},['later main/blur/texture composition may change the source colours']
    anchors=[];reasons=[]
    for anchor in source['anchors']:
        try:anchors.append((transform(anchor['rgb']),'transferred_'+anchor['role']))
        except (ValueError,ZeroDivisionError,OverflowError) as error:reasons.append(str(error))
    palette=_palette(anchors,model='conditional_transferred_source_anchors')
    palette['transfer_model']=model
    palette['conditions']=['Each supplying main lookup must receive this component colour; destination, other draws and history remain unresolved',
        'Nominal selected-stage RGB arithmetic followed by encoded unit-interval classification clamp; no actual displayed palette certificate']
    if source['rgb_component_intervals'] is not None:
        corners=list(itertools.product(*source['rgb_component_intervals']))
        try:
            values=[transform(rgb) for rgb in corners]
            if model=='conditional_ordered_main_rgb_suffix':
                palette['rgb_component_intervals']=[_suffix_interval(source['rgb_component_intervals'][c['base']['sample_channel']],c['steps_from_base']) for c in channels]
            else:palette['rgb_component_intervals']=[[min(rgb[i] for rgb in values),max(rgb[i] for rgb in values)] for i in range(3)]
            palette['hue_families_possible']=_box_families(palette['rgb_component_intervals'])
            palette['temperature_candidates']=sorted({TEMPERATURE[f] for f in palette['hue_families_possible']})
        except (ValueError,ZeroDivisionError,OverflowError) as error:reasons.append(str(error))
    return palette,reasons


def colour_character(analysis,description,prominence,context):
    """Summarize source palette candidates and prominence-weight their hierarchy."""
    elements=list(description.get('elements',[]));rows=[];hierarchy={};inherited=[];unknowns=[]
    if hasattr(analysis,'sections'):
        from scene_equations import _scalar
        existing={e['id'] for e in elements}
        for index in range(4):
            identity='wave_'+str(index)
            if identity not in existing and _scalar(analysis.values,f'wavecode_{index}_enabled',0,'bool'):
                elements.append({'id':identity,'stage':'drawing'})
    weights=prominence.get('by_component',{})
    provenance={'preset_sha256':analysis.source.get('preset_sha256'),'context_sha256':_digest(context or {}),
                'model_sha256':MODEL_SHA256,'parser_inputs_sha256':_digest(analysis.source.get('parser_inputs',{}))}
    for element in elements:
        identity=element['id'];weight=weights.get(identity,{});interval=weight.get('displayed_contribution_interval',[0.,1.])
        invalid=weight.get('known_invalid_native_domain',False)
        source,status,reasons=_source_palette(analysis,description,element)
        invalid|=source.get('known_invalid_native_domain',False)
        final,final_reasons=_final_palette(analysis,description,element,source)
        reasons+=final_reasons
        if invalid:
            status='unknown_colour';source=_palette(model='known_invalid_native_colour_domain')
            final={**_palette(),'transfer_model':'known invalid native source domain'}
            reasons+=weight.get('unknown_reasons',[]) or ['known invalid native input domain']
            interval=[0.,1.]
        eligible=(interval[1] is None or interval[1]>0) and not source.get('provably_inactive',False)
        if not eligible:status='inactive_source_colour'
        if status.startswith('inherited'):inherited.append(identity)
        record={'component_id':identity,'stage':element.get('stage'),'status':status,
            'source_palette':source,'final_candidate_palette':final,'contribution_interval':interval,
            'eligible_accent':eligible,'unknown_reasons':sorted(set(reasons)),'provenance':provenance}
        rows.append(record)
        palette=final if final['hue_families_possible'] else source
        if eligible:
            if status=='unknown_colour' or status=='inherited_colour':unknowns.append({'component_id':identity,'contribution_interval':interval,'reason':status})
            for family in palette['hue_families_possible']:
                row=hierarchy.setdefault(family,{'hue_family':family,'temperature':TEMPERATURE[family],
                    'weight_interval':[0.,0.],'contributors':[],'role':'conditional source/final candidate, not dominant image hue'})
                row['weight_interval'][1]=min(1.,row['weight_interval'][1]+(1. if interval[1] is None else interval[1]))
                row['contributors'].append(identity)
    useful=any(r['eligible_accent'] and (r['source_palette'].get('stochastic_vertex_colour') or r['source_palette']['anchors'] or
        0<len(r['source_palette']['hue_families_possible'])<len(FAMILIES)) for r in rows)
    return {'policy':POLICY,'provenance':provenance,'components':rows,
        'by_component':{r['component_id']:r for r in rows},
        'candidate_palette_hierarchy':sorted(hierarchy.values(),key=lambda r:(-r['weight_interval'][1],FAMILIES.index(r['hue_family']))),
        'inherited_component_ids':inherited,'unknown_contributors':unknowns,'useful_hue_description':bool(useful),
        'category_policy':{'hue_degrees':{name:[list(band) for band in spans] for name,spans in HUE_BANDS.items()},'grayscale_saturation_below':SATURATION_FLOOR,
            'near_black_value_at_most':VALUE_FLOOR,'temperature_by_family':TEMPERATURE,'fitted_to_human_labels':False},
        'conditions':['HSV families describe encoded source RGB, not measured image colour, lighting temperature or aesthetic judgment',
            'Independent RGB boxes admit hue candidates, not simultaneous or reached colours; source correlations may restrict them',
            'Prominence intervals order possible contribution; overlap, alpha, destination and feedback prevent guaranteed dominance',
            'Unknown inherited palettes remain unknown even when a texture-read mechanism is known'],
        'uses_rendered_images':False,'uses_equation_execution':False,'uses_shader_execution':False,'actual_image_palette_verified':False}
