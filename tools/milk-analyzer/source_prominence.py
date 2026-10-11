"""Conditional source support and transfer bounds, without display simulation.

Areas are continuous viewport fractions. They describe potential source influence,
not raster coverage or visible contrast; the latter always permits zero.
"""
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np

POLICY='source-effect-prominence-v1'
HISTORY={'main','blur1','blur2','blur3'}
MODEL_SOURCE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _clip_polygon(vertices):
    """Sutherland-Hodgman clipping in NDC; carried attributes stay affine."""
    for axis,bound,sign in ((0,-1,1),(0,1,-1),(1,-1,1),(1,1,-1)):
        if not vertices:break
        output=[];previous=vertices[-1];previous_inside=sign*(previous[axis]-bound)>=0
        for current in vertices:
            inside=sign*(current[axis]-bound)>=0
            if inside!=previous_inside:
                t=(bound-previous[axis])/(current[axis]-previous[axis])
                intersection=[a+t*(b-a) for a,b in zip(previous,current)]
                intersection[axis]=bound;output.append(intersection)
            if inside:output.append(current)
            previous=current;previous_inside=inside
        vertices=output
    return vertices


def _polygon_area(vertices):
    if len(vertices)<3:return 0.
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(vertices,vertices[1:]+vertices[:1])))/8


def _instance_controls(controls,index):
    """Substitute a native instance index in source algebra, without running EEL."""
    from shader_fields import Field
    memo={}
    def substitute(node,depth=0):
        if depth>64 or len(memo)>4096:raise ValueError('instance substitution budget exceeded')
        if id(node) in memo:return memo[id(node)]
        value=Field('constant',detail={'value':float(index)}) if node.op=='input' and node.detail.get('name')=='instance' else \
            Field(node.op,tuple(substitute(arg,depth+1) for arg in node.args),node.dtype,node.detail)
        memo[id(node)]=value;return value
    return {name:substitute(field) for name,field in controls.items()}


def _shape_controls(analysis):
    """Retain configured shapes filtered from family output by zero/disconnection.

    Reuse the producer's equation assembler and its native per-frame reset contract.
    """
    from effect_families import SHAPE,READONLY,_constant,Field,_EEL,select_equation
    from scene_equations import _scalar
    result=dict(getattr(analysis,'component_controls',{}))
    if not hasattr(analysis,'main'):return result
    def assemble(prefix,environment):
        selected=select_equation(analysis.sections.get(prefix),prefix,policy=analysis.policy)
        model=_EEL(environment,equation_phase=prefix)
        if selected['compile_status']=='accepted' and selected['tree_status']=='parsed':model.lower(selected['tree'])
        elif selected['compile_status']!='omitted':
            model.environment={name:Field('unknown',detail={'reason':'active equation tree/loading is unresolved'}) for name in environment}
        return model
    for index in range(4):
        identity='shape_'+str(index);prefix='shapecode_'+str(index)+'_'
        if identity in result or not _scalar(analysis.values,prefix+'enabled',0,'bool'):continue
        env={name:_constant(_scalar(analysis.values,prefix+name,default,dtype)) for name,(default,dtype) in SHAPE.items()}
        init_prefix=f'shape_{index}_init'
        init_inputs={**env,**{name:Field('input',detail={'name':'init:'+init_prefix+':'+name})
            for name in (*READONLY,*(f'q{i}' for i in range(1,33)))}}
        init=assemble(init_prefix,init_inputs)
        resets={**{name:Field('input',detail={'name':name}) for name in READONLY},**env,
                'instance':Field('input',detail={'name':'instance'}),
                'thick':_constant(_scalar(analysis.values,prefix+'thickoutline',0,'bool')),
                **{f't{i}':init.environment.get(f't{i}',_constant(0)) for i in range(1,9)},
                **{f'q{i}':analysis.main.get(f'q{i}',Field('unknown')) for i in range(1,33)}}
        frame_prefix=f'shape_{index}_per_frame'
        result[identity]=assemble(frame_prefix,analysis.frame_environment(frame_prefix,init.environment,resets)).environment
    return result


def _value_range(field,domains):
    from source_appearance import _phase_literal
    literal_failure=None
    try:value=_phase_literal(field)
    except (ValueError,RecursionError) as error:
        value=None;literal_failure=str(error)
    if value is not None and math.isfinite(value):return [value,value],None
    from source_control_bounds import scalar_value_envelope
    report=scalar_value_envelope(field,input_domains=domains)
    if literal_failure:
        report={**report,'literal_guard_failure':literal_failure,
                'unknown_reasons':sorted(set(report['unknown_reasons']+[literal_failure]))}
    pair=report['nominal_value_range']
    refinement=report.get('solver_refinement',{})
    refined=refinement.get('nominal_value_range')
    if refinement.get('status')=='bounded' and refined is not None:
        if pair is None or pair[0]<=refined[0]<=refined[1]<=pair[1]:
            pair=refined;report={**report,'used_solver_refinement':True}
    if pair is not None and not all(math.isfinite(v) for v in pair):pair=None
    return pair,report


