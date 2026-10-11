"""Radius-locked raw colour on affine polar source curves.

For R=Rc+Rs*s+Rt*t with Rs!=0 the sample on the curve is s=(R-Rc-Rt*t)/Rs, so
an affine raw label C0+Cs*s+Ct*t equals C0+(Cs/Rs)*(R-Rc-Rt*t)+Ct*t: a function
of radius and time only, independent of angle. While the radius keeps one sign
the displayed distance from the centre identifies that branch, so the
continuous curve paints concentric raw-colour rings. Per channel the exports are
the radial gradient Cs/Rs, the radial modulo period |Rs/Cs|*period, the
fixed-radius colour rate Ct-Cs*Rt/Rs and the iso-label ring drift Rt-Ct*Rs/Cs.
No sampled vertices, raster, visible ring count or mood credit follows.
"""
from fractions import Fraction
import math

from source_curve_projection import _exact,_span,_enclosure
from source_curve_feedback_relation import _origin
from source_parametric_wave import _display


POLICY='source-radial-colour-field-v1'
RATIONAL_BITS=8192


def _bounded(value):
    if max(abs(value.numerator).bit_length(),value.denominator.bit_length())>RATIONAL_BITS:
        raise ValueError('radial colour rational coefficient budget exceeded')
    return value


def _metadata(value):
    value=_bounded(value)
    return {'numerator':str(value.numerator),'denominator':str(value.denominator)}


def _coefficients(value):
    if not isinstance(value,dict):raise ValueError('exact affine coefficient metadata is absent')
    return {key:_bounded(_exact(value[key])) for key in ('constant','sample','time')}


def _pixel_scale(recipe,projection):
    if not isinstance(projection,dict) or projection.get('policy')!='source-curve-projection-v1':
        raise ValueError('qualified curve projection is absent')
    if projection.get('status') not in {'conditional_projected_coordinates','partial_projection'}:
        raise ValueError('curve projection coordinates are unresolved')
    origin=recipe.get('source_provenance');projected=projection.get('source_curve_provenance')
    if _origin(origin,'curve')!=_origin(projected,'projection') or origin!=projected:
        raise ValueError('curve/projection source provenance does not match')
    viewport=projection.get('viewport')
    if (projection.get('viewport_was_defaulted') is not False or not isinstance(viewport,list) or len(viewport)!=2
            or any(type(v) is not int or v<=0 for v in viewport)):
        raise ValueError('pixel periods require an explicit declared viewport')
    scale=max(viewport)
    if projection.get('nominal_source_to_pixel_scale_xy')!=[scale,-scale]:
        raise ValueError('curve projection is not isotropic at the nominal pixel scale')
    return scale


