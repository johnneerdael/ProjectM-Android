"""Structured approximate appearance and audio-control routes from contributing code.

Numeric categories are vocabulary IDs, not visual confidence or screen response
scores. Formulas describe authored control programs, never a shader replacement.
"""
import math
import hashlib
import json

POLICY='source-appearance-and-control-traits-v1'
FAMILY_CODES={'spatial_oscillatory_bands':10,'periodic_radial_glow':9,'builtin_wave_primitive':1,'custom_wave_primitive':1,'circular_wave_primitive':4,
    'point_cloud_primitive':2,'polygon_shape_primitive':3,'parametric_radial_curve':4,
    'polar_radial_sampling':5,'angular_mirror_fold':6,'cartesian_mirror_fold':6,
    'complex_quadratic_recurrence':7,'mandelbox_recurrence':7,'iterated_spatial_fold':7,
    'multi_copy_feedback_recursion':8,'radial_twist':8,'global_rotation':8,
    'spatial_rotation':8,'radial_feedback_transform':8,'angular_periodic_warp':8,
    'uv_advection':8,'image_driven_advection':8,'noise_driven_advection':8,
    'gradient_driven_advection':8,'nonlinear_feedback_map':8}
AUDIO={'bass':1,'mid':2,'treb':3,'bass_att':4,'mid_att':5,'treb_att':6,'vol':7,'vol_att':8}
EEL_AUDIO={name:code for name,code in AUDIO.items() if name not in {'vol','vol_att'}}
PACKED={'_c3':(1,2,3,7),'_c4':(4,5,6,8)}
SHAPE_CONTROLS={'x':('position_x','milkdrop shape coordinate'),'y':('position_y','milkdrop shape coordinate'),
    'rad':('radius','milkdrop shape radius'),'ang':('rotation','rad'),
    'r':('colour_r','encoded RGB component'),'g':('colour_g','encoded RGB component'),
    'b':('colour_b','encoded RGB component'),'a':('opacity','source opacity'),
    'r2':('perimeter_colour_r','encoded RGB component'),'g2':('perimeter_colour_g','encoded RGB component'),
    'b2':('perimeter_colour_b','encoded RGB component'),'a2':('perimeter_opacity','source opacity'),
    'border_r':('border_colour_r','encoded RGB component'),'border_g':('border_colour_g','encoded RGB component'),
    'border_b':('border_colour_b','encoded RGB component'),'border_a':('outline_opacity','source opacity'),
    'tex_zoom':('texture_zoom','source texture zoom ratio'),'tex_ang':('texture_rotation','rad')}
MESH_CONTROLS={'zoom':('zoom','source zoom ratio'),'zoomexp':('radial_zoom','source zoom exponent'),
    'rot':('rotation','rad/feedback step'),'dx':('translation_x','source UV displacement'),
    'dy':('translation_y','source UV displacement'),'sx':('scale_x','source UV scale'),
    'sy':('scale_y','source UV scale'),'warp':('deformation','source warp control')}


def _digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _canonical_lane(value):
    """Compose nested swizzles without changing cross-lane operations."""
    from shader_fields import Field
    from field_math import SWIZZLE
    while value.op=='member' and value.detail.get('swizzle'):
        parent=value.args[0]
        if parent.op!='member' or not parent.detail.get('swizzle'):break
        outer=value.detail['field'];inner=parent.detail['field']
        indices=[SWIZZLE[c] for c in outer]
        if any(index>=len(inner) for index in indices):break
        value=Field('member',parent.args,value.dtype,{'field':''.join(inner[index] for index in indices),'swizzle':True})
    return value


def _data_return(value):
    while value.op=='sequence':value=value.args[-1]
    return value


def _packed_reads(field):
    """Affirmative component reads, using the existing live LoopPlan slice."""
    from effect_families import _walk,_children,_strip,_CACHE
    from field_math import SWIZZLE
    cache=_CACHE.get();key=('appearance_packed_reads',id(field))
    if cache is not None and key in cache and cache[key][0] is field:return cache[key][1]
    result={}
    for node,path in _walk(_data_return(field)):
        projected=_canonical_lane(node)
        if projected.op=='member' and projected.detail.get('swizzle'):
            parent=_strip(projected.args[0])
            if parent.op=='input':
                name=parent.detail.get('name')
                result.setdefault(name,set()).update(SWIZZLE[c] for c in projected.detail['field'])
                continue
        for child in _children(node):
            if child.op=='input' and child.dtype=='float4' and node.op!='member':
                result.setdefault(child.detail['name'],set()).update(range(4))
    if cache is not None:cache[key]=(field,result)
    return result


