"""Source custom-wave polar curves, before projection, smoothing or feedback."""
from fractions import Fraction
import math

import numpy as np


POLICY='source-parametric-wave-v1'


def _affine(field):
    """Retain exact nominal algebra over stored source literals and conversions.

    Float-normalized phase terms can erase a small dynamic coefficient. Native
    folded constants remain atomic stored literals; dynamic graph arithmetic
    uses rational coefficients until outward bound/export rounding.
    """
    from source_appearance import _phase_literal
    memo={}

    def visit(node,depth=0):
        if depth>64 or len(memo)>=4096:raise ValueError('wave affine graph budget exceeded')
        key=id(node)
        if key in memo:return memo[key]
        if node.dtype!='float':return None
        if node.op in {'constant','cast','narrow','construct'}:
            value=_phase_literal(node)
            result=None if value is None else {'constant':Fraction(value),'sample':Fraction(0),'time':Fraction(0)}
        elif node.op=='input' and node.detail.get('name') in {'sample','time'}:
            result={name:Fraction(int(name==node.detail['name'])) for name in ('constant','sample','time')}
        elif node.op in {'negate','unary'} and len(node.args)==1:
            child=visit(node.args[0],depth+1)
            sign=-1 if node.op=='negate' or node.detail.get('operator')==0 else 1 if node.detail.get('operator')==1 else None
            result=None if child is None or sign is None else {name:sign*value for name,value in child.items()}
        elif node.op in {'add','subtract','multiply','divide'} and len(node.args)==2:
            a,b=[visit(arg,depth+1) for arg in node.args]
            if a is None or b is None:result=None
            elif node.op in {'add','subtract'}:
                sign=-1 if node.op=='subtract' else 1
                result={name:a[name]+sign*b[name] for name in a}
            elif node.op=='multiply':result=_multiply_affine(a,b)
            elif b['sample']!=0 or b['time']!=0 or b['constant']==0:result=None
            else:result={name:value/b['constant'] for name,value in a.items()}
        else:result=None
        if result is not None and any(max(value.numerator.bit_length(),value.denominator.bit_length())>65536 for value in result.values()):
            raise ValueError('wave rational coefficient budget exceeded')
        memo[key]=result
        return result

    return visit(field)


def _multiply_affine(a,b):
    if a['sample']==a['time']==0:return {name:a['constant']*value for name,value in b.items()}
    if b['sample']==b['time']==0:return {name:b['constant']*value for name,value in a.items()}
    return None


def _constant_exact(field):
    coefficients=_affine(field)
    if coefficients is not None and coefficients['sample']==coefficients['time']==0:return coefficients['constant']
    return None


def _exact_terms(field,scale=Fraction(1),depth=0):
    """Split affine syntax without multiplying any binary64 coefficients."""
    from effect_families import MAX_NORMALIZED_TERMS
    if depth>64:raise ValueError('wave term depth exceeded')
    if field.dtype=='float':
        if field.op in {'add','subtract'}:
            a=_exact_terms(field.args[0],scale,depth+1)
            b=_exact_terms(field.args[1],scale*(-1 if field.op=='subtract' else 1),depth+1)
            if len(a)+len(b)>MAX_NORMALIZED_TERMS:raise ValueError('wave term budget exceeded')
            return a+b
        if field.op=='negate':return _exact_terms(field.args[0],-scale,depth+1)
        if field.op=='multiply':
            for index in (0,1):
                constant=_constant_exact(field.args[index])
                if constant is not None:return _exact_terms(field.args[1-index],scale*constant,depth+1)
        if field.op=='divide':
            constant=_constant_exact(field.args[1])
            if constant not in {None,0}:return _exact_terms(field.args[0],scale/constant,depth+1)
    return [(scale,field)]


def _exact_product(field,depth=0):
    from effect_families import MAX_NORMALIZED_TERMS
    if depth>64:raise ValueError('wave product depth exceeded')
    constant=_constant_exact(field)
    if constant is not None:return constant,[]
    if field.dtype=='float' and field.op=='multiply':
        a,af=_exact_product(field.args[0],depth+1)
        b,bf=_exact_product(field.args[1],depth+1)
        if len(af)+len(bf)>MAX_NORMALIZED_TERMS:raise ValueError('wave factor budget exceeded')
        return a*b,af+bf
    if field.dtype=='float' and field.op=='divide':
        divisor=_constant_exact(field.args[1])
        if divisor not in {None,0}:
            scale,factors=_exact_product(field.args[0],depth+1)
            return scale/divisor,factors
    return Fraction(1),[field]


