"""Analytic source motion in normalized viewport coordinates.

One x unit is the viewport width; one y unit is the viewport height. Norms
are Euclidean in that coordinate system, not isotropic pixel distances. Native
sampling maps and potential inverse-map content transport remain distinct from
visible motion. No source program, image, or sequence of frames is executed.
"""
import hashlib
import json
import math
from pathlib import Path

import numpy as np

POLICY = 'source-static-motion-behaviour-v1'
TIME_NAMES = {'time', ':native-render-time-f32', '_c2.x'}


def validate_input_rates(request=None):
    rates={} if request is None else request
    if not isinstance(rates,dict):raise ValueError('declared scalar input rates must be an object')
    for name,value in rates.items():
        if not isinstance(name,str) or not name or name in TIME_NAMES or name=='_c2':
            raise ValueError('named non-clock scalar rate required')
        if type(value) not in {int,float} or not math.isfinite(value) or value<0:
            raise ValueError('finite nonnegative input rate per second required')
    return {name:float(value) for name,value in sorted(rates.items())}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _context(context):
    if not isinstance(context, dict):
        raise ValueError('motion context with viewport and feedback_fps required')
    viewport = context.get('viewport')
    if not isinstance(viewport, (list, tuple)) or len(viewport) != 2:
        raise ValueError('two positive finite viewport dimensions required')
    values = [*viewport, context.get('feedback_fps')]
    if any(type(v) not in {int, float} or not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('positive finite viewport and explicit feedback_fps required')
    w, h = viewport
    ax, ay = min(1., w/h), min(1., h/w)
    if not all(math.isfinite(v) and v > 0 for v in (ax, ay)):
        raise ValueError('viewport aspect outside finite motion domain')
    domains=context.get('scalar_input_domains',{})
    if not isinstance(domains,dict):raise ValueError('declared scalar input domains must be an object')
    for name,span in domains.items():
        if not isinstance(name,str) or not name or not isinstance(span,(list,tuple)) or len(span)!=2 or any(
                type(v) not in {int,float} or not math.isfinite(v) for v in span) or span[0]>span[1]:
            raise ValueError('finite ordered static input domain required')
    result={'viewport':list(viewport),'feedback_fps':values[-1],'aspect_x':ax,'aspect_y':ay,
            'scalar_input_domains':{name:list(span) for name,span in sorted(domains.items())},
            'scalar_input_maximum_rates_per_second':validate_input_rates(context.get('scalar_input_maximum_rates_per_second'))}
    if 'reference_profile' in context:result['reference_profile']=context['reference_profile']
    return result


def _effective_domains(analysis,context):
    """Combine declared premises with the prominence producer's conflict policy."""
    scenario=getattr(analysis,'input_scenario',None) or {}
    domains=dict(scenario.get('scalar_input_domains',{}))
    for name,span in context.get('scalar_input_domains',{}).items():
        if name in domains and list(domains[name])!=list(span):
            raise ValueError('conflicting scenario/context scalar input domain: '+name)
        domains[name]=list(span)
    return domains


def _row(kind, component_id, rate_kind, upper=None, reasons=()):
    return {'kind': kind, 'component_id': component_id, 'rate_kind': rate_kind,
            'unit': 'viewport units/second', 'speed_interval_vp_per_second': [0., upper],
            'estimate_kind': 'unknown' if upper is None else 'upper_bound',
            'visible_motion_speed_vp_per_second': None, 'unknown_reasons': list(reasons),
            'parameter_time_rate_is_motion_speed': False}


def _metrics(matrix, mean, fps):
    """Integrate ||B(q-.5)+d||^2 over the unit square analytically.

    A convex norm attains a maximum at a square vertex. The four expressions
    below are analytic extrema, not a mesh/grid, simulation or feature sample.
    """
    delta = np.asarray(matrix, dtype=float)-np.eye(2)
    mean = np.asarray(mean, dtype=float)
    rms = math.sqrt(float(mean@mean + np.sum(delta*delta)/12))
    extrema = [np.linalg.norm(mean + delta@np.array([x, y]))
               for x in (-.5, .5) for y in (-.5, .5)]
    maximum = float(max(extrema))
    metrics = {'rms_speed_vp_per_second': rms*fps,
               'maximum_speed_vp_per_second': maximum*fps,
               'mean_velocity_vp_per_second': (mean*fps).tolist(),
               'rms_displacement_vp_per_feedback_step': rms,
               'maximum_displacement_vp_per_feedback_step': maximum,
               'rms_measure': 'uniform unit-square analytic integral; not content-weighted',
               'maximum_measure': 'convex affine-norm extreme values over the whole unit square'}
    if not all(math.isfinite(v) for v in (rms, maximum, rms*fps, maximum*fps, *(mean*fps))):
        raise ValueError('nominal affine transport rate is nonfinite')
    return metrics


def _sampling_bound(displacement, context):
    terms = displacement.get('rms_upper_bound_terms')
    if terms is None: return None
    ax, ay = context['aspect_x'], context['aspect_y']
    # The existing bound uses Euclidean aspect-corrected UV. Divide its norm by
    # the smallest aspect for a sufficient normalized-viewport norm bound.
    value = (terms['translation_and_center'] + terms['centered_geometry']*math.hypot(ax, ay)
             + terms['procedural_warp']) / min(ax, ay) * context['feedback_fps']
    return math.nextafter(value, math.inf) if value and math.isfinite(value) else (0. if value == 0 else None)


def _native_wave_inverse_bound(analysis, description, context):
    """Prove strict inverse stability of the nominal in-viewport map.

    For W=Aq+b+g(q), ||W(q)-W(p)|| >= (sigma_min(A)-Lip(g))||q-p||.
    Rectangular native triangles have horizontal/vertical edges: each interpolated
    Jacobian column is an edge difference with the same per-axis derivative
    bound. The Frobenius bound therefore also covers either native diagonal.
    This proves uniqueness/stability for retained inverse branches; it does not
    assert that every source feature has an in-viewport inverse or model wrap.
    """
    recipe = description['native_warp_recipe']
    if recipe['model_kind'] != 'uniform_native_wave_warp' or analysis.stages['warp']['kind'] != 'fixed_warp':
        return None
    p = recipe['native_float32_controls']; wave = recipe['procedural_warp']
    ax, ay = context['aspect_x'], context['aspect_y']
    c, s = math.cos(p['rot']), math.sin(p['rot'])
    matrix = np.array([[c/(p['zoom']*p['sx']), -s/(p['zoom']*p['sy'])*ay/ax],
                       [s/(p['zoom']*p['sx'])*ax/ay, c/(p['zoom']*p['sy'])]])
    try:
        inverse = np.linalg.inv(matrix)
        inverse_frobenius = float(np.linalg.norm(inverse, 'fro'))
        minimum = math.nextafter(1/inverse_frobenius, -math.inf)
        factors = [abs(f['bias'])+abs(f['amplitude']) for f in wave['warp_factors']]
        derivative_matrix = [[0., 0.], [0., 0.]]
        amplitude = abs(wave['signed_term_amplitude'])
        for term in wave['terms']:
            row = 0 if term['axis'] == 'u' else 1
            for axis, coefficients in enumerate(term['phase_position_factor_coefficients']):
                derivative_matrix[row][axis] += 2*amplitude*abs(wave['warp_scale_inverse'])*sum(abs(k)*f for k, f in zip(coefficients, factors))
        # Orthogonal rotation preserves norm; division by aspect is bounded by
        # 1/min(aspect). Native triangle interpolation commutes with rotation.
        perturbation = math.nextafter(math.sqrt(sum(v*v for row in derivative_matrix for v in row))/min(ax, ay), math.inf)
        margin = math.nextafter(minimum-perturbation, -math.inf)
        if not math.isfinite(margin) or margin <= 1e-10*max(minimum, perturbation): return None
        terms = description['native_warp_displacement'].get('rms_upper_bound_terms')
        if terms is None: return None
        maximum_backward = (terms['translation_and_center'] + math.sqrt(3)*terms['centered_geometry']*math.hypot(ax, ay)+terms['procedural_warp']) / min(ax, ay)
        maximum = maximum_backward*context['feedback_fps']/margin
        energy = _sampling_bound(description['native_warp_displacement'], context)/margin
        if not all(math.isfinite(v) for v in (maximum, energy)): return None
        return {'maximum_speed_vp_per_second': math.nextafter(maximum, math.inf) if maximum else 0.,
                'rms_speed_vp_per_second_upper_bound': math.nextafter(energy, math.inf) if energy else 0.,
                'rms_measure': 'unnormalized transport energy over retained inverse-branch area; not content-weighted',
                'inverse_stability_proof': {'policy': 'native-wave-global-lipschitz-inverse-stability-v1',
                    'affine_minimum_singular_value': minimum,
                    'affine_minimum_singular_value_kind': 'lower_bound_from_inverse_frobenius_norm',
                    'procedural_jacobian_entry_absolute_upper_bounds': derivative_matrix,
                    'procedural_jacobian_operator_upper_bound': perturbation,
                    'positive_inverse_stability_margin': margin,
                    'scope': 'inverse branches retained within normalized viewport',
                    'native_triangle_interpolation_model': 'right triangles on a rectangular mesh; either diagonal',
                    'formula': '||inverse displacement|| <= ||backward displacement|| / (sigma_min_lower-Lip_upper)',
                    'native_storage_and_rounding_verified': False}}
    except (ValueError, OverflowError, ZeroDivisionError, np.linalg.LinAlgError): return None


def _bounded_uniform_transport(analysis, description, context):
    """A^-1 times bounded backward displacement; no phase/frame samples."""
    from source_native_warp import _f32
    from source_control_bounds import scalar_value_envelope
    from source_warp_displacement import native_warp_displacement
    transport = description['native_warp_transport']
    if analysis.stages['warp']['kind'] != 'fixed_warp': return None
    controls = transport.get('controls', {})
    if not controls or not all(row['uniform_across_vertices'] for row in controls.values()): return None
    scenario = getattr(analysis, 'input_scenario', None)
    input_domains=_effective_domains(analysis,context)
    domains = {}
    try:
        for name, row in controls.items():
            span = row['native_float32_endpoint_domain']
            if input_domains:
                report = scalar_value_envelope(analysis.mesh_controls[name], input_domains=input_domains)
                raw = report['nominal_value_range']
                span = None if raw is None else [_f32(v) for v in raw]
            if span is None: return None
            domains[name] = span
        if domains['zoomexp'] != [1, 1] or domains['warp'] != [0, 0]: return None
        for name in ('zoom', 'sx', 'sy'):
            if domains[name][0] <= 0 <= domains[name][1]: return None
            if any(_f32(1/v) == 0 for v in domains[name]): return None
        qualified = {**transport, 'status': 'bounded_uniform_affine_component',
                     'controls': {name: {**controls[name], 'native_float32_endpoint_domain': span}
                                  for name, span in domains.items()}}
        displacement = native_warp_displacement(analysis, qualified)
        terms = displacement['rms_upper_bound_terms']
        if terms is None: return None
        ax, ay = context['aspect_x'], context['aspect_y']
        inverse_norm = max(abs(z*stretch) for z in domains['zoom']
                           for name in ('sx', 'sy') for stretch in domains[name]) * max(ax, ay)/min(ax, ay)
        backward_max = (terms['translation_and_center'] + math.sqrt(3)*terms['centered_geometry']*math.hypot(ax, ay)) / min(ax, ay)
        maximum = inverse_norm * backward_max * context['feedback_fps']
        rms = inverse_norm * _sampling_bound(displacement, context)
        if not all(math.isfinite(v) for v in (maximum, rms)): return None
        return {'maximum_speed_vp_per_second': math.nextafter(maximum, math.inf) if maximum else 0.,
                'rms_speed_vp_per_second_upper_bound': math.nextafter(rms, math.inf) if rms else 0.,
                'native_float32_control_domains': domains, 'inverse_operator_norm_upper_bound': inverse_norm,
                'rms_bound_formula': '||A^-1|| * RMS(backward affine displacement)',
                'maximum_bound_formula': '||A^-1|| * (centre bound + operator bound * viewport half-diagonal)',
                'input_scenario_sha256': None if scenario is None else scenario['record_sha256']}
    except (ValueError, ZeroDivisionError, OverflowError): return None


def _native_motion(analysis, description, context):
    from source_native_warp import affine_center_displacement
    recipe = description['native_warp_recipe']
    if recipe['contribution'] == 'disconnected': return []
    forward = _row('forward_content_transport', 'mesh_warp', 'per_feedback_step')
    sampling = _row('backward_sampling_displacement', 'mesh_warp', 'per_feedback_step')
    rows = [forward, sampling]
    branch = analysis.stages['warp']['kind']
    complete = recipe['model_kind'] == 'uniform_affine' and branch == 'fixed_warp'
    forward['complete_native_sampling_map_proved'] = complete
    for row in rows:
        row['source_policy'] = recipe['policy']
        row['conditions'] = ['Continuous nominal map before wrap, texel shifts and mesh/native rounding',
                             'Feedback content, coverage, contrast, trails, injection and later composition remain unresolved']
    try:
        if recipe['model_kind'] not in {'uniform_affine', 'uniform_native_wave_warp'}:
            raise ValueError('; '.join(recipe['unknown_reasons']) or 'native affine recipe unresolved')
        p = recipe['native_float32_controls']
        ax, ay = context['aspect_x'], context['aspect_y']
        c, s = math.cos(p['rot']), math.sin(p['rot'])
        matrix = np.array([[c/(p['zoom']*p['sx']), -s/(p['zoom']*p['sy'])*ay/ax],
                           [s/(p['zoom']*p['sx'])*ax/ay, c/(p['zoom']*p['sy'])]])
        e = affine_center_displacement(p, c, s)
        mean = np.array([e[0]/ax, e[1]/ay])
        if not math.isfinite(float(np.linalg.cond(matrix))) or np.linalg.cond(matrix) > 1e12:
            raise ValueError('invertible affine map within numeric domain required')
        inverse = np.linalg.inv(matrix)
        forward_metrics = _metrics(inverse, -inverse@mean, context['feedback_fps'])
        backward_metrics = _metrics(matrix, mean, context['feedback_fps'])
        details = {'sampling_matrix': matrix.tolist(), 'forward_matrix': inverse.tolist(),
                   'native_float32_controls': dict(p), 'orientation': 'preserving' if np.linalg.det(matrix)>0 else 'reversing',
                   'operator_order': 'inverse of the composed native rotation, stretch, zoom, centre and translation map'}
        if complete:
            forward.update(details, **forward_metrics,
                           speed_interval_vp_per_second=[0., forward_metrics['maximum_speed_vp_per_second']],
                           estimate_kind='exact_nominal_affine_domain')
            sampling.update(**backward_metrics,
                            speed_interval_vp_per_second=[0., backward_metrics['maximum_speed_vp_per_second']],
                            estimate_kind='exact_nominal_affine_domain')
        else:
            component = _row('native_affine_component_transport', 'mesh_warp', 'per_feedback_step',
                             forward_metrics['maximum_speed_vp_per_second'])
            component.update(details, **forward_metrics, complete_native_sampling_map_proved=False,
                             conditions=['Isolated native affine component; procedural/custom map can alter or cancel transport'])
            rows.append(component)
            forward['unknown_reasons'] = ['procedural or custom warp requires complete-map invertibility and transport proof']
    except (ValueError, OverflowError, ZeroDivisionError, np.linalg.LinAlgError) as error:
        forward['unknown_reasons'] = [str(error)]
    if sampling['estimate_kind'] == 'unknown':
        uniform = description['native_warp_displacement']
        spatial = description['native_spatial_displacement']
        selected = uniform if uniform.get('rms_upper_bound_terms') is not None else spatial
        upper = _sampling_bound(selected, context)
        sampling['rms_speed_vp_per_second_upper_bound'] = upper
        sampling['estimate_kind'] = 'rms_upper_bound' if upper is not None else 'unknown'
        sampling['unknown_reasons'] = list(selected.get('unknown_reasons', []))
        # An RMS bound is not a pointwise maximum or percentile.
        sampling['speed_interval_vp_per_second'] = [0., None]
        if upper is not None: sampling['rms_speed_interval_vp_per_second'] = [0., upper]
        if spatial.get('status') == 'bounded_spatial_sampling_displacement':
            forward['unknown_reasons'] = ['bounded per-vertex sampling displacement does not prove a global inverse map']
    if forward['estimate_kind'] == 'unknown':
        bounded = (_native_wave_inverse_bound(analysis, description, context) or
                   _bounded_uniform_transport(analysis, description, context))
        if bounded is not None:
            forward.update(**bounded, estimate_kind='maximum_upper_bound', unknown_reasons=[],
                           speed_interval_vp_per_second=[0., bounded['maximum_speed_vp_per_second']],
                           complete_native_sampling_map_proved=True)
    if analysis.stages['warp']['kind'] == 'fixed_warp':
        selected = description['native_warp_displacement']
        if selected.get('rms_upper_bound_terms') is None:
            selected = description['native_spatial_displacement']
        terms = selected.get('rms_upper_bound_terms')
        if terms is not None:
            ax, ay = context['aspect_x'], context['aspect_y']
            displacement = (terms['translation_and_center'] + math.sqrt(3)*terms['centered_geometry']*math.hypot(ax, ay)
                            + terms['procedural_warp']) / min(ax, ay)
            maximum = displacement * context['feedback_fps']
            if math.isfinite(maximum):
                maximum = math.nextafter(maximum, math.inf) if maximum else 0.
                relation = _row('sampled_content_displacement_relation', 'mesh_warp', 'per_feedback_step', maximum)
                relation.update(maximum_speed_vp_per_second=maximum,
                                maximum_origin_output_distance_vp_per_feedback_step=displacement,
                                is_trajectory_speed=False, inverse_uniqueness_required=False,
                                estimate_kind='maximum_upper_bound',
                                conditions=['A valid retained sample origin q=W(p) is pulled to output p; ||q-p|| is bounded directly',
                                            'No inverse uniqueness, single feature trajectory or temporal advection is asserted',
                                            'Actual retained UV, no wrapping, fixed texture origin and no filtering/texel shifts are required',
                                            'Native scalar domains and selected fixed warp must hold; content contrast, injection and trails remain unknown'])
                rows.append(relation)
    return rows


def _response(controls, names, domains):
    from source_control_bounds import scalar_response_envelope
    return {name: scalar_response_envelope(controls[name], input_names=names, input_domains=domains)
            for name in ('x', 'y', 'rad', 'ang')}


def _geometry_motion(analysis, element, context):
    from source_control_bounds import scalar_value_envelope
    from effect_families import _deps
    from source_appearance import EEL_AUDIO
    component = element['id']
    controls = getattr(analysis, 'component_controls', {}).get(component)
    if controls is None:
        return [_row('geometry_trajectory', component, 'source_time_partial', reasons=['geometry formula is not qualified'])]
    scenario = getattr(analysis, 'input_scenario', None)
    domains = _effective_domains(analysis,context) or None
    reports = _response(controls, TIME_NAMES, domains)
    rates = {name: r['maximum_absolute_control_change_per_audio_unit'] for name, r in reports.items()}
    radius_span = scalar_value_envelope(controls['rad'], input_domains=domains)['nominal_value_range']
    radius = None if radius_span is None else max(map(abs, radius_span))
    centre = None if any(rates[n] is None for n in ('x', 'y')) else math.hypot(rates['x'], rates['y'])
    angular = (0. if rates['ang'] == 0 or radius == 0 else
               None if rates['ang'] is None or radius is None else radius*rates['ang'])
    local = None if rates['rad'] is None or angular is None else .5*math.hypot(rates['rad'], angular)
    upper = None if centre is None or local is None else centre+local
    reasons = []
    existing = element.get('vertex_motion', {})
    # Retain known native conversion / topology failures; optional symbolic
    # differentiation may repair a missing derivative but never these domains.
    for reason in existing.get('unknown_reasons', []):
        if 'float32' in reason or 'side count' in reason: reasons.append(reason)
    if reasons or upper is not None and not math.isfinite(upper): upper = None
    if upper is None and not reasons:
        reasons = sorted({reason for r in reports.values() for reason in r['unknown_reasons']}) or ['unbounded geometry radius or rate']
    row = _row('geometry_trajectory', component, 'source_time_partial', upper, reasons)
    trajectory = element.get('center_trajectory', {})
    row.update(maximum_speed_vp_per_second=upper, centre_speed_vp_per_second_upper_bound=centre,
               local_speed_vp_per_second_upper_bound=local,
               centre_velocity_vp_per_second=trajectory.get('linear_velocity_source_xy'),
               native_shape_aspect_y=context['aspect_y'], derivative_reports=reports,
               radius_value_range=radius_span,
               formula='hypot(dx/dt,dy/dt) + .5*hypot(dr/dt,abs(radius)*dangle/dt)',
               conditions=['Native shape centre source x/y are viewport fractions; radius is NDC and converts by .5',
                           'Horizontal local radius is multiplied by aspectY; upper norm uses max(aspectY,1)=1',
                           'Continuous source-time partial with audio, instance and persistent state held fixed',
                           'Triangle/orthogonal bounds precede clipping, material, overlap and later composition'])
    if scenario is not None: row['input_scenario_sha256'] = scenario['record_sha256']
    rows = [row]
    dependencies = set().union(*(_deps(controls[n]) for n in ('x', 'y', 'rad', 'ang')))
    state = dependencies - TIME_NAMES - set(EEL_AUDIO) - {'instance'}
    if state:
        rows.append(_row('geometry_state_update', component, 'per_feedback_step',
                         reasons=['persistent state or non-time input trajectory unresolved: '+', '.join(sorted(state))]))
    audio = dependencies & set(EEL_AUDIO)
    for band in sorted(audio):
        partial = _response(controls, {band}, domains)
        values = {name: r['maximum_absolute_control_change_per_audio_unit'] for name, r in partial.items()}
        centre_response = None if any(values[n] is None for n in ('x', 'y')) else math.hypot(values['x'], values['y'])
        angular_response = (0. if values['ang'] == 0 or radius == 0 else None if values['ang'] is None or radius is None else radius*values['ang'])
        local_response = None if values['rad'] is None or angular_response is None else .5*math.hypot(values['rad'], angular_response)
        response = None if centre_response is None or local_response is None else centre_response+local_response
        part = _row('geometry_audio_partial', component, 'audio_partial', reasons=['audio input change rate per second is not declared'])
        part.update(audio_input=band, maximum_response_vp_per_audio_unit=response,
                    response_unit='viewport units/audio unit', derivative_reports=partial,
                    conditions=['Single engine audio input varies while source time/state/other bands hold fixed',
                                'An amplitude domain supplies no temporal audio trajectory or per-second rate'])
        if scenario is not None: part['input_scenario_sha256'] = scenario['record_sha256']
        rows.append(part)
    declared=context['scalar_input_maximum_rates_per_second']
    varying=dependencies-TIME_NAMES-{'instance'}
    if varying and varying<=set(declared):
        from fractions import Fraction
        from source_sampling_motion import _finite_round
        input_reports={name:_response(controls,{name},domains) for name in sorted(varying)}
        combined={}
        for control in ('x','y','rad','ang'):
            terms=[rates[control]]
            for name,parts in input_reports.items():
                derivative=parts[control]['maximum_absolute_control_change_per_audio_unit']
                terms.append(None if derivative is None else _finite_round(Fraction(derivative)*Fraction(declared[name]),upper=True))
            combined[control]=None if any(v is None or not math.isfinite(v) for v in terms) else _finite_round(sum((Fraction(v) for v in terms),Fraction()),upper=True)
        def norm_upper(*values):
            result=math.hypot(*values)
            return math.nextafter(result,math.inf) if result else 0.
        centre_total=None if any(combined[n] is None for n in ('x','y')) else norm_upper(combined['x'],combined['y'])
        angular_total=0. if combined['ang']==0 or radius==0 else None if combined['ang'] is None or radius is None else _finite_round(Fraction(radius)*Fraction(combined['ang']),upper=True)
        local_norm=None if combined['rad'] is None or angular_total is None else norm_upper(combined['rad'],angular_total)
        local_total=None if local_norm is None or not math.isfinite(local_norm) else _finite_round(Fraction(.5)*Fraction(local_norm),upper=True)
        total=None if centre_total is None or not math.isfinite(centre_total) or local_total is None else _finite_round(Fraction(centre_total)+Fraction(local_total),upper=True)
        total_reasons=list(reasons)
        from source_control_bounds import original_scalar_domain_evidence
        original_domains={name:original_scalar_domain_evidence(controls[name],input_domains=domains)
            for name in ('x','y','rad','ang')}
        for name,proof in original_domains.items():
            if proof['status']!='bounded':total_reasons.append(name+' original argument domain unresolved: '+'; '.join(proof['unknown_reasons']))
        if not varying<=set(domains or {}):
            total_reasons.append('declared input rates require finite amplitude domains for combined geometry transport')
        native_ranges={}
        for name in ('x','y','rad','ang'):
            span=scalar_value_envelope(controls[name],input_domains=domains)['nominal_value_range']
            if span is None:
                total_reasons.append(name+' finite geometry value domain remains unresolved');continue
            projected=[2*v-1 for v in span] if name=='x' else sorted(1-2*v for v in span) if name=='y' else span
            with np.errstate(over='ignore',invalid='ignore'):
                converted=[float(np.float32(v)) for v in projected]
            if not all(math.isfinite(v) for v in converted):
                total_reasons.append(name+' input domain exceeds finite native float32 projection/conversion');continue
            native_ranges[name]=converted
        if all(name in native_ranges for name in ('x','y','rad')):
            radius_upper=max(map(abs,native_ranges['rad']))
            for axis,factor in (('x',context['aspect_y']),('y',1.)):
                upper=max(map(abs,native_ranges[axis]))+radius_upper*factor
                if upper>float(np.finfo(np.float32).max):
                    total_reasons.append(axis+' perimeter addition may exceed finite native float32 domain')
        if total_reasons or total is not None and not math.isfinite(total):total=None
        combined_row=_row('geometry_declared_input_transport',component,'declared_input_change_per_second',total,
            total_reasons or ([] if total is not None else ['declared input rates do not close the geometry formula/domain']))
        combined_row.update(maximum_speed_vp_per_second=total,
            declared_input_rates_per_second={name:declared[name] for name in sorted(varying)},
            native_projected_control_ranges=native_ranges,
            original_argument_domain_evidence=original_domains,
            combined_control_rates_per_second=combined,input_response_reports=input_reports,
            source_time_response_reports=reports,
            conditions=['Sum of independent scalar sensitivities times caller-declared input change ceilings, plus source-time response',
                'Finite declared input domains and supported continuous/piecewise-Lipschitz formulas hold between compared states',
                'Rates are assumptions about engine input values, not music BPM or measured audio; no recurrent-state evolution is inferred',
                'Native float upload, rasterization, feedback, visibility and output quantization remain separate'])
        rows.append(combined_row)
        if total is not None:
            for partial in rows[:-1]:partial['included_in_total_motion']=False
    return rows


def motion_evidence(analysis, description, context):
    """Join source geometry and native feedback movement with explicit context."""
    normalized = _context(context)
    effective_domains=_effective_domains(analysis,normalized)
    rows = _native_motion(analysis, description, normalized)
    stages = analysis.stages
    composite_kind = stages['composite']['kind']
    composite_reads = description.get('composition', {}).get('shader_sample_reads', {}).get('composite', [])
    if composite_reads is None:
        rows.append(_row('composite_sample_access', 'shader_composite', 'unresolved_source_access',
                         reasons=['Composite sample dependencies are unresolved; feedback exclusion is unproven']))
    final_reads_feedback = composite_reads is None or composite_kind in {'unknown', 'default_composite', 'legacy_composite'} or any(
        row.get('canonical_texture') in {'main', 'blur1', 'blur2', 'blur3'} for row in composite_reads)
    for stage in ('composite', 'warp'):
        if stages[stage]['kind'] != 'unknown' or stage == 'warp' and not final_reads_feedback: continue
        rows.append(_row('native_stage_selection', 'shader_'+stage, 'native_profile_selection',
                         reasons=['Native '+stage+' selection is unresolved; custom source disconnection does not exclude native fallback movement']))
    for element in description.get('elements', []):
        if element['id'].startswith('shape_'):
            rows.extend(_geometry_motion(analysis, element, normalized))
        elif element['stage'] == 'drawing':
            rows.append(_row('geometry_trajectory', element['id'], 'audio_and_source_time',
                             reasons=['wave/motion-vector geometry and audio trajectory remain unresolved']))
    from effect_families import _deps, SPATIAL
    from source_appearance import AUDIO
    live_ids = {element['id'] for element in description.get('elements', [])}
    for stage, field in getattr(analysis, 'outputs', {}).items():
        if 'shader_'+stage not in live_ids: continue
        deps = _deps(field)
        if deps & SPATIAL and deps & (TIME_NAMES | set(AUDIO) | {'_c2', '_c3', '_c4'}):
            rows.append(_row('procedural_shader_motion', 'shader_'+stage, 'source_time_and_audio',
                             reasons=['spatially varying temporal shader field requires contour/advection motion proof']))
    # Custom shader coordinate motion is already source-derived. Keep lookup
    # speed as sampling motion; this is not its feature transport or visibility.
    for lookup in description.get('activity', {}).get('motion_intensity', {}).get('texture_motion_bounds', []):
        speeds = lookup.get('maximum_lookup_axis_speed_uv_per_second', [])
        if len(speeds) != 2 or all(v == 0 for v in speeds): continue
        upper = None if any(v is None for v in speeds) else math.hypot(*speeds)
        row = _row('authored_sampling_time_partial', 'shader_'+lookup.get('stage', 'unknown'), 'source_time_partial', upper,
                   lookup.get('unknown_reasons', []))
        row['sampling_record'] = lookup
        row['complete_content_transport_proved'] = False
        rows.append(row)
    for stage, lookups in description.get('sampling_geometry', {}).get('stages', {}).items():
        for lookup in lookups or []:
            if lookup.get('native_mesh_transform_precedes_basis') or stage != 'composite': continue
            movement = lookup.get('sampling_motion', {})
            for part in (movement, movement.get('scenario_sampling_motion')):
                if part is None: continue
                speed = part.get('maximum_feature_speed_basis_uv_per_second')
                if speed is None or speed == 0 or movement.get('feature_basis') not in {'shader_uv', 'original_uv'}: continue
                row = _row('affine_lookup_feature_time_partial', 'shader_'+stage, 'source_time_partial', speed)
                row.update(maximum_speed_vp_per_second=speed,
                           feature_velocity_vp_per_second=part.get('signed_feature_velocity_basis_uv_per_second'),
                           fixed_texture_content_required=True,
                           sample_site_index=lookup['sample_site_index'], sampler=lookup['sampler'],
                           source_graph_path=lookup.get('source_graph_path'),
                           input_scenario_sha256=part.get('input_scenario_sha256'),
                           conditions=['Isolated fixed texture feature under a constant invertible authored affine lookup',
                                       'Uniform authored offset derivative is pulled back through the actual affine inverse',
                                       'Source-time seconds already apply; no feedback-FPS multiplier',
                                       'Texture history, wrap/filtering, multiple samples, composition and actual visible contrast remain unresolved'])
                rows.append(row)
    elements = {element['id']: element for element in description.get('elements', [])}
    for row in rows:
        if row['component_id'] == 'mesh_warp':
            row['source_evidence'] = [analysis.evidence(section, 'native feedback coordinate transport', 'mesh_controls')
                                      for section in ('per_frame_', 'per_pixel_')]
        else:
            row['source_evidence'] = elements.get(row['component_id'], {}).get('evidence', [])
    control_time_partials = [{
        'control': curve['control'], 'control_unit': curve['control_unit'],
        'maximum_absolute_control_rate_per_second': curve['maximum_absolute_control_rate_per_second'],
        'estimate_kind': curve['rate_estimate_kind'],
        'rate_is_content_motion_speed': False,
        'scenario_time_component': curve.get('scenario_time_component')}
        for curve in elements.get('mesh_warp', {}).get('motion_controls', [])]
    unknown = [{'component_id': row['component_id'], 'kind': row['kind'],
                'unknown_reasons': row['unknown_reasons'] or ['no maximum potential speed bound']}
               for row in rows if row.get('included_in_total_motion',True) and row['speed_interval_vp_per_second'][1] is None]
    maxima = [row['speed_interval_vp_per_second'][1] for row in rows
              if row.get('included_in_total_motion',True) and row['kind'] not in {'backward_sampling_displacement', 'native_affine_component_transport', 'sampled_content_displacement_relation'}]
    upper = None if any(v is None for v in maxima) else max(maxima, default=0.)
    result = {'policy': POLICY, 'unit': 'viewport units/second', 'coordinate_basis': 'normalized viewport UV',
              'context': normalized, 'context_sha256': _digest(normalized),
              'effective_scalar_input_domains':effective_domains,
              'effective_scalar_input_domains_sha256':_digest(effective_domains),
              'source_sha256': getattr(analysis, 'source', {}).get('preset_sha256'),
              'model_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'input_scenario_sha256': (getattr(analysis, 'input_scenario', None) or {}).get('record_sha256'),
              'contributions': rows, 'unresolved_contributors': unknown,
              'feedback_control_time_partials': control_time_partials,
              'maximum_potential_speed_interval_vp_per_second': [0., upper],
              'visible_motion_speed_vp_per_second': 0. if not rows else None,
              'uses_rendered_images': False, 'uses_shader_execution': False, 'uses_equation_execution': False,
              'texel_alignment_included': False, 'native_numeric_certified': False,
              'conditions': ['Source mathematical potential, not observed whole-screen motion or a percentile',
                             'Normalized x/y viewport distance is not isotropic physical-pixel distance',
                             'Uniform content has zero apparent motion under coordinate remapping; retained content uniformity is not proved',
                             'Wrap, pixel/texel storage, interpolation, native trails/detail, coverage/contrast and history remain unresolved',
                             'Dynamic native controls are per-step maps; their time derivatives do not replace per-step transport',
                             'Unknown contributors retain an unbounded possible impact; no image/render/frame simulation']}
    result['record_sha256'] = _digest(result)
    return result
