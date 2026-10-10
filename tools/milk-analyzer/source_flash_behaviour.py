"""Local nominal brightness changes, separate from displayed flash/coverage.

RGB infinity-norm bounds include smooth changes, not just source switch sites.
They are conditional partial time responses: audio/state/sample history are not
invented time trajectories. Source schedules never become observed event rates.
"""
import math

POLICY = 'source-local-brightness-behaviour-v1'
TIME_NAMES = {'time', ':native-render-time-f32', '_c2.x'}
PREMISES = [
    'Nominal source time advances continuously; audio, private state, sample values and geometry held fixed',
    'Relevant inputs/intermediates are finite; original phase, conversion and numeric-domain guards remain authoritative',
    'RGB infinity-norm ceiling before later passes/storage; lower bound zero does not assert an attained transition',
    'No affected area, guaranteed visible contrast, frame sequence, native byte parity or displayed flash frequency inferred',
    'Feedback sampling can miss/alias source events; native clock wrapping and floating-point steps remain separate',
]


def _maximum(values):
    return None if not values or any(v is None for v in values) else max(values)


def _delta(spans):
    if not spans or any(s is None for s in spans):return None
    differences = [s[1]-s[0] for s in spans]
    if not all(math.isfinite(v) and v >= 0 for v in differences):return None
    maximum = max(differences)
    return [0., math.nextafter(maximum, math.inf) if maximum else 0.]


def _record(identity, stage, part, kind):
    return {'component_id':identity, 'stage':stage, 'part':part, 'kind':kind,
            'brightness_metric':'local_RGB_infinity_norm',
            'maximum_brightness_change_per_second':None, 'brightness_delta_range':None,
            'brightness_value_range':None, 'periodic_contrast_range':None,
            'event_rate_hz':None, 'cycle_rate_hz':None, 'event_schedules':[],
            'nominal_continuity':'unknown', 'total_brightness_rate_known':False,
            'certainty':'unknown', 'unknown_reasons':[], 'premises':list(PREMISES),
            'native_numeric_certified':False, 'visible_flashing_verified':False,
            'source_evidence':{}}


def _deduplicate_schedules(events):
    """Identical RGB sites are one schedule; do not sum distinct schedules."""
    from source_appearance import _digest
    schedules = {}
    for event in events:
        key = _digest({k:v for k,v in event.items() if k not in
                       {'source_graph_path','absolute_control_jump','control_true_value','control_false_value','scope'}})
        schedules.setdefault(key, event)
    return list(schedules.values())


def _project_uniform_lanes(field):
    """Bind plain packed scalar lanes; never erase phase/conversion metadata."""
    from shader_fields import Field
    from field_math import SWIZZLE
    memo={}
    def visit(node,depth=0):
        if id(node) in memo:return memo[id(node)]
        if depth>64 or len(memo)>=512:raise ValueError('packed brightness projection budget exceeded')
        result=node
        if node.op=='member' and node.dtype=='float' and set(node.detail)=={'field','swizzle'} and node.detail['swizzle'] and len(node.detail['field'])==1:
            parent=node.args[0];lane=SWIZZLE.get(node.detail['field'])
            if parent.op=='input' and parent.dtype in {'float2','float3','float4'} and set(parent.detail)=={'name'} and lane is not None and lane<int(parent.dtype[-1]):
                result=Field('input',dtype='float',detail={'name':parent.detail['name']+'.'+'xyzw'[lane]})
        if result is node and node.op not in {'sample','input','unknown','uninitialized'}:
            result=Field(node.op,tuple(visit(a,depth+1) for a in node.args),node.dtype,node.detail)
        memo[id(node)]=result;return result
    return visit(field)


