"""Conditional local random-material difference ceilings, without RNG sampling.

Two admissible source states need not be adjacent, attained or visible. Refresh
opportunities describe source execution scope, never a measured event frequency.
"""
from fractions import Fraction
import math


POLICY='source-stochastic-material-brightness-v1'
GROUPS={'centre':('r','g','b','a'),'perimeter':('r2','g2','b2','a2'),
        'border':('border_r','border_g','border_b','border_a')}
FRAME_SCOPES={'main_frame_invocation','shape_instance_invocation'}


def _random_envelopes(recipe):
    from source_fill_envelopes import native_channel_envelope
    from source_material_temporal import _channel_from_curve
    from source_sampling_motion import _finite_round

    result=[]
    for channel in recipe['channels']:
        upper=_finite_round(Fraction(channel['maximum_random_argument'])/
                            Fraction(channel['division_denominator']),upper=True)
        curve={'nominal_value_range':None if upper is None else [0.,upper],
               'maximum_absolute_control_rate_per_second':None,'nominal_continuity':'unknown',
               'curve_kind':'unknown','unknown_reasons':[]}
        result.append(native_channel_envelope(_channel_from_curve(curve,'stochastic_rgb')))
    return result


def _differences(groups,blend, *, rng_only=False,unit_texture=False):
    """Barycentric product ceiling with outward rational final rounding."""
    from source_sampling_motion import _finite_round
    from source_shape_jump_bounds import _quadratic_maximum

    incoming=[None]*3
    blended=[None]*3
    alpha=[group['native_alpha_envelope'] for group in groups]
    if any(span is None for span in alpha):return incoming,blended
    amax=[Fraction(span[1]) for span in alpha]
    da=[Fraction(0) if rng_only else Fraction(span[1])-Fraction(span[0]) for span in alpha]
    linear=all(span[1]<=1 for span in alpha)
    for axis in range(3):
        colours=[group['native_rgb_component_envelopes'][axis] for group in groups]
        if any(span is None for span in colours):continue
        cmax=[Fraction(span[1]) for span in colours]
        dc=[]
        for group,span in zip(groups,colours):
            recipe=group['random_recipe']
            frozen=rng_only and (recipe is None or recipe['refresh_scope']=='preset_initialization')
            dc.append(Fraction(0) if frozen else Fraction(span[1])-Fraction(span[0]))
        contrast=[max(Fraction(span[1]),Fraction(1) if unit_texture else
                      1-min(Fraction(span[0]),1)) for span in colours]

        def ceiling(magnitudes):
            if linear and len(groups)==2:
                matrix=[[amax[i]*dc[j]+magnitudes[j]*da[i] for j in range(2)] for i in range(2)]
                return _quadratic_maximum(matrix)
            return _finite_round(min(max(amax),1)*max(dc)+max(magnitudes)*min(max(da),1),upper=True)

        incoming[axis]=ceiling(cmax)
        if blend=='source_alpha_additive':blended[axis]=incoming[axis]
        elif blend=='source_alpha_over':blended[axis]=ceiling(contrast)
    return incoming,blended


def _norm(values):
    return None if any(value is None for value in values) else max(values)


def _opportunities(scopes,complete,context):
    if not complete:return None
    if not scopes or set(scopes)=={'preset_initialization'}:return 0.
    if not set(scopes)<=FRAME_SCOPES|{'preset_initialization'}:return None
    fps=context.get('feedback_fps')
    if isinstance(fps,bool) or not isinstance(fps,(int,float)) or not math.isfinite(fps) or fps<=0:return None
    return float(fps)


