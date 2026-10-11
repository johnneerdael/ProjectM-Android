"""Local raw RGBA-labelled motion on a continuous affine polar source curve.

This algebra distinguishes material reparameterization from geometric-locus
drift. It supplies no sampled vertices, images, visible particles or mood proof.
"""
from fractions import Fraction
import math

from source_curve_projection import _exact, _span, _multiply, _enclosure, _outward
from source_curve_feedback_relation import _origin
from source_parametric_wave import _display, _sample_domain


POLICY='source-material-marker-motion-v1'
RATIONAL_BITS=8192


def _bounded(value):
    if max(abs(value.numerator).bit_length(),value.denominator.bit_length())>RATIONAL_BITS:
        raise ValueError('material-marker rational coefficient budget exceeded')
    return value


def _metadata(value):
    value=_bounded(value)
    return {'numerator':str(value.numerator),'denominator':str(value.denominator)}


def _coefficients(value):
    if not isinstance(value,dict):raise ValueError('exact affine coefficient metadata is absent')
    return {key:_bounded(_exact(value[key])) for key in ('constant','sample','time')}


def _sqrt_upper(radial,angular):
    """Round the Euclidean ceiling upward, checking its exact squared value."""
    square=radial**2+angular**2
    candidate=math.hypot(float(radial),float(angular))
    # Check the exact square after input/hypot rounding, including underflow.
    # A bounded correction avoids depending on any unbounded numerical loop.
    for _ in range(8):
        if not math.isfinite(candidate):raise ValueError('material-marker speed exceeds finite binary64 domain')
        if Fraction(candidate)**2>=square:return candidate
        candidate=math.nextafter(candidate,math.inf)
    raise ValueError('material-marker square-root outward enclosure is unresolved')


def _locus(radius,phase):
    result={'status':'unresolved','fixed_angle_sample_rate_exact':None,
        'fixed_angle_radius_rate_exact':None,'maximum_interior_normal_source_speed_per_second':None,
        'continuous_full_circle_locus_stationary':None,
        'radius_zero_points_excluded':True,'finite_polyline_pixels_static_proved':False,'visible_motion_speed':None,
        'scope':'continuous interior geometric locus, with tangential reparameterization removed; finite endpoints and sampled polyline excluded'}
    if phase['sample']!=0:
        rate=_bounded(-phase['time']/phase['sample'])
        radial=_bounded(radius['time']+radius['sample']*rate)
        result.update(status='conditional_fixed_angle_branch',
            fixed_angle_sample_rate_exact=_metadata(rate),fixed_angle_radius_rate_exact=_metadata(radial),
            maximum_interior_normal_source_speed_per_second=_outward(abs(radial),True))
    circle=radius['constant']!=0 and radius['sample']==radius['time']==0 and abs(phase['sample'])>=2*Fraction(355,113)
    if circle:result['continuous_full_circle_locus_stationary']=True
    return result


def _project_speed(recipe,projection,context,result,radial,angular):
    try:
        if not isinstance(projection,dict) or projection.get('policy')!='source-curve-projection-v1':
            raise ValueError('qualified curve projection is absent')
        if projection.get('status') not in {'conditional_projected_coordinates','partial_projection'}:
            raise ValueError('curve projection coordinates are unresolved')
        origin=recipe.get('source_provenance')
        projected=projection.get('source_curve_provenance')
        if _origin(origin,'curve')!=_origin(projected,'projection') or origin!=projected:
            raise ValueError('curve/projection source provenance does not match')
        viewport=context.get('viewport')
        if (not isinstance(viewport,(list,tuple)) or len(viewport)!=2 or
                any(type(value) is not int or not 0<value<2**31 for value in viewport)):
            raise ValueError('pixel conversion requires an explicit declared native int32 viewport')
        if projection.get('viewport')!=list(viewport) or projection.get('viewport_was_defaulted') is not False:
            raise ValueError('curve projection viewport must match the explicit declared viewport')
        if projection.get('source_time_domain')!=result['source_time_domain']:
            raise ValueError('curve projection source-time domain does not match the marker bound domain')
        scale=max(viewport)
        if projection.get('nominal_source_to_pixel_scale_xy')!=[scale,-scale]:
            raise ValueError('curve projection does not supply the qualified nominal pixel scale')
        stored=projection.get('native_stored_aspect_source_to_pixel_scale_xy')
        if (not isinstance(stored,list) or len(stored)!=2 or
                any(type(value) not in (int,float) or not math.isfinite(value) or value==0 for value in stored)):
            raise ValueError('curve projection lacks the native stored-aspect pixel scale')
        # The native float32 aspect can enlarge one axis slightly; the ceiling
        # uses the larger absolute axis scale so it bounds both conventions.
        native=max(Fraction(scale),*(abs(Fraction(value)) for value in stored))
        speed=_sqrt_upper(radial*native,angular*native)
        result.update(maximum_marker_pixels_speed_per_second=speed,
            nominal_marker_pixels_speed_per_second=_sqrt_upper(radial*scale,angular*scale),
            viewport=list(viewport),nominal_source_to_pixel_scale=scale,
            native_stored_aspect_pixel_scale_upper=float(native),projection_status='conditional_declared_projection')
    except (ValueError,OverflowError,KeyError,TypeError) as error:
        result['projection_unknown_reasons'].append(str(error))