def _colour_number(value,depth=0):
    number=_phase_literal(value)
    if number is not None:return number
    if depth>=64:return None
    if value.op in {'saturate','abs'}:
        child=_colour_number(value.args[0],depth+1)
        if child is not None:return min(1.,max(0.,child)) if value.op=='saturate' else abs(child)
    if value.op=='clamp':
        values=[_colour_number(arg,depth+1) for arg in value.args]
        if all(v is not None for v in values) and values[1]<=values[2]:
            return min(values[2],max(values[1],values[0]))
    return None


def _stage_programs(analysis):
    from source_stage_program import stage_programs
    try:return stage_programs(analysis)
    except Exception as error:  # noqa: BLE001 - optional structural export
        return {'policy':'source-stage-program-v1','stages':{},'unknown_reasons':[str(error)[:200]]}


def _expression(field):
    """Bounded equation/control DAG; unknown loops/programs are not expanded."""
    nodes=[];ids={}
    def visit(node):
        if id(node) in ids:return ids[id(node)]
        if len(nodes)>=256:raise ValueError('control expression export budget exceeded')
        index=len(nodes);ids[id(node)]=index;nodes.append(None)
        detail={key:value for key,value in node.detail.items() if key in {'value','name','field','operator','target_type','reason','index',
            'sampler','canonical_texture','surface','frame','site_index','sampling_policy','coordinate_convention','intrinsic','lod_effect',
            'numeric_domain','explicit_source_cast','equation_phase','value_binding','native_uniform_role','native_mesh_reset_input'}}
        nodes[index]={'op':node.op,'dtype':node.dtype,'args':[visit(arg) for arg in node.args],'detail':detail}
        if node.op.startswith('loop_'):nodes[index]['unresolved_loop_plan']=True
        return index
    try:
        root=visit(field);resources=not any(n['op']=='sample' or n.get('unresolved_loop_plan') for n in nodes)
        return {'root':root,'nodes':nodes,'resources_resolved':resources,
                'complete':resources and not any(n['op'] in {'unknown','uninitialized'} or n.get('unresolved_loop_plan') for n in nodes)}
    except (ValueError,RecursionError):return None


def _typed_control_identity(field,*,required=False):
    expression=_expression(field)
    if expression is None:
        if required:raise ValueError('source phase identity unresolved: control expression export budget exceeded')
        return None
    return _digest(expression)


def _direct_audio(field):
    from effect_families import _strip
    field=_strip(field)
    if field.op=='input':return EEL_AUDIO.get(field.detail.get('name'))
    if field.op=='member' and field.detail.get('swizzle') and len(field.detail.get('field',''))==1:
        parent=_strip(field.args[0]);name=parent.detail.get('name')
        if parent.op=='input' and name in PACKED:
            lane='xyzw'.find(field.detail['field'])
            if lane<0:lane='rgba'.find(field.detail['field'])
            return PACKED[name][lane] if lane>=0 else None
    return None


def _audio_codes(field,analysis):
    from effect_families import _deps
    dependencies=_deps(field)
    reads=_packed_reads(field)
    result={EEL_AUDIO[name] for name in dependencies if name in EEL_AUDIO}
    for name,codes in PACKED.items():
        if name not in dependencies:continue
        for index in reads.get(name,()):result.add(codes[index])
    for bank,letter in enumerate('abcdefgh'):
        if '_q'+letter not in dependencies:continue
        for lane in reads.get('_q'+letter,()):
                value=getattr(analysis,'main',{}).get('q'+str(bank*4+lane+1))
                if value is not None:result.update(EEL_AUDIO[name] for name in _deps(value) if name in EEL_AUDIO)
    for name in dependencies:
        if name.startswith('q') and name[1:].isdigit() and 1<=int(name[1:])<=32:
            main=getattr(analysis,'main',{}).get(name)
            if main is not None:result.update(EEL_AUDIO[name] for name in _deps(main) if name in EEL_AUDIO)
    return sorted(result)


