"""Per-point colour distribution of custom waves over the authored sample grid.

A custom wave evaluates its per-point code once per point with
``sample = j/(N-1)`` for j = 0..N-1 (MilkDrop2 milkdropfs.cpp custom-wave loop;
N is the per-frame sample count, at most 512). When the per-point r, g, b and a
graphs depend only on ``sample``, ``time`` and declared scalar inputs (audio
bands), their values over the finite sample grid are a closed-form function:
this module enumerates that grid at declared times with inputs held at their
declared midpoints and reports the colour distribution (mean, hue-family
shares, saturation). Hashed formulas such as ``((sample*5454)%100)*.01`` thus
become a measured spread instead of an unresolved [0,1] box.

Native conversion follows the existing custom-wave colour model: signed modulo
by 256/255, then clamp to [0,1]. Points written from persistent per-point
state, random calls or waveform values are unresolved; the record then says
which inputs blocked it. This is a source distribution of authored point
colours, not displayed coverage, additive accumulation or visible dominance.

When the per-point x and y graphs are closed-form in the same inputs, the
record also keeps the serialised colour/position programs and the source
position bounds, so an SDK can place the point cloud at any declared time.
Positions are MilkDrop source coordinates (x right, y down from the top, both
nominally in [0,1]); projection, dots/thick drawing and smoothing are separate.
"""
import colorsys
import itertools
import math

from time_expression import evaluate_inputs,hue_family,input_names

POLICY='source-custom-point-colour-distribution-v1'
PERIOD=256/255
TIMES=(0.,10.,20.,30.,40.,50.,60.)
MAX_REPRESENTATIVE=48


def _native(value):
    return min(1.,max(0.,math.fmod(math.fmod(value,PERIOD)+PERIOD,PERIOD)))


FPS=30.


# Seed of the generator that draws projectm-eval rand() calls in stochastic recurrences and point graphs
# for the exported statistics: a seeded draw from the authored distribution, not the engine's stream.
STOCHASTIC_SEED=20261012


def _names_of(graph):
    """Inputs of a graph, rand calls allowed (drawn from a generator); None for unsupported operations."""
    from eel_memory import input_names as names
    return names(graph,stochastic=True)


def _stochastic(graph):
    return isinstance(graph,dict) and any(node.get('op')=='rand' for node in graph.get('nodes') or [])


def _evaluate(graph,values,rng=None):
    """Scalar value of a graph; rand calls draw from rng (projectm-eval: uniform on [0, max(1, floor(x))]).

    Graphs inside time_expression's operation set keep its scalar evaluator; others (rand, bitwise,
    memory, loops) use eel_memory.
    """
    from time_expression import SUPPORTED
    if _stochastic(graph) or any(node.get('op') not in SUPPORTED for node in graph.get('nodes') or []):
        if _stochastic(graph) and rng is None:raise ValueError('random call needs a generator')
        import numpy as np
        from eel_memory import evaluate_np
        return float(np.asarray(evaluate_np(graph,values,rng)).reshape(-1)[0])
    return evaluate_inputs(graph,values)


def _complete(expression,values,base):
    # 'init:<section>:<name>' reads the init-time value of <name>; any other absent input is 0.
    missing=(_names_of(expression) or set())-set(values)
    return {**values,**{name:float(base.get(str(name).rsplit(':',1)[-1],0.)) for name in missing}}


def initial_state(recurrence,inputs,rng=None):
    """Wave state after its init code, from init-time inputs (bands, time 0)."""
    base={**inputs,'time':0.,'frame':0.}
    return {name:_evaluate(entry['initial'],_complete(entry['initial'],base,base),rng) for name,entry in recurrence['state'].items()}


def step_state(recurrence,state,inputs,time,frame,rng=None):
    """End-of-frame state from the start-of-frame state and this frame's inputs."""
    prefix=recurrence['state_input_prefix']
    values={**inputs,'time':float(time),'frame':float(frame),**{prefix+n:v for n,v in state.items()}}
    return {name:_evaluate(entry['update'],_complete(entry['update'],values,values),rng) for name,entry in recurrence['state'].items()}


def state_inputs(recurrence,state):
    """Point-graph inputs for a start-of-frame state."""
    return {recurrence['state_input_prefix']+n:v for n,v in state.items()}


