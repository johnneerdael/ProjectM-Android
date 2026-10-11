"""Join source activity producers for conditional, frame-free preferences."""
import hashlib
import json
import math
from pathlib import Path

POLICY='source-static-behaviour-v1'
DEFAULT_CONTEXT={'viewport':[1920,1080], 'feedback_fps':30., 'reference_profile':'declared-home-tv-reference'}


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def validate_context(request=None):
    request=dict(DEFAULT_CONTEXT if request is None else request)
    if set(request)-{'viewport','feedback_fps','reference_profile','scalar_input_domains','scalar_input_maximum_rates_per_second','output_storage','activity_preferences','texel_offset_pixels','main_texture_size'}:
        raise ValueError('unsupported static behaviour context field')
    viewport=request.get('viewport');fps=request.get('feedback_fps')
    if not isinstance(viewport,(list,tuple)) or len(viewport)!=2 or any(type(v) is not int or not 0<v<2**31 for v in viewport):
        raise ValueError('two positive int32 viewport dimensions required')
    if type(fps) not in {int,float} or not math.isfinite(fps) or not 0<fps<=1000:
        raise ValueError('finite positive feedback FPS up to1000 required')
    domains=request.get('scalar_input_domains',{})
    if not isinstance(domains,dict):raise ValueError('declared scalar input domains must be an object')
    for name,span in domains.items():
        if not isinstance(name,str) or not name or not isinstance(span,(list,tuple)) or len(span)!=2 or any(
                type(v) not in {int,float} or not math.isfinite(v) for v in span) or span[0]>span[1]:
            raise ValueError('finite ordered static input domain required')
    storage=request.get('output_storage','normalized-unorm')
    if storage not in {'normalized-unorm','unknown'}:
        raise ValueError('supported declared output storage required')
    from static_behaviour_scoring import validate_preferences
    from source_motion_behaviour import validate_input_rates
    preferences=validate_preferences(request.get('activity_preferences'))
    offsets=request.get('texel_offset_pixels')
    if offsets is not None and (not isinstance(offsets,(list,tuple)) or len(offsets)!=2 or
            any(type(v) not in {int,float} or not math.isfinite(v) for v in offsets)):
        raise ValueError('explicit finite texel-offset pixel pair required')
    texture=request.get('main_texture_size')
    if texture is not None and (not isinstance(texture,(list,tuple)) or len(texture)!=2 or
            any(type(v) is not int or not 0<v<2**31 for v in texture)):
        raise ValueError('explicit positive int32 main texture dimensions required')
    result={'activity_preferences':preferences,'output_storage':storage,'viewport':list(viewport),'feedback_fps':float(fps),
            'reference_profile':request.get('reference_profile','caller-declared-reference'),
            'texel_offset_pixels':None if offsets is None else list(offsets),
            'main_texture_size':None if texture is None else list(texture),
            'scalar_input_maximum_rates_per_second':validate_input_rates(request.get('scalar_input_maximum_rates_per_second')),
            'scalar_input_domains':{name:list(span) for name,span in sorted(domains.items())}}
    if not isinstance(result['reference_profile'],str) or not result['reference_profile']:
        raise ValueError('named declared reference profile required')
    return result


def _complete(analysis,flashing,motion):
    """Initial complete scope: selected custom RGB independent of stored images.

    Other paths remain productive partial evidence. Absence of a listed hazard
    never closes the feedback/audio/storage model for them.
    """
    if analysis.stages['composite']['kind']!='custom_composite':return False
    if getattr(analysis,'unknowns',[]):return False
    if analysis.stages['composite'].get('source_contains_clip'):return False
    final=[r for r in flashing['records'] if r['component_id']=='shader_composite']
    if not final or any(not r['total_brightness_rate_known'] for r in final):return False
    if flashing['source_hazards']:return False
    return not motion['unresolved_contributors']