def _aggregate_shape_support(controls,instances,viewport,domains):
    """Sum unclipped polygon envelopes over the full native instance domain.

    This is a union upper bound, without independence, clipping or overlap credit.
    Unknown positions cannot invalidate the geometric area theorem, but known
    nonfinite native conversions must still prevent transparency certification.
    """
    ranges={};evidence={};unknown=[];invalid=False
    native_domains={**domains,'instance':[0.,float(instances-1)]}
    for name in ('rad','x','y','ang','sides'):
        pair,report=_value_range(controls[name],native_domains)
        ranges[name]=pair
        if report is not None:evidence[name]=report
        if pair is None:continue
        if name=='sides':
            invalid|=not all(-(2**31)-1<v<2**31 for v in pair)
        else:
            values=pair
            if name=='x':values=[2*v-1 for v in pair]
            if name=='y':values=[1-2*v for v in pair]
            with np.errstate(over='ignore',invalid='ignore'):
                invalid|=not all(math.isfinite(float(np.float32(v))) for v in values)
    aspect=min(1.,viewport[1]/viewport[0]);radius=ranges['rad'];sides=ranges['sides']
    if radius is not None and not invalid:
        with np.errstate(over='ignore',invalid='ignore'):
            magnitude=max(abs(float(np.float32(v))) for v in radius)
            projected=[float(np.float32(magnitude*float(np.float32(aspect)))),magnitude]
            for axis,name in enumerate(('x','y')):
                if ranges[name] is None:continue
                center=[float(np.float32(2*v-1 if name=='x' else 1-2*v)) for v in ranges[name]]
                # Individually finite controls can still overflow when native
                # float32 radius offsets are added to the transformed centre.
                invalid|=not all(math.isfinite(float(np.float32(c+sign*projected[axis])))
                    for c in center for sign in (-1,1))
    area=1.;perimeter=4.*instances;summed=None
    if radius is not None and sides is not None and not invalid:
        radius=[float(np.float32(v)) for v in radius]
        magnitude=max(map(abs,radius))
        # n*sin(2*pi/n) increases for native n>=3. The greatest admitted
        # side count therefore bounds every polygon in the whole group.
        n=max(3,min(100,math.trunc(sides[1])))
        # Avoid assuming libm's trig/product rounding encloses ideal geometry.
        # 355/113 > pi; for n>=5 this upper angle is below pi/2. A positive
        # last term of the alternating sin series is an upper enclosure there.
        pi_upper=Fraction(355,113)
        theta=2*pi_upper/n
        sine_upper=Fraction(1) if n<=4 else min(Fraction(1),sum(
            ((-1)**k*theta**(2*k+1)/math.factorial(2*k+1) for k in range(7)),Fraction(0)))
        exact=instances*n*Fraction(magnitude)**2*sine_upper/8*min(Fraction(1),Fraction(viewport[1],viewport[0]))
        try:summed=float(exact)
        except OverflowError:summed=math.inf
        if math.isfinite(summed) and Fraction(summed)<exact:summed=math.nextafter(summed,math.inf)
        if not math.isfinite(summed):summed=None
        area=1. if summed is None else min(1.,summed)
        exact_perimeter=instances*min(Fraction(4),pi_upper*Fraction(magnitude))
        perimeter=float(exact_perimeter)
        if Fraction(perimeter)<exact_perimeter:perimeter=math.nextafter(perimeter,math.inf)
    else:unknown.append('finite aggregate radius/native side-count envelope unresolved')
    if invalid:unknown.append('aggregate geometry has a potentially invalid native conversion')
    unknown.append('aggregate polygon support has no clipping/overlap lower bound')
    return {'area_fraction_interval':[0.,area],'nominal_area_fraction':None,
            'summed_nominal_area_fraction':None,'summed_clipped_area_fraction_upper':summed if summed is not None else float(instances),
            'method':'aggregate polygon area envelope','perimeter_fraction_upper':perimeter,
            'distinct_support_count':instances,'known_invalid_native_domain':invalid,
            'projection_translation_ndc':[1/viewport[0],1/viewport[1]],'aspect_y':aspect,
            'configured_instances':instances,'parameter_ranges':[{'instance_interval':[0,instances-1],
                'radius':radius,'center_x':ranges['x'],'center_y':ranges['y'],
                'side_count':sides,'angle':ranges['ang'],'range_evidence':evidence}]},unknown


