"""Local affine-polar turn spacing against one qualified radial feedback step.

No equations, points, shaders, frames or feedback histories are executed. The
comparison concerns ideal source ingredients, never achieved trail thickness.
"""
from fractions import Fraction
import math

from source_curve_projection import _exact,_span,_enclosure,_multiply,_number


POLICY='source-curve-feedback-relation-v1'
PI_INTERVAL=(Fraction(333,106),Fraction(355,113))


def _mapping(value,name):
    if not isinstance(value,dict):raise ValueError(name+' must be a source evidence object')
    return value


def _metadata(value):
    if max(abs(value.numerator).bit_length(),value.denominator.bit_length())>8192:
        raise ValueError('curve/feedback rational metadata budget exceeded')
    return {'numerator':str(value.numerator),'denominator':str(value.denominator)}


def _origin(value,name):
    from engine_profiles import CORE_2334_ENGINE,matches
    origin=_mapping(value,name+' provenance')
    digest=origin.get('preset_sha256')
    if not isinstance(digest,str) or len(digest)!=64 or any(character not in '0123456789abcdef' for character in digest):
        raise ValueError(name+' requires a source preset SHA256')
    parser=_mapping(origin.get('parser_inputs'),name+' parser inputs')
    engine=_mapping(parser.get('engine'),name+' engine')
    if not matches(engine,CORE_2334_ENGINE):raise ValueError(name+' requires the qualified exact source34 engine identity')
    return digest


def _affine_coefficients(recipe,name):
    value=_mapping(recipe.get(name+'_affine_coefficients_exact'),name+' exact source coefficients')
    return {key:_exact(value[key]) for key in ('constant','sample','time')}


def _shift(span,amount):return span[0]+amount,span[1]+amount


def _inverse_span(span,divisor):
    if divisor==0:raise ValueError('source radial sample coefficient is zero')
    return tuple(sorted(value/divisor for value in span))


def _absolute_span(span):
    return (Fraction(0) if span[0]<=0<=span[1] else min(map(abs,span)),max(map(abs,span)))


def _clipping_scopes(initial,retained,fresh,adjacent_radius_shift,aspects):
    """Cover all described ideal branches, with retained-orbit flags separate."""
    old_max=max(initial[1],retained[1])
    fresh_max=max(initial[1],fresh[1])
    adjacent_max=fresh_max+2*adjacent_radius_shift[1]
    inscribed=min(aspects)
    return {'directional_rectangular_clipping_may_intervene':max(old_max,fresh_max,adjacent_max)>inscribed,
            'nominal_old_layer_directional_clipping_may_intervene':old_max>inscribed,
            'nominal_fresh_branch_directional_clipping_may_intervene':fresh_max>inscribed,
            'nominal_adjacent_branch_directional_clipping_may_intervene':adjacent_max>inscribed,
            'directional_clipping_scope':'retained orbit plus current/fresh source and selected adjacent positive-radius branch; ideal coordinate potential only, not raster or reached ray validity'}