def recurrence_trajectory(recurrence,held,times,fps=FPS,rng=None):
    """Start-of-frame state values at the given source times, stepping the recurrence from t=0.

    Frame k (k>=0) renders at source time (k+1)/fps; the state read by frame k is the value after
    k updates. Inputs other than the wave's own state, time and frame are taken from held.
    """
    state=initial_state(recurrence,held,rng)
    frames=sorted({max(0,int(round(t*fps))-1) for t in times});out={};k=0
    for target in frames:
        while k<target:
            state=step_state(recurrence,state,held,(k+1)/fps,k,rng);k+=1
        out[target]=state_inputs(recurrence,state)
    return {t:out[max(0,int(round(t*fps))-1)] for t in times}


def waveform_point_values(waveform,count,frame):
    """value1/value2 per point for one frame from the declared reference PCM windows."""
    from builtin_wave_geometry import custom_wave_values,reference_windows
    windows=_WINDOWS.get('data')
    if windows is None:windows=_WINDOWS['data']=reference_windows()
    window=windows[int(frame)%len(windows)]
    params=waveform['params']
    return custom_wave_values(window,sample_count=count,scaling=params['scaling'],wave_scale=params['wave_scale'],
                              smoothing=params['smoothing'],sep=params['sep'])


_WINDOWS={}


def point_state_series(point_recurrence,carry,inputs_at,rng=None):
    """Start-of-point values for each point and the carry-out after the last point.

    inputs_at(j) gives point j's inputs (sample, value1/2, time, bands, frame state). rng draws the
    rand calls of a stochastic recurrence, one draw per call and point as in the engine.
    """
    prefix=point_recurrence['state_input_prefix'];programs=point_recurrence['state']
    state=dict(carry);series=[]
    for j in itertools.count():
        values=inputs_at(j)
        if values is None:break
        series.append(dict(state))
        current={**values,**{prefix+n:v for n,v in state.items()}}
        state={name:_evaluate(entry['update'],_complete(entry['update'],current,current),rng) for name,entry in programs.items()}
    return series,state