def _shape_support(controls,instances,viewport,domains):
    from source_appearance import _phase_literal
    unknown=[];records=[];nominal=0.;nominal_known=True;polygons=[];spans=[];perimeters=[];known_invalid=False
    if viewport is None:return {'area_fraction_interval':[0.,1.],'nominal_area_fraction':None,
        'summed_nominal_area_fraction':None,'method':'unresolved target viewport','parameter_ranges':[]},['positive target viewport dimensions are required']
    aspect=min(1.,viewport[1]/viewport[0])
    if instances<=0:return {'area_fraction_interval':[0.,0.],'nominal_area_fraction':0.,
        'summed_nominal_area_fraction':0.,'method':'no configured instances','parameter_ranges':[]},[]
    if instances>256:return _aggregate_shape_support(controls,instances,viewport,domains)
    for index in range(instances):
        c=_instance_controls(controls,index)
        radius,report=_value_range(c['rad'],domains);x,xr=_value_range(c['x'],domains);y,yr=_value_range(c['y'],domains)
        literals={}
        for name in ('sides','ang'):
            try:literals[name]=_phase_literal(c[name])
            except (ValueError,RecursionError) as error:
                literals[name]=None;unknown.append(name+' literal guard unresolved: '+str(error))
        sides=literals['sides'];angle=literals['ang']
        records.append({'instance':index,'radius':radius,'center_x':x,'center_y':y,
                        'range_evidence':{name:r for name,r in (('rad',report),('x',xr),('y',yr)) if r is not None}})
        if sides is None or not -(2**31)-1<sides<2**31 or radius is None:
            nominal_known=False
            known_invalid|=sides is not None and not -(2**31)-1<sides<2**31
            perimeters.append(4.)
            spans.append([0.,1.]);unknown.append('finite radius envelope and native integer side count unresolved');continue
        sides=max(3,min(100,math.trunc(sides)))
        with np.errstate(over='ignore',invalid='ignore'):
            radius=[float(np.float32(v)) for v in radius]
        if not all(math.isfinite(v) for v in radius):
            nominal_known=False
            known_invalid=True;perimeters.append(4.)
            spans.append([0.,1.]);unknown.append('radius finite float32 conversion unresolved');continue
        magnitude=max(map(abs,radius));area=sides*magnitude*magnitude*math.sin(math.tau/sides)/8*aspect
        if not math.isfinite(area):area=1.
        nominal+=area
        perimeters.append(min(4.,math.pi*magnitude))
        if x is not None and y is not None and x[0]==x[1] and y[0]==y[1] and radius[0]==radius[1] and angle is not None and math.isfinite(angle):
            # Native source converts the centre after its double affine transform,
            # and radius/angle before projection. Ideal trig is explicit below.
            cx=float(np.float32(2*x[0]-1))+1/viewport[0]
            cy=float(np.float32(1-2*y[0]))+1/viewport[1]
            angle=float(np.float32(angle))
            if not all(math.isfinite(v) for v in (cx,cy,angle)):
                known_invalid=True
                spans.append([0.,1.]);unknown.append('center/angle finite float32 conversion unresolved');continue
            polygon=[[cx+radius[0]*math.cos(math.tau*j/sides+angle+math.pi/4)*aspect,
                      cy+radius[0]*math.sin(math.tau*j/sides+angle+math.pi/4)] for j in range(sides)]
            clipped=_clip_polygon(polygon);visible=min(1.,_polygon_area(clipped))
            if abs(visible-1)<1e-12:visible=1.
            spans.append([visible,visible]);polygons.append(clipped)
        else:
            upper=min(1.,area)
            if x is not None and y is not None:
                left=max(-1.,2*x[0]-1+1/viewport[0]-magnitude*aspect);right=min(1.,2*x[1]-1+1/viewport[0]+magnitude*aspect)
                bottom=max(-1.,1-2*y[1]+1/viewport[1]-magnitude);top=min(1.,1-2*y[0]+1/viewport[1]+magnitude)
                upper=min(upper,max(0.,right-left)*max(0.,top-bottom)/4)
            spans.append([0.,upper]);unknown.append('dynamic center/radius/angle: clipped support only has an upper bound')
    exact=len(polygons)==instances and all(p==polygons[0] for p in polygons)
    area_pair=spans[0] if exact else [max(span[0] for span in spans),min(1.,sum(span[1] for span in spans))]
    return {'area_fraction_interval':area_pair,'nominal_area_fraction':nominal/instances if nominal_known else None,
            'summed_nominal_area_fraction':nominal if nominal_known else None,'method':'coincident clipped polygon union' if exact else 'clipped polygon union bounds',
            'summed_clipped_area_fraction_upper':sum(span[1] for span in spans),
            'perimeter_fraction_upper':max(perimeters) if exact else sum(perimeters),
            'distinct_support_count':1 if exact else instances,'known_invalid_native_domain':known_invalid,
            'projection_translation_ndc':[1/viewport[0],1/viewport[1]],
            'aspect_y':aspect,'configured_instances':instances,'parameter_ranges':records},unknown