def _finite_composite_guard(field,domains):
    """Bound simple scalar shader intermediates without assuming finite phases.

    This restricted binary32 envelope is a declared source-operation model,
    not a target-driver or transcendental precision certificate.
    """
    import numpy as np
    from effect_families import _CACHE
    from source_activity import blackout_colour_channels
    from source_flash_behaviour import _project_uniform_lanes
    token=_CACHE.set({});memo={};active=set();inputs=set()
    def round32(span):
        with np.errstate(over='ignore',invalid='ignore',under='ignore'):
            lo=float(np.nextafter(np.float32(span[0]),np.float32(-math.inf)))
            hi=float(np.nextafter(np.float32(span[1]),np.float32(math.inf)))
        if not math.isfinite(lo) or not math.isfinite(hi):raise ValueError('intermediate may exceed finite binary32 domain')
        # Include possible subnormal flushing without claiming a driver policy.
        if lo<np.finfo(np.float32).tiny and hi>-np.finfo(np.float32).tiny:
            lo=min(lo,0.);hi=max(hi,0.)
        return [lo,hi]
    def visit(node,depth=0):
        key=id(node)
        if key in memo:return memo[key]
        if key in active or depth>64 or len(memo)+len(active)>=256:raise ValueError('finite shader guard traversal unresolved')
        active.add(key)
        try:
            if node.op=='constant':
                value=node.detail.get('native_value',node.detail.get('value'))
                if type(value) not in {int,float} or not math.isfinite(value):raise ValueError('nonfinite shader literal')
                span=[float(value),float(value)]
                if node.dtype!='int':span=round32(span)
            elif node.op=='input' and node.dtype=='float':
                inputs.add(node.detail.get('name'))
                span=domains.get(node.detail.get('name'))
                if span is None:raise ValueError('native shader input domain unresolved: '+str(node.detail.get('name')))
                span=round32(span)
            elif node.dtype=='float' and node.op in {'add','subtract','multiply'} and len(node.args)==2:
                a,b=(visit(arg,depth+1) for arg in node.args)
                if node.op=='add':span=[a[0]+b[0],a[1]+b[1]]
                elif node.op=='subtract':span=[a[0]-b[1],a[1]-b[0]]
                else:
                    products=[x*y for x in a for y in b];span=[min(products),max(products)]
                span=round32(span)
            elif node.dtype=='float' and node.op in {'sin','cos'} and len(node.args)==1:
                visit(node.args[0],depth+1);span=round32([-1.,1.])
            elif node.dtype=='float' and node.op=='cast' and len(node.args)==1 and node.args[0].op=='constant':
                span=round32(visit(node.args[0],depth+1))
            else:raise ValueError('finite shader guard unsupported operation: '+node.op)
            memo[key]=span
            return span
        finally:active.remove(key)
    result={'policy':'restricted-binary32-finite-source-guard-v1','status':'unresolved',
            'native_numeric_certified':False,'declared_input_domains':domains,
            'conditions':['Basic operations use outward binary32 enclosures and include subnormal flushing',
                          'Finite sin/cos use their mathematical unit range; precision and target-driver behavior remain unverified'],
            'unknown_reasons':[]}
    try:
        channels=[_project_uniform_lanes(c) for c in blackout_colour_channels(field)]
        if len(channels)!=3:raise ValueError('three scalar RGB channels required')
        result.update(status='bounded',channel_ranges=[visit(c) for c in channels])
    except (ValueError,RecursionError,OverflowError,IndexError) as error:
        result['unknown_reasons']=[str(error)]
    finally:
        result['visited_nodes']=len(memo);result['dynamic_input_names']=sorted(inputs);_CACHE.reset(token)
    return result


