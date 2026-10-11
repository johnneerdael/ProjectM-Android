"""RGBA8 stored-level decay orbits for a fixed uniform warp decay.

The pinned source34 warp writes ``decay * texture(main)`` (mediump) into the
GL_RGBA / UNSIGNED_BYTE main image. Inside a locally uniform neighbourhood
bilinear sampling returns the stored level k/255, so the next stored level is
the unorm8 conversion of the shader product. The orbit is computed under three
declared arithmetic profiles: exact real, float32 and fp16 mediump. Levels near
a rounding tie can differ between them, so results are reported per profile and
as intervals. GLES prefers round-to-nearest conversion; truncation would remove
the nonzero floor. This is no visible trail, brightness or mood certificate.
"""
from fractions import Fraction
import math

import numpy as np


POLICY='source-unorm8-decay-persistence-v2'
LEVELS=255
PROFILES=('real','float32','fp16_mediump')
ORBIT_STATUSES={'conditional_quantized_decay_orbit','conditional_quantized_decay_orbit_profile_dependent'}


def _round_level(value):
    """Return (level, tie) for round-to-nearest; GLES leaves tie direction open."""
    floor=math.floor(value)
    remainder=value-floor
    if remainder==Fraction(1,2):return floor,True
    return (floor+1 if remainder>Fraction(1,2) else floor),False


def _product(level,gain,profile):
    """Shader product of a fetched unorm8 level and the decay, before conversion."""
    if profile=='real':return level*Fraction(gain)/LEVELS
    kind=np.float32 if profile=='float32' else np.float16
    texel=kind(level/LEVELS)
    return Fraction(float(kind(texel*kind(gain))))


def _level_map(gain,profile):
    """Next stored level for every level, with exact-tie flags."""
    return [_round_level(_product(k,gain,profile)*LEVELS) for k in range(LEVELS+1)]


def _orbit(mapping):
    orbit=[LEVELS]
    while True:
        level,tie=mapping[orbit[-1]]
        if tie:return None
        if level==orbit[-1] or len(orbit)>LEVELS+1:return orbit
        orbit.append(level)


