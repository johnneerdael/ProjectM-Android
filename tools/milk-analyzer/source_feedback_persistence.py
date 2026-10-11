"""Exact RGBA8 level orbits for a fixed uniform warp decay.

The pinned source34 warp writes ``decay * texture(main)`` into the GL_RGBA /
UNSIGNED_BYTE main image. Inside a locally uniform neighbourhood bilinear
sampling returns the stored level k/255, so the next stored level is the
round-to-nearest unorm8 conversion of k*d. Every level with k*(1-d) < 1/2 is a
fixed point: faint content never decays further, and a full-white level stalls
at the largest such level. This is integer arithmetic on the nominal float32
product; it is no visible trail, brightness or mood certificate.
"""
from fractions import Fraction
import math


POLICY='source-unorm8-decay-persistence-v1'
LEVELS=255


def _round_level(value):
    """Return (level, tie) for round-to-nearest; GLES leaves tie direction open."""
    floor=math.floor(value)
    remainder=value-floor
    if remainder==Fraction(1,2):return floor,True
    return (floor+1 if remainder>Fraction(1,2) else floor),False


def unorm8_decay_persistence(transfer,context):
    """Derive the stored-level decay orbit from full white for a fixed decay.

    ``transfer`` is the exported ``feedback_transfer`` record; only the
    ``fixed_main_decay`` model with zero offset and image-independent sampling
    qualifies. ``context`` supplies the declared output storage and optional
    feedback FPS for seconds conversions.
    """
    result={'policy':POLICY,'status':'unknown','decay_gain':None,'storage_levels':LEVELS,
        'largest_stuck_level':None,'floor_level_from_full':None,'floor_fraction_from_full':None,
        'level_orbit_from_full':None,'steps_to_floor_from_full':None,'steps_to_half_from_full':None,
        'seconds_to_floor_from_full':None,'seconds_to_half_from_full':None,'tie_levels':[],
        'quantized_decay_absent':None,'permanent_residual_possible':None,
        'visible_trail_length':None,'actual_feedback_persistence':None,
        'native_numeric_certified':False,'uses_rendered_images':False,
        'uses_equation_execution':False,'uses_shader_execution':False,'unknown_reasons':[],
        'conditions':['Pinned source34 legacy warp writes decay*texture(main) into the GL_RGBA/UNSIGNED_BYTE main image',
            'Locally uniform neighbourhood: bilinear sampling of equal texels returns the stored level; edges, gradients and filtering mix levels',
            'Nominal real product of the float32 decay and k/255, then round-to-nearest unorm8 conversion; mediump/fp16 shader arithmetic and driver rounding are not certified',
            'No later drawing, blending, blur, diffusion pass or composite changes the stored level; levels are stored values, not displayed brightness',
            'Every level k with k*(1-d)<1/2 is a fixed point, so faint stored content can persist indefinitely under these premises']}
    try:
        if not isinstance(context,dict) or context.get('output_storage')!='normalized-unorm':
            raise ValueError('declared normalized-unorm output storage is required')
        if not isinstance(transfer,dict) or transfer.get('policy')!='source-warp-colour-transfer-v1':
            raise ValueError('supported warp colour transfer is absent')
        if transfer.get('source_model')!='fixed_main_decay':
            raise ValueError('only the fixed main-decay warp model has a uniform level map')
        if transfer.get('coordinate_feedback_dependency') is not False:
            raise ValueError('image-dependent sampling coordinates break the uniform level map')
        offset=transfer.get('constant_offset_rgb')
        if not isinstance(offset,list) or len(offset)!=3 or any(value!=0 for value in offset):
            raise ValueError('a nonzero constant colour offset changes the level map')
        gain=transfer.get('uniform_diagonal_gain')
        if type(gain) not in (int,float) or not math.isfinite(gain) or not 0<gain<=1:
            raise ValueError('a finite uniform decay gain in (0,1] is required')
        decay=Fraction(gain)
        result['decay_gain']=float(gain)
        ties=[k for k in range(LEVELS+1) if _round_level(k*decay)[1]]
        stuck=[k for k in range(LEVELS+1) if not _round_level(k*decay)[1] and _round_level(k*decay)[0]==k]
        result['largest_stuck_level']=max(stuck)
        result['quantized_decay_absent']=result['largest_stuck_level']==LEVELS
        result['permanent_residual_possible']=result['largest_stuck_level']>0
        orbit=[LEVELS]
        while True:
            level,tie=_round_level(orbit[-1]*decay)
            if tie:
                result['tie_levels']=ties
                result['status']='conditional_quantized_decay_orbit_ambiguous_ties'
                result['unknown_reasons'].append('an exact half-level tie occurs on the orbit; GLES tie direction is unspecified')
                return result
            if level==orbit[-1]:break
            orbit.append(level)
        result['tie_levels']=ties
        floor=orbit[-1]
        half=next((index for index,level in enumerate(orbit) if 2*level<=LEVELS),None)
        result.update(status='conditional_quantized_decay_orbit',level_orbit_from_full=orbit,
            floor_level_from_full=floor,floor_fraction_from_full=floor/LEVELS,
            steps_to_floor_from_full=len(orbit)-1,steps_to_half_from_full=half)
        fps=context.get('feedback_fps')
        if type(fps) in (int,float) and math.isfinite(fps) and fps>0:
            result['seconds_to_floor_from_full']=(len(orbit)-1)/fps
            result['seconds_to_half_from_full']=None if half is None else half/fps
    except (ValueError,TypeError,OverflowError) as error:
        result['unknown_reasons'].append(str(error))
    return result


