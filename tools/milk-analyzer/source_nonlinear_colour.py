"""Conditional shader colour ranges through supported nonlinear scalar math."""
from shader_fields import Field


def nonlinear_texture_colour_bounds(analysis,warp_vertex,*,input_domains=None):
    from source_advection import substitute_sample_values
    from source_control_bounds import scalar_value_envelope,scalar_response_envelope
    from source_appearance import _data_return,_canonical_lane,_audio_codes,_packed_reads,EEL_AUDIO,PACKED
    from effect_families import _parts,_deps
    from field_math import SWIZZLE
    from source_native_warp import _f32
    from source_polar import _nodes
    stages={};flat_inputs={}
    time_names={'time',':native-render-time-f32','_c2.x'}
    for stage in ('warp','composite'):
        r={'source_model':'unknown','channel_value_envelopes':None,
            'raw_rgb_bounds_if_samples_unit_interval':None,'sample_textures':[],
            'colour_difference_gain':None,'whole_feedback_contraction':None,
            'actual_feedback_persistence':None,'visible_flashing':None,'unknown_reasons':[],
            'channel_threshold_resets':[],'scalar_palette':None,
            'direct_sample_colour_response':{'policy':'source-direct-sample-colour-response-v1','samples':[],
                'includes_sampling_coordinate_response':False,'visible_response_strength':None,'conditions':[]},
            'direct_colour_time_response':{'policy':'source-fixed-sample-colour-time-response-v1','status':'unknown',
                'channels':[],'channel_order':['r','g','b'],'samples_are_held_fixed':True,
                'includes_sampling_coordinate_response':False,'total_rgb_rate_per_second':None,
                'visible_flash_frequency_hz':None,
                'conditions':['Sample RGBA values are independent [0,1] inputs held fixed; changing sample positions/history are separate',
                    'Declared source-time aliases advance together at one source second per second between clock resets/wraps',
                    'Audio, state, frame counters, FPS, progress, spatial coordinates and all other inputs held fixed',
                    'Native float32 clock/upload quantization and finite precision are not continuous-rate certificates',
                    'Raw stage RGB partial rates exclude geometry, feedback, subsequent composition/storage, prominence and mood']},
            'direct_colour_audio_response':{'policy':'source-fixed-sample-colour-audio-response-v1','status':'unknown',
                'bands':[],'includes_sampling_coordinate_response':False,'visible_response_strength':None,
                'conditions':['Sampled RGBA colours are independent declared local inputs held fixed during each band variation',
                              'Selected band aliases vary by the same delta; other audio/time/state/coordinates are fixed',
                              'Bounds concern raw stage RGB, not displayed brightness, feedback evolution, sample movement, screen area or mood',
                              'Audio-dependent native float32 uploads/casts and discontinuities remain unresolved']}}
        field=analysis.outputs.get(stage)
        if field is None:
            r['unknown_reasons']=['no authored stage field'];stages[stage]=r;continue
        try:
            replaced,samples=substitute_sample_values(_data_return(field),known_vertex=warp_vertex if stage=='warp' else None)
            domains=dict(input_domains or {});memo={};active=set();assumptions=set()
            for name,sample in samples:
                for lane in 'xyzw':domains[name+'.'+lane]=[0.,1.]
            local_sample_names=set(domains)-set(input_domains or {})
            derived=set();derived_audio={};derived_time=set();derived_samples={}
            def project(node,depth=0):
                original=node;key=id(original)
                if key in memo:return memo[key][1]
                node=_canonical_lane(original)
                if depth>64 or len(memo)+len(active)>=4096 or key in active:
                    raise ValueError('nonlinear colour projection budget/cycle exceeded')
                active.add(key)
                try:value=calculate(node,depth)
                finally:active.remove(key)
                memo[key]=(original,value);return value
            def calculate(node,depth):
                if node.op=='cast' and node.dtype=='float' and len(node.args)==1 and node.detail.get('target_type')=='float':
                    child=node.args[0]
                    if child.dtype in {'float','float2','float3','float4'}:
                        parts=_parts(child)
                        if parts and parts[0].dtype=='float':return project(parts[0],depth+1)
                if node.op in {'length','distance'}:
                    vectors=[]
                    for arg in node.args:
                        parts=_parts(arg)
                        vectors.append(Field('components',tuple(project(v,depth+1) for v in parts),arg.dtype))
                    return Field(node.op,tuple(vectors),node.dtype,node.detail)
                if node.op=='dot' and len(node.args)==2:
                    a,b=map(_parts,node.args)
                    if len(a)!=len(b) or not 1<=len(a)<=4:raise ValueError('colour dot dimensions unresolved')
                    value=Field('constant',detail={'value':0.})
                    for x,y in zip(a,b):
                        value=Field('add',(value,Field('multiply',(project(x,depth+1),project(y,depth+1)),'float')),'float')
                    return value
                if node.op=='narrow' and node.detail.get('numeric_domain')=='shader-float32':
                    child=project(node.args[0],depth+1);report=scalar_value_envelope(child,input_domains=domains)
                    span=report['nominal_value_range']
                    assumptions.update(set(report['assumed_finite_input_names'])-local_sample_names-derived)
                    if span is None:raise ValueError('native colour-input upload domain unresolved')
                    name=':nonlinear-colour-narrow-'+str(len(memo));domains[name]=[_f32(v) for v in span];derived.add(name)
                    derived_audio[name]=set(_audio_codes(node,analysis))
                    dependencies=_deps(child)
                    derived_samples[name]=(dependencies&local_sample_names)|set().union(*(
                        derived_samples.get(k,set()) for k in dependencies))
                    if _deps(node)&time_names or 0 in _packed_reads(node).get('_c2',set()):derived_time.add(name)
                    return Field('input',dtype='float',detail={'name':name})
                if node.op=='member' and node.detail.get('swizzle') and len(node.detail.get('field',''))==1:
                    parent=node.args[0];lane=SWIZZLE[node.detail['field']]
                    if parent.op=='input' and parent.dtype.startswith('float'):
                        return Field('input',dtype='float',detail={'name':parent.detail['name']+'.'+'xyzw'[lane]})
                    if parent.op=='normalize' and len(parent.args)==1:
                        vector=parent.args[0];parts=_parts(vector)
                        if vector.dtype not in {'float','float2','float3','float4'} or lane>=len(parts):raise ValueError('normalized colour lane/type unresolved')
                        projected=Field('components',tuple(project(v,depth+1) for v in parts),vector.dtype)
                        return Field('normalized_component',(projected,),'float',{'index':lane})
                    if parent.op=='domain_checked':
                        child=_parts(parent.args[0])[lane]
                        return Field('domain_checked',(project(child,depth+1),),'float',parent.detail)
                    if parent.op not in {'input','sample'}:
                        parts=_parts(parent)
                        if lane<len(parts):
                            p=parts[lane]
                            if not (p.op=='member' and p.args and p.args[0] is parent):return project(p,depth+1)
                return Field(node.op,tuple(project(arg,depth+1) for arg in node.args),node.dtype,node.detail)
            channels=[];projected=[]
            for lane in _parts(replaced)[:3]:
                try:
                    selected=project(lane)
                    channel=scalar_value_envelope(selected,input_domains=domains)
                except (ValueError,RecursionError,OverflowError,IndexError) as error:
                    channel=scalar_value_envelope(Field('unresolved',dtype='float'))
                    channel['unknown_reasons']=[str(error)]
                    selected=Field('unknown',detail={'reason':str(error)})
                channels.append(channel);projected.append(selected)
            if len(channels)!=3:raise ValueError('nonlinear RGB scalar lanes unresolved')
            response=r['direct_colour_audio_response']
            for code in _audio_codes(replaced,analysis):
                names={name for name,c in EEL_AUDIO.items() if c==code}
                names.update(name+'.'+'xyzw'[lane] for name,cs in PACKED.items() for lane,c in enumerate(cs) if c==code)
                reports=[]
                for selected in projected:
                    tainted=any(n.op=='input' and code in derived_audio.get(n.detail.get('name'),set()) for n,path in _nodes(selected))
                    report=scalar_response_envelope(Field('unknown') if tainted else selected,input_names=names,input_domains=domains)
                    if tainted:report['unknown_reasons']=['audio-dependent native float32 upload prevents a continuous direct-colour bound']
                    reports.append(report)
                response['bands'].append({'input_code':code,'channel_order':['r','g','b'],
                    'control_unit':'raw stage RGB component/declared audio input unit','channel_response_envelopes':reports})
            response['status']='conditional source direct-colour paths'
            time_response=r['direct_colour_time_response']
            for selected in projected:
                tainted=any(n.op=='input' and n.detail.get('name') in derived_time for n,path in _nodes(selected))
                report=scalar_response_envelope(Field('unknown') if tainted else selected,input_names=time_names,input_domains=domains)
                channel={k:v for k,v in report.items() if k not in {'policy','maximum_absolute_control_change_per_audio_unit',
                    'maximum_time_rate','visible_response_strength','conditions'}}
                channel['maximum_absolute_rgb_rate_per_source_second']=report['maximum_absolute_control_change_per_audio_unit']
                if tainted:channel['unknown_reasons']=['time-dependent native float32 upload prevents a continuous direct-colour bound']
                time_response['channels'].append(channel)
            time_response['status']='conditional source direct-colour time paths'
            from source_sample_colour_response import sample_colour_response
            r['direct_sample_colour_response']=sample_colour_response(projected,samples,domains,derived_samples)
            from source_threshold_resets import channel_threshold_resets
            r['channel_threshold_resets']=channel_threshold_resets(projected,domains)
            from source_scalar_palette import scalar_palette
            r['scalar_palette']=scalar_palette(projected,domains,local_sample_names)
            if input_domains is None and all(sel.op!='unknown' for sel in projected):
                flat_inputs[stage]=(projected,samples,dict(domains))
            spans=[c['nominal_value_range'] for c in channels]
            r['channel_value_envelopes']=channels
            r['sample_textures']=sorted({s.detail.get('canonical_texture') for name,s in samples},key=str)
            if all(span is not None for span in spans):
                r['source_model']='bounded_declared_texture_inputs';r['raw_rgb_bounds_if_samples_unit_interval']=spans
            elif any(span is not None for span in spans):r['source_model']='partial_declared_texture_inputs'
            r['unknown_reasons']=[reason for c in channels for reason in c['unknown_reasons']]
            r['assumed_finite_nontexture_input_names']=sorted(assumptions|set().union(*(
                set(c['assumed_finite_input_names'])-local_sample_names-derived for c in channels)))
        except (ValueError,RecursionError,OverflowError,IndexError) as error:r['unknown_reasons']=[str(error)]
        stages[stage]=r
    flat=None
    if input_domains is None:
        from source_flat_field import flat_field
        context=getattr(analysis,'behaviour_context',None) or {}
        flat=flat_field(flat_inputs,fps=context.get('feedback_fps') if isinstance(context,dict) else None)
    scenario=getattr(analysis,'input_scenario',None)
    if scenario is not None and input_domains is None:
        extra=nonlinear_texture_colour_bounds(analysis,warp_vertex,input_domains=scenario['scalar_input_domains'])
        for stage,r in stages.items():
            r['scenario_colour_envelope']={**extra['stages'][stage],
                'input_scenario_sha256':scenario['record_sha256'],
                'observed_runtime_inputs':False,'runtime_binding_verified':False}
    return {'policy':'source-nonlinear-declared-texture-colour-ranges-v1','stages':stages,'flat_field':flat,
        'uses_shader_execution':False,'uses_equation_execution':False,'uses_rendered_images':False,
        'conditions':['Direct sampled RGBA components independently lie in [0,1]; this input premise is not certified by source',
                      'Nominal scalar arithmetic ranges, explicit packed-input and native-upload domains; no time/pixel samples',
                      'Known nonfinite uploads, singular or unsupported operation domains remain unknown',
                      'Patched shader abs/domain lowering is retained; no blanket negative-power-base reinterpretation',
                      'Correlation, native precision/storage, sampling positions/history, drawing/detail and final display remain separate',
                      'Range bounds do not establish sensitivity, continuity, visible flashing, palette or mood']}