def _shape_opacity(controls,element,domains):
    from source_appearance import _phase_literal
    from source_material import shape_material
    from source_material_temporal import shape_material_temporal
    from source_fill_envelopes import native_channel_envelope
    material=element.get('material') or shape_material(controls,'')
    if domains:
        from source_material_temporal import shape_scenario_material_envelope
        temporal=shape_scenario_material_envelope(controls,
            {'scalar_input_domains':domains,'record_sha256':_digest(domains)})
    else:temporal=element.get('material_temporal') or shape_material_temporal(controls)
    pairs=[native_channel_envelope(temporal['channels'][name]) for name in ('a','a2')]
    texture=material['texture']['role'];unknown=[]
    if any(pair is None for pair in pairs):
        pair=[0.,1.];unknown.append('native modulo alpha endpoint envelope unresolved')
    else:
        pair=[min(p[0] for p in pairs),min(1.,max(p[1] for p in pairs))]
        pair[0]=min(1.,pair[0])
    if texture!='untextured_vertex_gradient':
        pair[0]=0.;unknown.append('sampled texture RGBA/asset binding unknown; finite unit-alpha premise bounds multiplication')
    border=material['border_vertex_rgba'][3]
    border_possible=material['border_draw_enabled'] is not False and border!=0
    rgb=[native_channel_envelope(temporal['channels'][name]) for name in ('r','g','b','r2','g2','b2')]
    from source_material_temporal import PERIOD
    excursion=max(1.,max(PERIOD if v is None else v[1] for v in rgb))
    invalid=any('finite native colour conversion' in reason and
                (not reason.startswith('border_') or border_possible) for reason in material['unknown_reasons'])
    for name in ('additive','textured'):
        try:value=_phase_literal(controls[name])
        except (ValueError,RecursionError) as error:
            value=None;unknown.append(name+' literal guard unresolved: '+str(error))
        if value is not None and not -(2**31)-1<value<2**31:
            invalid=True;unknown.append(name+' is outside the native integer conversion domain')
    if texture!='untextured_vertex_gradient' and material['texture'].get('tex_zoom_source')==0:
        invalid=True;unknown.append('textured native UV divides by zero tex_zoom')
    if invalid:unknown.append('known invalid native material conversion prevents transparency certification')
    return {'interval':pair,'method':'native vertex alpha endpoint envelope',
            'mean_fill_alpha':element.get('fill_contribution',{}).get('mean_fill_alpha'),
            'source_rgb_difference_ceiling':excursion,
            'known_invalid_native_domain':invalid,
            'texture_role':texture,'border_possible':border_possible},unknown


def _pointwise_main(sample):
    from source_sampling import _affine_basis_map
    from source_appearance import _phase_literal
    try:
        matrix,offset=_affine_basis_map(sample.args[0],('_uv',),output_width=2)
        return np.array_equal(matrix,np.array([[1,0,0,0],[0,1,0,0]])) and all(_phase_literal(v)==0 for v in offset)
    except (ValueError,RecursionError):return False