def _prune_predicates(field, domains, rejected, identity):
    """Prune only supported nominal predicates; report native query separately."""
    from shader_fields import Field
    from source_control_bounds import scalar_value_envelope
    from source_proofs import predicate_evidence
    memo = {}
    active = set()

    def visit(node, depth=0):
        key = id(node)
        if key in memo:return memo[key]
        if depth > 64 or len(memo)+len(active) >= 512 or key in active:
            raise ValueError('brightness predicate traversal budget exceeded')
        active.add(key)
        try:
            # Do not reconstruct sampled-coordinate or persistent-state programs.
            if node.op in {'sample','input','unknown','uninitialized'}:
                result = node
            elif node.op=='cast' and node.dtype=='float' and len(node.args)==1 and node.args[0].dtype=='bool':
                proxy=Field('select',(node.args[0],Field('constant',dtype='float',detail={'value':1.}),Field('constant',dtype='float',detail={'value':0.})),'float')
                selected=visit(proxy,depth+1)
                result=selected if selected.op=='constant' else node
            elif node.op == 'select' and len(node.args) == 3:
                predicate = node.args[0]
                if predicate.dtype=='float' and predicate.op in {'greater','less','greater_equal','less_equal','equal','not_equal'} and not predicate.detail:
                    predicate=Field(predicate.op,predicate.args,'bool',predicate.detail)
                nominal = predicate_evidence(predicate, input_domains=domains)
                truth = None if nominal is None else nominal.get('truth_value')
                envelope = None
                if truth is None:
                    envelope = scalar_value_envelope(predicate, input_domains=domains)
                    span = envelope['nominal_value_range']
                    if span == [0.,0.]:truth = False
                    elif span == [1.,1.]:truth = True
                    elif predicate.op in {'greater','less','greater_equal','less_equal'} and len(predicate.args)==2:
                        operands=[scalar_value_envelope(a,input_domains=domains) for a in predicate.args]
                        a,b=[r['nominal_value_range'] for r in operands]
                        if a is not None and b is not None:
                            envelope['comparison_operand_envelopes']=operands
                            if predicate.op=='greater':
                                if a[1]<=b[0]:truth=False
                                elif a[0]>b[1]:truth=True
                            elif predicate.op=='less':
                                if a[0]>=b[1]:truth=False
                                elif a[1]<b[0]:truth=True
                            elif predicate.op=='greater_equal':
                                if a[1]<b[0]:truth=False
                                elif a[0]>=b[1]:truth=True
                            elif predicate.op=='less_equal':
                                if a[0]>b[1]:truth=False
                                elif a[1]<=b[0]:truth=True
                if truth is not None:
                    native = predicate_evidence(predicate, input_domains=domains,
                                                numeric_model='ieee754-binary32-rne')
                    # A known native disagreement must not inherit nominal pruning.
                    if native is not None and native.get('truth_value') is not None and native['truth_value'] != truth:
                        rejected.append({'component_id':identity,'rejection_applied':False,
                            'nominal_proof':nominal,'native_expression_proof':native,
                            'native_numeric_certified':False,'reason':'nominal/native expression predicate disagreement; both branches retained'})
                        result = Field(node.op, tuple(visit(a,depth+1) for a in node.args), node.dtype, node.detail)
                    else:
                        rejected.append({'component_id':identity,'selected_branch':bool(truth),'rejection_applied':True,
                            'nominal_proof':nominal,'nominal_envelope':envelope,'native_expression_proof':native,
                            'native_numeric_certified':False,'reason':'unreachable branch in qualified nominal input domain'})
                        result = visit(node.args[1 if truth else 2], depth+1)
                else:
                    result = Field(node.op, tuple(visit(a,depth+1) for a in node.args), node.dtype, node.detail)
            else:
                result = Field(node.op, tuple(visit(a,depth+1) for a in node.args), node.dtype, node.detail)
        finally:active.remove(key)
        memo[key] = result
        return result
    return visit(field)


def _direct_colour_nodes(field):
    """Visit colour algebra without traversing sampled-coordinate programs."""
    stack=[(field,0)];seen=set()
    while stack:
        node,depth=stack.pop()
        if id(node) in seen:continue
        if depth>64 or len(seen)>=512:raise ValueError('direct brightness traversal budget exceeded')
        seen.add(id(node));yield node
        if node.op!='sample':stack.extend((a,depth+1) for a in node.args)