def stochastic_material_brightness(analysis,element,context):
    """Return shape fill/border bounds when random RGB/alpha is present.

    Nonrandom live groups remain in each part. Unsupported random expressions,
    absent alpha/native domains and invalid colour conversions retain nulls.
    """
    from effect_families import _has
    from source_colour_character import _random_vertex_palette
    from source_fill_envelopes import native_channel_envelope

    controls=getattr(analysis,'component_controls',{}).get(element['id'])
    if controls is None or 'material' not in element:return []
    if not any(_has(controls[name],'rand') for names in GROUPS.values() for name in names):return []
    recipes=_random_vertex_palette(controls) or {}
    temporal=element.get('scenario_material_envelope') or element['material_temporal']
    channels=temporal['channels']
    material=element['material']
    records=[]
    for part,names in (('fill',('centre','perimeter')),('border',('border',))):
        if part=='border' and temporal['border_gate']['nominal_always_enabled'] is False:continue
        groups={}
        reasons=[]
        scopes=set()
        complete=True
        invalid=False
        for name in names:
            channel_names=GROUPS[name]
            recipe=recipes.get(name)
            random_rgb=any(_has(controls[n],'rand') for n in channel_names[:3])
            if random_rgb and recipe is None:
                rgb=[None]*3
                reasons.append(name+' random RGB has no supported group recipe')
                complete=False
            else:
                rgb=_random_envelopes(recipe) if recipe else [native_channel_envelope(channels[n]) for n in channel_names[:3]]
            alpha=native_channel_envelope(channels[channel_names[3]])
            if _has(controls[channel_names[3]],'rand'):
                # Random alpha has no producer recipe, even if a caller supplied
                # a value range; do not fabricate a resampling/weighting proof.
                alpha=None
                complete=False
                reasons.append(name+' random alpha has no supported recipe')
            if recipe:scopes.update(channel['refresh_scope'] for channel in recipe['channels'])
            for n in channel_names:
                channel=channels[n]
                if channel['raw_time_curve']['nominal_value_range'] is not None and channel['native_float32_endpoint_domain'] is None:
                    invalid=True
                    reasons.append(n+' has no finite native float32 endpoint domain')
            if any(span is None for span in rgb):reasons.append(name+' native RGB endpoint domain is unresolved')
            if alpha is None:reasons.append(name+' native alpha endpoint domain is unresolved')
            groups[name]={'status':'supported_random_recipe' if recipe else 'unresolved' if any(span is None for span in rgb) else 'native_endpoint_envelope',
                          'random_recipe':recipe,'native_rgb_component_envelopes':rgb,
                          'native_alpha_envelope':alpha}

        # The raw border draw gate is separate from native modulo alpha. Its
        # possible off state participates in the two-state material ceiling.
        if part=='border' and temporal['border_gate']['nominal_always_enabled'] is not True:
            alpha=groups['border']['native_alpha_envelope']
            if alpha is not None:groups['border']['native_alpha_envelope']=[0.,alpha[1]]
            reasons.append('border gate may turn the draw off; no gate event rate is proved')
        blend=material['blend_mode']
        if blend is None:reasons.append('native blend mode is unresolved')
        values=list(groups.values())
        incoming,blended=_differences(values,blend)
        _,rng=_differences(values,blend,rng_only=True)
        textured=part=='fill' and material['texture']['role']!='untextured_vertex_gradient'
        partial=None
        if textured:
            pin,pblend=_differences(values,blend,unit_texture=True)
            _,prng=_differences(values,blend,rng_only=True,unit_texture=True)
            partial={'maximum_incoming_rgb_difference':pin,'maximum_blended_rgb_difference':pblend,
                     'maximum_local_rgb_infinity_norm_difference':_norm(pblend),
                     'maximum_rng_induced_frame_rgb_difference':prng,'sample_rgba_domain':[0,1],
                     'sample_rgba_is_held_fixed':True,
                     'scope':'partial material difference only with the same fixed texture sample RGBA in the declared unit domain'}
            incoming=blended=rng=[None]*3
            reasons.append('texture sample/geometry/history is unresolved; only a fixed unit-texture material partial is available')
        records.append({'policy':POLICY,'element_id':element['id'],'part':part,'groups':groups,
            'maximum_incoming_rgb_difference':incoming,'maximum_blended_rgb_difference':blended,
            'maximum_local_rgb_infinity_norm_difference':_norm(blended),
            'maximum_rng_induced_frame_rgb_difference':rng,
            'maximum_rng_induced_frame_rgb_infinity_norm_difference':_norm(rng),
            'maximum_continuous_rgb_rate_per_second':None,
            'refresh_scopes':sorted(scopes),'refresh_scope_metadata_complete':complete,
            'maximum_frame_refresh_opportunities_per_second':_opportunities(scopes,complete,context),
            'configured_instances':element['geometry']['configured_instances'],
            'instance_frequency_aggregation':'none; instances do not define a per-pixel temporal event frequency',
            'blend_mode':blend,'destination_rgb_domain':[0,1],
            'fixed_unit_texture_partial':partial,'known_invalid_native_domain':invalid,
            'rng_distribution_assumed':False,'independent_draws_assumed':False,
            'other_material_inputs_temporally_fixed_proved':False,
            'event_frequency_hz':None,'visible_flash_strength':None,'visible_flashing_verified':False,
            'native_numeric_certified':False,'whole_preset_activity_credit':False,
            'uses_rendered_images':False,'uses_equation_execution':False,
            'unknown_reasons':list(dict.fromkeys(reasons)),
            'scope':'two admissible material states at fixed geometry, coverage, barycentric weights, sample and destination before storage/later passes',
            'conditions':['Finite supported source arithmetic and finite native conversions are conditional premises, not native execution certification',
                'Random recipe arguments/divisors are fixed finite constants; all source intermediate operations remain finite and supplied native endpoint domains hold',
                'Reuse supported native random RGB group recipes and outward native modulo envelopes; copied draws retain identity and separate sites imply neither independence nor an RNG distribution',
                'Fixed nonnegative barycentric weights sum to one; alpha is clamped after interpolation and optional RGB/output clipping is nonexpansive',
                'Two-state ceilings allow varying admissible material inputs; RNG-only frame partial additionally holds all non-RNG inputs and alpha/gate fixed',
                'Init-only copies persist within a preset: zero RNG frame partial proves nothing about changes in alpha, geometry or other inputs',
                'Declared FPS bounds frame refresh opportunities only; instance invocations/draw sites are not per-pixel Hz and no attained event/cycle rate follows',
                'Borders, instance overlap, raster footprint, moving geometry, storage, texture/history, later shaders and feedback do not acquire visibility or whole-mood evidence',
                'Random steps supply no continuous derivative, probability, minimum jump, displayed flash strength/frequency or safe-absence claim']})
    return records
