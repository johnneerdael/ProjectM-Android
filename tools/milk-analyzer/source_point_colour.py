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
import math

from time_expression import evaluate_inputs,hue_family,input_names

POLICY='source-custom-point-colour-distribution-v1'
PERIOD=256/255
TIMES=(0.,10.,20.,30.,40.,50.,60.)
MAX_REPRESENTATIVE=48


def _native(value):
    return min(1.,max(0.,math.fmod(math.fmod(value,PERIOD)+PERIOD,PERIOD)))


FPS=30.


def _complete(expression,values,base):
    # 'init:<section>:<name>' reads the init-time value of <name>; any other absent input is 0.
    missing=(input_names(expression) or set())-set(values)
    return {**values,**{name:float(base.get(str(name).rsplit(':',1)[-1],0.)) for name in missing}}


def initial_state(recurrence,inputs):
    """Wave state after its init code, from init-time inputs (bands, time 0)."""
    base={**inputs,'time':0.,'frame':0.}
    return {name:evaluate_inputs(entry['initial'],_complete(entry['initial'],base,base)) for name,entry in recurrence['state'].items()}


def step_state(recurrence,state,inputs,time,frame):
    """End-of-frame state from the start-of-frame state and this frame's inputs."""
    prefix=recurrence['state_input_prefix']
    values={**inputs,'time':float(time),'frame':float(frame),**{prefix+n:v for n,v in state.items()}}
    return {name:evaluate_inputs(entry['update'],_complete(entry['update'],values,values)) for name,entry in recurrence['state'].items()}


def state_inputs(recurrence,state):
    """Point-graph inputs for a start-of-frame state."""
    return {recurrence['state_input_prefix']+n:v for n,v in state.items()}


def recurrence_trajectory(recurrence,held,times,fps=FPS):
    """Start-of-frame state values at the given source times, stepping the recurrence from t=0.

    Frame k (k>=0) renders at source time (k+1)/fps; the state read by frame k is the value after
    k updates. Inputs other than the wave's own state, time and frame are taken from held.
    """
    state=initial_state(recurrence,held)
    frames=sorted({max(0,int(round(t*fps))-1) for t in times});out={};k=0
    for target in frames:
        while k<target:
            state=step_state(recurrence,state,held,(k+1)/fps,k);k+=1
        out[target]=state_inputs(recurrence,state)
    return {t:out[max(0,int(round(t*fps))-1)] for t in times}


def point_colour_distribution(programs,sample_count,held_inputs,*,times=TIMES,positions=None,recurrence=None):
    """Return the distribution record for serialised per-point r,g,b,a graphs.

    recurrence (optional) is the wave's per-frame state recurrence; its state inputs are then
    resolved by stepping it from t=0 under the held inputs, and the record keeps it for SDKs.
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
            inputs=input_names(program)
            if inputs is None:raise ValueError(name+' graph contains an unsupported operation')
            names|=inputs
        state_names=set()
        if recurrence:
            prefix=recurrence['state_input_prefix'];state_names={prefix+n for n in recurrence['state']}
            for entry in recurrence['state'].values():
                for graph in (entry['initial'],entry['update']):
                    found=input_names(graph)
                    if found is None:raise ValueError('wave recurrence contains an unsupported operation')
                    names|={n for n in found if not (isinstance(n,str) and n.startswith('init:'))}-{'frame'}
            for name in (positions or {}).values():
                found=input_names(name) if name else None
                if found:names|=found
        held={name:(float(span[0])+float(span[1]))/2 for name,span in held_inputs.items()
              if name in names and isinstance(span,(list,tuple)) and len(span)==2}
        blocked=sorted(map(str,names-{'sample','time'}-set(held)-state_names))
        if blocked:
            result['unresolved_inputs']=blocked
            raise ValueError('per-point colour depends on unresolved inputs')
        trajectory=recurrence_trajectory(recurrence,held,times) if state_names else None
        result['held_inputs']=held;result['sample_count']=count
        result['depends_on_sample']='sample' in names;result['depends_on_time']='time' in names
        grid=times if 'time' in names or state_names else (0.,)
        result['times_s']=list(grid)
        points=[]
        for time in grid:
            for j in range(count):
                values={**held,**(trajectory[time] if trajectory else {}),'time':time,'sample':j/(count-1) if count>1 else 0.}
                rgba=[_native(evaluate_inputs(programs[name],values)) for name in 'rgba']
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
        result.update(_positions(positions,count,held,grid,trajectory))
        if result['positions_closed_form']:result['programs']={**programs,**positions}
        if state_names:
            result['frame_recurrence']=recurrence
            result['conditions'].append('wave per-frame state stepped from t=0 at 30 fps under the held inputs')
    except (ValueError,KeyError,TypeError,RecursionError) as error:
        result['unknown_reasons'].append(str(error))
    return result


def _positions(positions,count,held,grid,trajectory=None):
    """Source x/y bounds when the per-point position graphs are closed-form."""
    if not positions or any(positions.get(name) is None for name in 'xy'):return {}
    names=set()
    for name in 'xy':
        inputs=input_names(positions[name])
        if inputs is None:return {}
        names|=inputs
    state=set(next(iter(trajectory.values()))) if trajectory else set()
    if names-{'sample','time'}-set(held)-state:return {}
    try:
        xs=[];ys=[]
        for time in (grid if 'time' in names or state else (0.,)):
            for j in range(count):
                values={**held,**(trajectory[time] if trajectory else {}),'time':time,'sample':j/(count-1) if count>1 else 0.}
                xs.append(evaluate_inputs(positions['x'],values));ys.append(evaluate_inputs(positions['y'],values))
    except ValueError:return {}
    return {'positions_closed_form':True,'position_bounds':{'x':[min(xs),max(xs)],'y':[min(ys),max(ys)]}}
