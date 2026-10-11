"""Flat-field steady state of a feedback loop, from projected stage colour graphs.

For spatially uniform content every feedback sample (the main image and its
blurs, at any coordinate) returns the same per-channel value v. The warp stage
then reduces to a 3-D recurrence v_{n+1} = Q(F(v_n)), where F is the projected
warp RGB as a function of the sampled lanes and Q clamps to [0,1] and rounds to
the RGBA8 storage grid. Iterating from black (or another declared start) shows
whether flat regions decay to black, saturate, settle on a colour or cycle; the
composite at that state gives the displayed colour of flat regions. Nothing
outside this declared uniform-content model is claimed: edges, drawn elements,
gradients and advection change real content. Iteration evaluates nominal source
arithmetic on three numbers per step; no pixel frames are rendered.
"""
import math

POLICY='source-flat-field-steady-state-v1'
FEEDBACK_TEXTURES={'main','blur1','blur2','blur3'}
STEPS=900
ALPHA=1.0


def _point(graph,domains):
    from source_control_bounds import scalar_value_envelope
    span=scalar_value_envelope(graph,input_domains=domains).get('nominal_value_range')
    if span is None:raise ValueError('flat-field channel is unbounded')
    low,high=float(span[0]),float(span[1])
    if abs(low-high)>1e-7:raise ValueError('flat-field channel depends on undeclared inputs')
    return (low+high)/2


def _uniform_domains(samples,value,domains):
    lanes=dict(domains)
    for name,sample in samples:
        texture=str(sample.detail.get('canonical_texture'))
        if texture not in FEEDBACK_TEXTURES:raise ValueError('non-feedback texture '+texture+' has no uniform-content value')
        for index,lane in enumerate('xyz'):lanes[name+'.'+lane]=[value[index],value[index]]
        lanes[name+'.w']=[ALPHA,ALPHA]
    return lanes


def flat_field(stages,fps=None,start=(0.,0.,0.),steps=STEPS):
    """Iterate the warp flat-field map and evaluate the composite at its state.

    ``stages`` maps 'warp'/'composite' to (projected RGB graphs, samples, domains)
    as built by the nonlinear colour module.
    """
    result={'policy':POLICY,'status':'unknown','start_rgb':list(start),'steps':steps,'trajectory_checkpoints':[],
        'state':None,'state_rgb':None,'cycle_period_steps':None,'settle_steps':None,'settle_seconds':None,
        'composite_rgb_at_state':None,'composite_rgb_at_start':None,'flat_region_behaviour':None,
        'storage':'clamp to [0,1], round to RGBA8 each step','alpha_lane_assumed':ALPHA,
        'actual_displayed_background_verified':False,'uses_rendered_images':False,'uses_equation_execution':False,
        'unknown_reasons':[],
        'conditions':['Uniform content: every main/blur sample returns the same per-channel value at every coordinate',
            'Warp RGB is the projected source graph with samples replaced by that value and alpha lane 1; other inputs at declared values',
            'Nominal arithmetic then clamp and RGBA8 rounding each step; native float32/mediump arithmetic is not reproduced',
            'Drawn elements, gradients, edges, advection and blur differences change real content away from this flat-field model']}
    try:
        warp=stages.get('warp')
        if warp is None:raise ValueError('no projected warp stage')
        graphs,samples,domains=warp
        state=[float(v) for v in start];seen={};history=[]
        for step in range(steps+1):
            key=tuple(int(round(v*255)) for v in state)
            if key in seen:
                first=seen[key];period=step-first
                result.update(cycle_period_steps=period,settle_steps=first,state_rgb=[k/255 for k in key])
                result['state']='fixed_point' if period==1 else 'cycle'
                break
            seen[key]=step;history.append(key)
            if step in (0,1,10,30,100,300,steps):result['trajectory_checkpoints'].append({'step':step,'rgb':[k/255 for k in key]})
            if step==steps:break
            lanes=_uniform_domains(samples,state,domains)
            raw=[_point(graph,lanes) for graph in graphs]
            state=[min(1.,max(0.,round(min(1.,max(0.,v))*255)/255)) for v in raw]
        else:
            pass
        if result['state'] is None:
            result.update(state='not_settled_within_steps',state_rgb=[k/255 for k in history[-1]])
        if fps and result['settle_steps'] is not None:result['settle_seconds']=result['settle_steps']/fps
        rgb=result['state_rgb']
        result['flat_region_behaviour']=('decays_to_black' if max(rgb)<=2/255 else
            'saturates_to_white' if min(rgb)>=253/255 else 'settles_on_colour' if result['state']=='fixed_point' else
            'cycles' if result['state']=='cycle' else 'still_changing')
        composite=stages.get('composite')
        if composite is not None:
            graphs_c,samples_c,domains_c=composite
            for name,value in (('composite_rgb_at_state',rgb),('composite_rgb_at_start',list(start))):
                try:
                    lanes=_uniform_domains(samples_c,value,domains_c)
                    result[name]=[min(1.,max(0.,_point(graph,lanes))) for graph in graphs_c]
                except (ValueError,ArithmeticError) as error:result['unknown_reasons'].append('composite: '+str(error))
        result['status']='conditional_flat_field_state'
    except (ValueError,ArithmeticError,RecursionError) as error:
        result['unknown_reasons'].append(str(error))
    return result