def _displayed_output(analysis,flashing,context):
    """Preserve raw RGB evidence and qualify only declared normalized storage."""
    result={'policy':'declared-normalized-output-clamp-v1',
            'storage':context['output_storage'],'raw_channel_ranges':None,
            'stored_channel_ranges':None,'constant_rgb':None,'constant_rgb_qualified':False,'maximum_rgb_difference':None,
            'native_model_stored_channel_ranges':None,'native_enclosure_consistent_with_nominal':False,
            'raw_ranges_changed':False,'native_numeric_certified':False,
            'native_finite_guard':{'status':'unresolved','unknown_reasons':['No selected supported finite RGB program']},
            'conditions':['Declared normalized fixed-point output clamps finite RGB to[0,1]',
                          'Stored values are nominal before output quantization; this is not native-driver certification']}
    if context['output_storage']!='normalized-unorm' or analysis.stages['composite']['kind']!='custom_composite':
        return result
    field=analysis.outputs.get('composite')
    if field is None:return result
    result['native_finite_guard']=_finite_composite_guard(field,context['scalar_input_domains'])
    records=[r for r in flashing.get('records',[]) if r['component_id']=='shader_composite']
    if len(records)!=1:return result
    spans=[r.get('nominal_value_range') for r in records[0].get('source_evidence',{}).get('channel_value_envelopes',[])]
    if len(spans)!=3 or any(not isinstance(span,(list,tuple)) or len(span)!=2 or
            any(type(v) not in {int,float} or not math.isfinite(v) for v in span) or span[0]>span[1] for span in spans):
        return result
    stored=[[max(0.,min(1.,v)) for v in span] for span in spans]
    result.update(raw_channel_ranges=[list(s) for s in spans],stored_channel_ranges=stored,
                  raw_ranges_changed=stored!=[list(s) for s in spans],
                  maximum_rgb_difference=max(high-low for low,high in stored))
    if all(low==high for low,high in stored):result['constant_rgb']=[s[0] for s in stored]
    guard=result['native_finite_guard']
    if guard['status']=='bounded':
        native_stored=[[max(0.,min(1.,v)) for v in span] for span in guard['channel_ranges']]
        result['native_model_stored_channel_ranges']=native_stored
        # An overly wide native enclosure cannot turn a tight nominal formula
        # into an automatic calm result (for example, lost-significance terms).
        result['native_enclosure_consistent_with_nominal']=all(
            actual[0]>=nominal[0]-(1e-6+.05*(nominal[1]-nominal[0])) and
            actual[1]<=nominal[1]+(1e-6+.05*(nominal[1]-nominal[0]))
            for actual,nominal in zip(native_stored,stored))
        if result['constant_rgb'] is not None:
            result['constant_rgb_qualified']=not guard['dynamic_input_names'] or all(a==b for a,b in native_stored)
    return result


def _shape_state(analysis,description,context):
    """Export private-state proofs without amending drawing/activity guards."""
    from engine_profiles import CORE_2334_ENGINE, matches
    from scene_equations import SHAPE, _scalar, source_settings
    from source_shape_state_domains import RESET, ZERO_POLICY, shape_state_domain_evidence
    source=analysis.source
    engine=source.get('parser_inputs',{}).get('engine')
    initialization=ZERO_POLICY if isinstance(engine,dict) and matches(engine,CORE_2334_ENGINE) else None
    values=source_settings(source)
    declared={name:span for name,span in context['scalar_input_domains'].items() if name in RESET}
    components=[]
    for index in range(4):
        if not _scalar(values,f'shapecode_{index}_enabled',0,'bool'):continue
        default,kind=SHAPE['num_inst']
        count=_scalar(values,f'shapecode_{index}_num_inst',default,kind)
        if count<=0:continue
        # The native loop uses saved configuration, not equation writes or a
        # caller's narrower declaration. Main Q remains an explicit premise.
        inputs={**declared,'instance':[0,count-1]}
        proof=shape_state_domain_evidence(source,policy=analysis.policy,shape_index=index,
            input_domains=inputs,initial_variable_policy=initialization)
        components.append({**proof,'component_id':f'shape_{index}','shape_index':index,
                           'native_instance_count':count,'input_domains':inputs})
    return {'policy':'source-shape-state-export-v1','components':components,
            'by_component':{row['component_id']:row for row in components},
            'native_numeric_certified':False,'visible_motion_certified':False,
            'uses_rendered_images':False,'uses_shader_execution':False,'uses_equation_execution':False,
            'conditions':['Conditional nominal state/output domains do not establish motion, prominence or mood eligibility']}


def _curve_projections(analysis,description,context):
    from source_curve_projection import curve_projection
    from scene_equations import _scalar
    from source_motion_behaviour import _effective_domains
    domains=_effective_domains(analysis,context)
    components=[]
    for element in description.get('elements',[]):
        recipe=element.get('parameters',{}).get('source_curve_recipe')
        if recipe is None:continue
        identity=element['id']
        index=identity.removeprefix('wave_')
        dots=bool(_scalar(analysis.values,'wavecode_'+index+'_bUseDots',0,'bool'))
        projected=curve_projection(recipe,{'viewport':context['viewport'],
            'source_time_domain':domains.get('time'),'wave_use_dots':dots})
        components.append({**projected,'component_id':identity})
    return {'policy':'source-curve-projection-export-v1','components':components,
            'by_component':{row['component_id']:row for row in components},
            'uses_rendered_images':False,'native_numeric_certified':False}