def persistence_horizon_steps(persistence):
    """Return named stored-level horizons usable as declared feedback steps."""
    if not isinstance(persistence,dict) or persistence.get('status')!='conditional_quantized_decay_orbit':return []
    rows=[]
    for name,key in (('half_level','steps_to_half_from_full'),('floor_level','steps_to_floor_from_full')):
        steps=persistence.get(key)
        if type(steps) is int and steps>0:rows.append((name,steps))
    return rows


def persistence_layer_sweep(relation,persistence):
    """Compare retained/fresh separation at stored-level horizons with turn pitch.

    The relation's closed-form n-step separations must include each horizon.
    Crossing one pitch means retained copies drift across a whole inter-turn
    gap before their stored level reaches the floor; it supports a conditional
    gap-filling hypothesis, never achieved density or visible thickness.
    """
    result={'policy':'source-persistence-layer-sweep-v1','status':'unknown','horizons':[],
        'interturn_gap_crossed_by_retained_layers_above_floor':None,'final_visible_density':None,
        'actual_overlap_verified':False,'actual_trail_thickness_pixels':None,
        'uses_rendered_images':False,'uses_equation_execution':False,'unknown_reasons':[],
        'conditions':['Closed-form nominal radial relation at a declared reference sample; other samples and turns can differ',
            'Stored-level horizons assume the conditional uniform-neighbourhood RGBA8 decay orbit from full white',
            'Crossing compares separation with turn pitch only; line width, filtering, overlap, clipping and composite remain unverified']}
    try:
        if not isinstance(relation,dict) or relation.get('status')!='conditional_local_curve_feedback_relation':
            raise ValueError('qualified local curve/feedback relation is absent')
        horizons=persistence_horizon_steps(persistence)
        if not horizons:raise ValueError('stored-level persistence horizons are unresolved')
        pitch=relation.get('interturn_pitch_pixels_interval')
        if (not isinstance(pitch,list) or len(pitch)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in pitch)
                or not 0<pitch[0]<=pitch[1]):raise ValueError('finite positive inter-turn pitch interval is absent')
        steps={row.get('declared_steps'):row for row in relation.get('nominal_n_step_relations',[]) if isinstance(row,dict)}
        result['status']='conditional_persistence_layer_sweep'
        for name,count in horizons:
            row={'horizon':name,'steps':count,'separation_pixels_interval':None,'separation_exceeds_pitch':None,
                 'gap_crossings_lower_bound':None}
            entry=steps.get(count)
            span=None if not isinstance(entry,dict) or entry.get('status')!='conditional_closed_form_radial_relation' else \
                entry.get('relative_old_minus_new_pixel_separation_interval')
            if (isinstance(span,list) and len(span)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in span)
                    and span[0]<=span[1]):
                low=0 if span[0]<=0<=span[1] else min(abs(span[0]),abs(span[1]))
                high=max(abs(span[0]),abs(span[1]))
                row['separation_pixels_interval']=span
                row['separation_exceeds_pitch']=True if low>pitch[1] else False if high<pitch[0] else None
                row['gap_crossings_lower_bound']=math.floor(low/pitch[1])
            else:result['unknown_reasons'].append(f'{name} horizon of {count} steps has no closed-form separation')
            result['horizons'].append(row)
        floor=next((row for row in result['horizons'] if row['horizon']=='floor_level'),None)
        if floor is not None:result['interturn_gap_crossed_by_retained_layers_above_floor']=floor['separation_exceeds_pitch']
    except (ValueError,TypeError) as error:
        result['unknown_reasons'].append(str(error))
    return result