def unorm8_decay_persistence(transfer,context):
    """Derive stored-level decay orbits from full white for a fixed decay.

    ``transfer`` is the exported ``feedback_transfer`` record; only the
    ``fixed_main_decay`` model with zero offset and image-independent sampling
    qualifies. ``context`` supplies the declared output storage and optional
    feedback FPS for seconds conversions. ``level_orbit_from_full`` is the
    float32 reference profile; ``profiles`` keeps every profile separately.
    """
    result={'policy':POLICY,'status':'unknown','decay_gain':None,'storage_levels':LEVELS,
        'reference_profile':'float32','profiles':{},'profiles_agree':None,
        'largest_stuck_level':None,'largest_stuck_level_interval':None,
        'floor_level_from_full':None,'floor_level_interval':None,'floor_fraction_from_full':None,
        'level_orbit_from_full':None,'steps_to_floor_from_full':None,'steps_to_floor_interval':None,
        'steps_to_half_from_full':None,'steps_to_half_interval':None,
        'seconds_to_floor_from_full':None,'seconds_to_half_from_full':None,'tie_levels':[],
        'quantized_decay_absent':None,'permanent_residual_possible':None,
        'conversion_rule':'round-to-nearest unorm8 (GLES preferred); truncation would leave no nonzero floor',
        'visible_trail_length':None,'actual_feedback_persistence':None,
        'native_numeric_certified':False,'uses_rendered_images':False,
        'uses_equation_execution':False,'uses_shader_execution':False,'unknown_reasons':[],
        'conditions':['Pinned source34 legacy warp writes min(decay,1)*texture(main) at mediump into the GL_RGBA/UNSIGNED_BYTE main image',
            'Locally uniform neighbourhood: bilinear sampling of equal texels returns the stored level; edges, gradients and filtering mix levels',
            'Arithmetic profiles: exact real, float32 and fp16 mediump products, then round-to-nearest unorm8; a driver can differ near ties and truncating conversion removes the floor',
            'No later drawing, blending, blur, diffusion pass or composite changes the stored level; levels are stored values, not displayed brightness',
            'projectM-TV policy: original MilkDrop2 blends decay during transitions and quantizes it to an 8-bit colour',
            'Levels that map to themselves are fixed points, so faint stored content can persist indefinitely under these premises']}
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
        result['decay_gain']=float(gain)
        ties=set();rows={}
        for profile in PROFILES:
            mapping=_level_map(gain,profile)
            ties.update(k for k,(_,tie) in enumerate(mapping) if tie)
            orbit=_orbit(mapping)
            stuck=max(k for k,(level,tie) in enumerate(mapping) if level==k and not tie)
            row={'largest_stuck_level':stuck,'level_orbit_from_full':orbit,'floor_level_from_full':None,
                 'steps_to_floor_from_full':None,'steps_to_half_from_full':None}
            if orbit is not None:
                row.update(floor_level_from_full=orbit[-1],steps_to_floor_from_full=len(orbit)-1,
                    steps_to_half_from_full=next((i for i,level in enumerate(orbit) if 2*level<=LEVELS),None))
            rows[profile]=row
        result['profiles']=rows;result['tie_levels']=sorted(ties)
        if any(row['level_orbit_from_full'] is None for row in rows.values()):
            result['status']='conditional_quantized_decay_orbit_ambiguous_ties'
            result['unknown_reasons'].append('an exact half-level tie occurs on an orbit; GLES tie direction is unspecified')
            return result
        span=lambda key:[min(r[key] for r in rows.values()),max(r[key] for r in rows.values())]
        reference=rows['float32']
        halves=[r['steps_to_half_from_full'] for r in rows.values()]
        agree=len({tuple(r['level_orbit_from_full']) for r in rows.values()})==1
        result.update(status='conditional_quantized_decay_orbit' if agree else 'conditional_quantized_decay_orbit_profile_dependent',
            profiles_agree=agree,largest_stuck_level=reference['largest_stuck_level'],
            largest_stuck_level_interval=span('largest_stuck_level'),
            floor_level_from_full=reference['floor_level_from_full'],floor_level_interval=span('floor_level_from_full'),
            floor_fraction_from_full=reference['floor_level_from_full']/LEVELS,
            level_orbit_from_full=reference['level_orbit_from_full'],
            steps_to_floor_from_full=reference['steps_to_floor_from_full'],steps_to_floor_interval=span('steps_to_floor_from_full'),
            steps_to_half_from_full=reference['steps_to_half_from_full'],
            steps_to_half_interval=None if None in halves else [min(halves),max(halves)])
        result['quantized_decay_absent']=all(r['largest_stuck_level']==LEVELS for r in rows.values())
        result['permanent_residual_possible']=any(r['floor_level_from_full']>0 for r in rows.values())
        fps=context.get('feedback_fps')
        if type(fps) in (int,float) and math.isfinite(fps) and fps>0:
            result['seconds_to_floor_from_full']=result['steps_to_floor_from_full']/fps
            half=result['steps_to_half_from_full']
            result['seconds_to_half_from_full']=None if half is None else half/fps
    except (ValueError,TypeError,OverflowError) as error:
        result['unknown_reasons'].append(str(error))
    return result


def persistence_horizon_steps(persistence):
    """Return (name, count) stored-level horizons across arithmetic profiles."""
    if not isinstance(persistence,dict) or persistence.get('status') not in ORBIT_STATUSES:return []
    rows=[]
    profiles=persistence.get('profiles') or {}
    for name,key in (('half_level','steps_to_half_from_full'),('floor_level','steps_to_floor_from_full')):
        values={row.get(key) for row in profiles.values() if isinstance(row,dict)}
        for steps in sorted(v for v in values if type(v) is int and v>0):rows.append((name,steps))
    return rows


def _horizon_rows(rows,name):
    return [row for row in rows if row['horizon']==name]


