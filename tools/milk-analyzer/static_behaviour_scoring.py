"""Initial preference mapping over source brightness, transport and extent.

The point estimate describes known source potential, not a measured percentile.
Missing contributing effects widen the range and veto automatic eligibility.
"""
import hashlib
import json
import math

POLICY = 'static-activity-preference-v1'
BANDS = (('Chill', 1., 30.), ('Normal', 25., 75.), ('Intense', 70., 100.))
RULES = {'motion_reference_vp_s': .75, 'brightness_reference_rgb_s': 1.,
         'flash_contrast_reference': .30, 'flash_cycle_reference_hz': 2.,
         'smooth_flash_candidate_minimum_hz': .5,
         'negligible_integrated_rgb_difference': .03,
         'maximum_eligible_score_width': 10.}
DIAGNOSTIC_MOTION = {'backward_sampling_displacement', 'native_affine_component_transport',
                     'sampled_content_displacement_relation'}


def _span(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('two activity interval endpoints required')
    low, high = value
    if type(low) not in {int, float} or not math.isfinite(low) or low < 0:
        raise ValueError('finite nonnegative activity lower endpoint required')
    if high is not None and (type(high) not in {int, float} or not math.isfinite(high) or high < low):
        raise ValueError('ordered finite activity upper endpoint required')
    return float(low), None if high is None else float(high)


def _product(a, b):
    if a == 0 or b == 0:
        return 0.
    return None if a is None or b is None else a*b


def _scale(span, extent, reference):
    return [min(1., span[0]*extent[0]/reference),
            None if _product(span[1], extent[1]) is None else min(1., _product(span[1], extent[1])/reference)]


def validate_preferences(preferences=None):
    if preferences is not None and not isinstance(preferences,dict):
        raise ValueError('preference overrides must be an object')
    overrides={} if preferences is None else dict(preferences)
    if set(overrides)-set(RULES):raise ValueError('unknown activity preference')
    for key,value in overrides.items():
        if type(value) not in {int,float} or not math.isfinite(value):raise ValueError('finite activity preference required')
        if key in {'negligible_integrated_rgb_difference','maximum_eligible_score_width'}:
            if value<0 or value>(1 if key=='negligible_integrated_rgb_difference' else 99):raise ValueError('activity preference outside allowed range')
        elif value<=0:raise ValueError('positive activity reference required')
    return {**RULES,**overrides}


def score_static_behaviour(evidence,*,preferences=None):
    """Return conditional bands, reasons and a separately named potential index."""
    rules=validate_preferences(preferences)
    prominence=evidence.get('prominence', {}).get('by_component', {})
    rows=[]; partial_rows=[]; unknown=[]; flash_possible=False

    def support(identity, brightness=False):
        item=prominence.get(identity)
        if item is None:
            unknown.append({'component_id':identity, 'reason':'displayed contribution has no source bound'})
            return (0., None)
        if item.get('known_invalid_native_domain'):
            unknown.append({'component_id':identity, 'reason':'known invalid native source domain'})
            return (0., None)
        # Brightness deltas already include material alpha. Motion uses the
        # alpha/transfer-weighted contribution, with no second alpha product.
        if brightness:
            area=_span(item['displayed_support_fraction_interval'])
            gain=_span(item['final_transfer']['difference_gain_interval'])
            return _product(area[0], gain[0]), _product(area[1], gain[1])
        return _span(item['displayed_contribution_interval'])

    for record in evidence.get('flashing', {}).get('records', []):
        identity=record['component_id']; extent=support(identity, brightness=True)
        output=evidence.get('displayed_output',{}) if identity=='shader_composite' else {}
        if output.get('constant_rgb') is not None and not output.get('constant_rgb_qualified'):
            unknown.append({'component_id':identity,'dimension':'flashing',
                            'reason':'nominal output saturation has no qualified finite native constant envelope'})
            continue
        if output.get('constant_rgb_qualified'):
            rows.append({'component_id':identity,'dimension':'flashing','strength_interval':[0.,0.],
                         'reason':'declared normalized output clamp makes all final RGB channels constant'})
            continue
        if extent[1] == 0:
            rows.append({'component_id':identity,'dimension':'flashing','strength_interval':[0.,0.],
                         'reason':'source transfer proves no displayed contribution'})
            continue
        contrast=record.get('periodic_contrast_range') or record.get('brightness_delta_range')
        if (identity=='shader_composite' and evidence.get('output_model_complete') and
                record.get('uniform_rgb_over_viewport') and
                record.get('periodic_attainment',{}).get('complete_cycle_in_declared_interval') and
                record.get('periodic_contrast_range') is not None and
                not output.get('raw_ranges_changed')):
            # A complete, uniform, unclipped final RGB cycle reaches every
            # display pixel: its support/identity cannot have a zero lower
            # weight. This remains a declared nominal full-cycle contrast.
            extent=(1.,1.)
        if contrast is not None and output.get('raw_ranges_changed') and output.get('maximum_rgb_difference') is not None:
            contrast=[0.,min(_span(contrast)[1],output['maximum_rgb_difference'])] if _span(contrast)[1] is not None else [0.,output['maximum_rgb_difference']]
        frequency=record.get('cycle_rate_hz'); events=record.get('event_rate_hz')
        continuous=record.get('nominal_continuity') == 'smooth_nominal'
        rate=record.get('maximum_brightness_change_per_second')
        strength=None
        if contrast is not None and frequency is not None:
            delta=_span(contrast)
            multiplier=min(1., frequency/rules['flash_cycle_reference_hz'])
            if continuous and frequency<rules['smooth_flash_candidate_minimum_hz']:
                multiplier*=frequency/rules['smooth_flash_candidate_minimum_hz']
            strength=_scale([v*multiplier if v is not None else None for v in delta], extent,
                            rules['flash_contrast_reference'])
            size=_product(delta[1],extent[1])
            flash_possible |= (size is None or size>rules['negligible_integrated_rgb_difference']) and (
                not continuous or frequency>=rules['smooth_flash_candidate_minimum_hz'])
        elif rate is not None and continuous and record.get('total_brightness_rate_known'):
            strength=_scale([0.,rate], extent,rules['brightness_reference_rgb_s'])
            if contrast is not None:
                # Fast but barely changing colour cannot acquire a high
                # contrast-based activity index from the rate ceiling alone.
                contrast_strength=_scale(_span(contrast),extent,rules['flash_contrast_reference'])
                if contrast_strength[1] is not None:
                    strength[1]=contrast_strength[1] if strength[1] is None else min(strength[1],contrast_strength[1])
            size=None if contrast is None else _product(_span(contrast)[1],extent[1])
            flash_possible |= strength[1] is None or strength[1]>.3 and (
                size is None or size>rules['negligible_integrated_rgb_difference'])
        partial=record.get('fixed_unit_texture_material_partial')
        if partial is not None:
            partial_rate=partial.get('maximum_brightness_change_per_second')
            partial_delta=partial.get('brightness_delta_range')
            partial_strength=[0.,None]
            if partial_rate is not None and partial_delta is not None and partial.get('nominal_continuity') in {'smooth_nominal','piecewise_lipschitz'}:
                partial_strength=_scale([0.,partial_rate],extent,rules['brightness_reference_rgb_s'])
                contrast_cap=_scale(_span(partial_delta),extent,rules['flash_contrast_reference'])
                if partial_strength[1] is not None and contrast_cap[1] is not None:
                    partial_strength[1]=min(partial_strength[1],contrast_cap[1])
            partial_rows.append({'component_id':identity,'dimension':'flashing',
                'scope':'fixed_texture_material_partial','strength_interval':partial_strength,
                'included_in_total_activity_bound':False,
                'premises':list(partial.get('premises',[])),
                'reason':'conditional vertex material modulation with texture samples and destination held fixed'})
            # This estimate supplies a potential signal but never closes the
            # texture/history or input trajectory gaps in the parent record.
            unknown.append({'component_id':identity,'dimension':'flashing',
                            'reason':'fixed-texture material response excludes texture/history trajectories'})
        if strength is None or not record.get('total_brightness_rate_known'):
            unknown.append({'component_id':identity,'dimension':'flashing',
                            'reason':'total brightness trajectory or transition extent unresolved'})
        if strength is not None:
            rows.append({'component_id':identity,'dimension':'flashing','strength_interval':strength,
                         'reason':'local source brightness response joined to spatial extent and final difference gain'})
        if events not in (None,0) and not continuous:
            flash_possible=True

    for record in evidence.get('motion', {}).get('contributions', []):
        if record['kind'] in DIAGNOSTIC_MOTION or not record.get('included_in_total_motion',True):
            continue
        identity=record['component_id']; extent=support(identity)
        speed=_span(record['speed_interval_vp_per_second'])
        strength=_scale(speed,extent,rules['motion_reference_vp_s'])
        rows.append({'component_id':identity,'dimension':'motion','strength_interval':strength,
                     'reason':'source movement ceiling joined to displayed contribution; no observed flow percentile'})
        if strength[1] is None:
            unknown.append({'component_id':identity,'dimension':'motion',
                            'reason':'source movement or displayed contribution unresolved'})

    for hazard in evidence.get('flashing', {}).get('source_hazards', []):
        identity=hazard.get('element_id') or 'shader_'+hazard.get('stage','composite')
        if support(identity,brightness=True)[1] != 0:
            flash_possible=True
            unknown.append({'component_id':identity,'dimension':'flashing',
                            'reason':'contributing source flash mechanism is not exhaustively quantified'})
    if not evidence.get('output_model_complete'):
        unknown.append({'component_id':'preset-output','reason':'complete displayed source activity model not established'})
    known=[r['strength_interval'][1] for r in rows if r['strength_interval'][1] is not None]
    low=max((r['strength_interval'][0] for r in rows), default=0.)
    high=1. if unknown else max(known,default=0.)
    interval=[1.+99.*low,1.+99.*high]
    potential=known+[r['strength_interval'][1] for r in partial_rows if r['strength_interval'][1] is not None]
    point=None if not potential or unknown and max(potential)==0. else 1.+99.*max(potential)
    predicted=[] if point is None else [n for n,a,b in BANDS if a<=point<=b and (n!='Chill' or not flash_possible and not unknown)]
    eligible=[n for n,a,b in BANDS if not unknown and a<=interval[0] and interval[1]<=b and
              interval[1]-interval[0]<=rules['maximum_eligible_score_width'] and (n!='Chill' or not flash_possible)]
    result={'policy':POLICY,'model_status':'assumed source-potential preference mapping; uncalibrated',
            'intensity':{'value':point,'value_kind':'known-source potential index', 'interval':interval,
                         'interval_kind':'source bounds and unresolved contribution ranges'},
            'predicted_bands':predicted,'eligible_bands':eligible,'flash_possible':flash_possible,
            'contributions':rows,'partial_contributions':partial_rows,'unknown_contributors':unknown,'preference_rules':dict(rules),
            'uses_rendered_images':False,'appearance_accuracy_verified':False,
            'limitations':['Upper source bounds are not a typical visible response or native whole-domain certificate',
                           'Area/contrast/history, native arithmetic and unresolved paths remain explicit',
                           'Predicted bands use known source potential; automatic eligibility additionally requires complete bounded evidence']}
    result['record_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return result