def bilinear_diffusion_spread(relation,persistence,context=None):
    """Bound bilinear-resampling spread of retained layers at stored-level horizons.

    A bilinear tap at sub-texel offset f spreads a texel with variance f(1-f)
    <= 1/4 texel^2 per axis, so n retained resamples spread at most sqrt(n/4)
    pixels per axis; the engine's uniform-offset reference is 1/6 per step.
    Whole-texel offsets add nothing, so no positive lower bound exists. Comparing
    the ceiling with half the per-step layer separation says whether adjacent
    retained copies can merge into continuous bands.
    """
    result={'policy':'source-bilinear-diffusion-spread-v1','status':'unknown','horizons':[],
        'per_step_variance_upper_texels2':0.25,'per_step_variance_uniform_offset_reference_texels2':1/6,
        'adjacent_layer_merge_possible':None,'adjacent_layer_merge_guaranteed':None,
        'extra_diffusion_pass_excluded':None,'actual_trail_thickness_pixels':None,'final_visible_density':None,
        'uses_rendered_images':False,'uses_equation_execution':False,'unknown_reasons':[],
        'conditions':['Main texture texel equals one output pixel and warp reads use GL_LINEAR at the stored size',
            'No extra feedback-diffusion pass: the engine adds (s^2-1)/6 render px^2 per frame only above its line reference scale s>1',
            'Variance bound per axis per resample; offsets, mesh interpolation and storage rounding can reduce spread, so merge is only possible',
            'Separation is the closed-form reference-sample relation; other samples and turns can differ']}
    try:
        context={} if context is None else context
        scale=context.get('feedback_diffusion_scale')
        if scale is not None:
            if type(scale) not in (int,float) or not math.isfinite(scale) or scale<=0:
                raise ValueError('declared feedback_diffusion_scale must be finite and positive')
            if scale>1:raise ValueError('declared scale above the line reference adds an extra diffusion pass')
            result['extra_diffusion_pass_excluded']=True
        if not isinstance(relation,dict) or relation.get('status')!='conditional_local_curve_feedback_relation':
            raise ValueError('qualified local curve/feedback relation is absent')
        horizons=persistence_horizon_steps(persistence)
        if not horizons:raise ValueError('stored-level persistence horizons are unresolved')
        step=relation.get('relative_old_minus_new_pixel_step_interval')
        if (not isinstance(step,list) or len(step)!=2 or
                any(type(v) not in (int,float) or not math.isfinite(v) for v in step) or step[0]>step[1]):
            raise ValueError('finite per-step layer separation interval is absent')
        separation=0 if step[0]<=0<=step[1] else min(abs(step[0]),abs(step[1]))
        result['status']='conditional_bilinear_spread_bound'
        for name,count in horizons:
            result['horizons'].append({'horizon':name,'steps':count,'sigma_upper_pixels':math.sqrt(count/4),
                'sigma_uniform_offset_reference_pixels':math.sqrt(count/6)})
        first=min(row['sigma_upper_pixels'] for row in result['horizons'])
        result['adjacent_layer_merge_possible']=first>=separation/2
        result['minimum_per_step_layer_separation_pixels']=separation
    except (ValueError,TypeError) as error:
        result['unknown_reasons'].append(str(error))
    return result