def _fixed_sample_expression(field):
    from shader_fields import Field
    memo={}
    def visit(node,depth=0):
        if id(node) in memo:return memo[id(node)]
        if depth>64 or len(memo)>=512:raise ValueError('fixed-sample brightness traversal budget exceeded')
        if node.op=='input' and node.detail=={'name':'_c2.x'}:
            result=Field('member',(Field('input',dtype='float4',detail={'name':'_c2'}),),'float',{'field':'x','swizzle':True})
        else:
            result=(Field('sample',(),node.dtype,node.detail) if node.op=='sample' else
                    Field(node.op,tuple(visit(a,depth+1) for a in node.args),node.dtype,node.detail))
        memo[id(node)]=result;return result
    return visit(field)


def _smooth_frequencies(fields):
    from source_motion import motion_control
    frequencies = set()
    for field in fields:
        candidates=[field]+[n for n in _direct_colour_nodes(field) if n.op in {'sin','cos'}]
        for candidate in candidates:
            curve = motion_control(_fixed_sample_expression(candidate),'brightness','RGB',application='local source colour',_include_switch_events=False)
            if curve['curve_kind'] == 'sinusoidal_time' and curve['amplitude_value'] != 0:
                frequencies.add(curve['frequency_hz'])
    return next(iter(frequencies)) if len(frequencies) == 1 else None


def _shader_record(analysis, description, stage, field, domains, rejected):
    from source_activity import blackout_colour_channels
    from source_control_bounds import scalar_response_envelope, scalar_value_envelope, merge_continuity
    from source_time_switches import time_switch_events
    from effect_families import _walk
    row = _record('shader_'+stage,stage,'RGB','shader_brightness_change')
    channels = [_prune_predicates(_project_uniform_lanes(c),domains,rejected,row['component_id']) for c in blackout_colour_channels(field)]
    responses = [scalar_response_envelope(c,input_names=TIME_NAMES,input_domains=domains) for c in channels]
    values = [scalar_value_envelope(c,input_domains=domains) for c in channels]
    row['maximum_brightness_change_per_second'] = _maximum([c['maximum_absolute_control_change_per_audio_unit'] for c in responses])
    row['brightness_delta_range'] = _delta([c['nominal_value_range'] for c in values])
    row['nominal_continuity'] = merge_continuity([c['nominal_continuity'] for c in responses])
    row['source_evidence'] = {'channel_responses':responses,'channel_value_envelopes':values}
    if callable(getattr(analysis,'evidence',None)):
        section='comp_' if stage=='composite' else 'warp_'
        row['contributing_code_paths']=[analysis.evidence(section,'local brightness source-time response','output.RGB')]
    spans=[c['nominal_value_range'] for c in values]
    row['brightness_value_range'] = None if any(s is None for s in spans) else [min(s[0] for s in spans),max(s[1] for s in spans)]
    from source_motion import motion_control
    curves=[motion_control(_fixed_sample_expression(c),'brightness','RGB',application='local source colour',_include_switch_events=False) for c in channels]
    if all(c['curve_kind'] in {'constant','sinusoidal_time'} for c in curves) and any(c['curve_kind']=='sinusoidal_time' for c in curves):
        contrast=max(2*abs(c['amplitude_value']) if c['curve_kind']=='sinusoidal_time' else 0. for c in curves)
        row['periodic_contrast_range']=[contrast,contrast]
        row['premises'].append('Pure uniform RGB sinusoid traverses a complete nominal period; contrast is attainable in source algebra, not certified display pixels')
    row['cycle_rate_hz'] = _smooth_frequencies(channels)
    row['event_schedules'] = _deduplicate_schedules([e for c in channels for e in time_switch_events(_fixed_sample_expression(c))])
    if len(row['event_schedules']) == 1:
        row['event_rate_hz'] = row['event_schedules'][0]['nominal_event_rate_hz']
    elif len(row['event_schedules']) > 1:
        row['unknown_reasons'].append('simultaneous or interleaved source events unresolved; channel schedule rates are not summed')
    names = set().union(*(set(c['assumed_finite_input_names']) for c in responses))
    other = names-TIME_NAMES
    if other:
        row['unknown_reasons'].append('audio/state/input time trajectories unresolved: '+', '.join(sorted(other)))
    samples = any(n.op=='sample' for c in channels for n,path in _walk(c))
    from effect_families import _deps
    dependencies=set().union(*(_deps(c) for c in channels))
    row['uniform_rgb_over_viewport']=dependencies<=TIME_NAMES and not samples
    clocks=dependencies&TIME_NAMES
    row['periodic_attainment']={'scope':'nominal complete-cycle contrast within a declared clock interval',
        'clock_input':next(iter(clocks)) if len(clocks)==1 else None,
        'complete_cycle_in_declared_interval':False,
        'actual_clock_trajectory_verified':False}
    if row['uniform_rgb_over_viewport'] and len(clocks)==1 and row['cycle_rate_hz'] not in (None,0):
        interval=domains.get(next(iter(clocks)))
        period=1/row['cycle_rate_hz']
        row['periodic_attainment'].update(period_seconds=period,declared_clock_interval=interval)
        if interval is not None:
            row['periodic_attainment']['complete_cycle_in_declared_interval']=interval[1]-interval[0]>=period
    if samples:
        row['unknown_reasons'].append('sampled texture/history changes and lookup transport are separate from direct colour response')
        # Reuse the qualified original sample replacement/domain calculus. Never
        # invent sample RGB domains or erase coordinate/native-upload guards here.
        model = description.get('nonlinear_texture_colour_bounds',{}).get('stages',{}).get(stage,{})
        if model:
            conditional = model.get('scenario_colour_envelope') if domains else None
            model = conditional or model
            direct = model.get('direct_colour_time_response',{}).get('channels',[])
            if len(direct)==3:
                row['maximum_brightness_change_per_second'] = _maximum([c['maximum_absolute_rgb_rate_per_source_second'] for c in direct])
                row['nominal_continuity'] = merge_continuity([c['nominal_continuity'] for c in direct])
                row['source_evidence']['qualified_fixed_sample_response'] = direct
            row['brightness_delta_range'] = _delta(model.get('raw_rgb_bounds_if_samples_unit_interval',[]))
            row['source_evidence']['sample_domain_assumptions'] = model.get('conditions',[])
    if row['maximum_brightness_change_per_second'] is None:
        row['unknown_reasons'].append('no finite supported continuous brightness rate; discontinuity/domain/native conversion remains unresolved')
    if row['brightness_delta_range'] is None:
        row['unknown_reasons'].append('local brightness two-state range unresolved')
    row['total_brightness_rate_known'] = not other and not samples and row['maximum_brightness_change_per_second'] is not None
    row['certainty'] = 'conditional_nominal_bound' if row['brightness_delta_range'] is not None else 'unknown'
    return row


