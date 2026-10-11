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


def point_colour_distribution(programs,sample_count,held_inputs,*,times=TIMES,positions=None):
    """Return the distribution record for serialised per-point r,g,b,a graphs."""
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
        held={name:(float(span[0])+float(span[1]))/2 for name,span in held_inputs.items()
              if name in names and isinstance(span,(list,tuple)) and len(span)==2}
        blocked=sorted(map(str,names-{'sample','time'}-set(held)))
        if blocked:
            result['unresolved_inputs']=blocked
            raise ValueError('per-point colour depends on unresolved inputs')
        result['held_inputs']=held;result['sample_count']=count
        result['depends_on_sample']='sample' in names;result['depends_on_time']='time' in names
        grid=times if 'time' in names else (0.,)
        result['times_s']=list(grid)
        points=[]
        for time in grid:
            for j in range(count):
                values={**held,'time':time,'sample':j/(count-1) if count>1 else 0.}
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
        result.update(_positions(positions,count,held,grid))
        if result['positions_closed_form']:result['programs']={**programs,**positions}
    except (ValueError,KeyError,TypeError,RecursionError) as error:
        result['unknown_reasons'].append(str(error))
    return result


def _positions(positions,count,held,grid):
    """Source x/y bounds when the per-point position graphs are closed-form."""
    if not positions or any(positions.get(name) is None for name in 'xy'):return {}
    names=set()
    for name in 'xy':
        inputs=input_names(positions[name])
        if inputs is None:return {}
        names|=inputs
    if names-{'sample','time'}-set(held):return {}
    try:
        xs=[];ys=[]
        for time in (grid if 'time' in names else (0.,)):
            for j in range(count):
                values={**held,'time':time,'sample':j/(count-1) if count>1 else 0.}
                xs.append(evaluate_inputs(positions['x'],values));ys.append(evaluate_inputs(positions['y'],values))
    except ValueError:return {}
    return {'positions_closed_form':True,'position_bounds':{'x':[min(xs),max(xs)],'y':[min(ys),max(ys)]}}