def _material_marker_motions(analysis,description,context,evidence):
    import source_material_marker_motion
    from source_motion_behaviour import _effective_domains
    declared_time=_effective_domains(analysis,context).get('time')
    components=[]
    for element in description.get('elements',[]):
        recipe=element.get('parameters',{}).get('source_curve_recipe')
        if recipe is None:continue
        identity=element['id']
        projection=evidence['curve_projection']['by_component'].get(identity)
        marker_context={'viewport':context['viewport']}
        # Reuse the projection's declared time domain so pixel ceilings stay
        # bound to the same source interval rather than a second assumption.
        if projection is not None and projection.get('source_time_domain') is not None:
            marker_context['source_time_domain']=projection['source_time_domain']
        elif projection is None and declared_time is not None:
            marker_context['source_time_domain']=declared_time
        row=source_material_marker_motion.material_marker_motion(recipe,projection,marker_context)
        components.append({**row,'component_id':identity})
    return {'policy':'source-material-marker-export-v1','components':components,
            'by_component':{row['component_id']:row for row in components},
            'uses_equation_execution':False,'uses_rendered_images':False,
            'native_numeric_certified':False,'whole_preset_activity_credit':False}


def _radial_colour_fields(analysis,description,context,evidence):
    import source_radial_colour_field
    from source_motion_behaviour import _effective_domains
    declared_time=_effective_domains(analysis,context).get('time')
    components=[]
    for element in description.get('elements',[]):
        recipe=element.get('parameters',{}).get('source_curve_recipe')
        if recipe is None:continue
        identity=element['id']
        projection=evidence['curve_projection']['by_component'].get(identity)
        field_context={'feedback_fps':context['feedback_fps']}
        if declared_time is not None:field_context['source_time_domain']=declared_time
        row=source_radial_colour_field.radial_colour_field(recipe,projection,field_context,
            persistence=evidence.get('feedback_persistence'))
        components.append({**row,'component_id':identity})
    return {'policy':'source-radial-colour-field-export-v1','components':components,
            'by_component':{row['component_id']:row for row in components},
            'uses_equation_execution':False,'uses_rendered_images':False,
            'native_numeric_certified':False,'whole_preset_activity_credit':False}


def _mesh_field(analysis,description,context):
    from source_mesh_field import mesh_field_structure
    return mesh_field_structure(analysis,context)


def _motion_vectors(analysis,description,context):
    from source_motion_vector_element import motion_vector_element
    return motion_vector_element(analysis,context)


def _affine_radial_feedback(analysis,description,context):
    from source_affine_radial_feedback import affine_radial_feedback
    from engine_profiles import CORE_2334_ENGINE
    recipe=description.get('native_warp_recipe',{})
    consumed=recipe.get('contribution')=='consumed'
    if consumed and (recipe.get('shader_branch')!='legacy' or
                     analysis.source.get('parser_inputs',{}).get('engine')!=CORE_2334_ENGINE):
        return {'policy':'source-affine-radial-feedback-v1','status':'unknown',
                'unknown_reasons':['Central sampler requires pinned source34 radius lineage and a selected legacy/default warp'],
                'visible_motion_speed':None,'actual_feedback_lifetime':None,
                'native_numeric_certified':False,'whole_preset_activity_credit':False,
                'uses_equation_execution':False,'uses_rendered_images':False}
    return affine_radial_feedback(analysis,context,consumed=consumed)


def _feedback_persistence(analysis,description,context):
    from source_feedback_persistence import unorm8_decay_persistence
    return unorm8_decay_persistence(description.get('feedback_transfer'),context)


def _borders(analysis,persistence,context):
    from source_borders import border_operators
    return border_operators(analysis,context,persistence)