def _fixed_unit_texture_material_partial(element):
    """Bound vertex-material modulation with one fixed unit-RGBA sample.

    Texture multiplication cannot increase the incoming rate/difference bound.
    Over blending additionally needs the destination term: even RGB texture0
    can make changing alpha alter destination1. It must not inherit an
    untextured positive-colour lower bound as its contrast against destination.
    """
    from source_shape_activity import shape_activity, _sum_products
    from source_shape_jump_bounds import shape_material_jump_bounds
    from source_fill_envelopes import native_channel_envelope
    from source_appearance import _digest
    material=element['material'];texture=material['texture']
    channels=element['material_temporal']['channels']
    names=('r','g','b','a','r2','g2','b2','a2')
    result={'policy':'source-fixed-unit-texture-material-modulation-v1',
        'component_id':element['id'],'part':'fill','brightness_metric':'local_RGB_infinity_norm',
        'maximum_brightness_change_per_second':None,'brightness_delta_range':None,
        'nominal_continuity':'unknown','total_brightness_rate_known':False,
        'texture_history_change_rate':None,'sampling_coordinate_response_included':False,
        'declared_texture_rgba_domain':[[0.,1.] for _ in range(4)],
        'texture_role':texture['role'],'requested_texture_name':texture.get('requested_name'),
        'texture_binding_verified':texture.get('actual_binding_verified') is True,
        'native_numeric_certified':False,'visible_flashing_verified':False,
        'unknown_reasons':[], 'source_evidence':{},
        'premises':['Sampled texture RGBA is fixed at the source site and each lane lies in[0,1]',
            'Geometry, barycentric position, lookup coordinates, texture selection/style and destination RGB in[0,1] are fixed',
            'Only vertex colour/alpha source-time modulation varies; other audio/state inputs hold fixed',
            'All contributing vertex channels and native conversions remain finite; existing modulo/blend/domain guards apply',
            'Texture motion/history, unknown asset contents, native quantization, later composition and display visibility are excluded',
            'A positive partial ceiling is not an attained change, an observed flash or a whole-preset flash-absence certificate']}
    invalid=[name for name in names if channels[name]['native_float32_endpoint_domain'] is None]
    if invalid:
        result['unknown_reasons'].append('native material endpoint domain unresolved: '+', '.join(invalid))
        result['source_evidence']['unresolved_channel_domains']=invalid
        result['record_sha256']=_digest(result)
        return result
    # Invoke the existing untextured supremum: fixed texture factors<=1 cannot
    # amplify vertex material partials. Keep temporal channels unchanged.
    proxy={**element,'material':{**material,'texture':{**texture,'role':'untextured_vertex_gradient'}}}
    changes,_=shape_activity(proxy)
    change=next((row for row in changes if row['part']=='fill'),None)
    additive={**proxy,'material':{**proxy['material'],'blend_mode':'source_alpha_additive'}}
    jumps=shape_material_jump_bounds(additive)
    jump=next((row for row in jumps if row['part']=='fill'),None)
    blend=material['blend_mode']
    if blend not in {'source_alpha_additive','source_alpha_over'}:
        result['unknown_reasons'].append('native blend mode is unresolved')
    else:
        if change is not None:
            result['maximum_brightness_change_per_second']=_maximum(change['maximum_blended_rgb_rate_per_second'])
            result['unknown_reasons'].extend(change['unknown_reasons'])
            result['source_evidence']['maximum_incoming_rgb_rate_per_second']=change['maximum_incoming_rgb_rate_per_second']
            result['source_evidence']['maximum_blended_rgb_rate_per_second']=change['maximum_blended_rgb_rate_per_second']
            result['source_evidence']['rate_conditions']=[c for c in change['conditions'] if not c.startswith('Fill requires untextured')]
        if jump is not None:
            differences=jump['maximum_incoming_rgb_difference']
            result['unknown_reasons'].extend(jump['unknown_reasons'])
            alpha=[native_channel_envelope(channels[name]) for name in ('a','a2')]
            alpha_difference=None if any(span is None for span in alpha) else min(1.,max(span[1]-span[0] for span in alpha))
            if blend=='source_alpha_over':
                differences=[None if delta is None or alpha_difference is None else _sum_products(1.,delta,1.,alpha_difference) for delta in differences]
            maximum=_maximum(differences)
            result['brightness_delta_range']=None if maximum is None else [0.,maximum]
            result['source_evidence'].update(maximum_incoming_rgb_difference=jump['maximum_incoming_rgb_difference'],
                maximum_blended_rgb_difference=differences,maximum_clamped_alpha_difference=alpha_difference,
                difference_formula='incoming difference + alpha difference * fixed destination ceiling1' if blend=='source_alpha_over' else 'incoming alpha*RGB difference',
                difference_conditions=[c for c in jump['conditions'] if not c.startswith('Untextured source RGB')],
                incoming_supremum_reduction='Fixed texture RGBA factors in[0,1] cannot amplify the delegated untextured incoming partial')
    if result['maximum_brightness_change_per_second'] is not None:
        result['nominal_continuity']='piecewise_lipschitz' # Clamped textured alpha can introduce finite-rate kinks.
    else:result['unknown_reasons'].append('material partial time rate lacks a finite supported stable-modulo bound')
    if result['brightness_delta_range'] is None:result['unknown_reasons'].append('fixed-texture material difference remains unresolved')
    result['unknown_reasons']=sorted(set(result['unknown_reasons']))
    result['source_evidence']['delegated_calculus']=['source_shape_activity.shape_activity','source_shape_jump_bounds.shape_material_jump_bounds']
    result['record_sha256']=_digest(result)
    return result


