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
    if set(request)-{'viewport','feedback_fps','reference_profile','scalar_input_domains','scalar_input_maximum_rates_per_second','output_storage','activity_preferences'}:
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
    result={'activity_preferences':preferences,'output_storage':storage,'viewport':list(viewport),'feedback_fps':float(fps),
            'reference_profile':request.get('reference_profile','caller-declared-reference'),
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
                                             'source_stochastic_brightness.py','source_parametric_wave.py']},
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