def _legacy_transfer(analysis,domains,result,viewport=None):
    """Bound image-colour response with live scalar controls held fixed.

    Native post-equation clamps and blend draw weights are distinct from EEL
    source values. Echo samples current main, not an additional history surface.
    """
    from effect_families import _walk,_SemanticBudget
    from legacy_composite import gamma_weights,source_tint_amount
    from engine_profiles import CORE_2331_DISPLAY
    from source_forms import known_invalid_phase_offset
    from source_native_warp import _f32
    unknown=result['unknown_reasons'];main=getattr(analysis,'main',{})
    ranges={};evidence={}
    def control(name,clamp=None,*,float32=True):
        field=main.get(name)
        if field is None:raise ValueError('missing live legacy control '+name)
        nodes=list(_walk(field,preserve_zero_products=True))
        if any(n.op in {'unknown','uninitialized','unresolved','sequence'} or n.op.startswith('loop_') for n,p in nodes):
            raise ValueError('opaque live legacy control '+name)
        if any(n.op=='constant' and not isinstance(n.detail.get('value'),(int,float)) for n,p in nodes):
            raise ValueError('nonfinite live legacy control '+name)
        if known_invalid_phase_offset(field,preserve_zero_products=True):
            raise ValueError('known invalid live legacy control domain '+name)
        pair,report=_value_range(field,domains)
        evidence[name]=report
        if clamp is not None:
            pair=list(clamp) if pair is None else [max(clamp[0],min(clamp[1],v)) for v in pair]
        if pair is not None and float32:pair=[_f32(v) for v in pair]
        ranges[name]=pair
        return pair
    try:
        gamma=control('gamma',(0.,8.));alpha=control('echo_alpha')
        if alpha is None:raise ValueError('live echo alpha has no finite float32 envelope')
        flags={name:control(name,float32=False) for name in ('brighten','darken','solarize','invert')}
        tint=source_tint_amount(analysis.source)
        if tint is None or not math.isfinite(tint):raise ValueError('native legacy tint policy/amount unresolved')
        # Normalized native corner shade is in [.5,1] before static fShader.
        # This conservative box also bounds out-of-range positive tint amounts.
        tint_gain=1. if tint<=float(np.float32(.001)) else max(1.,abs(1.-.5*tint))
        echo=alpha[1]>float(np.float32(.001));selection='active or possible native echo' if echo else 'native gamma-only branch'
        if echo:
            # Out-of-int orientation is explicitly handled by native omission;
            # a known constant outside that domain selects gamma-only output.
            orientation=control('echo_orient',float32=False)
            truncated=None if orientation is None else [math.trunc(v) for v in orientation]
            if truncated is not None and (truncated[1]<-(2**31) or truncated[0]>2**31-1):
                echo=False;selection='native orientation conversion fallback'
            else:control('echo_zoom',(.001,1000.))
        if echo:
            blend_gain=max(abs(1.-v)+abs(v) for v in (max(alpha[0],float(np.float32(.001))),alpha[1]))
            gamma_gain=max(1.,gamma[1])
        else:blend_gain=1.;gamma_gain=gamma[1]
        weights=None
        if gamma[0]==gamma[1]:
            weights=gamma_weights(gamma[0],echo=echo,control_policy=CORE_2331_DISPLAY)
            gamma_gain=sum(abs(v) for v in weights)
        # Each post-clamp gamma redraw weight is in [0,1]. Preserve a finite
        # native vertex-colour product premise, including excessive tint/alpha.
        mix_magnitude=max(abs(v) for v in (*alpha,*(1.-v for v in alpha))) if echo else 1.
        _f32(tint_gain*mix_magnitude)
        filter_gain=2.**sum(flags[name]!=[0.,0.] for name in ('brighten','darken','solarize'))
        gain=gamma_gain*blend_gain*tint_gain*filter_gain
        if not math.isfinite(gain):raise ValueError('native legacy response gain overflow')
    except _SemanticBudget:raise
    except (ValueError,RecursionError,OverflowError) as error:
        unknown.append('native legacy response unresolved: '+str(error));return result
    landscape=(isinstance(viewport,(list,tuple)) and len(viewport)==2 and
        all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in viewport) and viewport[0]>=viewport[1])
    result.update(difference_gain_interval=[0.,gain],pointwise_support_preserved=not echo and landscape,
        method='native legacy absolute blend/redraw and ordered pointwise filter gain ceiling',
        legacy_response={'native_control_ranges':ranges,'source_range_evidence':evidence,
            'echo_selection':selection,'gamma_redraw_weights':weights,
            'gamma_absolute_weight_sum_upper':gamma_gain,'echo_absolute_blend_weight_sum_upper':blend_gain,
            'tint_absolute_gain_upper':tint_gain,'ordered_filter_gain_upper':filter_gain,
            'tint_amount':float(tint),'tint_corner_formula':'shade=.6+.3*sin(time*30*rate+phase+corner*mult+random_offset), '
                'normalized by the corner maximum, .5+.5*shade, then mixed with 1 by tint_amount when it exceeds 0.001',
            'tint_random_offsets_known':False,
            'application_order':['hue_and_gamma_echo_draws','brighten','darken','solarize','invert'],
            'sample_textures':['main'],'source_role':'current warped main with drawing',
            'includes_scalar_control_response':False,'native_numeric_certified':False,
            'conditions':['Live scalar controls are held fixed for the image-colour difference bound',
                'Listed source scalar inputs and relevant EEL intermediates are finite; declared domains are conditional',
                'Contributing native hue phases and vertex-colour products are finite',
                'Native gamma/zoom clamps precede float conversion; echo alpha is unclamped',
                'Main is finite encoded unit-interval RGBA, sampled with nonnegative unit-mass bilinear filtering',
                'Nominal blend/redraw/polynomial bounds exclude native rounding and storage quantization jumps']})
    if echo:unknown.append('native echo resampling may expand nonzero source support; accumulated feedback remains separate')
    elif not landscape:unknown.append('native legacy portrait aspect expansion or unresolved viewport prevents support preservation')
    return result