def _routes(control,unit,value,analysis):
    from effect_families import _terms,_walk,_deps
    from source_triggers import switch_triggers
    codes=_audio_codes(value,analysis);result=[];bridges={}
    dependencies=_deps(value)
    reads=_packed_reads(value)
    for bank,letter in enumerate('abcdefgh'):
        if '_q'+letter not in dependencies:continue
        for lane in reads.get('_q'+letter,()):
                name='q'+str(bank*4+lane+1)
                main=getattr(analysis,'main',{}).get(name)
                if main is not None:bridges[name]=_expression(main)
    for name in dependencies:
        if name.startswith('q') and name[1:].isdigit() and 1<=int(name[1:])<=32:
            main=getattr(analysis,'main',{}).get(name)
            if main is not None:bridges[name]=_expression(main)
    q_narrowings=[]
    for node,path in _walk(value):
        name=node.detail.get('native_uniform_role')
        if isinstance(name,str) and name.startswith('q') and name[1:].isdigit() and 1<=int(name[1:])<=32:
            main=getattr(analysis,'main',{}).get(name)
            if main is not None:bridges[name]=_expression(main)
            q_narrowings.append(node)
    for code in codes:
        gain=0.;exact=True
        for coefficient,term in _terms(value):
            dependent=code in _audio_codes(term,analysis)
            if not dependent:continue
            if _direct_audio(term)==code:gain+=coefficient
            else:exact=False
        if any(code in _audio_codes(node,analysis) for node in q_narrowings):exact=False
        from source_control_bounds import scalar_response_envelope
        response_names={name for name,c in EEL_AUDIO.items() if c==code}
        response_names.update(name+'.'+'xyzw'[lane] for name,cs in PACKED.items() for lane,c in enumerate(cs) if c==code)
        response=scalar_response_envelope(value,input_names=response_names)
        result.append({'input_code':code,'control':control,'control_unit':unit,
            'dependency_kind':'source causal control path','linear_gain':gain if exact else None,
            'gain_unit':unit+'/declared audio input unit' if exact else None,
            'expression':_expression(value),'q_bridge_expressions':bridges,
            'has_threshold_or_clamp':any(n.op in {'select','less','greater','less_equal','greater_equal','equal','eel_equal','clamp','saturate','min','max'} for n,p in _walk(value)),
            'switch_triggers':switch_triggers(value,code),
            'nominal_audio_response':response,
            'visible_response_strength':None,
            'conditions':['input domains, source branch and later clipping/composition retain the control change'],
            'limitations':['Control dependency/gain does not establish affected screen area or perceived response magnitude']})
    return result


def _phase_literal(value,depth=0,*,_memo=None):
    """Fold scalar literals while retaining integer conversion semantics."""
    from effect_families import _CACHE
    if _memo is None:
        cache=_CACHE.get()
        _memo={} if cache is None else cache.setdefault('appearance_literals',{})
    key=id(value)
    saved=_memo.get(key)
    if saved is not None and saved[0] is value:return saved[1]
    if depth>64:return None
    if len(_memo)>=65536:raise ValueError('source literal distinct-node budget exceeded')
    result=_phase_literal_uncached(value,depth,_memo)
    _memo[key]=(value,result)
    return result


def _phase_literal_uncached(value,depth,memo):
    if value.op=='constant' and type(value.detail.get('value')) in {int,float}:
        result=float(value.detail['value'])
    elif value.op=='member' and value.detail.get('swizzle') and len(value.detail.get('field',''))==1:
        from effect_families import _parts
        from field_math import SWIZZLE
        value=_canonical_lane(value);parent=value.args[0];lane=SWIZZLE[value.detail['field']]
        if parent.op=='input' or parent.op=='sample':return None
        parts=_parts(parent)
        if lane>=len(parts):return None
        projected=parts[lane]
        if projected.op=='member' and projected.args and projected.args[0] is parent:return None
        result=_phase_literal(projected,depth+1,_memo=memo)
        if result is None:return None
    elif value.op in {'cast','narrow','construct','unary','negate'} and len(value.args)==1:
        result=_phase_literal(value.args[0],depth+1,_memo=memo)
        if result is None:return None
        if value.op=='negate' or value.op=='unary' and value.detail.get('operator')==0:result=-result
        elif value.op=='unary' and value.detail.get('operator')!=1:return None
    elif value.op in {'add','subtract','multiply','divide'} and len(value.args)==2:
        a=_phase_literal(value.args[0],depth+1,_memo=memo);b=_phase_literal(value.args[1],depth+1,_memo=memo)
        if a is None or b is None or value.op=='divide' and b==0:return None
        result={'add':lambda:a+b,'subtract':lambda:a-b,'multiply':lambda:a*b,'divide':lambda:a/b}[value.op]()
    else:return None
    if value.dtype=='float' and (value.op in {'cast','narrow','construct'} or
            value.detail.get('numeric_domain')=='shader-float32'):
        # These are explicit typed shader conversions. Plain EEL constants and
        # arithmetic remain double-valued; do not round every symbolic literal.
        import numpy as np
        with np.errstate(over='ignore',invalid='ignore'):result=float(np.float32(result))
    if not math.isfinite(result):return None
    if value.dtype=='int':
        if not -(2**31)<=result<2**31:return None
        result=float(math.trunc(result))
    elif value.dtype!='float':return None
    return result