def radial_colour_field(recipe,projection=None,context=None):
    """Derive per-channel radius-locked raw colour for an affine polar recipe."""
    result={'policy':POLICY,'status':'unknown','channels':{},'continuous_curve_colour_angle_independent':None,
        'concentric_ring_pattern':None,'radius_branch':None,'source_time_domain':None,'nominal_source_to_pixel_scale':None,
        'displayed_colour_angle_independent':None,'visible_ring_count':None,'actual_visible_contrast':None,
        'native_numeric_certified':False,'uses_equation_execution':False,'uses_rendered_images':False,
        'whole_preset_activity_credit':False,'unknown_reasons':[],'projection_unknown_reasons':[],
        'conditions':['Raw labels are exact affine source coefficients before native signed modulo, clamps, interpolation and storage',
            'Rs!=0 and one radius sign over the declared domain make the displayed centre distance identify a unique sample',
            'Ring shapes are circles only under an isotropic aspect-corrected projection about the exact constant centre',
            'Finite sampled polylines, smoothing, line width, feedback layering and composition can change displayed colour; angle independence is for the continuous source curve only',
            'Retained layers under a qualified central radial feedback map keep angle independence, but the deposit age at a pixel can depend on angle']}
    try:
        if not isinstance(recipe,dict) or recipe.get('policy')!='source-parametric-wave-v1':
            raise ValueError('supported source curve recipe is absent')
        radius=_coefficients(recipe.get('radius_affine_coefficients_exact'))
        if radius['sample']==0:raise ValueError('radius does not vary with sample; colour is not a function of radius')
        sign=recipe.get('radius_sign')
        if radius['time']!=0 and recipe.get('radius_sign_is_time_invariant') is not True:
            # A declared finite time domain can still prove one radius sign:
            # R is affine in (s,t), so its extremes lie at the domain corners.
            domain=(context or {}).get('source_time_domain')
            if domain is None:raise ValueError('time-varying radius needs a declared source-time domain or proved sign')
            times=_span(domain)
            corners=[radius['constant']+radius['sample']*s+radius['time']*t for s in (0,1) for t in times]
            sign=('strictly_positive' if min(corners)>0 else 'strictly_negative' if max(corners)<0 else
                  'nonnegative_with_possible_zero' if min(corners)>=0 else
                  'nonpositive_with_possible_zero' if max(corners)<=0 else 'crosses_zero')
            result['source_time_domain']=_enclosure(times)
        if sign not in {'strictly_positive','strictly_negative','nonnegative_with_possible_zero','nonpositive_with_possible_zero'}:
            raise ValueError('radius sign changes across the sample domain; displayed radius has two branches')
        result['radius_branch']=sign
        material=recipe.get('spatial_vertex_colour')
        if not isinstance(material,dict) or material.get('policy')!='source-custom-wave-spatial-colour-bands-v1':
            raise ValueError('supported spatial RGBA material metadata is absent')
        period=material.get('native_colour_modulo_period')
        if type(period) not in (int,float) or not math.isfinite(period) or period<=0:
            raise ValueError('native colour modulo period is absent')
        scale=None
        if projection is not None:
            try:
                scale=_pixel_scale(recipe,projection);result['nominal_source_to_pixel_scale']=scale
            except (ValueError,TypeError,KeyError) as error:result['projection_unknown_reasons'].append(str(error))
        channels=material.get('channels') or {}
        varying=[];moving=False
        for name in 'rgb':
            row={'status':'unknown','radial_gradient_per_source_unit_exact':None,'fixed_radius_rate_exact':None,
                 'fixed_radius_rate_per_second':None,'ring_drift_source_units_per_second_exact':None,
                 'ring_drift_source_units_per_second':None,'radial_modulo_period_source_units':None,
                 'radial_modulo_period_pixels':None,'unknown_reasons':[]}
            result['channels'][name]=row
            try:
                channel=channels[name]
                if channel.get('native_float32_domain_at_source_time_zero_finite') is not True:
                    raise ValueError('finite native channel domain is unproved')
                c=_coefficients(channel.get('affine_coefficients_exact'))
                gradient=_bounded(c['sample']/radius['sample'])
                rate=_bounded(c['time']-c['sample']*radius['time']/radius['sample'])
                row.update(radial_gradient_per_source_unit_exact=_metadata(gradient),
                    fixed_radius_rate_exact=_metadata(rate),fixed_radius_rate_per_second=_display(rate))
                if c['sample']==0:
                    row['status']='uniform_channel'
                    moving=moving or rate!=0
                    continue
                drift=_bounded(radius['time']-c['time']*radius['sample']/c['sample'])
                source_period=float(Fraction(period)*abs(1/gradient))
                row.update(status='radius_locked_channel',ring_drift_source_units_per_second_exact=_metadata(drift),
                    ring_drift_source_units_per_second=_display(drift),radial_modulo_period_source_units=source_period,
                    radial_modulo_period_pixels=None if scale is None else source_period*scale)
                varying.append(name);moving=moving or rate!=0
            except (ValueError,KeyError,TypeError,AttributeError,ZeroDivisionError) as error:
                row['unknown_reasons'].append(str(error))
        if any(row['status']=='unknown' for row in result['channels'].values()):
            raise ValueError('one or more RGB channels lack supported exact affine coefficients')
        result.update(status='conditional_radius_locked_colour',continuous_curve_colour_angle_independent=True)
        if varying:result['concentric_ring_pattern']='drifting_or_cycling' if moving else 'static_at_fixed_radius'
        else:result['concentric_ring_pattern']='uniform_colour_no_rings'
    except (ValueError,KeyError,TypeError,OverflowError) as error:
        result['unknown_reasons'].append(str(error))
    return result