def persistence_layer_sweep(relation,persistence):
    """Compare retained/fresh separation at stored-level horizons with turn pitch.

    The relation's closed-form n-step separations must include each horizon.
    Crossing one pitch means retained copies drift across a whole inter-turn
    gap before their stored level reaches the floor; it supports a conditional
    gap-filling hypothesis, never achieved density or visible thickness. With
    profile-dependent horizons the crossing must hold at every floor horizon.
    """
    result={'policy':'source-persistence-layer-sweep-v2','status':'unknown','horizons':[],
        'interturn_gap_crossed_before_floor':None,'final_visible_density':None,
        'actual_overlap_verified':False,'actual_trail_thickness_pixels':None,
        'uses_rendered_images':False,'uses_equation_execution':False,'unknown_reasons':[],
        'conditions':['Closed-form nominal radial relation at a declared reference sample; other samples and turns can differ',
            'Stored-level horizons assume the conditional uniform-neighbourhood RGBA8 decay orbit from full white under each arithmetic profile',
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
        floors=[row['separation_exceeds_pitch'] for row in _horizon_rows(result['horizons'],'floor_level')]
        if floors and all(value is True for value in floors):result['interturn_gap_crossed_before_floor']=True
        elif floors and all(value is False for value in floors):result['interturn_gap_crossed_before_floor']=False
    except (ValueError,TypeError) as error:
        result['unknown_reasons'].append(str(error))
    return result


def _feature_map_jacobian_upper(radial):
    """Largest forward retained-feature stretch of the qualified radial map.

    Forward radial stretch is 1/(dr_source/dr_output); tangential stretch is
    r_output/r_source = a+b*r_output, the zoom itself.
    """
    if not isinstance(radial,dict) or radial.get('status')!='conditional_affine_radial_sampler':
        raise ValueError('qualified radial feedback map is absent; previous spread magnification is unbounded')
    derivative=radial.get('radial_sampling_derivative_range');zoom=radial.get('nominal_zoom_range')
    for span in (derivative,zoom):
        if (not isinstance(span,list) or len(span)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in span)
                or not 0<span[0]<=span[1]):raise ValueError('finite positive radial derivative/zoom ranges are required')
    return max(1/derivative[0],zoom[1],1.0)


def bilinear_diffusion_spread(relation,persistence,context=None,radial=None):
    """Bound bilinear-resampling spread of retained layers at stored-level horizons.

    Each GL_LINEAR read at sub-texel offset f adds variance f(1-f)<=1/4 texel^2
    per axis, and the feature map stretches spread by at most J per step.
    After n steps Var<=(1/4)*sum_{k=1..n} J^(2k). Whole-texel offsets add
    nothing, so there is no positive lower bound: layers *can* merge, and a
    negative answer is never asserted.
    """
    result={'policy':'source-bilinear-diffusion-spread-v2','status':'unknown','horizons':[],
        'per_step_variance_upper_texels2':0.25,'per_step_variance_uniform_offset_reference_texels2':1/6,
        'feature_map_stretch_upper':None,'adjacent_layer_merge_possible':None,
        'extra_diffusion_pass_excluded':None,'actual_trail_thickness_pixels':None,'final_visible_density':None,
        'uses_rendered_images':False,'uses_equation_execution':False,'unknown_reasons':[],
        'conditions':['Main texture texel equals one output pixel and warp reads use GL_LINEAR at the stored size',
            'Spread is stretched at most by the qualified radial map stretch J per step; Var_n<=(1/4)*sum_{k=1..n} J^(2k)',
            'An extra feedback-diffusion pass, added above the engine line-reference scale, would only widen spread; merge stays possible',
            'Offsets, mesh interpolation and storage rounding can reduce spread and line width can add to it; no merge lower bound exists',
            'Separation is the closed-form reference-sample relation; other samples and turns can differ']}
    try:
        context={} if context is None else context
        scale=context.get('feedback_diffusion_scale')
        if scale is not None:
            if type(scale) not in (int,float) or not math.isfinite(scale) or scale<=0:
                raise ValueError('declared feedback_diffusion_scale must be finite and positive')
            result['extra_diffusion_pass_excluded']=scale<=1
        if not isinstance(relation,dict) or relation.get('status')!='conditional_local_curve_feedback_relation':
            raise ValueError('qualified local curve/feedback relation is absent')
        horizons=persistence_horizon_steps(persistence)
        if not horizons:raise ValueError('stored-level persistence horizons are unresolved')
        stretch=_feature_map_jacobian_upper(radial)
        result['feature_map_stretch_upper']=stretch
        step=relation.get('relative_old_minus_new_pixel_step_interval')
        if (not isinstance(step,list) or len(step)!=2 or
                any(type(v) not in (int,float) or not math.isfinite(v) for v in step) or step[0]>step[1]):
            raise ValueError('finite per-step layer separation interval is absent')
        separation=0 if step[0]<=0<=step[1] else min(abs(step[0]),abs(step[1]))
        result['status']='conditional_bilinear_spread_bound'
        square=stretch*stretch
        for name,count in horizons:
            # Every read, including the newest, is stretched once more: sum_{k=1..n} J^(2k).
            total=count if square==1 else square*(square**count-1)/(square-1)
            result['horizons'].append({'horizon':name,'steps':count,'sigma_upper_pixels':math.sqrt(total/4),
                'sigma_uniform_offset_reference_pixels':math.sqrt(count/6)})
        largest=max(row['sigma_upper_pixels'] for row in result['horizons'])
        # Only a positive possibility is supported; spread can always be smaller.
        result['adjacent_layer_merge_possible']=True if largest>=separation/2 else None
        result['minimum_per_step_layer_separation_pixels']=separation
    except (ValueError,TypeError,OverflowError) as error:
        result['unknown_reasons'].append(str(error))
    return result