def _colour_product(value,depth=0):
    """Retain numeric casts when collecting a common colour multiplier."""
    if depth>64:raise ValueError('source colour product depth exceeded')
    number=_phase_literal(value)
    if number is not None:return number,[]
    if value.op=='multiply' and value.dtype=='float':
        a,af=_colour_product(value.args[0],depth+1);b,bf=_colour_product(value.args[1],depth+1)
        if len(af)+len(bf)>256 or not math.isfinite(a*b):raise ValueError('source colour product budget/nonfinite coefficient')
        return a*b,af+bf
    return 1.,[value]


def _phase_terms(value,scale=1.,depth=0):
    """Split floating affine syntax without erasing quantizing conversions."""
    if depth>64:raise ValueError('source phase normalization depth exceeded')
    terms=None
    if value.dtype=='float':
        if value.op=='negate' or value.op=='unary' and value.detail.get('operator')==0:
            terms=_phase_terms(value.args[0],-scale,depth+1)
        elif value.op in {'add','subtract'}:
            terms=_phase_terms(value.args[0],scale,depth+1)+_phase_terms(value.args[1],
                scale*(-1 if value.op=='subtract' else 1),depth+1)
        elif value.op=='multiply':
            for index in (0,1):
                number=_phase_literal(value.args[index])
                if number is not None:
                    terms=_phase_terms(value.args[1-index],scale*number,depth+1);break
        elif value.op=='divide':
            number=_phase_literal(value.args[1])
            if number not in {None,0}:terms=_phase_terms(value.args[0],scale/number,depth+1)
    if terms is None:terms=[(scale,value)]
    if len(terms)>256 or any(not math.isfinite(c) for c,t in terms):
        raise ValueError('source phase normalization budget/nonfinite coefficient')
    return terms


def _oscillator(value):
    from effect_families import _deps
    bias=0.;osc=None;amplitude=0.
    for coefficient,term in _phase_terms(value):
        number=_phase_literal(term)
        if number is not None:bias+=coefficient*number;continue
        if term.op not in {'sin','cos'} or osc is not None:return None
        osc=term;amplitude=coefficient
    if osc is None or amplitude==0:return None
    # Fully clipped oscillators cannot generate colour diversity at the sink.
    if bias-abs(amplitude)>=1 or bias+abs(amplitude)<=0:return None
    from shader_fields import Field
    offset=-math.pi/2 if osc.op=='sin' else 0.;merged={}
    for coefficient,term in _phase_terms(osc.args[0]):
        number=_phase_literal(term)
        if number is not None:offset+=coefficient*number
        else:
            key=_typed_control_identity(term,required=True);old=merged.get(key,(0.,term))[0]
            merged[key]=(old+coefficient,term)
    merged={key:pair for key,pair in merged.items() if pair[0]!=0}
    if not merged:return None
    if not math.isfinite(offset) or any(not math.isfinite(c) for c,t in merged.values()):
        raise ValueError('source phase normalization nonfinite result')
    # cos(-phase) == cos(phase). Canonicalize orientation after converting
    # sin(phase) to cos(phase-pi/2), retaining its distinct offset.
    orientation=-1 if merged[sorted(merged)[0]][0]<0 else 1
    offset*=orientation;terms=[];variable_terms=[]
    for key,(coefficient,term) in sorted(merged.items()):
        coefficient*=orientation;terms.append((coefficient,key))
        variable_terms.append(term if coefficient==1 else Field('multiply',(Field('constant',detail={'value':coefficient}),term)))
    source_amplitude=amplitude
    if amplitude<0:
        amplitude=-amplitude;offset+=math.pi
    variable=variable_terms[0]
    for term in variable_terms[1:]:variable=Field('add',(variable,term))
    return {'bias':bias,'amplitude':amplitude,'source_amplitude':source_amplitude,
            'offset':offset,'phase_key':tuple(sorted(terms)),
            'variable_phase_expression':variable,'oscillator_function_code':2 if osc.op=='sin' else 1,
            'phase_expression':osc.args[0],
            'phase_dependencies':_deps(osc.args[0])}