def material_marker_motion(recipe,projection=None,context=None):
    """Derive a common raw RGBA label branch; optionally qualify pixel units.

    Declare source_time_domain for time-growing radius bounds. Declare viewport
    and supply a matching source34 curve_projection for nominal pixel ceilings.
    A common label requires identical -Ct/Cs in all varying sample channels and
    Ct=0 for every sample-uniform channel, including alpha.
    """
    result={'policy':POLICY,'status':'unknown','raw_material_status':'unresolved_common_label',
        'channel_constraints':{},'marker_sample_rate_per_second':None,'marker_sample_rate_exact':None,
        'marker_radius_rate_source_coordinates_per_second':None,'marker_radius_rate_exact':None,
        'marker_phase_rate_radians_per_second':None,'marker_phase_rate_exact':None,
        'maximum_marker_source_speed_per_second':None,'maximum_marker_pixels_speed_per_second':None,
        'nominal_marker_pixels_speed_per_second':None,'native_stored_aspect_pixel_scale_upper':None,
        'marker_speed_formula':'sqrt((Rt+Rs*dsdt)^2 + (maxAbsR*(Pt+Ps*dsdt))^2)',
        'source_speed_unit':'Euclidean source custom-wave x/y coordinate units per source-time second',
        'source_time_domain':None,'time_domain_is_observed':False,'radius_source_interval':None,
        'source_geometric_locus':None,'projection_status':'unresolved','viewport':None,
        'nominal_source_to_pixel_scale':None,'source_provenance':recipe.get('source_provenance',{}) if isinstance(recipe,dict) else {},
        'native_numeric_certified':False,'unique_visible_particles_verified':False,
        'actual_visible_contrast':None,'visible_motion_speed':None,'whole_preset_activity_credit':False,
        'missing_marker_proves_quietness':False,'uses_equation_execution':False,'uses_rendered_images':False,
        'unknown_reasons':[],'projection_unknown_reasons':[],
        'conditions':['A regular local branch holds raw RGBA labels constant before native RGB fmod and alpha clamp: each nonzero Cs requires ds/dt=-Ct/Cs, and every zero-Cs channel requires Ct=0',
            'Exact affine source coefficients remain fixed; finite source intermediates and a branch strictly inside the finite sample/time domain are required; this is no lifetime or attained trajectory proof',
            'Sample-uniform raw material supplies no identifiable label; changing uniform colour or alpha is temporal modulation, not material point motion and not proof of quietness',
            'The raw label velocity uses dR/dt=Rt+Rs*dsdt and dPhi/dt=Pt+Ps*dsdt; geometric interior normal drift removes tangential reparameterization and is independent evidence',
            'The geometric normal relation excludes zero-radius points and branch endpoints; finite native intermediate validity is a condition, not numeric or trigonometric certification',
            'Native RGB modulo repeats can create repeated labels; signed fmod across zero and alpha saturation can erase labels or break equivalence, so no unique particles or actual visual tracking follows',
            'Finite sampled polylines, interpolation, smoothing, raster, clipping, feedback and final composition remain separate; no actual visibility, contrast, visible speed, or mood certification follows',
            'Declared projection scales are nominal source-to-pixel conversions with matching pinned source34 engine/preset/viewport provenance, not observed speed or driver certification']}
    try:
        if context is not None and not isinstance(context,dict):raise ValueError('material-marker context must be a JSON object or omitted')
        context={} if context is None else context
        if not isinstance(recipe,dict) or recipe.get('policy')!='source-parametric-wave-v1':raise ValueError('supported source curve recipe is absent')
        if recipe.get('waveform_independent_geometry') is not True:raise ValueError('waveform-independent geometry is unproved')
        domain=recipe.get('sample_domain')
        if not isinstance(domain,dict):raise ValueError('native finite sample domain is absent')
        count=domain.get('effective_samples')
        if type(count) is not int or not 2<=count<=512 or domain.get('single_dot_nonfinite_sample_excluded') is not True:
            raise ValueError('native finite multi-point sample domain is unproved')
        sample=_span(domain.get('native_float32_endpoint_interval'))
        if list(sample)!=list(map(Fraction,_sample_domain(count)['native_float32_endpoint_interval'])):
            raise ValueError('sample endpoint enclosure does not match the finite native sample count')
        radius=_coefficients(recipe.get('radius_affine_coefficients_exact'))
        phase=_coefficients(recipe.get('phase_affine_coefficients_exact'))
        centres=recipe.get('centre_source_xy_exact')
        if not isinstance(centres,list) or len(centres)!=2:raise ValueError('exact constant centre metadata is absent')
        centres=[_bounded(_exact(value)) for value in centres]
        # Optional material or projection failure must preserve independent geometry.
        try:result['source_geometric_locus']=_locus(radius,phase)
        except (ValueError,OverflowError) as error:result['unknown_reasons'].append(str(error))
        result['status']='unresolved_common_raw_material_marker'
        material=recipe.get('spatial_vertex_colour')
        if not isinstance(material,dict) or material.get('policy')!='source-custom-wave-spatial-colour-bands-v1':
            raise ValueError('supported spatial RGBA material metadata is absent')
        channels=material.get('channels')
        if not isinstance(channels,dict):raise ValueError('RGBA coefficient channels are absent')
        ratios=[];uniform_rates=[];failed=False
        for name in 'rgba':
            row={'status':'unresolved','required_marker_sample_rate_exact':None,'raw_sample_rate_exact':None,
                'raw_time_rate_exact':None,'unknown_reasons':[]}
            result['channel_constraints'][name]=row
            try:
                channel=channels[name]
                if not isinstance(channel,dict):raise ValueError('channel coefficient object is absent')
                if channel.get('native_float32_domain_at_source_time_zero_finite') is not True:
                    raise ValueError('finite native channel domain at source time zero is unproved')
                coefficients=_coefficients(channel.get('affine_coefficients_exact'))
                cs,ct=coefficients['sample'],coefficients['time']
                row.update(raw_sample_rate_exact=_metadata(cs),raw_time_rate_exact=_metadata(ct))
                if cs!=0:
                    rate=_bounded(-ct/cs)
                    ratios.append(rate)
                    row.update(status='sample_varying_label',required_marker_sample_rate_exact=_metadata(rate))
                else:
                    uniform_rates.append(ct)
                    row['status']='sample_uniform_static' if ct==0 else 'sample_uniform_temporal_modulation'
            except (ValueError,OverflowError,KeyError,TypeError) as error:
                row['unknown_reasons'].append(str(error));failed=True
        if failed:raise ValueError('one or more RGBA channels lack supported exact affine coefficients')
        if not ratios:
            result.update(status='conditional_uniform_raw_material',raw_material_status=
                'sample_uniform_temporal_modulation' if any(uniform_rates) else 'sample_uniform_static_raw_material')
            return result
        if len(set(ratios))!=1 or any(uniform_rates):raise ValueError('RGBA channels have no common constant raw-label branch rate')
        rate=ratios[0]
        radial=_bounded(radius['time']+radius['sample']*rate)
        angular=_bounded(phase['time']+phase['sample']*rate)
        result.update(status='conditional_marker_rates_speed_unresolved',raw_material_status='sample_varying_common_label',
            marker_sample_rate_per_second=_display(rate),marker_sample_rate_exact=_metadata(rate),
            marker_radius_rate_source_coordinates_per_second=_display(radial),marker_radius_rate_exact=_metadata(radial),
            marker_phase_rate_radians_per_second=_display(angular),marker_phase_rate_exact=_metadata(angular))
        span=_multiply((radius['sample'],)*2,sample)
        span=(span[0]+radius['constant'],span[1]+radius['constant'])
        time=None
        try:
            if context.get('source_time_domain') is not None:
                time=_span(context['source_time_domain'])
                result['source_time_domain']=_enclosure(time)
        except (ValueError,TypeError) as error:result['unknown_reasons'].append(str(error))
        if radius['time']!=0:
            if time is None:
                span=None
                result['unknown_reasons'].append('time-growing radius requires a finite declared source-time domain for angular marker-speed bounds')
            else:
                growth=_multiply((radius['time'],)*2,time)
                span=(span[0]+growth[0],span[1]+growth[1])
        if span is not None:
            magnitude=max(map(abs,span))
            largest=Fraction((2**24-1)*2**104)
            if any(2*(abs(centre)+magnitude)+1>largest for centre in centres):
                raise ValueError('declared radius/centre envelope lacks a finite native float32 coordinate domain')
            result['radius_source_interval']=_enclosure(span)
        if angular==0:angular_ceiling=Fraction(0)
        elif span is not None:angular_ceiling=_bounded(max(map(abs,span))*abs(angular))
        else:return result
        result['maximum_marker_source_speed_per_second']=_sqrt_upper(radial,angular_ceiling)
        result['status']='conditional_raw_material_marker'
        if projection is not None:_project_speed(recipe,projection,context,result,radial,angular_ceiling)
    except (ValueError,OverflowError,KeyError,TypeError,AttributeError) as error:
        result['unknown_reasons'].append(str(error))
    return result