def _shape_records(analysis, element, domains, rejected):
    from source_shape_activity import shape_activity
    from source_shape_jump_bounds import shape_material_jump_bounds
    from source_time_switches import time_switch_events
    controls = getattr(analysis,'component_controls',{}).get(element['id'],{})
    start=len(rejected)
    pruned={name:_prune_predicates(value,domains,rejected,element['id']) for name,value in controls.items() if name in element['material_temporal']['channels']}
    if len(rejected)>start:
        from source_material_temporal import shape_material_temporal
        controls={**controls,**pruned}
        element={**element,'material_temporal':shape_material_temporal(controls)}
    from source_symbolic import active_identity
    refinements={}
    local_element=element
    if active_identity() is not None:
        from source_control_bounds import scalar_response_envelope
        temporal=element['material_temporal']
        qualified_channels=dict(temporal['channels'])
        for name,channel in temporal['channels'].items():
            prior=channel['raw_time_curve']['maximum_absolute_control_rate_per_second']
            if name not in controls or prior is None or prior==0 or channel['possible_native_wrap_jump'] is not False:continue
            response=scalar_response_envelope(controls[name],input_names=TIME_NAMES)
            refinements[name]=response
            rate=response['maximum_absolute_control_change_per_audio_unit']
            if rate is not None and rate<prior:
                qualified_channels[name]={**channel,'raw_time_curve':{**channel['raw_time_curve'],'maximum_absolute_control_rate_per_second':rate}}
        local_element={**element,'material_temporal':{**temporal,'channels':qualified_channels}}
    changes, hazards = shape_activity(local_element)
    jumps = {r['part']:r for r in shape_material_jump_bounds(element)}
    rows = []
    for part,names in [('fill',('r','g','b','a','r2','g2','b2','a2')),
                       ('border',('border_r','border_g','border_b','border_a'))]:
        row = _record(element['id'],element['stage'],part,'shape_material_brightness_change')
        row['contributing_code_paths']=element.get('evidence',[])
        row['source_evidence']['qualified_material_hazards']=hazards
        if part=='fill' and element['material']['texture']['role']!='untextured_vertex_gradient':
            row['fixed_unit_texture_material_partial']=_fixed_unit_texture_material_partial(local_element)
        channels = element['material_temporal']['channels']
        transparent = not any(channels[n]['may_be_consumed'] for n in names)
        change = next((r for r in changes if r['part']==part),None)
        jump = jumps.get(part)
        if transparent:
            row.update(maximum_brightness_change_per_second=0., brightness_delta_range=[0.,0.],
                       nominal_continuity='smooth_nominal', total_brightness_rate_known=True,certainty='zero_consumed_alpha')
            row['source_evidence']['reason'] = 'all material channels are unconsumed at zero effective alpha'
        else:
            if change:
                row['maximum_brightness_change_per_second'] = _maximum(change['maximum_blended_rgb_rate_per_second'])
                row['unknown_reasons'].extend(change['unknown_reasons'])
            if jump:
                maximum = _maximum(jump['maximum_blended_rgb_difference'])
                row['brightness_delta_range'] = None if maximum is None else [0.,maximum]
                row['unknown_reasons'].extend(jump['unknown_reasons'])
            row['source_evidence'].update(material_change_bounds=change,material_jump_bounds=jump)
            if refinements:row['source_evidence']['symbolic_channel_responses']={n:refinements[n] for n in names if n in refinements}
            fields = [controls[n] for n in names if n in controls and channels[n]['may_be_consumed']]
            row['cycle_rate_hz'] = _smooth_frequencies(fields)
            row['event_schedules'] = _deduplicate_schedules([event for field in fields for event in time_switch_events(field)])
            # A channel modulo cadence is a source-boundary schedule only, never
            # a reached or simultaneous packed-byte material flash certificate.
            modulo = {n:channels[n]['nominal_modulo_schedule'] for n in names
                      if channels[n]['may_be_consumed'] and channels[n]['possible_native_wrap_jump'] is True}
            if modulo:row['source_evidence']['nominal_modulo_schedules'] = modulo
            if len(row['event_schedules'])==1:row['event_rate_hz']=row['event_schedules'][0]['nominal_event_rate_hz']
            elif len(row['event_schedules'])>1:row['unknown_reasons'].append('simultaneous material events unresolved; no sum of channel rates')
            if modulo or any(h.get('kind')=='shape_border_draw_gate' for h in hazards) and part=='border':
                row['unknown_reasons'].append('possible native modulo/draw gate event; reached transition timing remains unresolved')
            row['nominal_continuity'] = 'smooth_nominal' if row['maximum_brightness_change_per_second'] is not None else 'unknown'
            from effect_families import _deps
            dependencies=set().union(*(_deps(f) for f in fields)) if fields else set()
            varying=dependencies-TIME_NAMES
            if varying:row['unknown_reasons'].append('audio/state/input time trajectories unresolved: '+', '.join(sorted(varying)))
            row['total_brightness_rate_known'] = not varying and not modulo and row['maximum_brightness_change_per_second'] is not None and not row['unknown_reasons']
            row['certainty'] = 'conditional_material_bound' if row['brightness_delta_range'] is not None else 'unknown'
        row['unknown_reasons'] = sorted(set(row['unknown_reasons']))
        rows.append(row)
    return rows