def _colour(field,*,allow_shared_multiplier=True):
    from effect_families import _parts,_walk
    from shader_fields import Field
    from shader_fields import uses_input_components
    from source_temporal import oscillator_timing
    field=_data_return(field)
    parts=[_canonical_lane(part) for part in _parts(field)[:3]]
    result={'mode_code':None,'bias_rgb':None,'amplitude_rgb':None,'phase_offsets_rad':None,
        'distinct_channel_phases':None,'constant_rgb':None,'depends_on_time':None,
        'palette_diversity':None,'guaranteed_visible':False,
        'conditions':['selected RGB path, source input domains and later masks/storage retain the colour contribution']}
    values=[_phase_literal(p) for p in parts]
    if len(parts)==3 and all(v is not None for v in values):
        result.update(mode_code=0,constant_rgb=[min(1.,max(0.,v)) for v in values]);return result
    identities=[_typed_control_identity(p) for p in parts]
    if len(parts)==3 and None not in identities and len(set(identities))==1:
        result.update(mode_code=1);return result
    signals=[];gains=[]
    for part in parts:
        terms=[(coefficient,term) for coefficient,term in _phase_terms(part) if _phase_literal(term)!=0]
        if len(terms)!=1 or _phase_literal(terms[0][1]) is not None:break
        gain,signal=terms[0]
        if gain<=0:break
        identity=_typed_control_identity(signal)
        if identity is None:break
        gains.append(gain);signals.append(identity)
    if len(signals)==3 and len(set(signals))==1:
        result.update(mode_code=2,tint_rgb=gains)
        result['conditions'].append('fixed chromaticity requires a nonsaturating nonnegative signal domain')
        return result
    if allow_shared_multiplier and len(parts)==3:
        products=[_colour_product(part) for part in parts]
        common=set(_typed_control_identity(factor) for factor in products[0][1])
        for coefficient,factors in products[1:]:common&={_typed_control_identity(factor) for factor in factors}
        common.discard(None)
        if common:
            if any(_typed_control_identity(factor) in common and _colour_number(factor)==0 for factor in products[0][1]):
                result.update(mode_code=0,constant_rgb=[0.,0.,0.]);return result
            reduced=[];multipliers=[]
            for index,(coefficient,factors) in enumerate(products):
                remaining=[]
                for factor in factors:
                    if _typed_control_identity(factor) in common:
                        if index==0:multipliers.append(factor)
                    else:remaining.append(factor)
                lane=Field('constant',detail={'value':coefficient})
                for factor in remaining:lane=Field('multiply',(lane,factor))
                reduced.append(lane)
            inner=_colour(Field('components',tuple(reduced),'float3'),allow_shared_multiplier=False)
            if inner['mode_code'] in {3,5}:
                inner['shared_multiplier_expressions']=[_expression(factor) for factor in multipliers]
                inner['conditions'].append('shared spatial/feedback multiplier keeps the generated palette visible')
                return inner
    try:oscillators=[_oscillator(p) for p in parts]
    except ValueError as error:
        result['unknown_reasons']=[str(error)]
        oscillators=[]
    if len(oscillators)==3 and all(o is not None for o in oscillators) and len({o['phase_key'] for o in oscillators})==1:
        offsets=[o['offset'] for o in oscillators]
        distinct=[]
        for offset in offsets:
            if not any(abs(math.remainder(offset-old,math.tau))<1e-6 for old in distinct):distinct.append(offset)
        if len(distinct)>1:
            result.update(mode_code=3,bias_rgb=[o['bias'] for o in oscillators],
                amplitude_rgb=[o['amplitude'] for o in oscillators],phase_offsets_rad=offsets,
                distinct_channel_phases=len(distinct),
                common_phase_expression=_expression(oscillators[0]['variable_phase_expression']),
                temporal=oscillator_timing(oscillators),
                depends_on_time=int(any(uses_input_components(o['phase_expression'],'_c2',{0}) or
                                       bool(o['phase_dependencies']&{'time',':native-render-time-f32'}) for o in oscillators)))
            result['conditions'].append('the common phase varies sufficiently; coefficients/phases are source forms, not a measured hue histogram')
            return result
    if len(oscillators)==3 and all(o is not None for o in oscillators) and len({o['phase_key'] for o in oscillators})>1:
        result.update(mode_code=5,bias_rgb=[o['bias'] for o in oscillators],
            amplitude_rgb=[o['source_amplitude'] for o in oscillators],phase_offsets_rad=[o['offset'] for o in oscillators],
            channel_phase_expressions=[_expression(o['phase_expression']) for o in oscillators],
            oscillator_function_codes=[o['oscillator_function_code'] for o in oscillators],
            temporal=oscillator_timing(oscillators),
            depends_on_time=int(any(uses_input_components(o['phase_expression'],'_c2',{0}) or
                                   bool(o['phase_dependencies']&{'time',':native-render-time-f32'}) for o in oscillators)))
        result['conditions'].append('independent channel phases vary; no common cycle period or measured colour diversity established')
        return result
    if any(n.op=='sample' for n,p in _walk(field)):
        result['mode_code']=4
        result['conditions'].append('actual palette depends on sampled image/feedback contents')
    return result