def _closed_form_step(n, *, a,b,local_radius,radial_domain,native_rate,fps,source_sample,
                      sample_rate,sample_domain,radius_time,source_time,projection_time,
                      adjacent_direction,sample_turn,radius_sample,pixel_scale,aspects,gain):
    row={'declared_steps':n,'status':'unknown','unknown_reasons':[],
         'retained_native_radius_interval':None,'fresh_native_radius_interval':None,
         'relative_old_minus_new_pixel_separation_interval':None,
         'ideal_colour_difference_gain_power_upper_bound':None,
         'colour_gain_power_unknown_reason':None,
         'directional_rectangular_clipping_may_intervene':None,
         'nominal_old_layer_directional_clipping_may_intervene':None,
         'nominal_fresh_branch_directional_clipping_may_intervene':None,
         'nominal_adjacent_branch_directional_clipping_may_intervene':None,
         'actual_trail_thickness_pixels':None,'actual_overlap_verified':False,
         'actual_feedback_lifetime':None,'native_numeric_certified':False,
         'formula':'F^n(r)=a^n*r/(1-b*r*S_n); S_n=(a^n-1)/(a-1), or n when a=1',
         'scope':'declared finite nominal map composition before sampling/storage, with one same-angle fresh branch; no iterated frames or reached pixels'}
    try:
        if max(abs(a.numerator).bit_length(),a.denominator.bit_length())*n>8192:
            raise ValueError('closed-form power rational budget exceeded')
        power=a**n
        series=Fraction(n) if a==1 else (power-1)/(a-1)
        slope=b*series
        denominator=tuple(sorted(1-slope*r for r in local_radius))
        if denominator[0]<=0:raise ValueError('closed-form feedback composition reaches an inverse pole')
        retained=tuple(power*r/(1-slope*r) for r in local_radius)
        # Positive monotone F cannot cross a fixed point. Each orbit is monotone
        # between its initial/final radii. S_n is increasing for a>0, so its final
        # positive denominator also guards all earlier poles when b>=0.
        if min(local_radius[0],retained[0])<radial_domain[0] or max(local_radius[1],retained[1])>radial_domain[1]:
            raise ValueError('nominal monotone feedback orbit leaves the qualified enclosing radial domain')
        future_sample=_shift(source_sample,sample_rate*n/fps)
        if future_sample[0]<sample_domain[0] or future_sample[1]>sample_domain[1]:
            raise ValueError('n-step same-angle source branch leaves the finite sample domain')
        fresh=_shift(local_radius,native_rate*n/fps)
        if fresh[0]<=0:raise ValueError('n-step fresh source branch reaches nonpositive radius')
        if radius_time!=0 and source_time[1]+n/fps>_span(projection_time)[1]:
            raise ValueError('declared source time domain does not cover the n-step relation')
        adjacent_shift=tuple(sorted(adjacent_direction*value for value in sample_turn))
        radial_shift=_multiply((radius_sample,)*2,adjacent_shift)
        if (future_sample[0]+adjacent_shift[0]<sample_domain[0] or future_sample[1]+adjacent_shift[1]>sample_domain[1] or
                fresh[0]/2+radial_shift[0]<=0):
            raise ValueError('n-step adjacent positive-radius source branch leaves its regular domain')
        numerator=tuple(sorted(power-1+slope*r for r in local_radius))
        delta=_multiply(local_radius,_multiply(numerator,(1/denominator[1],1/denominator[0])))
        relative=_shift(delta,-native_rate*n/fps)
        gain_power=None
        gain_reason='qualified colour gain bound is unavailable' if gain is None else None
        if gain is not None:
            exact_gain=Fraction(gain)
            if max(abs(exact_gain.numerator).bit_length(),exact_gain.denominator.bit_length())*n<=8192:
                try:gain_power=_enclosure((exact_gain**n,)*2)[1]
                except (ValueError,OverflowError) as error:gain_reason=str(error)
            else:gain_reason='colour gain power rational budget exceeded'
        row.update(status='conditional_closed_form_radial_relation',
            retained_native_radius_interval=_enclosure(retained),fresh_native_radius_interval=_enclosure(fresh),
            relative_old_minus_new_pixel_separation_interval=_enclosure(tuple(value*pixel_scale for value in relative)),
            ideal_colour_difference_gain_power_upper_bound=gain_power,
            colour_gain_power_unknown_reason=gain_reason,
            **_clipping_scopes(local_radius,retained,fresh,radial_shift,aspects),
            conditions=['Initial/final positive radii and monotone fractional-linear orbit bound all intermediate nominal radii; positive final denominator guards prior inverse poles',
                'Finite parameter/time/radius and adjacent-branch conditions hold through the declared n-step interval; coefficients and cadence remain fixed',
                'Enclosing disk validity is not rectangular viewport/ray, wrapping, clipping, smoothing, raster, texel or storage validity',
                'Gain^n is an ideal colour-operator difference bound under inherited premises, never achieved stroke intensity, layer count, lifetime or trail thickness'])
    except (ValueError,OverflowError,ZeroDivisionError) as error:row['unknown_reasons'].append(str(error))
    return row