def flash_evidence(analysis, description, context):
    """Produce JSON local flashing evidence; visibility is joined by the caller."""
    viewport = context.get('viewport')
    fps = context.get('feedback_fps')
    if not isinstance(viewport,(list,tuple)) or len(viewport)!=2 or any(type(v) is not int or v<=0 for v in viewport):
        raise ValueError('positive integer viewport dimensions required')
    if type(fps) not in {int,float} or not math.isfinite(fps) or fps<=0:
        raise ValueError('finite positive feedback_fps required')
    scenario = getattr(analysis,'input_scenario',None)
    domains = dict((scenario or {}).get('scalar_input_domains',{}))
    domains.update(context.get('scalar_input_domains',{}))
    result = {'policy':POLICY,'records':[],'rejected_predicates':[],'unknown_reasons':[],
              'context':{'viewport':list(viewport),'feedback_fps':fps,
                         'input_scenario_sha256':(scenario or {}).get('record_sha256'),
                         'scalar_input_domains':domains},
              'uses_rendered_images':False,'uses_equation_execution':False,'uses_shader_execution':False,
              'native_numeric_certified':False,'visible_flashing_verified':False}
    for stage,field in getattr(analysis,'outputs',{}).items():
        try:
            result['records'].append(_shader_record(analysis,description,stage,field,domains,result['rejected_predicates']))
        except (ValueError,RecursionError,OverflowError,IndexError) as error:
            row = _record('shader_'+stage,stage,'RGB','shader_brightness_change')
            row['unknown_reasons'] = [str(error)]
            result['records'].append(row)
    for element in description.get('elements',[]):
        if 'material_temporal' in element and 'material' in element:
            try:result['records'].extend(_shape_records(analysis,element,domains,result['rejected_predicates']))
            except (ValueError,RecursionError,OverflowError,IndexError) as error:
                row = _record(element['id'],element['stage'],'material','shape_material_brightness_change')
                row['unknown_reasons'] = [str(error)]
                result['records'].append(row)
    # Retain all existing discontinuity, nearest-sampling, normalization and
    # blackout mechanisms. Main records quantify rate/delta, these can remain
    # unresolved hazards even with a zero partial time derivative.
    existing = description.get('activity',{}).get('flashing',{})
    shapes={r['component_id'] for r in result['records'] if r['kind']=='shape_material_brightness_change'}
    result['source_hazards'] = [h for h in existing.get('hazards',[]) if not (
        h.get('element_id') in shapes and h.get('kind') in {'shape_channel_modulo_crossing','shape_border_draw_gate'})]
    material_hazards={}
    from source_appearance import _digest
    for row in result['records']:
        for hazard in row['source_evidence'].get('qualified_material_hazards',[]):material_hazards.setdefault(_digest(hazard),hazard)
    result['source_hazards'].extend(material_hazards.values())
    result['unknown_reasons'].extend(existing.get('unknown_reasons',[]))
    if not result['records']:result['unknown_reasons'].append('no qualified local brightness contributor')
    from source_appearance import _digest
    rejections={}
    for rejection in result['rejected_predicates']:rejections.setdefault(_digest(rejection),rejection)
    result['rejected_predicates']=list(rejections.values())
    result['context_sha256'] = _digest(result['context'])
    result['source_sha256'] = getattr(analysis,'source',{}).get('preset_sha256')
    return result