def _curve_feedback_relations(analysis,description,context,evidence):
    from fractions import Fraction
    from source_curve_feedback_relation import curve_feedback_relation
    from source_curve_projection import _exact,_span,_enclosure
    components=[]
    for element in description.get('elements',[]):
        recipe=element.get('parameters',{}).get('source_curve_recipe')
        if recipe is None:continue
        identity=element['id']
        projection=evidence['curve_projection']['by_component'].get(identity,{})
        from source_feedback_persistence import persistence_horizon_steps,persistence_layer_sweep
        horizons=[count for _,count in persistence_horizon_steps(evidence.get('feedback_persistence'))]
        counts=sorted({1,4,16,*(count for count in horizons if count<=128)})
        selection={'policy':'source-sample-midpoint-diagnostic-v1','source_sample':.5,
                   'declared_feedback_step_counts':counts,
                   'persistence_horizon_step_counts':horizons,
                   'is_typical_or_observed':False,'native_vertex_attainment_verified':False,
                   'scope':'declared continuous source-sample reference, not displayed dominance or a whole-curve trajectory'}
        try:
            coefficients={key:_exact(value) for key,value in recipe['radius_affine_coefficients_exact'].items()}
            time=None
            if coefficients['time']!=0:
                time=_span(projection.get('source_time_domain'))[0]
                selection['declared_source_time_reference']=float(time)
            radius=2*(coefficients['constant']+coefficients['sample']*Fraction(1,2)+
                      coefficients['time']*(0 if time is None else time))
            relation_context={'source_radius_domain':_enclosure((radius,radius)),
                              'feedback_fps':context['feedback_fps'],
                              'feedback_step_counts':selection['declared_feedback_step_counts']}
            if time is not None:relation_context['local_source_time_domain']=_enclosure((time,time))
            row=curve_feedback_relation(recipe,projection,evidence['affine_radial_feedback'],
                description.get('feedback_envelope',{}),context=relation_context)
            row['persistence_layer_sweep']=persistence_layer_sweep(row,evidence.get('feedback_persistence'))
            from source_feedback_persistence import bilinear_diffusion_spread
            row['bilinear_diffusion_spread']=bilinear_diffusion_spread(row,evidence.get('feedback_persistence'),
                radial=evidence.get('affine_radial_feedback'))
        except (ValueError,KeyError,OverflowError,ZeroDivisionError) as error:
            row={'policy':'source-curve-feedback-relation-v1','status':'unknown',
                 'unknown_reasons':[str(error)],'actual_trail_thickness_pixels':None,
                 'final_visible_density':None,'whole_preset_activity_credit':False,
                 'uses_equation_execution':False,'uses_rendered_images':False}
        components.append({**row,'component_id':identity,'reference_selection':selection})
    return {'policy':'source-curve-feedback-export-v1','components':components,
            'by_component':{row['component_id']:row for row in components},
            'uses_equation_execution':False,'uses_rendered_images':False,
            'native_numeric_certified':False,'whole_preset_activity_credit':False}


def _radial_uv_envelope(evidence,context):
    from source_radial_uv_envelope import radial_uv_envelope
    declared={'viewport':context['viewport'],'texel_offset_pixels':context['texel_offset_pixels']}
    if context['main_texture_size'] is not None:declared['texture_size']=context['main_texture_size']
    return radial_uv_envelope(evidence['affine_radial_feedback'],declared)