def _final_transfer(analysis,description,domains=None,viewport=None):
    from effect_families import _walk,_SemanticBudget
    from source_appearance import _data_return,_phase_literal
    selected=analysis.stages['composite'];field=analysis.outputs.get('composite');unknown=[]
    result={'difference_gain_interval':[0.,None],'pointwise_support_preserved':False,
            'method':'unresolved composite transfer','unknown_reasons':unknown}
    if selected['kind']=='unknown':
        unknown.append('custom composite selection/compilation is unresolved');return result
    if field is None:
        if selected['kind']=='default_composite':
            result.update(difference_gain_interval=[0.,1.],pointwise_support_preserved=True,
                          method='selected native default main-texture copy')
            return result
        if selected['kind']=='legacy_composite':return _legacy_transfer(analysis,domains or {},result,viewport)
        unknown.append('native default/echo/filter transfer and its support are not fully resolved')
        return result
    nodes=list(_walk(_data_return(field)))
    from source_forms import known_invalid_phase_offset
    try:invalid=known_invalid_phase_offset(field,preserve_zero_products=True)
    except _SemanticBudget:raise
    except (ValueError,RecursionError) as error:
        unknown.append('composite domain guard unresolved: '+str(error))
        result['method']='unresolved composite domain guard'
        return result
    if invalid:
        unknown.append('known invalid composite domains prevent an independence or gain claim');return result
    samples=[n for n,p in nodes if n.op=='sample' and n.detail.get('canonical_texture') in HISTORY]
    opaque=any(n.op in {'unknown','uninitialized','unresolved','sequence'} or n.op.startswith('loop_') for n,p in nodes)
    if selected.get('source_contains_clip'):
        unknown.append('composite discard may retain prior display pixels');return result
    if not samples and not opaque:
        result.update(difference_gain_interval=[0.,0.],method='final RGB independent of main/blur drawing');return result
    if opaque:
        unknown.append('opaque RGB path may contain unresolved main/blur dependence');return result
    result['pointwise_support_preserved']=all(s.detail.get('canonical_texture')=='main' and _pointwise_main(s) for s in samples)
    nonlinear=description.get('nonlinear_texture_colour_bounds',{}).get('stages',{}).get('composite',{})
    spans=nonlinear.get('raw_rgb_bounds_if_samples_unit_interval')
    if spans is not None and all(math.isfinite(a) and math.isfinite(b) for a,b in spans):
        result['normalized_output_difference_ceiling']=min(1.,max(b-a for a,b in spans))
    coordinate_history=False
    for sample in samples:
        for node,path in _walk(sample.args[0]):
            if node.op=='sample' and node.detail.get('canonical_texture') in HISTORY or node.op in {'unknown','unresolved','uninitialized'} or node.op.startswith('loop_'):
                coordinate_history=True;break
    if coordinate_history:
        unknown.append('history-dependent or opaque coordinates prevent use of fixed-sample colour gain')
        return result
    transfer=description.get('texture_colour_transfer',{}).get('stages',{}).get('composite',{})
    if transfer.get('source_model')=='affine_sample_colour' and transfer.get('coordinate_sample_dependency') is False:
        weights=[s['matrix_rgb_rgba'] for s in transfer['sample_contributions'] if s['canonical_texture'] in HISTORY]
        gain=max((sum(abs(v) for m in weights for v in m[row]) for row in range(3)),default=0.)
        result.update(difference_gain_interval=[0.,gain],method='affine main/blur RGB difference norm')
    else:
        entries=nonlinear.get('direct_sample_colour_response',{}).get('samples',[])
        weights=[s['matrix_rgb_rgba_gain_upper_bounds'] for s in entries if s['canonical_texture'] in HISTORY]
        valid=bool(weights) and all(v is not None and math.isfinite(v) for m in weights for row in m for v in row)
        if valid:
            gain=max(sum(v for m in weights for v in m[row]) for row in range(3))
            result.update(difference_gain_interval=[0.,gain],method='qualified nonlinear sample difference ceiling')
            # A singleton raw output box is an output independence proof under
            # the explicit sampled-RGBA domain, including saturated suffixes.
            spans=nonlinear.get('raw_rgb_bounds_if_samples_unit_interval')
            if spans is not None and all(a==b for a,b in spans):
                result.update(difference_gain_interval=[0.,0.],method='saturation/range proves output independence')
        else:
            from source_colour_modulus import sampled_colour_difference_modulus
            modulus=sampled_colour_difference_modulus(analysis,input_domains=domains)
            if modulus['status']=='bounded':
                result['sampled_colour_modulus']=modulus
                result['method']='conditional fixed-site sampled-colour difference modulus'
                main_only=all(not s['varying'] or s['canonical_texture']=='main' for s in modulus['sample_sites'])
                if main_only and all(c['lipschitz_gain_upper'] is not None for c in modulus['channels']):
                    result['difference_gain_interval']=[0.,max(c['lipschitz_gain_upper'] for c in modulus['channels'])]
                elif main_only:
                    unknown.append('fractional colour power has no finite rate gain at zero; two-state modulus is separate')
                else:
                    unknown.append('main-to-blur perturbation propagation is unresolved; shader-site modulus does not bound incoming drawing')
            else:
                unknown.append('nonlinear/gamma/mask difference gain unresolved under source domains')
                result['sampled_colour_modulus_unresolved']=modulus
    if any(s.detail.get('canonical_texture') in {'blur1','blur2','blur3'} for s in samples):
        site_gain=result['difference_gain_interval']
        result['sample_site_difference_gain_interval']=list(site_gain)
        if site_gain[1]!=0:
            result['difference_gain_interval']=[0.,None]
            unknown.append('main-to-blur perturbation propagation is unresolved; sample-site gain is not an incoming-main gain')
    if not result['pointwise_support_preserved']:
        unknown.append('sampling/blur may expand any nonzero source footprint to the whole display')
    return result