def _display(value):
    """Export approximate numeric metadata without inventing a zero/finite value."""
    try:result=float(value)
    except OverflowError:return None
    return result if math.isfinite(result) and (result!=0 or value==0) else None


def _display_coefficients(coefficients):
    return {name:_display(value) for name,value in coefficients.items()}


def _exact_coefficients(coefficients):
    return {name:{'numerator':str(value.numerator),'denominator':str(value.denominator)} for name,value in coefficients.items()}


def _axis(field):
    from source_appearance import _expression
    centre=Fraction(0)
    oscillation=None
    terms=_exact_terms(field)
    if len(terms)>256:return None
    for coefficient,term in terms:
        literal=_constant_exact(term)
        if literal is not None:
            centre+=coefficient*literal
            continue
        if oscillation is not None:return None
        scale,factors=_exact_product(term)
        trig=[factor for factor in factors if factor.op in {'sin','cos'} and factor.dtype=='float' and len(factor.args)==1]
        if len(trig)!=1:return None
        oscillator=trig[0]
        coefficients={'constant':coefficient*scale,'sample':Fraction(0),'time':Fraction(0)}
        radius_factors=[]
        for factor in factors:
            if factor is oscillator:continue
            part=_affine(factor)
            if part is None:return None
            coefficients=_multiply_affine(coefficients,part)
            if coefficients is None:return None
            radius_factors.append(_expression(factor))
        phase=_affine(oscillator.args[0])
        if coefficients is None or phase is None:return None
        radius_expression={'kind':'exact_factored_source_radius',
                           'scale':_exact_coefficients({'constant':coefficient*scale})['constant'],
                           'factors':radius_factors}
        oscillation=(oscillator,coefficients,phase,radius_expression)
    if oscillation is None:return None
    c=float(centre)
    if not math.isfinite(c):return None
    with np.errstate(over='ignore',invalid='ignore'):
        # Reject a known impossible native coordinate at the centre itself.
        if not math.isfinite(float(np.float32(c*2-1))):return None
    return c,oscillation,centre


def _sample_domain(count):
    if count is None or not math.isfinite(count) or not -(2**31)<=count<2**31:return None
    samples=min(512,max(0,math.trunc(count)))
    if samples<2:return None # MilkDrop single-dot sample is nonfinite 0/0.
    multiplier=np.float32(1)/np.float32(samples-1)
    endpoint=float(np.float32(samples-1)*multiplier)
    return {'nominal_interval':[0.,1.],'native_float32_endpoint_interval':[0.,max(1.,endpoint)],
            'effective_samples':samples,'formula':'float32(j) * float32(1 / (N-1)), 0 <= j < N',
            'single_dot_nonfinite_sample_excluded':True,
            'native_endpoint_arithmetic_mode':'binary32 nominal arithmetic; native driver/evaluator execution unverified'}


def _radius_span(radius,sample_interval):
    from source_sampling_motion import _finite_round
    values=[Fraction(radius['constant'])+Fraction(radius['sample'])*Fraction(sample) for sample in sample_interval]
    low,high=min(values),max(values)
    lower=_finite_round(-low,upper=True)
    upper=_finite_round(high,upper=True)
    return None if lower is None or upper is None else [-lower,upper]


def _finite_coordinate_domain(centres,radius,sample_interval):
    span=_radius_span(radius,sample_interval)
    if span is None:return False
    maximum=max(map(abs,span))
    with np.errstate(over='ignore',invalid='ignore'):
        return all(math.isfinite(float(np.float32((centre+sign*maximum)*2-1)))
                   for centre in centres for sign in (-1,1))