def static_behaviour(analysis,description,context=None):
    from effect_families import _CACHE,_SemanticBudget
    from source_flash_behaviour import flash_evidence
    from source_motion_behaviour import motion_evidence
    from source_prominence import prominence_evidence
    from static_behaviour_scoring import score_static_behaviour
    from source_colour_character import colour_character
    normalized=validate_context(context)
    token=_CACHE.set({}) if _CACHE.get() is None else None
    try:
        result={'policy':POLICY,'context':normalized,'context_sha256':_digest(normalized),
                'preset_sha256':analysis.source.get('preset_sha256'),
                'engine':analysis.source.get('parser_inputs',{}).get('engine'),
                'model_sources':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                for name in ['source_static_behaviour.py','source_flash_behaviour.py',
                                             'source_motion_behaviour.py','source_prominence.py','source_colour_character.py','static_behaviour_scoring.py',
                                             'source_blur_propagation.py','source_colour_modulus.py',
                                             'source_shape_state_domains.py','source_proofs_worker.py',
                                             'source_stochastic_brightness.py','source_parametric_wave.py',
                                             'source_curve_projection.py','source_affine_radial_feedback.py',
                                             'source_curve_feedback_relation.py','source_radial_uv_envelope.py',
                                             'source_material_marker_motion.py','source_feedback_persistence.py',
                                             'source_radial_colour_field.py','source_mesh_field.py',
                                             'source_motion_vector_element.py','source_borders.py',
                                             'source_point_colour.py']},
                'uses_rendered_images':False,'uses_shader_execution':False,'uses_equation_execution':False,
                'native_numeric_certified':False,'appearance_accuracy_verified':False}
        result['producer_failures']={}
        def produce(name,function,args,fallback):
            # Separate bounded traversal caches prevent one exhausted producer
            # from discarding or poisoning independent source facts.
            producer_token=_CACHE.set({})
            try:
                return function(*args)
            except (_SemanticBudget,RecursionError,OverflowError,ValueError,IndexError) as error:
                result['producer_failures'][name]={'error_type':type(error).__name__,'reason':str(error)}
                return {**fallback,'status':'unresolved','unknown_reasons':[str(error)]}
            finally:
                _CACHE.reset(producer_token)
        arguments=(analysis,description,normalized)
        result['shape_state']=produce('shape_state',_shape_state,arguments,{'by_component':{},'components':[]})
        result['curve_projection']=produce('curve_projection',_curve_projections,arguments,{'by_component':{},'components':[]})
        result['material_marker_motion']=produce('material_marker_motion',_material_marker_motions,
            (*arguments,result),{'by_component':{},'components':[]})
        result['mesh_field']=produce('mesh_field',_mesh_field,arguments,{'controls':{},'patterns':[]})
        result['motion_vectors']=produce('motion_vectors',_motion_vectors,arguments,{'activation':None})
        result['affine_radial_feedback']=produce('affine_radial_feedback',_affine_radial_feedback,arguments,
            {'native_numeric_certified':False,'visible_motion_speed':None,'whole_preset_activity_credit':False})
        result['feedback_persistence']=produce('feedback_persistence',_feedback_persistence,arguments,
            {'largest_stuck_level':None,'visible_trail_length':None})
        result['borders']=produce('borders',_borders,(analysis,result['feedback_persistence'],normalized),
            {'borders':[],'darken_centre':None})
        result['radial_colour_field']=produce('radial_colour_field',_radial_colour_fields,
            (*arguments,result),{'by_component':{},'components':[]})
        result['curve_feedback_relation']=produce('curve_feedback_relation',_curve_feedback_relations,
            (*arguments,result),{'by_component':{},'components':[]})
        result['radial_uv_envelope']=produce('radial_uv_envelope',_radial_uv_envelope,(result,normalized),
            {'coordinate_wrap_possible':None,'linear_filter_footprint_edge_crossing_possible':None})
        result['flashing']=produce('flashing',flash_evidence,arguments,
            {'records':[],'source_hazards':[{'stage':'composite','reason':'flashing producer incomplete'}]})
        result['motion']=produce('motion',motion_evidence,arguments,
            {'contributions':[],'unresolved_contributors':[{'reason':'motion producer incomplete'}]})
        result['prominence']=produce('prominence',prominence_evidence,arguments,{'by_component':{},'components':[]})
        result['colour']=produce('colour',colour_character,(analysis,description,result['prominence'],normalized),
            {'components':[],'by_component':{},'candidate_palette_hierarchy':[],'useful_hue_description':False})
        result['status']='partial' if result['producer_failures'] else 'computed'
        result['displayed_output']=_displayed_output(analysis,result['flashing'],normalized)
        result['output_model_complete']=normalized['output_storage']!='unknown' and result['displayed_output']['native_enclosure_consistent_with_nominal'] and not result['producer_failures'] and _complete(analysis,result['flashing'],result['motion'])
        result['classification']=score_static_behaviour(result,preferences=normalized['activity_preferences'])
        result['limitations']=['Reference viewport/FPS/input domains are declared assumptions, not device observations',
            'Physical component bounds and source potential estimates are not rendered appearance or native certification',
            'Remaining feedback/audio/state/composition gaps remain explicit and can prevent automatic mood eligibility']
        result['record_sha256']=_digest(result)
        return result
    except (_SemanticBudget,RecursionError,OverflowError,ValueError,IndexError) as error:
        return {'policy':POLICY,'context':normalized,'context_sha256':_digest(normalized),
                'status':'unresolved','unknown_reasons':[str(error)],
                'uses_rendered_images':False,'uses_shader_execution':False,'uses_equation_execution':False,
                'output_model_complete':False,'appearance_accuracy_verified':False}
    finally:
        if token is not None:_CACHE.reset(token)