def point_colour_distribution(programs,sample_count,held_inputs,*,times=TIMES,positions=None,recurrence=None,waveform=None,
                              point_recurrence=None):
    """Return the distribution record for serialised per-point r,g,b,a graphs.

    recurrence (optional) is the wave's per-frame state recurrence; its state inputs are then
    resolved by stepping it from t=0 under the held inputs, and the record keeps it for SDKs.
    waveform (optional) {'params': scaling/wave_scale/smoothing/sep} resolves value1/value2 from the
    declared reference PCM windows (oscilloscope mode); the record keeps the parameters.
    """
    result={'policy':POLICY,'status':'unknown','sample_count':None,'times_s':None,'held_inputs':{},
            'depends_on_sample':None,'depends_on_time':None,'mean_rgb':None,'alpha_weighted_mean_rgb':None,
            'mean_alpha':None,'mean_saturation':None,'hue_family_shares':{},'representative_points':[],
            'unresolved_inputs':[],'unknown_reasons':[],'uses_equation_execution':False,'uses_rendered_images':False,
            'actual_displayed_palette_verified':False,'positions_closed_form':False,'position_bounds':None,
            'programs':None,
            'conditions':['sample = j/(N-1) over the authored per-frame sample count; per-frame code that changes N is not modelled',
                          'declared scalar inputs are held at their midpoints; time is sampled at the listed source times',
                          'native signed modulo by 256/255 then clamp; additive accumulation, coverage and visibility are separate']}
    try:
        count=int(sample_count) if sample_count is not None else None
        if count is None or not 1<=count<=512:raise ValueError('authored sample count unresolved')
        if any(p is None for p in programs.values()):raise ValueError('per-point colour graph unresolved')
        names=set()
        for name,program in programs.items():
            inputs=_names_of(program)
            if inputs is None:raise ValueError(name+' graph contains an unsupported operation')
            names|=inputs
        graphs=[*programs.values(),*[g for g in (positions or {}).values() if g]]
        for source in (recurrence,point_recurrence):
            for entry in ((source or {}).get('state') or {}).values():graphs+=[entry['initial'],entry['update']]
        stochastic=any(_stochastic(graph) for graph in graphs)
        rng=None
        if stochastic:
            import numpy as np
            rng=np.random.default_rng(STOCHASTIC_SEED)
        state_names=set()
        if recurrence:
            prefix=recurrence['state_input_prefix'];state_names={prefix+n for n in recurrence['state']}
            for entry in recurrence['state'].values():
                for graph in (entry['initial'],entry['update']):
                    found=_names_of(graph)
                    if found is None:raise ValueError('wave recurrence contains an unsupported operation')
                    names|={n for n in found if not (isinstance(n,str) and n.startswith('init:'))}-{'frame'}
            for name in (positions or {}).values():
                found=_names_of(name) if name else None
                if found:names|=found
        held={name:(float(span[0])+float(span[1]))/2 for name,span in held_inputs.items()
              if name in names and isinstance(span,(list,tuple)) and len(span)==2}
        wave_names={'value1','value2'} if waveform else set()
        point_names=set()
        if point_recurrence:
            point_names={point_recurrence['state_input_prefix']+n for n in point_recurrence['state']}
            for entry in point_recurrence['state'].values():
                for graph in (entry['initial'],entry['update']):
                    found=_names_of(graph)
                    if found is None:raise ValueError('point recurrence contains an unsupported operation')
                    names|={n for n in found if not (isinstance(n,str) and n.startswith('init:'))}
        blocked=sorted(map(str,names-{'sample','time'}-set(held)-state_names-wave_names-point_names))
        # Plain names left in point graphs come from inlined main per-frame graphs (Q values): a consumer
        # resolves them by stepping the exported frame program, so the programs are kept without statistics.
        frame_inputs=[n for n in blocked if ':' not in n or n.startswith('state:per_frame_:')]
        if blocked and len(frame_inputs)<len(blocked):
            result['unresolved_inputs']=blocked
            raise ValueError('per-point colour depends on unresolved inputs')
        if frame_inputs:
            start=recurrence_trajectory(recurrence,held,(0.,),rng=rng) if state_names else None
            result.update(_positions(positions,count,held,(0.,),start,waveform if wave_names&_names(positions) else None,
                                     point_recurrence if point_names else None,rng))
            if not result.get('positions_closed_form'):
                result['unresolved_inputs']=blocked
                raise ValueError('per-point colour depends on unresolved inputs')
            result['frame_inputs']=sorted(set(frame_inputs)|set(result.get('frame_inputs') or []))
            result.update(status='frame_state_point_colours',sample_count=count,held_inputs=held,programs={**programs,**positions},stochastic=stochastic)
            if waveform and (wave_names&(names|_names(positions))):
                result['waveform_inputs']={**waveform,'source':'declared reference PCM windows (oscilloscope value1/value2)'}
            if point_names:result['point_recurrence']=point_recurrence
            if state_names:result['frame_recurrence']=recurrence
            result['conditions'].append('colours read main per-frame state; statistics need its stepped values, so only the programs are exported')
            return result
        trajectory=recurrence_trajectory(recurrence,held,times,rng=rng) if state_names else None
        result['held_inputs']=held;result['sample_count']=count
        result['depends_on_sample']='sample' in names;result['depends_on_time']='time' in names
        uses_wave=bool(wave_names&names)
        grid=times if 'time' in names or state_names or uses_wave else (0.,)
        result['times_s']=list(grid)
        points=[]
        for time in grid:
            wave=waveform_point_values(waveform,count,max(0,int(round(time*FPS))-1)) if uses_wave else None
            def point_inputs(j,time=time,wave=wave):
                if j>=count:return None
                values={**held,**(trajectory[time] if trajectory else {}),'time':time,'sample':j/(count-1) if count>1 else 0.}
                if wave:values.update(value1=float(wave[0][j]),value2=float(wave[1][j]))
                return values
            pstate=None
            if point_recurrence:
                carry=initial_state({'state':point_recurrence['state']},held,rng)
                pstate,_=point_state_series(point_recurrence,carry,point_inputs,rng)
            for j in range(count):
                values=point_inputs(j)
                if pstate:values.update({point_recurrence['state_input_prefix']+n:v for n,v in pstate[j].items()})
                rgba=[_native(_evaluate(programs[name],values,rng)) for name in 'rgba']
                points.append(rgba)
        total=len(points);alpha=sum(p[3] for p in points)
        result['mean_rgb']=[sum(p[i] for p in points)/total for i in range(3)]
        result['mean_alpha']=alpha/total
        result['alpha_weighted_mean_rgb']=[sum(p[i]*p[3] for p in points)/alpha for i in range(3)] if alpha>0 else None
        result['mean_saturation']=sum(colorsys.rgb_to_hsv(*p[:3])[1] for p in points)/total
        shares={}
        for p in points:
            family=hue_family(p[:3]);shares[family]=shares.get(family,0)+1/total
        result['hue_family_shares']={k:round(v,4) for k,v in sorted(shares.items(),key=lambda item:-item[1])}
        stride=max(1,total//MAX_REPRESENTATIVE)
        result['representative_points']=[[round(v,4) for v in p] for p in points[::stride][:MAX_REPRESENTATIVE]]
        result['status']='closed_form_point_colours'
        result.update(_positions(positions,count,held,grid,trajectory,waveform if uses_wave or wave_names else None,point_recurrence,rng))
        result['stochastic']=stochastic
        if stochastic:
            result['conditions'].append('rand calls are seeded draws from projectm-eval\'s uniform distribution (one per call and point), not the engine\'s random stream')
        if result['positions_closed_form']:result['programs']={**programs,**positions}
        if result['positions_closed_form'] and waveform and (uses_wave or (wave_names&_names(positions))):
            result['waveform_inputs']={**waveform,'source':'declared reference PCM windows (oscilloscope value1/value2)'}
            result['conditions'].append('value1/value2 from the declared reference PCM windows, frame index wrapped')
        if point_names:
            result['point_recurrence']=point_recurrence
            result['conditions'].append('per-point state evaluated point by point from its initial value at each sampled time')
        if state_names:
            result['frame_recurrence']=recurrence
            result['conditions'].append('wave per-frame state stepped from t=0 at 30 fps under the held inputs')
    except (ValueError,KeyError,TypeError,RecursionError) as error:
        result['unknown_reasons'].append(str(error))
    return result


def _names(graphs):
    found=set()
    for graph in (graphs or {}).values():
        names=input_names(graph) if graph else None
        if names:found|=names
    return found


def _positions(positions,count,held,grid,trajectory=None,waveform=None,point_recurrence=None,rng=None):
    """Source x/y bounds when the per-point position graphs are closed-form (rand drawn from rng)."""
    if not positions or any(positions.get(name) is None for name in 'xy'):return {}
    names=set()
    for name in 'xy':
        inputs=_names_of(positions[name])
        if inputs is None:return {}
        names|=inputs
    state=set(next(iter(trajectory.values()))) if trajectory else set()
    wave_names={'value1','value2'} if waveform else set()
    point_names={point_recurrence['state_input_prefix']+n for n in point_recurrence['state']} if point_recurrence else set()
    extra=names-{'sample','time'}-set(held)-state-wave_names-point_names
    if extra:
        # Inlined main per-frame graphs (Q values) leave plain per-frame state and audio names; they are
        # resolved per frame by a consumer stepping the exported frame program (start-of-frame values;
        # names never written read 0). Other scoped state is not resolvable here.
        if any(not isinstance(n,str) or (':' in n and not n.startswith('state:per_frame_:')) for n in extra):return {}
        return {'positions_closed_form':True,'position_bounds':None,'frame_inputs':sorted(extra)}
    uses_wave=bool(names&wave_names)
    try:
        xs=[];ys=[]
        for time in (grid if 'time' in names or state or uses_wave else (0.,)):
            wave=waveform_point_values(waveform,count,max(0,int(round(time*FPS))-1)) if uses_wave else None
            def point_inputs(j,time=time,wave=wave):
                if j>=count:return None
                values={**held,**(trajectory[time] if trajectory else {}),'time':time,'sample':j/(count-1) if count>1 else 0.}
                if wave:values.update(value1=float(wave[0][j]),value2=float(wave[1][j]))
                return values
            pstate=point_state_series(point_recurrence,initial_state({'state':point_recurrence['state']},held,rng),point_inputs,rng)[0] if point_names else None
            for j in range(count):
                values=point_inputs(j)
                if pstate:values.update({point_recurrence['state_input_prefix']+n:v for n,v in pstate[j].items()})
                xs.append(_evaluate(positions['x'],values,rng));ys.append(_evaluate(positions['y'],values,rng))
    except ValueError:return {}
    return {'positions_closed_form':True,'position_bounds':{'x':[min(xs),max(xs)],'y':[min(ys),max(ys)]}}
