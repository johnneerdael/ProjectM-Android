"""Scalar palette maps: stage RGB as a function of one sampled scalar.

Many shaders reduce sampled colours to one scalar s (a luminance, a blend of
blurs, a contrast-enhanced value) and then build RGB as f(s). When every path
from the projected RGB channels to the sampled inputs passes through one common
scalar node, the stage output is exactly a palette f(s). This module finds that
node, bounds s from the declared unit sample domains and evaluates f at points
across the range with the same nominal value arithmetic used elsewhere, so
translator semantics (abs/domain power lowering, clamps) are kept. Colours are
reported raw and clamped to [0,1] for the declared normalized output. Other
inputs (time, audio, q) are held at declared domains; when they change the
palette, colours become intervals and the record says so.

The palette describes how displayed colour depends on content; it does not
say which s values actually occur on screen.
"""
import colorsys
import math

from shader_fields import Field

POLICY='source-scalar-palette-map-v1'
POINTS=33
HUE_BANDS={'red':((0,15),(345,360)),'orange':((15,45),),'yellow':((45,75),),
           'green':((75,165),),'cyan':((165,195),),'blue':((195,255),),
           'purple':((255,285),),'pink':((285,345),)}


def _family(rgb):
    hue,saturation,value=colorsys.rgb_to_hsv(*rgb)
    if value<.02 or saturation<.08:return 'grayscale'
    degrees=hue*360
    return next(name for name,bands in HUE_BANDS.items() if any(a<=degrees<b for a,b in bands))


def _walk(node,seen=None):
    seen=set() if seen is None else seen
    stack=[node]
    while stack:
        current=stack.pop()
        if id(current) in seen:continue
        seen.add(id(current));yield current
        stack.extend(current.args)


def _depends(node,names,memo):
    key=id(node)
    if key in memo:return memo[key]
    if node.op=='input':value=node.detail.get('name') in names
    else:value=any(_depends(arg,names,memo) for arg in node.args)
    memo[key]=value
    return value


def _replace(node,target,replacement,memo):
    if node is target:return replacement
    key=id(node)
    if key in memo:return memo[key]
    value=node if not node.args else Field(node.op,tuple(_replace(a,target,replacement,memo) for a in node.args),node.dtype,node.detail)
    memo[key]=value
    return value


def _candidates(channels,sample_names):
    """Scalar float nodes depending on samples, nearest the outputs first."""
    memo={};order=[];seen=set()
    frontier=list(channels)
    while frontier and len(order)<512:
        following=[]
        for node in frontier:
            if id(node) in seen:continue
            seen.add(id(node))
            if node.dtype=='float' and _depends(node,sample_names,memo) and node.op!='input':order.append(node)
            following.extend(node.args)
        frontier=following
    return order


def scalar_palette(channels,domains,sample_names,*,points=POINTS):
    """Return the palette record for three projected scalar RGB channel graphs."""
    from source_control_bounds import scalar_value_envelope
    result={'policy':POLICY,'status':'unknown','scalar_range':None,'samples':[],'hue_families':[],
        'other_inputs_change_palette':None,'colours_are_intervals':False,'scalar_expression_root_op':None,
        'black_content_scalar':None,'white_content_scalar':None,'black_content_rgb':None,'white_content_rgb':None,
        'black_content_hue_family':None,'white_content_hue_family':None,'occurring_scalar_values':None,
        'actual_displayed_palette_verified':False,'uses_shader_execution':False,'uses_rendered_images':False,
        'unknown_reasons':[],
        'conditions':['Every projected RGB path to sampled inputs passes through the reported scalar; RGB is f(scalar) exactly in nominal arithmetic',
            'Scalar range assumes independent sampled RGBA components in [0,1]; actual content occupies an unknown subset',
            'Other inputs are held within declared domains; native float32 rounding and storage are not modelled',
            'Clamped colours assume normalized fixed-point output; later composition and display remain separate']}
    try:
        if len(channels)!=3 or any(c.op=='unknown' for c in channels):raise ValueError('three resolved RGB channels are required')
        sample_names=set(sample_names)
        if not any(_depends(c,sample_names,{}) for c in channels):
            result['status']='no_sample_dependence';return result
        chosen=None
        for candidate in _candidates(channels,sample_names):
            marker=Field('input',dtype='float',detail={'name':':palette-scalar'})
            replaced=[_replace(c,candidate,marker,{}) for c in channels]
            memo={}
            if not any(_depends(r,sample_names,memo) for r in replaced):
                chosen=(candidate,replaced);break
        if chosen is None:
            result['status']='multiple_independent_sample_paths';return result
        candidate,replaced=chosen
        result['scalar_expression_root_op']=candidate.op
        span=scalar_value_envelope(candidate,input_domains=domains).get('nominal_value_range')
        if span is None or not all(math.isfinite(v) for v in span):raise ValueError('palette scalar range is unbounded')
        low,high=float(span[0]),float(span[1])
        result['scalar_range']=[low,high]
        for label,value in (('black',0.),('white',1.)):
            fixed={**domains,**{n:[value,value] for n in sample_names}}
            point=scalar_value_envelope(candidate,input_domains=fixed).get('nominal_value_range')
            result[label+'_content_scalar']=None if point is None else [float(point[0]),float(point[1])]
            colour=[scalar_value_envelope(c,input_domains=fixed).get('nominal_value_range') for c in channels]
            if all(span is not None for span in colour):
                rgb=[min(1.,max(0.,(float(a)+float(b))/2)) for a,b in colour]
                result[label+'_content_rgb']=rgb;result[label+'_content_hue_family']=_family(rgb)
        other=set()
        for r in replaced:
            other|={n.detail.get('name') for n in _walk(r) if n.op=='input'}-{':palette-scalar'}
        result['other_inputs_change_palette']=bool(other)
        families={}
        for index in range(points):
            s=low+(high-low)*index/(points-1) if points>1 else low
            raw=[]
            for r in replaced:
                value=scalar_value_envelope(r,input_domains={**domains,':palette-scalar':[s,s]}).get('nominal_value_range')
                if value is None:raise ValueError('palette channel unbounded at scalar '+format(s,'.4g'))
                raw.append([float(value[0]),float(value[1])])
            interval=any(abs(a-b)>1e-9 for a,b in raw)
            result['colours_are_intervals']|=interval
            mid=[(a+b)/2 for a,b in raw]
            clamped=[min(1.,max(0.,v)) for v in mid]
            family=_family(clamped)
            families[family]=families.get(family,0)+1
            result['samples'].append({'scalar':s,'raw_rgb_interval':raw,'clamped_rgb':clamped,'hue_family':family})
        result['hue_families']=[name for name,_ in sorted(families.items(),key=lambda item:-item[1])]
        result['status']='conditional_scalar_palette'
    except (ValueError,RecursionError,OverflowError,ArithmeticError) as error:
        result['unknown_reasons'].append(str(error))
    return result