def prominence_evidence(analysis,description,context):
    """Join continuous primitive support, native alpha and final RGB transfer.

    ``displayed_contribution_interval`` bounds instantaneous normalized integrated
    influence. Feedback history is a separate unresolved contributor; no lifetime
    tiny-area or guaranteed visible-contrast claim is made.
    """
    from scene_equations import _scalar
    context=dict(context or {});viewport=context.get('viewport')
    if not (isinstance(viewport,(list,tuple)) and len(viewport)==2 and
            all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in viewport)):
        viewport=None
    domains=getattr(analysis,'input_scenario',None) or {}
    domains=dict(domains.get('scalar_input_domains',{}))
    for name,span in context.get('scalar_input_domains',{}).items():
        if name in domains and list(domains[name])!=list(span):
            raise ValueError('conflicting scenario/context scalar input domain: '+name)
        domains[name]=list(span)
    from source_blur_propagation import blur_propagation_evidence
    blur_propagation=blur_propagation_evidence(getattr(analysis,'main',{}),input_domains=domains)
    elements={e['id']:e for e in description.get('elements',[])}
    controls=_shape_controls(analysis);identities=sorted(set(elements)|set(controls))
    final=_final_transfer(analysis,description,domains,viewport);components=[]
    source_identity=analysis.source.get('preset_sha256')
    model_identity=_digest({'policy':POLICY,'projection':'TV-source31-NDC-aspectY-angle-pi4',
                           'model_source_sha256':MODEL_SOURCE_SHA256,
                           'storage':'continuous-support/native-alpha/independent-sample-difference'})
    provenance={'preset_sha256':source_identity,'context_sha256':_digest(context),'model_sha256':model_identity,
                'target_profile':getattr(analysis,'profile',None),'parser_inputs_sha256':_digest(analysis.source.get('parser_inputs',{})),
                'input_scenario_sha256':(getattr(analysis,'input_scenario',None) or {}).get('record_sha256')}
    for identity in identities:
        element=elements.get(identity,{})
        stage=element.get('stage','drawing' if identity in controls else 'unknown');unknown=[]
        incoming_rgb=None;allowance=0.;known_invalid=False
        if identity in controls:
            count=_scalar(analysis.values,'shapecode_'+identity.removeprefix('shape_')+'_num_inst',1,'int')
            support,reasons=_shape_support(controls[identity],count,viewport,domains);unknown+=reasons
            opacity,reasons=_shape_opacity(controls[identity],element,domains);unknown+=reasons
            area=support['area_fraction_interval'];alpha=opacity['interval']
            summed_area=support.get('summed_clipped_area_fraction_upper',area[1]*max(0,count))
            source=[0.,min(1.,summed_area*alpha[1])]
            # Integrating the entire nonnegative fan also bounds every clipped
            # subset. Endpoint max remains a separate bound for resampling.
            mean_alpha=element.get('fill_contribution',{}).get('mean_fill_alpha')
            if mean_alpha is None:
                mean_bounds=element.get('fill_envelope',{}).get('mean_alpha_bounds')
                mean_alpha=None if mean_bounds is None else mean_bounds[1]
            nominal_sum=support.get('summed_nominal_area_fraction')
            if nominal_sum is not None and mean_alpha is not None:
                source[1]=min(source[1],nominal_sum*mean_alpha)
            means=element.get('fill_contribution',{}).get('mean_source_rgb_times_alpha')
            if means is not None and nominal_sum is not None:
                incoming_rgb=[[0.,None if value is None else min(1.,nominal_sum*value)] for value in means]
            # Constant same-position repeated shapes retain a common spatial
            # support even when additive/over blending accumulates alpha.
            source[1]=min(area[1],source[1])
            if opacity['border_possible']:
                unknown.append('border stroke width/authored-native replay support is unresolved')
                source[1]=1.;area=[0.,1.]
            known_invalid=support.get('known_invalid_native_domain',False) or opacity.get('known_invalid_native_domain',False)
            if known_invalid:
                source=[0.,1.];area=[0.,1.]
                unknown.append('known invalid native geometry/material domain prevents a zero source contribution certificate')
            elif viewport is not None and 0<area[1]<1:
                radius=math.hypot(1/viewport[0],1/viewport[1])
                allowance=min(1-area[1],support.get('perimeter_fraction_upper',4.)*radius+
                              math.pi*radius*radius*support.get('distinct_support_count',count))
        else:
            support={'area_fraction_interval':[0.,1.],'nominal_area_fraction':None,
                     'method':'full-screen stage' if stage in {'warp','composite','mesh_warp'} else 'wave stroke/audio support unresolved'}
            opacity={'interval':[0.,1.],'method':'stage or waveform opacity unresolved'}
            source=[0.,1.];area=support['area_fraction_interval']
            if stage in {'warp','composite','mesh_warp'}:
                support['area_fraction_interval']=[1.,1.];area=[1.,1.]
            else:unknown.append('wave/audio primitive screen support unresolved')
        transfer={'difference_gain_interval':[0.,1.],'pointwise_support_preserved':True,'method':'already final composite RGB','unknown_reasons':[]} if stage=='composite' else dict(final)
        if known_invalid and 'legacy_response' in transfer:
            transfer={**transfer,'difference_gain_interval':[0.,None],'pointwise_support_preserved':False,
                'unknown_reasons':transfer['unknown_reasons']+[
                    'known invalid incoming domain contradicts the finite sampled-main legacy response premise']}
        gain=transfer['difference_gain_interval'][1]
        if source[1]==0 or gain==0:
            displayed=[0.,0.];display_area=[0.,0.]
        else:
            preserved=transfer['pointwise_support_preserved'];display_area=[0.,min(1.,area[1]+allowance)] if preserved else [0.,1.]
            # With arbitrary resampling only the per-texel alpha ceiling survives;
            # using source integral here would invent area preservation.
            local_alpha=min(1.,opacity['interval'][1]*max(1,support.get('configured_instances',1)))
            if opacity.get('border_possible'):local_alpha=1.
            incoming=(source[1]+allowance*local_alpha if preserved else local_alpha)*opacity.get('source_rgb_difference_ceiling',1.)
            if known_invalid:incoming=1.
            displayed=[0.,display_area[1] if gain is None else min(display_area[1],incoming*gain)]
            modulus=transfer.get('sampled_colour_modulus')
            main_only=modulus is not None and all(not s['varying'] or s['canonical_texture']=='main' for s in modulus['sample_sites'])
            if main_only and not known_invalid:
                from source_colour_modulus import evaluate_colour_modulus
                # Per-site perturbation, never the area-averaged injection.
                # Nonpointwise sampling can spread a tiny source over the
                # whole display; only the local encoded-RGBA ceiling survives.
                delta=min(1.,local_alpha*opacity.get('source_rgb_difference_ceiling',1.))
                response=evaluate_colour_modulus(modulus,delta)
                if response is not None:
                    displayed[1]=min(displayed[1],display_area[1]*min(1.,response))
            if not known_invalid and transfer.get('normalized_output_difference_ceiling') is not None:
                displayed[1]=min(displayed[1],transfer['normalized_output_difference_ceiling'])
        unknown+=transfer['unknown_reasons']
        record={'component_id':identity,'stage':stage,'support':support,'opacity':opacity,
                'final_transfer':transfer,'source_contribution_interval':source,
                'incoming_source_rgb_integral_intervals':incoming_rgb,
                'sampling_support_allowance_fraction':allowance,'known_invalid_native_domain':known_invalid,
                'displayed_support_fraction_interval':display_area,
                'displayed_contribution_interval':displayed,'visible_contrast_interval':[0.,displayed[1]],
                'feedback_contribution_interval':[0.,0.] if gain==0 or source[1]==0 else [0.,1.],
                'unknown_reasons':sorted(set(unknown)),'provenance':provenance,
                'source_paths':element.get('evidence',[]) or ([analysis.evidence(identity+'_per_frame',
                    'configured source shape projection/material reaches final transfer','shape controls')] if identity in controls else []),
                'premises':['Continuous ideal-trigonometric polygon clipping after finite float32 parameter conversion; native raster edges/rounding are excluded',
                    'Target aspectY=min(1,height/width); shape centre=(2*x-1,1-2*y), NDC radius, corner angle=ang+pi/4',
                    'Patched custom-shape projection translates by (+1/targetWidth,+1/targetHeight) before native Y inversion; nominal area remains unshifted',
                    'Pointwise main lookups assume the declared Native target dimensions and nonnegative unit-mass bilinear filtering; one target-texel support dilation is included',
                    'Samples and destination RGBA are finite encoded unit-interval inputs; texture bindings and GPU precision are source contracts',
                    'Contribution is possible integrated RGB influence, not measured contrast; destination, overlap order and other draws can erase it',
                    'Optional solver refinements concern guarded nominal source domains, not certified native rounding; their complete evidence is retained in parameter_ranges',
                    'Instantaneous contribution excludes unknown accumulated feedback/history; a tiny injection need not remain tiny']}
        components.append(record)
    return {'policy':POLICY,'context':context,'provenance':provenance,'components':components,
            'blur_propagation':blur_propagation,
            'by_component':{r['component_id']:r for r in components},
            'unknown_reasons':sorted(set(reason for r in components for reason in r['unknown_reasons'])),
            'units':{'support':'continuous viewport area fraction','contribution':'normalized integrated encoded RGB difference ceiling',
                     'transfer':'encoded RGB difference / input encoded RGBA difference'},
            'uses_rendered_images':False,'uses_equation_execution':False,'uses_shader_execution':False}
