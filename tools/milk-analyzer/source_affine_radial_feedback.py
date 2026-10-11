"""Conditional source central radial sampling for constant-affine EEL zoom.

The smooth rational sampler is nominal source algebra. EEL rounding, the
per-vertex float32 zoom cast and triangle interpolation are not its derivative.
No equation, shader, image or feedback history is executed here.
"""
from fractions import Fraction
import math
import sys

from source_native_warp import _f32
from source_curve_projection import _enclosure, _multiply, _span


POLICY = 'source-affine-radial-feedback-v1'
NEUTRAL = {'zoomexp': 1., 'rot': 0., 'warp': 0., 'cx': .5, 'cy': .5,
           'dx': 0., 'dy': 0., 'sx': 1., 'sy': 1.}


def _exact(value):
    return {'numerator': str(value.numerator), 'denominator': str(value.denominator)}


def _display(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('radial metadata exceeds finite binary64 domain')
    return None if result == 0 and value != 0 else result


def _affine(field, radius_domain):
    """Keep exact binary literal algebra and guard every original subexpression."""
    from source_appearance import _phase_literal
    memo = {}
    active = set()

    def visit(node, depth=0):
        key = id(node)
        if key in active or depth > 64 or len(memo) >= 4096:
            raise ValueError('radial affine graph budget or cycle')
        if key in memo:
            return memo[key]
        active.add(key)
        if node.dtype != 'float':
            raise ValueError('radial affine control is not scalar float')
        if node.op == 'constant':
            literal = node.detail.get('value')
            if type(literal) not in {int, float} or not math.isfinite(literal):
                raise ValueError('radial source literal is nonfinite')
            result = Fraction(literal), Fraction(0)
        elif node.op == 'input':
            if node.detail.get('name') != 'rad' or node.detail.get('native_mesh_reset_input') is not True:
                raise ValueError('radial affine control has state/audio/unknown or nonreset coordinate input')
            result = Fraction(0), Fraction(1)
        elif node.op in {'cast', 'narrow', 'construct'}:
            # A dynamic conversion is piecewise rather than a real affine map.
            # Validate its child before accepting a converted constant atom.
            children = [visit(arg, depth+1) for arg in node.args]
            literal = _phase_literal(node)
            if literal is None or any(b != 0 for a, b in children):
                raise ValueError('dynamic numeric conversion is not const-affine radial algebra')
            result = Fraction(literal), Fraction(0)
        elif node.op == 'negate' and len(node.args) == 1:
            result = tuple(-value for value in visit(node.args[0], depth+1))
        elif node.op in {'add', 'subtract', 'multiply', 'divide'} and len(node.args) == 2:
            a, b = [visit(arg, depth+1) for arg in node.args]
            if node.op in {'add', 'subtract'}:
                sign = -1 if node.op == 'subtract' else 1
                result = a[0]+sign*b[0], a[1]+sign*b[1]
            elif node.op == 'multiply':
                if a[1] != 0 and b[1] != 0:
                    raise ValueError('zoom is not affine in native radius')
                result = a[0]*b[0], a[0]*b[1]+a[1]*b[0]
            else:
                if b[1] != 0 or b[0] == 0:
                    raise ValueError('original radial divisor is singular or nonconstant')
                result = a[0]/b[0], a[1]/b[0]
        else:
            raise ValueError('radial control contains unsupported operation or side effect: '+node.op)
        if any(max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > 65536 for value in result):
            raise ValueError('radial rational coefficient budget exceeded')
        span = _affine_span(result, radius_domain)
        if max(map(abs, span)) > Fraction(sys.float_info.max):
            raise ValueError('original radial expression lacks a finite EEL intermediate domain')
        active.remove(key)
        memo[key] = result
        return result

    return visit(field)


def _affine_span(coefficients, radius):
    a, b = coefficients
    return tuple(sorted(a+b*r for r in radius))


def _effect_guard(analysis):
    if '_domain' in analysis.mesh_controls:
        raise ValueError('mesh original _domain guard remains unresolved')
    for row in getattr(analysis, 'unknowns', []):
        if row.get('section') in {'per_frame_', 'per_frame_init_', 'per_pixel_'}:
            raise ValueError('original main/mesh equation domain or effects unresolved: '+row.get('reason', 'unknown'))
    # An unused memory/random/loop operation cannot be silently erased by a
    # pure output slice. Traverse the original accepted equation trees too.
    from equation_loading import select_equation
    sections = getattr(analysis, 'source', {}).get('sections', {})
    for prefix in ('per_frame_init_', 'per_frame_', 'per_pixel_'):
        if prefix not in sections:
            continue
        selected = select_equation(sections[prefix], prefix, policy=getattr(analysis, 'policy', 'strict-raw-v1'))
        if selected.get('compile_status') not in {'accepted', 'empty'}:
            raise ValueError('original equation is not accepted for radial proof')
        pending = [selected.get('tree')]
        count = 0
        while pending:
            node = pending.pop()
            count += 1
            if count > 16384:
                raise ValueError('original radial equation effect budget exceeded')
            if isinstance(node, dict):
                function = node.get('function', '')
                if function in {'rand', 'loop', 'while', 'mem', 'megabuf', 'gmegabuf', 'freembuf', 'memcpy', 'memset'}:
                    raise ValueError('original radial equation has unsupported side effect: '+function)
                pending.extend(value for value in node.values() if isinstance(value, (dict, list)))
            elif isinstance(node, list):
                pending.extend(node)


def _regions(a, b, maximum):
    crossover = None if b == 0 else (1-a)/b
    boundaries = [Fraction(0), maximum]
    if crossover is not None and 0 < crossover < maximum:
        boundaries.insert(1, crossover)
    regions = []
    for low, high in zip(boundaries, boundaries[1:]):
        zoom = a+b*(low+high)/2
        feature = 'neutral' if zoom == 1 else 'outward' if zoom > 1 else 'inward'
        sampling = {'neutral': 'neutral', 'outward': 'inward', 'inward': 'outward'}[feature]
        regions.append({'output_radius_interval': _enclosure((low, high)),
                        'feature_direction': feature, 'sampling_direction': sampling,
                        'direction_applies_to_interval_interior': True})
    return crossover, regions


def affine_radial_feedback(analysis, context=None, *, consumed=True):
    """Describe z(r)=a+b*r using a declared native viewport.

    Optional source_radius_domain bounds a fixed feature before one ideal
    feedback step. Optional feedback_fps converts that step ceiling to a rate;
    it declares cadence and does not measure or simulate a trajectory.
    """
    context = {} if context is None else context
    source = getattr(analysis, 'source', {})
    result = {'policy': POLICY, 'status': 'unknown', 'unknown_reasons': [],
        'viewport': None, 'native_aspect_xy': None, 'output_radius_domain': None,
        'zoom_affine_coefficients_exact': None, 'zoom_affine_coefficients': None,
        'nominal_zoom_range': None, 'native_float32_zoom_endpoint_domain': None,
        'sampled_source_radius_range': None, 'radial_sampling_derivative_range': None,
        'neutral_radius_crossover': None, 'neutral_radius_crossover_exact': None,
        'all_radii_neutral': None, 'direction_regions': [], 'fixed_feature_projection': None,
        'sampler_formula': 'r_source = r_output / (a + b*r_output)',
        'radial_sampling_derivative_formula': 'a / (a + b*r_output)^2',
        'inverse_formula': 'r_output = a*r_source / (1 - b*r_source)',
        'native_numeric_certified': False, 'uses_equation_execution': False,
        'uses_rendered_images': False, 'visible_motion_speed': None,
        'actual_feedback_lifetime': None, 'whole_preset_activity_credit': False,
        'source_provenance': {'preset_sha256': source.get('preset_sha256'),
                              'parser_inputs': source.get('parser_inputs', {})},
        'radius_basis_evidence': {
            'eel_and_gpu_share_uploaded_radius': False,
            'basis': 'source34 mesh radius hypotf(pos.x*aspectX,pos.y*aspectY)',
            'continuous_radius_exact_native_certified': False},
        'source_anchors': {
            'native_aspects': 'source34 ProjectM.cpp:675-678 cast viewport dimensions before float division; stored inverse aspects',
            'legacy_default_shader': 'source34 PerPixelMesh.cpp:390,459 GetDefaultWarpShader selects GetLegacyPresetWarpVertexShader; MilkdropStaticShaders.cpp.in:34-36 adds PROJECTM_LEGACY_WARP',
            'native_radius': 'source34 PerPixelMesh.cpp:187 radiusAngle.radius=hypotf(x*aspectX,y*aspectY)',
            'eel_radius': 'source34 PerPixelMesh.cpp:284 rad=double(curRadiusAngle.radius)',
            'native_zoom_cast': 'source34 PerPixelMesh.cpp:302 zoom=float(perPixelContext.zoom)',
            'gpu_radius': 'source34 PresetWarpVertexShaderGlsl330.vert:4,17 radius=rad_ang.x; attribute3 is radiusAngleBuffer',
            'sampler': 'source34 PresetWarpVertexShaderGlsl330.vert:47-53,88-95 nested power, inverse zoom, aspect undo, texel offset',
            'original_radius': 'MilkDrop2 vis_milk2/plugin.cpp:2281,2289 vertinfo.rad=aspect-corrected sqrtf; vertices copy rad',
            'original_sampler': 'MilkDrop2 vis_milk2/milkdropfs.cpp:1841,1865,1877-1916 EEL radius, float zoom, power, aspect undo'},
        'conditions': [
            'Analytic nominal source/control projection only, conditional on the pinned source34 native radius and sampling formulas',
            'EEL rad is the same stored float32 mesh radius uploaded as GPU rad_ang.x; original MilkDrop2 uses the same aspect-corrected norm with sqrtf instead of hypotf',
            'The smooth radius variable replaces the stored hypotf mesh samples; source literals retain exact rational binary values, while EEL intermediate rounding and underflow are excluded',
            'Native zoom is cast to float32 after each per-pixel equation; finite positive endpoint conversions are checked, but the rational sampler and derivative precede that varying cast and GPU pow/arithmetic',
            'Required controls are constant and neutral after finite native conversion; zoomexp=1, warp=rot=dx=dy=0, sx=sy=1, cx=cy=.5',
            'Declared viewport gives native stored float32 aspects after dimension casts; output radius lies in the aspect-corrected enclosing disk, not a reached pixel or full disk coverage claim',
            'Positive a and positive z on the whole declared output domain make r/z monotone; inverse requires 1-b*r_source>0 and output inside the declared radial domain',
            'Sampling moves toward the centre when z>1; a retained fixed image feature moves outward under the inverse map, with the directions reversed when z<1',
            'Step displacement and any declared-FPS rate precede texel offset, mesh interpolation, texture sampling, feedback decay, drawings, transitions and later composition',
            'No executed trajectory, actual lifetime, native bytes, visible speed, mood or whole-preset certification follows']}
    if not consumed:
        result['status'] = 'not_contributing'
        return result
    try:
        from engine_profiles import CORE_2334_ENGINE, matches
        inputs = source.get('parser_inputs', {})
        engine = inputs.get('engine') if isinstance(inputs, dict) else None
        if not isinstance(engine, dict) or not matches(engine, CORE_2334_ENGINE):
            raise ValueError('direct radial sampler requires the exact source34 engine identity')
        stages = getattr(analysis, 'stages', {})
        stage = stages.get('warp') if isinstance(stages, dict) else None
        if not isinstance(stage, dict) or stage.get('kind') != 'fixed_warp':
            raise ValueError('direct central radial sampler requires the selected fixed/default warp stage')
        result['radius_basis_evidence']['eel_and_gpu_share_uploaded_radius'] = True
        if not isinstance(context, dict):
            raise ValueError('radial context must be a declared mapping')
        viewport = context.get('viewport')
        if not isinstance(viewport, (list, tuple)) or len(viewport) != 2 or any(type(v) is not int or not 0 < v < 2**31 for v in viewport):
            raise ValueError('radial domain requires a declared positive int32 viewport')
        width, height = viewport
        aspects = [_f32(_f32(width)/_f32(height)) if height > width else 1.,
                   _f32(_f32(height)/_f32(width)) if width > height else 1.]
        if any(v <= 0 or _f32(1/v) == 0 for v in aspects):
            raise ValueError('native aspect reciprocal domain is unusable')
        # Enclose both ideal and float-stored corner radius, padded outward;
        # hypotf intermediate/driver error remains an explicit condition.
        maximum = Fraction(math.nextafter(max(math.hypot(*aspects), _f32(math.hypot(*aspects))), math.inf))
        radius = Fraction(0), maximum
        _effect_guard(analysis)
        controls = analysis.mesh_controls
        for name, target in NEUTRAL.items():
            if name not in controls:
                raise ValueError(name+' control missing')
            a0, b0 = _affine(controls[name], radius)
            if b0 != 0 or _f32(float(a0)) != target:
                raise ValueError(name+' is changing or nonneutral for a central radial sampler')
        if 'zoom' not in controls:
            raise ValueError('zoom control missing')
        a, b = _affine(controls['zoom'], radius)
        zoom = _affine_span((a, b), radius)
        if a <= 0 or zoom[0] <= 0:
            raise ValueError('radial zoom domain reaches zero or a negative value')
        native = [_f32(v) for v in _enclosure(zoom)]
        if native[0] <= 0 or any(_f32(1/v) == 0 for v in native):
            raise ValueError('native radial zoom/reciprocal domain is zero or unusable')
        from scene_equations import _scalar
        scale = _scalar(analysis.values, 'fWarpScale', 1, 'float')
        if scale == 0 or _f32(1/scale) == 0:
            raise ValueError('original warp scale reciprocal is unusable even with zero warp')
        _scalar(analysis.values, 'fWarpAnimSpeed', 1, 'float')
        sampled = (Fraction(0), maximum/(a+b*maximum))
        derivative = tuple(sorted(a/(a+b*r)**2 for r in radius))
        crossover, regions = _regions(a, b, maximum)
        fps = context.get('feedback_fps')
        if fps is not None and (type(fps) not in {int, float} or not math.isfinite(fps) or fps <= 0):
            raise ValueError('feedback_fps must be finite positive declared cadence')
        projection = None
        if 'source_radius_domain' in context:
            sr = _span(context['source_radius_domain'])
            denominator = tuple(sorted(1-b*r for r in sr))
            if sr[0] < 0 or denominator[0] <= 0:
                raise ValueError('source feature radius is negative or inverse reaches its pole')
            output = tuple(a*r/(1-b*r) for r in sr)
            if output[0] < 0 or output[1] > maximum:
                raise ValueError('inverse feature output lies outside declared viewport radius domain')
            # Interval extension of delta=s*((a-1)+b*s)/(1-b*s)
            # conservatively handles any interior displacement extremum.
            numerator = tuple(sorted(a-1+b*r for r in sr))
            ratio = _multiply(numerator, (1/denominator[1], 1/denominator[0]))
            delta = _multiply(sr, ratio)
            displacement = max(map(abs, delta))
            pixel_scale = Fraction(max(viewport), 2)
            pixel_displacement = displacement*pixel_scale
            projection = {'source_radius_interval': _enclosure(sr), 'output_radius_interval': _enclosure(output),
                'output_minus_source_radius_interval': _enclosure(delta),
                'maximum_absolute_displacement_radius_per_step': _enclosure((displacement, displacement))[1],
                'nominal_radius_to_pixel_scale': float(pixel_scale),
                'pixel_projection_basis': 'ideal viewport-ratio isotropic projection; stored native aspect rounding is excluded',
                'maximum_absolute_displacement_pixels_per_step': _enclosure((pixel_displacement, pixel_displacement))[1],
                'declared_feedback_fps': fps, 'fps_is_observed': False,
                'maximum_absolute_displacement_pixels_per_second': None if fps is None else _enclosure((pixel_displacement*Fraction(fps),)*2)[1],
                'native_rounding_or_interpolation_included': False,
                'scope': 'one fixed feature and one nominal inverse sampling step; no lifetime trajectory'}
        result.update(status='conditional_affine_radial_sampler', viewport=list(viewport), native_aspect_xy=aspects,
            output_radius_domain=_enclosure(radius),
            zoom_affine_coefficients_exact={'a': _exact(a), 'b': _exact(b)},
            zoom_affine_coefficients={'a': _display(a), 'b': _display(b)},
            nominal_zoom_range=_enclosure(zoom), native_float32_zoom_endpoint_domain=native,
            sampled_source_radius_range=_enclosure(sampled), radial_sampling_derivative_range=_enclosure(derivative),
            neutral_radius_crossover=None if crossover is None else _display(crossover),
            neutral_radius_crossover_exact=None if crossover is None else _exact(crossover),
            all_radii_neutral=a == 1 and b == 0, direction_regions=regions, fixed_feature_projection=projection)
    except (ValueError, OverflowError, RecursionError, ZeroDivisionError) as error:
        result['unknown_reasons'].append(str(error))
    return result