def curve_feedback_relation(curve_recipe,projection,radial_feedback,colour_feedback, *, context=None):
    """Compare one old-layer inverse step with a same-angle fresh source branch.

    Context optionally declares source_radius_domain, feedback_fps and
    local_source_time_domain. Radius/cadence otherwise come from the qualified
    radial fixed_feature_projection. A time-varying radius requires a supplied
    projection time domain covering both ends of the local comparison step.
    Optional feedback_step_counts lists at most16 distinct declared integers
    in1..128 for bounded closed-form compositions, independently of one-step
    validity. These are algebraic source relations, not feedback frame runs.
    """
    result={'policy':POLICY,'status':'unknown','unknown_reasons':[],
        'viewport':None,'source_native_radius_domain':None,'declared_feedback_fps':None,'fps_is_observed':False,
        'local_source_time_domain':None,'nominal_native_radius_to_pixel_scale':None,
        'interturn_pitch_native_radius_interval':None,'interturn_pitch_pixels_interval':None,
        'signed_native_fixed_angle_radial_rate_exact':None,'signed_native_fixed_angle_radial_rate_interval':None,
        'feedback_inverse_radius_step_interval':None,'feedback_inverse_pixel_step_interval':None,
        'new_source_radius_step_interval':None,'new_source_pixel_step_interval':None,
        'relative_old_minus_new_radius_step_interval':None,'relative_old_minus_new_pixel_step_interval':None,
        'local_nominal_absolute_step_spacing_to_turn_pitch_ratio_interval':None,
        'local_nominal_step_spacing_less_than_interturn_pitch':None,
        'directional_rectangular_clipping_may_intervene':None,
        'nominal_old_layer_directional_clipping_may_intervene':None,
        'nominal_fresh_branch_directional_clipping_may_intervene':None,
        'nominal_adjacent_branch_directional_clipping_may_intervene':None,
        'nominal_old_layer_outside_horizontal_extent_possible':None,
        'nominal_old_layer_outside_vertical_extent_possible':None,
        'colour_difference_gain_upper_bound':None,'ideal_colour_half_life_evaluations_reference':None,
        'colour_envelope_status':'unknown','colour_envelope_source_identity_independently_verified':False,
        'actual_overlap_verified':False,'actual_trail_thickness_pixels':None,'final_visible_density':None,
        'actual_feedback_lifetime':None,'feedback_history_or_wrapping_verified':False,
        'nominal_n_step_relations':[],'uses_iterated_frame_updates':False,
        'visible_motion_speed':None,'native_numeric_certified':False,'whole_preset_activity_credit':False,
        'uses_equation_execution':False,'uses_shader_execution':False,'uses_rendered_images':False,
        'source_provenance':None,'reference_input_conditions':{},
        'scope':'one nominal local fixed-angle radial step and finite adjacent-turn scale; no feedback trajectory or reached pixels',
        'conditions':['Require matching source preset/qualified source34 engine identities and a declared shared viewport; accepted radial policy implies neutral central controls and selected fixed/default warp',
            'Use exact source affine coefficients and centre(.5,.5); positive signed wave radius R gives ideal aspect-corrected native radius r=2*R',
            'The r=2*R and radius-to-pixel factor max(viewport)/2 relations exclude stored aspect/inverse-aspect rounding, EEL arithmetic, float32 zoom/upload, mesh interpolation and GPU arithmetic',
            'Adjacent same-angle branches differ by 2*pi/phase_sample in sample; native pitch is abs(4*pi*radius_sample/phase_sample), enclosed using 333/106 < pi < 355/113',
            'Hold a regular angular branch fixed: native radial rate=2*(radius_time-radius_sample*phase_time/phase_sample); require finite nonzero sample phase and regular current/future finite sample/radius domains',
            'Old-layer inverse displacement at r is a*r/(1-b*r)-r; subtract fresh radial rate/declaredFPS for the relative one-step separation',
            'The declared cadence is a source-time step assumption, not measured rendering cadence; clock jumps/wraps and changing coefficients are excluded',
            'The radial enclosing disk is not rectangular viewport/ray validity; clipping, texel offsets, interpolation, sampler wrap/filtering, line smoothing/width and raster footprint may change or suppress the local source relation',
            'Colour difference gain and ideal half-life remain independent conditional operator bounds supplied from the same source analysis; the colour schema carries no independent source identity proof',
            'Nonlinear radius evolution changes each older layer step; never multiply point displacement or this local step by half-life to certify trail thickness, layer count or visible density',
            'Drawing order, colour/alpha, injection, quantization/storage, transition/detail paths, feedback history and final colour/composition remain separate; no native, visible, mood or whole-preset certification follows']}
    try:
        if context is None:context={}
        context=_mapping(context,'relation context')
        curve_recipe=_mapping(curve_recipe,'curve recipe')
        projection=_mapping(projection,'curve projection')
        radial_feedback=_mapping(radial_feedback,'radial feedback')
        colour_feedback=_mapping(colour_feedback,'colour feedback')
        if curve_recipe.get('policy')!='source-parametric-wave-v1' or curve_recipe.get('waveform_independent_geometry') is not True:
            raise ValueError('supported waveform-independent source curve is required')
        if projection.get('policy')!='source-curve-projection-v1' or projection.get('status')!='conditional_projected_coordinates' or projection.get('viewport_was_defaulted') is not False:
            raise ValueError('qualified source projection with an explicitly declared viewport/domain is required')
        if radial_feedback.get('policy')!='source-affine-radial-feedback-v1' or radial_feedback.get('status')!='conditional_affine_radial_sampler':
            raise ValueError('qualified central fixed/default radial sampler is required')
        basis=_mapping(radial_feedback.get('radius_basis_evidence'),'radial basis')
        if basis.get('eel_and_gpu_share_uploaded_radius') is not True:raise ValueError('qualified native radius basis is absent')
        hashes=[_origin(curve_recipe.get('source_provenance'),'curve'),
                _origin(projection.get('source_curve_provenance'),'projection'),
                _origin(radial_feedback.get('source_provenance'),'radial feedback')]
        if len(set(hashes))!=1:raise ValueError('curve/projection/feedback source preset identities differ')
        viewport=projection.get('viewport')
        if not isinstance(viewport,(list,tuple)) or len(viewport)!=2 or any(type(value) is not int or not 0<value<2**31 for value in viewport):
            raise ValueError('shared viewport requires positive native int32 dimensions')
        if list(viewport)!=radial_feedback.get('viewport'):raise ValueError('projection and radial viewport identities differ')
        centres=curve_recipe.get('centre_source_xy_exact')
        if not isinstance(centres,list) or len(centres)!=2 or any(_exact(value)!=Fraction(1,2) for value in centres):
            raise ValueError('source curve requires exact central(.5,.5) coordinates')
        radius=_affine_coefficients(curve_recipe,'radius')
        phase=_affine_coefficients(curve_recipe,'phase')
        if phase['sample']==0 or radius['sample']==0:raise ValueError('regular nonzero sample phase and radial sample slope are required')
        sample_data=_mapping(curve_recipe.get('sample_domain'),'curve sample domain')
        if type(sample_data.get('effective_samples')) is not int or not 2<=sample_data['effective_samples']<=512 or sample_data.get('single_dot_nonfinite_sample_excluded') is not True:
            raise ValueError('finite multi-point sample domain is required')
        sample_domain=_span(sample_data.get('native_float32_endpoint_interval'))
        fixed=radial_feedback.get('fixed_feature_projection')
        fixed={} if fixed is None else _mapping(fixed,'fixed feature projection')
        fps_value=context.get('feedback_fps',fixed.get('declared_feedback_fps'))
        fps=_number(fps_value)
        if fps<=0:raise ValueError('positive declared feedback cadence is required')
        local_radius=_span(context.get('source_radius_domain',fixed.get('source_radius_interval')))
        if local_radius[0]<=0:raise ValueError('local native radius must be strictly positive')
        source_time=None
        projection_time=projection.get('source_time_domain')
        if radius['time']!=0:
            domain=_span(projection_time)
            source_time=_span(context['local_source_time_domain']) if 'local_source_time_domain' in context else (domain[0],domain[1]-1/fps)
            if source_time[0]>source_time[1] or source_time[0]<domain[0] or source_time[1]+1/fps>domain[1]:
                raise ValueError('declared time domain must cover the entire current/new local step')
        elif 'local_source_time_domain' in context:source_time=_span(context['local_source_time_domain'])
        time_offset=(0,0) if source_time is None else _multiply((radius['time'],)*2,source_time)
        source_sample=_inverse_span((local_radius[0]/2-radius['constant']-time_offset[1],
                                     local_radius[1]/2-radius['constant']-time_offset[0]),radius['sample'])
        sample_rate=-phase['time']/phase['sample']
        future_sample=_shift(source_sample,sample_rate/fps)
        if any(span[0]<sample_domain[0] or span[1]>sample_domain[1] for span in (source_sample,future_sample)):
            raise ValueError('current or new fixed-angle branch leaves the finite sample domain')
        native_rate=2*(radius['time']+radius['sample']*sample_rate)
        source_step=native_rate/fps
        if local_radius[0]+source_step<=0:raise ValueError('new source radius reaches the zero-radius angular singularity')
        sample_turn=tuple(2*pi/abs(phase['sample']) for pi in PI_INTERVAL)
        adjacent_direction=None
        for direction in (-1,1):
            shift=tuple(sorted(direction*value for value in sample_turn))
            radial_shift=_multiply((radius['sample'],)*2,shift)
            pairs=[(source_sample,tuple(value/2 for value in local_radius)),
                   (future_sample,tuple((value+source_step)/2 for value in local_radius))]
            if all(sample[0]+shift[0]>=sample_domain[0] and sample[1]+shift[1]<=sample_domain[1] and
                   radial[0]+radial_shift[0]>0 for sample,radial in pairs):
                adjacent_direction=direction
                break
        if adjacent_direction is None:
            raise ValueError('no finite strictly-positive-radius adjacent branch persists across the comparison step')
        pitch=tuple(4*abs(radius['sample'])*pi/abs(phase['sample']) for pi in PI_INTERVAL)
        coefficients=_mapping(radial_feedback.get('zoom_affine_coefficients_exact'),'exact radial zoom')
        a,b=(_exact(coefficients[key]) for key in ('a','b'))
        if a<=0:raise ValueError('positive radial inverse coefficient is required')
        denominator=tuple(sorted(1-b*r for r in local_radius))
        if denominator[0]<=0:raise ValueError('radial inverse reaches its pole')
        after=tuple(a*r/(1-b*r) for r in local_radius)
        radial_domain=_span(radial_feedback.get('output_radius_domain'))
        if local_radius[1]>radial_domain[1] or after[0]<radial_domain[0] or after[1]>radial_domain[1]:
            raise ValueError('local radial inverse leaves the qualified enclosing radius domain')
        numerator=tuple(sorted(a-1+b*r for r in local_radius))
        delta=_multiply(local_radius,_multiply(numerator,(1/denominator[1],1/denominator[0])))
        relative=_shift(delta,-source_step)
        pixel_scale=Fraction(max(viewport),2)
        absolute=_absolute_span(relative)
        ratio=(absolute[0]/pitch[1],absolute[1]/pitch[0])
        aspects=radial_feedback.get('native_aspect_xy')
        if not isinstance(aspects,list) or len(aspects)!=2:raise ValueError('qualified native aspect pair is absent')
        aspects=list(map(_number,aspects))
        if any(value<=0 or value>1 for value in aspects):raise ValueError('qualified native aspect pair is invalid')
        orbit_max=max(local_radius[1],after[1])
        gain=None
        if colour_feedback.get('policy')=='source-varying-affine-feedback-colour-envelope-v1' and colour_feedback.get('source_model')=='bounded_affine_main_sample_colour':
            supplied=colour_feedback.get('maximum_colour_difference_gain')
            if type(supplied) in {int,float} and math.isfinite(supplied) and supplied>=0:gain=supplied
        half_life=colour_feedback.get('ideal_perturbation_half_life_upper_bound_evaluations')
        if (gain is None or not 0<gain<1 or colour_feedback.get('coordinate_feedback_dependency') is not False or
                colour_feedback.get('sufficient_contraction_bound') is not True or
                type(half_life) not in {int,float} or not math.isfinite(half_life) or half_life<0):half_life=None
        result.update(status='conditional_local_curve_feedback_relation',viewport=list(viewport),
            source_native_radius_domain=_enclosure(local_radius),declared_feedback_fps=float(fps),
            local_source_time_domain=None if source_time is None else _enclosure(source_time),
            nominal_native_radius_to_pixel_scale=float(pixel_scale),
            interturn_pitch_native_radius_interval=_enclosure(pitch),interturn_pitch_pixels_interval=_enclosure(tuple(value*pixel_scale for value in pitch)),
            signed_native_fixed_angle_radial_rate_exact=_metadata(native_rate),signed_native_fixed_angle_radial_rate_interval=_enclosure((native_rate,)*2),
            feedback_inverse_radius_step_interval=_enclosure(delta),feedback_inverse_pixel_step_interval=_enclosure(tuple(value*pixel_scale for value in delta)),
            new_source_radius_step_interval=_enclosure((source_step,)*2),new_source_pixel_step_interval=_enclosure((source_step*pixel_scale,)*2),
            relative_old_minus_new_radius_step_interval=_enclosure(relative),relative_old_minus_new_pixel_step_interval=_enclosure(tuple(value*pixel_scale for value in relative)),
            local_nominal_absolute_step_spacing_to_turn_pitch_ratio_interval=_enclosure(ratio),
            local_nominal_step_spacing_less_than_interturn_pitch=absolute[1]<pitch[0],
            **_clipping_scopes(local_radius,after,_shift(local_radius,source_step),radial_shift,aspects),
            nominal_old_layer_outside_horizontal_extent_possible=orbit_max>aspects[0],
            nominal_old_layer_outside_vertical_extent_possible=orbit_max>aspects[1],
            colour_difference_gain_upper_bound=gain,ideal_colour_half_life_evaluations_reference=half_life,
            colour_envelope_status='conditional_operator_bound' if gain is not None else 'unknown',
            source_provenance=curve_recipe['source_provenance'],
            reference_input_conditions={name:value.get('conditions',[]) for name,value in
                [('curve',curve_recipe),('projection',projection),('radial_feedback',radial_feedback),('colour_feedback',colour_feedback)]})
        counts=context.get('feedback_step_counts',[])
        if not isinstance(counts,list) or len(counts)>16 or any(type(n) is not int or not 1<=n<=128 for n in counts):
            result['unknown_reasons'].append('optional feedback_step_counts requires at most16 integers in1..128')
        else:
            for n in dict.fromkeys(counts):
                result['nominal_n_step_relations'].append(_closed_form_step(n,a=a,b=b,
                    local_radius=local_radius,radial_domain=radial_domain,native_rate=native_rate,fps=fps,
                    source_sample=source_sample,sample_rate=sample_rate,sample_domain=sample_domain,
                    radius_time=radius['time'],source_time=source_time,projection_time=projection_time,
                    adjacent_direction=adjacent_direction,sample_turn=sample_turn,radius_sample=radius['sample'],
                    pixel_scale=pixel_scale,aspects=aspects,gain=gain))
    except (ValueError,OverflowError,KeyError,ZeroDivisionError) as error:
        result['unknown_reasons'].append(str(error))
    return result