def _joint_spatial_rgb(coefficients,period):
    """Keep a shared affine sample phase through nominal RGB modulo.

    Derive the fundamental common period algebraically, with source time fixed.
    Do not sample RGB values, infer reached hues or equate nominal modulo with
    finite native fmod/interpolation/storage behaviour.
    """
    result={'policy':'source-affine-rgb-joint-spatial-period-v1','status':'unknown',
        'nominal_joint_period_sample':None,'nominal_joint_period_sample_exact':None,
        'signed_channel_windings':None,'fixed_source_time_required':True,
        'temporal_flash_frequency_hz':None,'reached_palette_verified':False,
        'remainder_model':'nominal Euclidean modulo congruence; not native signed-fmod equality',
        'native_periodicity_verified':False,
        'native_numeric_certified':False,'uses_equation_execution':False,
        'uses_rendered_images':False,'unknown_reasons':[],
        'conditions':['Joint periodicity concerns affine raw RGB modulo at fixed finite source time, not alpha, reached hues, temporal flashes or final palette',
            'The period can extend beyond the finite native sample domain; no complete colour cycle or repeated displayed bands are certified',
            'Native signed fmod is not globally periodic across zero; each original and translated channel must retain a compatible remainder sign for this congruence to describe native repetition',
            'Native float32 arithmetic/fmod, negative-value conventions, interpolation and composition remain separate from this nominal translation relation']}
    try:
        if any(coefficients.get(name) is None for name in 'rgb'):
            raise ValueError('all three finite affine RGB source channels are required')
        slopes=[coefficients[name]['sample'] for name in 'rgb']
        if any(max(abs(value.numerator).bit_length(),value.denominator.bit_length())>4096 for value in slopes):
            raise ValueError('joint RGB rational period budget exceeded')
        if all(value==0 for value in slopes):
            result.update(status='uniform_over_source_sample',signed_channel_windings={name:0 for name in 'rgb'})
            return result
        denominator=1
        for value in slopes:
            denominator=math.lcm(denominator,value.denominator)
            if denominator.bit_length()>4096:raise ValueError('joint RGB denominator budget exceeded')
        numerators=[value.numerator*(denominator//value.denominator) for value in slopes]
        common=Fraction(math.gcd(*numerators),denominator)
        sample_period=Fraction(period)/common
        if max(abs(sample_period.numerator).bit_length(),sample_period.denominator.bit_length())>4096:
            raise ValueError('joint RGB period export budget exceeded')
        result.update(status='nominal_rgb_modulo_congruence',
            nominal_joint_period_sample=_display(sample_period),
            nominal_joint_period_sample_exact=_exact_coefficients({'value':sample_period})['value'],
            signed_channel_windings={name:int(value/common) for name,value in zip('rgb',slopes)})
    except ValueError as error:
        result['unknown_reasons'].append(str(error))
    return result


def _spatial_colours(controls,sample_domain):
    from source_material_temporal import PERIOD
    from source_appearance import _expression
    channels={};affine_channels={}
    for name in 'rgba':
        field=controls[name]
        coefficients=_affine(field)
        interval=None if coefficients is None else _radius_span(coefficients,sample_domain['native_float32_endpoint_interval'])
        finite=False
        if interval is not None:
            with np.errstate(over='ignore',invalid='ignore'):
                finite=all(math.isfinite(float(np.float32(value))) for value in interval)
        if not finite:coefficients=None
        affine_channels[name]=coefficients
        channels[name]={'source_expression':_expression(field),
            'affine_coefficients':None if coefficients is None else _display_coefficients(coefficients),
            'affine_coefficients_exact':None if coefficients is None else _exact_coefficients(coefficients),
            'raw_source_range_at_source_time_zero':interval if finite else None,
            'native_float32_domain_at_source_time_zero_finite':finite,
            'nominal_modulo_cycles_across_sample_domain':None if coefficients is None else _display(abs(coefficients['sample'])/Fraction(PERIOD)),
            'temporal_rate_or_event_frequency':None}
    return {'policy':'source-custom-wave-spatial-colour-bands-v1','channels':channels,
            'joint_rgb_spatial_pattern':_joint_spatial_rgb(affine_channels,PERIOD),
            'native_colour_modulo_period':PERIOD,'temporal_flash_frequency_hz':None,
            'actual_displayed_colour_bands_verified':False,
            'scope':'affine vertex colour along source sample index; native modulo/quantization, interpolation and composition remain separate',
            'conditions':['Spatial modulo cycles describe source colour ingredients, never temporal flashes or reached screen bands',
                'Time-varying channels require finite source time and native conversion; no lifetime domain follows from the time-zero interval',
                'Pinned projectM uploads float32 modulo colours; original MilkDrop2 packs integer bytes, so these are not Windows pixel-equivalence claims']}


def _signed_enclosure(value):
    """Outward signed endpoints, allowing a justified zero on one side."""
    from source_sampling_motion import _finite_round
    negative_lower=_finite_round(-value,upper=True)
    upper=_finite_round(value,upper=True)
    if negative_lower is None or upper is None:
        try:rounded=float(value)
        except OverflowError:return None
        if rounded==0:
            if value>0:negative_lower=0.
            elif value<0:upper=0.
    return None if negative_lower is None or upper is None else [-negative_lower,upper]


def _source_locus_relation(radius,phase,circle,complete_circle,spatial_colours):
    """Remove tangential reparameterization on a finite interior polar branch."""
    from source_sampling_motion import _finite_round
    from source_material_temporal import PERIOD

    sample_rate=None if phase['sample']==0 else -phase['time']/phase['sample']
    radial_rate=None if sample_rate is None else radius['time']+radius['sample']*sample_rate
    colours={}
    for name,channel in (spatial_colours or {}).get('channels',{}).items():
        exact=channel['affine_coefficients_exact']
        coefficients=None if exact is None else {key:Fraction(int(pair['numerator']),int(pair['denominator'])) for key,pair in exact.items()}
        rate=None if sample_rate is None or coefficients is None else coefficients['time']+coefficients['sample']*sample_rate
        colours[name]={'raw_source_colour_rate_per_second':None if rate is None else _display(rate),
            'raw_source_colour_rate_exact':None if rate is None else _exact_coefficients({'rate':rate})['rate'],
            'raw_source_colour_rate_enclosure':None if rate is None else _signed_enclosure(rate),
            'nominal_raw_modulo_cycles_per_source_second':None if rate is None else _display(abs(rate)/Fraction(PERIOD)),
            'native_modulo_event_frequency_hz':None,
            'source_expression':channel['source_expression'],
            'unknown_reasons':['fixed-angle reparameterization requires a nonzero sample phase coefficient'] if sample_rate is None else
                              ['raw colour has no supported finite affine source domain'] if coefficients is None else []}
    return {'policy':'source-parametric-wave-locus-v1',
        'status':'unresolved' if sample_rate is None else 'conditional_fixed_angle_branch',
        'fixed_angle_branch_sample_rate_per_second':None if sample_rate is None else _display(sample_rate),
        'fixed_angle_branch_sample_rate_exact':None if sample_rate is None else _exact_coefficients({'rate':sample_rate})['rate'],
        'fixed_angle_branch_sample_rate_enclosure':None if sample_rate is None else _signed_enclosure(sample_rate),
        'fixed_angle_branch_radial_rate_source_coordinates_per_second':None if radial_rate is None else _display(radial_rate),
        'fixed_angle_branch_radial_rate_exact':None if radial_rate is None else _exact_coefficients({'rate':radial_rate})['rate'],
        'fixed_angle_branch_radial_rate_enclosure':None if radial_rate is None else _signed_enclosure(radial_rate),
        'maximum_interior_geometric_normal_speed_source_coordinates_per_second':None if radial_rate is None else _finite_round(abs(radial_rate),upper=True),
        'radial_rate_semantics':'signed source radius rate; radial-distance rate direction additionally depends on the sign of radius',
        'normal_speed_semantics':'upper only for the interior continuous curve in Euclidean source x/y units; tangential reparameterization removed',
        'continuous_full_circle_locus_stationary':True if circle and complete_circle else None,
        'whole_curve_locus_motion_bound':None,
        'finite_parameter_endpoints_motion_resolved':False,'radius_zero_points_excluded':True,
        'finite_polyline_pixels_static_proved':False,'fixed_sample_colours_stationary_proved':False,
        'fixed_angle_colour':{'channels':colours,'native_colour_modulo_period':PERIOD,
            'native_modulo_operation':'qualified native vertex colour modulo before interpolation/storage',
            'visible_flash_frequency_hz':None,'independent_colour_channels_assumed':False,
            'scope':'raw source colour on the same fixed-angle interior branch; finite native conversion/modulo/quantization and visibility remain separate'},
        'visible_motion_speed':None,'native_numeric_certified':False,'whole_preset_activity_credit':False,
        'unknown_reasons':['sample phase coefficient is zero; no invertible fixed-angle sample relation'] if sample_rate is None else [],
        'conditions':['For R=R0+Rs*sample+Rt*time and phase=phase0+phase_s*sample+phase_t*time, hold an angular branch fixed: ds/dt=-phase_t/phase_s and dR/dt=Rt-Rs*phase_t/phase_s',
            'Require nonzero sample phase, nonzero radius, finite supported source arithmetic and a branch strictly inside the finite sample parameter interval; branch endpoints and centre crossings are excluded',
            'The radial reparameterized velocity has norm abs(dR/dt); its projection on the geometric curve normal cannot exceed that norm',
            'A constant nonzero radius covering a proved full angular circle has a stationary continuous source locus even when the sampled parameter vertices move',
            'Finite sample points, smoothed polylines, raster pixels, parameter endpoints, aspect projection, colour/alpha interpolation, storage, composition and feedback are not stationary-visibility proofs',
            'A spatial affine colour C=C0+Cs*sample+Ct*time has fixed-angle raw rate Ct-Cs*phase_t/phase_s; copied colour dependencies share this same reparameterization',
            'Nominal modulo cycles use abs(raw colour rate)/the declared native modulo period only while that interior branch and finite colour domain exist; reached native events, cadence, quantization and visible flashing remain unknown',
            'Exact coefficient fractions decide zeros and bounds; display underflow is null rather than an invented zero, and all reported rate enclosures round outward']}


def parametric_wave_recipe(x,y, *, sample_count,point_controls=None,source_provenance=None):
    """Recognize matched sin/cos lanes with shared affine radius and phase."""
    from effect_families import _deps,_same,_walk
    from source_appearance import _expression
    from source_forms import known_invalid_phase_offset
    from source_sampling_motion import _finite_round

    try:
        if any(field.dtype!='float' for field in (x,y)):return None
        if any(not _deps(field)<={'sample','time'} for field in (x,y)):return None
        # Do not strip dynamic numeric conversions to find a nominal circle.
        for field in (x,y):
            if known_invalid_phase_offset(field,preserve_zero_products=True):return None
            for node,path in _walk(field,preserve_zero_products=True):
                if node.op in {'cast','narrow','construct'} and node.args:
                    from source_appearance import _phase_literal
                    if _phase_literal(node) is None:return None
        axes=[_axis(field) for field in (x,y)]
        if any(axis is None for axis in axes):return None
        centres=[axis[0] for axis in axes]
        (tx,rx,px,radius_expression),(ty,ry,py,_)=[axis[1] for axis in axes]
        if {tx.op,ty.op}!={'sin','cos'} or not _same(tx.args[0],ty.args[0]) or rx!=ry or px!=py:return None
        radius=rx
        phase=px
        sample_domain=_sample_domain(sample_count)
        if sample_domain is None or not any(radius.values()):return None
        if not _finite_coordinate_domain(centres,radius,sample_domain['native_float32_endpoint_interval']):return None
        # A sample-varying affine radius with nonzero sample phase is the spiral
        # candidate. Time-only radial growth remains a distinct polar recipe.
        circle=radius['sample']==0 and radius['time']==0 and radius['constant']!=0 and phase['sample']!=0
        spiral=radius['sample']!=0 and phase['sample']!=0
        curve='circle_candidate' if circle else 'affine_radius_polar_spiral_candidate' if spiral else 'affine_radius_polar_curve_candidate'
        nominal_span=_radius_span(radius,[0.,1.])
        native_span=_radius_span(radius,sample_domain['native_float32_endpoint_interval'])
        if nominal_span is None or native_span is None:return None
        rate=radius['time']
        speed=None
        if rate==0:
            speed=_finite_round(max(map(abs,map(Fraction,native_span)))*abs(Fraction(phase['time'])),upper=True)
        elif phase['time']==0:speed=_finite_round(abs(rate),upper=True)
        vertex_orientation=1 if tx.op=='sin' else -1
        orientation=-vertex_orientation # orthogonalProjection reverses vertex Y again.
        deps=set().union(*(_deps(point_controls[name]) for name in 'xyrgba')) if point_controls else _deps(x)|_deps(y)
        sign='strictly_positive' if nominal_span[0]>0 else 'strictly_negative' if nominal_span[1]<0 else \
            'nonnegative_with_possible_zero' if nominal_span[0]>=0 else 'nonpositive_with_possible_zero' if nominal_span[1]<=0 else 'crosses_zero'
        complete_circle=circle and abs(phase['sample'])>=2*Fraction(355,113)
        spatial_colours=None if point_controls is None else _spatial_colours(point_controls,sample_domain)
        return {'policy':POLICY,'curve_class':curve,'centre_source_xy':centres,
            'centre_source_xy_exact':[_exact_coefficients({'centre':axis[2]})['centre'] for axis in axes],
            'radius_affine_coefficients':_display_coefficients(radius),'phase_affine_coefficients':_display_coefficients(phase),
            'radius_affine_coefficients_exact':_exact_coefficients(radius),'phase_affine_coefficients_exact':_exact_coefficients(phase),
            'coefficient_basis':{'constant':'source literal','sample':'normalized custom-wave sample','time':'source-time seconds'},
            'axis_trig_functions':[tx.op,ty.op],'sample_domain':sample_domain,
            'nominal_radius_interval_at_source_time_zero':nominal_span,'radius_sign':sign,
            'radius_sign_is_time_invariant':rate==0,
            'exact_nominal_constant_radius_circle':circle,
            'complete_circle_parameter_range':complete_circle,
            'complete_circle_range_proof':'exact phase extent >= 2*(355/113), a conservative rational upper bound for 2*pi; false means this sufficient proof is absent',
            'nominal_turns_across_sample_domain':_display(abs(phase['sample'])/Fraction(math.tau)),
            'nominal_phase_cycles_per_source_second':_display(abs(phase['time'])/Fraction(math.tau)),
            'signed_radial_time_rate_source_coordinates_per_second':_display(rate),
            'maximum_fixed_sample_source_coordinate_speed_per_second':speed,
            'fixed_sample_source_speed_formula':'sqrt(radius_time_rate^2 + radius(sample,time)^2 * phase_time_rate^2)',
            'speed_unit':'Euclidean source custom-wave x/y coordinate units per source-time second',
            'signed_native_ndc_angular_orientation':orientation,
            'signed_native_vertex_angular_orientation_before_orthographic_projection':vertex_orientation,
            'orientation_definition':'positive is counterclockwise for increasing phase in final OpenGL X-right/Y-up clip NDC after orthogonalProjection flips vertex Y; temporal direction also depends on signed phase time rate',
            'native_projection':{'vertex_x':'(2*x-1)*invAspectX','vertex_y':'(1-2*y)*invAspectY',
                'clip_ndc_x':'(2*x-1)*invAspectX','clip_ndc_y':'(2*y-1)*invAspectY',
                'orthographic_vertex_y_scale':-1,'aspect_factors_resolved':False},
            'waveform_independent_geometry':True,
            'waveform_independent_point_program':deps<={'sample','time'},
            'point_input_dependencies':sorted(deps),
            'source_expressions':{'x':_expression(x),'y':_expression(y),'radius':radius_expression,'phase':_expression(tx.args[0])},
            'source_provenance':source_provenance or {},
            'spatial_vertex_colour':spatial_colours,
            'source_locus_relation':_source_locus_relation(radius,phase,circle,complete_circle,spatial_colours),
            'visible_motion_speed':None,'native_numeric_certified':False,'whole_preset_activity_credit':False,
            'uses_equation_execution':False,'uses_rendered_images':False,
            'conditions':['Matched plain scalar sin/cos lanes use the same phase and shared finite constant-affine radius over sample/time',
                'Exact rational algebra over stored source literals decides zero/growth/classification and rounds bound endpoints outward; native-folded constants retain their stored values',
                'Numeric coefficients and phase turns/cycles are approximate displays; unrepresentable nonzero/finite numeric displays are null and exact coefficient fractions remain available',
                'The analytic sample curve precedes finite native sample points, line smoothing, aspect projection, clipping, thickness, alpha, shaders and feedback; displayed circles/spirals are candidates',
                'Custom-wave point x/y reload .5+value1/.5+value2 in both native projectM and original MilkDrop2; only explicit waveform-independent geometry qualifies',
                'Nominal sample domain is [0,1]; speed ceilings include the binary32 endpoint enclosure for the constant effective sample count, excluding single-dot 0/0',
                'Finite source intermediates, trigonometric arguments, time and native coordinate conversions are required; no native rounding/trig or driver certification follows',
                'Source x/y units have no assumed display aspect; the vertex Y flip and orthogonalProjection Y reversal both participate in final clip-NDC orientation',
                'A negative radius contributes a half-turn phase offset; zero/crossing radii may collapse at the centre, without undefined zero-radius direction being certified',
                'Time-rate bounds hold sample fixed; growing time-dependent radii have no uniform lifetime speed unless angular time rate is zero',
                'Phase turns/cycles describe an analytic coordinate parameter, not visible revolutions, displayed flash frequency or a mood verdict']}
    except (ValueError,OverflowError,RecursionError):return None


def parametric_wave_from_analysis(analysis,identity):
    """Rebuild native frame/point reloads without changing existing wave graphs."""
    from effect_families import Field,_constant,_EEL,select_equation
    from scene_equations import _scalar,READONLY
    from source_colour_character import _assemble
    from source_appearance import _phase_literal

    prefix='wavecode_'+identity.removeprefix('wave_')+'_'
    if not _scalar(analysis.values,prefix+'enabled',0,'bool'):return None
    defaults={name:_constant(_scalar(analysis.values,prefix+name,512 if name=='samples' else 1,'int' if name=='samples' else 'float'))
              for name in ('samples','r','g','b','a')}
    init_prefix=identity+'_init'
    init=_assemble(analysis,init_prefix,{**defaults,**{name:Field('input',detail={'name':'init:'+init_prefix+':'+name})
        for name in (*READONLY,*(f'q{i}' for i in range(1,33)))}})
    resets={**defaults,**{name:Field('input',detail={'name':name}) for name in READONLY},
        **{f'q{i}':analysis.main.get(f'q{i}',Field('unknown')) for i in range(1,33)},
        **{f't{i}':init.environment.get(f't{i}',_constant(0)) for i in range(1,9)}}
    frame_prefix=identity+'_per_frame'
    frame=_assemble(analysis,frame_prefix,analysis.frame_environment(frame_prefix,init.environment,resets))
    point_prefix=identity+'_per_point'
    selected=select_equation(analysis.sections.get(point_prefix),point_prefix,policy=analysis.policy)
    if selected['compile_status']!='accepted' or selected['tree_status']!='parsed':return None
    point={name:frame.environment.get(name,Field('unknown'))
           for name in (*'rgba',*READONLY,*(f'q{i}' for i in range(1,33)),*(f't{i}' for i in range(1,9)))}
    # LoadReadOnlyStateVariables copies the host inputs before wave frame code.
    # Q/T and RGBA copy after execution; the point clock is the earlier snapshot.
    point.update({name:resets[name] for name in READONLY})
    for name in _EEL.assignment_targets(selected['tree'])-set('rgbaxy')-{'sample','value1','value2'}:
        point[name]=Field('input',detail={'name':'state:'+point_prefix+':'+name})
    point.update({name:Field('input',detail={'name':name}) for name in ('sample','value1','value2')})
    for axis,value in (('x','value1'),('y','value2')):
        point[axis]=Field('add',(_constant(.5),point[value]),'float')
    controls=_assemble(analysis,point_prefix,point).environment
    return parametric_wave_recipe(controls['x'],controls['y'],sample_count=_phase_literal(frame.environment['samples']),
        point_controls=controls,source_provenance={'preset_sha256':analysis.source.get('preset_sha256'),
            'parser_inputs':analysis.source.get('parser_inputs',{}),'profile':analysis.profile,'point_section':point_prefix})