def appearance_from_analysis(analysis):
    from effect_families import _parts,_number,_walk
    from source_motion import motion_control,planar_trajectory,shape_vertex_motion
    from source_composition import composition_from_analysis
    from source_sampling import sampling_geometry
    from source_feedback import feedback_transfer
    from source_colour_processing import colour_processing
    from source_colour_mix import texture_colour_transfer
    from source_hue import composite_hue_recipe
    from source_waveform import waveform_recipe,consumed_wave_controls
    elements={}
    for family in analysis.families:
        identity=family['component'] or ('mesh_warp' if family['stage']=='mesh_warp' else 'shader_'+family['stage'])
        element=elements.setdefault(identity,{'id':identity,'stage':family['stage'],'family_codes':[],
            'mechanisms':[],'parameters':{},'colour':None,'audio_routes':[],
            'approximate_screen_coverage':None,'conditions':[],'evidence':[]})
        if family['stage']=='mesh_warp':element['legacy_ids']=['shader_mesh_warp']
        code=FAMILY_CODES.get(family['mechanism'])
        if code is not None and code not in element['family_codes']:element['family_codes'].append(code)
        element['mechanisms'].append(family['mechanism'])
        if family['mechanism'] in {'periodic_radial_glow','spatial_oscillatory_bands'}:
            element.setdefault('procedural_forms',[]).append(family['parameters'])
        else:element['parameters'].update(family['parameters'])
        element['conditions'].extend(family['conditions']);element['evidence'].extend(family['evidence'])
    for stage,field in analysis.outputs.items():
        composite=analysis.outputs.get('composite')
        if stage=='warp' and composite is not None and not any(
                n.op=='sample' and n.detail.get('canonical_texture') in {'main','blur1','blur2','blur3'}
                for n,p in _walk(composite)):continue
        identity='shader_'+stage
        element=elements.setdefault(identity,{'id':identity,'stage':stage,'family_codes':[],'mechanisms':[],
            'parameters':{},'colour':None,'audio_routes':[],'approximate_screen_coverage':None,'conditions':[],'evidence':[]})
        element['colour']=_colour(field)
        if stage=='composite':
            hue=composite_hue_recipe(field)
            if hue is not None:
                element['native_colour_generators']=[hue]
        for channel,value in zip('rgb',_parts(_data_return(field))[:3]):element['audio_routes']+=_routes('colour_'+channel,'encoded RGB component',value,analysis)
    for identity,controls in getattr(analysis,'component_controls',{}).items():
        if identity not in elements:continue #later composite disconnected this drawing
        from source_geometry import shape_geometry,shape_audio_area_response
        from source_material import shape_material,shape_fill_contribution
        elements[identity]['geometry']=shape_geometry(controls,elements[identity]['parameters']['instances'])
        elements[identity]['material']=shape_material(controls,analysis.values.get('shapecode_'+identity.removeprefix('shape_')+'_image',''))
        from source_material_temporal import shape_material_temporal
        elements[identity]['material_temporal']=shape_material_temporal(controls)
        if getattr(analysis,'input_scenario',None) is not None:
            from source_material_temporal import shape_scenario_material_envelope
            elements[identity]['scenario_material_envelope']=shape_scenario_material_envelope(controls,analysis.input_scenario)
        elements[identity]['fill_contribution']=shape_fill_contribution(elements[identity]['geometry'],elements[identity]['material'])
        from source_fill_envelopes import shape_fill_envelope
        elements[identity]['fill_envelope']=shape_fill_envelope(controls,elements[identity]['geometry'],elements[identity]['material'],elements[identity]['material_temporal'])
        elements[identity]['audio_area_response']=shape_audio_area_response(controls,elements[identity]['geometry'],elements[identity]['fill_contribution'])
        elements[identity]['center_trajectory']=planar_trajectory([controls['x'],controls['y']])
        from source_shape_audio_motion import shape_audio_center_response
        elements[identity]['audio_center_response']=shape_audio_center_response(controls,input_scenario=getattr(analysis,'input_scenario',None))
        elements[identity]['vertex_motion']=shape_vertex_motion(controls,elements[identity]['geometry'],elements[identity]['center_trajectory'])
        from effect_families import _deps
        if any('instance' in _deps(controls[name]) for name in ('x','y','rad','ang','sides')):
            from source_instances import shape_instance_motion
            elements[identity]['instance_motion']=shape_instance_motion(controls,elements[identity]['parameters']['instances'])
        elements[identity]['motion_controls']=[motion_control(controls[name],*SHAPE_CONTROLS[name],
            application='shape geometry parameter',input_scenario=getattr(analysis,'input_scenario',None)) for name in ('x','y','rad','ang') if name in controls]
        for name,(control,unit) in SHAPE_CONTROLS.items():
            if name in controls:
                material=elements[identity]['material']
                if name in {'tex_zoom','tex_ang'} and material['texture']['role']=='untextured_vertex_gradient':continue
                if name in {'border_r','border_g','border_b'} and material['border_draw_enabled'] is False:continue
                value=controls[name];elements[identity]['parameters'][name]=_number(value)
                elements[identity]['audio_routes']+=_routes(control,unit,value,analysis)
    from shader_fields import uses_input_components
    warp=analysis.outputs.get('warp');composite=analysis.outputs.get('composite')
    consumes_mesh=warp is None or uses_input_components(warp,'_uv',{0,1})
    consumes_feedback=composite is None or any(n.op=='sample' and
        n.detail.get('canonical_texture') in {'main','blur1','blur2','blur3'} for n,p in _walk(composite))
    if consumes_mesh and consumes_feedback:
        routes=[];parameters={};motion=[]
        for name,(control,unit) in MESH_CONTROLS.items():
            value=getattr(analysis,'mesh_controls',{}).get(name)
            if value is not None:
                routes+=_routes(control,unit,value,analysis);parameters[name]=_number(value)
                motion.append(motion_control(value,control,unit,application='feedback sampling transform each step',input_scenario=getattr(analysis,'input_scenario',None)))
        neutral={'zoom':1,'radial_zoom':1,'scale_x':1,'scale_y':1,'rotation':0,'translation_x':0,'translation_y':0,'deformation':0}
        if routes or any(r['curve_kind']!='constant' or r['constant_value']!=neutral[r['control']] for r in motion):
            element=elements.setdefault('mesh_warp',{'id':'mesh_warp','stage':'mesh_warp','family_codes':[8],
                'mechanisms':[],'parameters':{},'colour':None,'audio_routes':[],
                'approximate_screen_coverage':None,'conditions':[],'evidence':[]})
            element['parameters'].update(parameters)
            element['mechanisms'].append('native_feedback_transform_controls')
            element['audio_routes']=routes;element['motion_controls']=motion
            element['conditions']+=['active warp consumes transformed UV and final composite retains feedback',
                                  'feedback contains visible texture; sampling-map motion is not a screen-speed measurement']
            element['evidence']+=[analysis.evidence(prefix,'source native feedback controls retain source curves','output')
                                 for prefix in ['per_frame_','per_pixel_']]
    if 'builtin_wave' in elements:
        elements['builtin_wave']['waveform_recipe']=waveform_recipe(analysis)
        from source_wave_material import wave_material
        elements['builtin_wave']['wave_material']=wave_material(analysis,elements['builtin_wave']['waveform_recipe'])
        for name,unit in [('wave_mode','native waveform mode'),('wave_x','native waveform position control'),
                          ('wave_y','native waveform position/separation control'),('wave_mystery','native mode-specific mystery control'),
                          ('wave_a','source opacity'),('wave_r','encoded RGB component'),('wave_g','encoded RGB component'),('wave_b','encoded RGB component')]:
            if name in consumed_wave_controls(elements['builtin_wave']['waveform_recipe']['effective_mode']):
                routes=_routes(name,unit,analysis.main[name],analysis)
                for route in routes:route['conditions'].append('selected native waveform mode consumes this authored control')
                elements['builtin_wave']['audio_routes']+=routes
    for element in elements.values():
        if element['colour'] is None:element['colour']={'mode_code':None,'palette_diversity':None,'constant_rgb':None,'guaranteed_visible':False}
        element['conditions']=list(dict.fromkeys(element['conditions']))
    final_colour=elements.get('shader_composite',{}).get('colour') or {}
    palette_candidate=final_colour.get('mode_code') in {3,5}
    if final_colour.get('mode_code')==4:
        palette_candidate=any(e['colour'].get('mode_code') in {3,5} for e in elements.values())
    psychedelic=any(7 in e['family_codes'] for e in elements.values()) and palette_candidate
    feedback=feedback_transfer(analysis)
    from source_feedback_envelopes import feedback_envelope
    from source_native_warp import native_warp_recipe
    from source_warp_transport import native_warp_transport
    from source_radial_zoom import native_radial_zoom
    from source_warp_displacement import native_warp_displacement
    transport=native_warp_transport(analysis,consumed=consumes_mesh and consumes_feedback)
    radial=native_radial_zoom(transport)
    texture_transfer=texture_colour_transfer(analysis,feedback['vertex_colour_binding']['rgba'])
    displacement=native_warp_displacement(analysis,transport,radial_zoom=radial)
    from source_spatial_displacement import spatial_displacement
    from source_texture_envelopes import texture_colour_envelopes
    from source_nonlinear_colour import nonlinear_texture_colour_bounds
    result={'schema_version':1,'policy':POLICY,'status':'conditional source description',
        'elements':list(elements.values()),'composition':composition_from_analysis(analysis,elements),
        'feedback_transfer':feedback,
        'feedback_envelope':feedback_envelope(analysis),
        'native_warp_recipe':native_warp_recipe(analysis,consumed=consumes_mesh and consumes_feedback),
        'native_warp_transport':transport,
        'native_radial_zoom':radial,
        'native_warp_displacement':displacement,
        'native_spatial_displacement':spatial_displacement(analysis,displacement),
        'native_input_bindings':getattr(analysis,'native_input_bindings',{}),
        'sampling_geometry':sampling_geometry(analysis),
        'colour_processing':colour_processing(analysis),
        'texture_colour_transfer':texture_transfer,
        'texture_colour_envelopes':texture_colour_envelopes(texture_transfer),
        'nonlinear_texture_colour_bounds':nonlinear_texture_colour_bounds(analysis,feedback['vertex_colour_binding']['rgba']),
        'stage_programs':_stage_programs(analysis),
        'execution_unknowns':list(analysis.unknowns),
        'uses_rendered_images':False,'uses_shader_execution':False,
        'uses_equation_execution':False,'appearance_match_accuracy':None,
        'activity':{'flashing':{'value':None,'status':'unknown'},'motion_intensity':{'value':None,'status':'unknown'}},
        'mood_matches':{'chill':{'eligible':None},'psychedelic':{'candidate':True if psychedelic else None,'confidence':None}},
        'limitations':['Forms and controls are contributing source constructions, not dominant-frame/coverage estimates',
                       'Source phase palette does not establish rendered colour diversity or flash permission',
                       'Unknown activity cannot be promoted to a confident Chill preference match',
                       'Audio inputs are engine bands/attenuated bands/volume, not isolated instruments or vocals']}
    from source_activity import source_activity
    result['activity']=source_activity(analysis,result)
    from source_feedback_sensitivity import feedback_colour_sensitivity
    result['feedback_colour_sensitivity']=feedback_colour_sensitivity(result,
        warp_contains_clip=analysis.stages['warp'].get('source_contains_clip',False))
    from source_static_behaviour import static_behaviour
    result['static_behaviour']=static_behaviour(analysis,result,getattr(analysis,'behaviour_context',None))
    result['record_sha256']=_digest(result)
    return result
