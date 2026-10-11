"""Conditional UV rectangle of a qualified central affine-radial sampler.

Coordinate wrapping and a declared GL_LINEAR footprint are different questions.
These nominal envelopes do not execute a mesh or certify native pixel taps.
"""
from fractions import Fraction
import math

from engine_profiles import CORE_2334_ENGINE, matches
from source_affine_radial_feedback import POLICY as RADIAL_POLICY
from source_curve_projection import _enclosure, _exact, _number, _span
from source_native_warp import _f32


POLICY = 'source-radial-uv-envelope-v1'


def _size(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2 or any(type(v) is not int or not 0 < v < 2**31 for v in value):
        raise ValueError(name+' must declare two positive int32 dimensions')
    return list(value)


def _qualified(recipe, viewport):
    if not isinstance(recipe, dict) or recipe.get('policy') != RADIAL_POLICY or recipe.get('status') != 'conditional_affine_radial_sampler':
        raise ValueError('qualified source affine-radial sampler record is required')
    provenance = recipe.get('source_provenance')
    inputs = provenance.get('parser_inputs') if isinstance(provenance, dict) else None
    engine = inputs.get('engine') if isinstance(inputs, dict) else None
    if not isinstance(engine, dict) or not matches(engine, CORE_2334_ENGINE):
        raise ValueError('UV envelope requires the exact source34 sampler identity')
    evidence = recipe.get('radius_basis_evidence')
    if not isinstance(evidence, dict) or evidence.get('eel_and_gpu_share_uploaded_radius') is not True:
        raise ValueError('source34 default warp/radius qualification is absent')
    if _size(recipe.get('viewport'), 'sampler viewport') != viewport:
        raise ValueError('declared viewport differs from the qualified sampler viewport')
    width, height = viewport
    aspects = [_f32(_f32(width)/_f32(height)) if height > width else 1.,
               _f32(_f32(height)/_f32(width)) if width > height else 1.]
    if recipe.get('native_aspect_xy') != aspects:
        raise ValueError('sampler aspect identity does not match the declared viewport')
    maximum = Fraction(math.nextafter(max(math.hypot(*aspects), _f32(math.hypot(*aspects))), math.inf))
    if _span(recipe.get('output_radius_domain')) != (Fraction(0), maximum):
        raise ValueError('sampler radius domain differs from the declared viewport/aspects')
    coefficients = recipe.get('zoom_affine_coefficients_exact')
    if not isinstance(coefficients, dict):
        raise ValueError('exact affine radial coefficient metadata is absent')
    a, b = (_exact(coefficients.get(name)) for name in ('a', 'b'))
    zoom = tuple(sorted((a, a+b*maximum)))
    if a <= 0 or zoom[0] <= 0:
        raise ValueError('radial UV zoom domain is singular or nonpositive')
    native = [_f32(v) for v in _enclosure(zoom)]
    if native[0] <= 0 or any(_f32(1/v) == 0 for v in native):
        raise ValueError('native radial UV zoom reciprocal domain is unusable')
    if recipe.get('native_float32_zoom_endpoint_domain') != native:
        raise ValueError('native zoom domain does not match the exact sampler coefficients')
    return a, b, tuple(map(Fraction, aspects)), maximum, provenance


def radial_uv_envelope(recipe, context=None):
    """Bound nominal transformed UV over the declared output rectangle.

    Require context viewport equal to the qualified sampler viewport, and an
    explicit texel_offset_pixels pair. Optional texture_size independently
    declares the sampled texture for a conditional GL_LINEAR footprint bound.
    """
    result = {'policy': POLICY, 'status': 'unknown', 'unknown_reasons': [],
        'viewport': None, 'native_aspect_xy': None, 'texel_offset_pixels': None,
        'native_float32_texel_offset_pixels': None, 'nominal_texel_offset_uv': None,
        'texture_size': None, 'nominal_uv_rectangle': None, 'envelope_basis': None,
        'coordinate_range_within_unit_window_xy': None, 'coordinate_wrap_possible': None,
        'linear_filter_safe_coordinate_window_xy': None,
        'linear_filter_footprint_within_texture_window_xy': None,
        'linear_filter_footprint_edge_crossing_possible': None,
        'finite_vertex_interpolation_preserves_convex_envelope_conditionally': False,
        'input_radial_policy': RADIAL_POLICY, 'source_provenance': None,
        'uses_equation_execution': False, 'uses_rendered_images': False,
        'native_numeric_certified': False, 'actual_wrap_sample_observed': False,
        'actual_linear_filter_footprint_certified': False, 'pixel_coverage_certified': False,
        'wrap_vs_clamp_visual_difference': None, 'whole_preset_activity_credit': False,
        'source_anchors': {
            'runtime_default': 'source34 ProjectM.hpp:375-376 m_texelOffsetX/Y=0; SetTexelOffsets may change them',
            'offset_uniform': 'source34 PerPixelMesh.cpp:370-371 divides runtime pixel offsets by float viewport dimensions',
            'offset_application': 'source34 PresetWarpVertexShaderGlsl330.vert:88-95 undo aspect correction then add texelOffset',
            'default_branch': 'source34 PerPixelMesh.cpp:390,459 selects GetLegacyPresetWarpVertexShader',
            'original': 'MilkDrop2 vis_milk2/milkdropfs.cpp:1791-1792 uses .5/textureSize offsets; 1914-1920 applies them after aspect undo'},
        'conditions': [
            'Input policy requires exact source34 identity, selected fixed/default warp and neutral central controls; arbitrary custom shaders/rotation/stretch are excluded by that qualification',
            'Texel pixel offsets are explicitly declared, not inferred from the zero source default or from original MilkDrop2 half-texel alignment; declaration does not observe runtime configuration',
            'Nominal map is UV=.5+.5*normalized_output_axis/(a+b*aspect_corrected_radius)+offset_pixels/viewport_axis',
            'For a>0 and b>=0, increasing the other axis increases the denominator, and the axis-boundary ratio is increasing with that axis; extrema are at axis boundary with other axis zero',
            'For b<0 and positive zoom on the enclosing radius disk, radius<=rmax and abs(normalized_output_axis)<=1 give the safe bound abs(UV-.5-offset)<=.5/(a+b*rmax)',
            'The full continuous rectangle includes boundaries; extrema need not be reached by mesh vertices or pixel centres',
            'Exact rational coefficient and bound arithmetic excludes EEL rounding, radius hypotf error, per-vertex zoom narrowing, stored inverse-aspect cancellation, viewport division rounding and GPU arithmetic',
            'Finite vertex UV values inside this rectangle remain inside its convex envelope under nonnegative triangle interpolation weights; default orthographic constant-W projection and interpolation rounding exclusions are required',
            'UV inside [0,1] excludes coordinate wrap only in this nominal map; GL_LINEAR footprint safety instead requires each sample centre in [.5/texture_dimension,1-.5/texture_dimension]',
            'Texture dimensions are independently declared and need not equal viewport dimensions; absent dimensions leave filter footprint edge crossing unresolved',
            'Possible edge crossing is conservative source envelope evidence, not an observed wrapped tap, active sampler-state proof, pixel footprint, visible difference, mood or feedback-lifetime certificate']}
    try:
        if not isinstance(context, dict):
            raise ValueError('UV envelope context must be an explicit declared mapping')
        if set(context)-{'viewport', 'texel_offset_pixels', 'texture_size'}:
            raise ValueError('unsupported UV envelope context assumptions')
        viewport = _size(context.get('viewport'), 'viewport')
        a, b, aspects, maximum, provenance = _qualified(recipe, viewport)
        offsets = context.get('texel_offset_pixels')
        if not isinstance(offsets, (list, tuple)) or len(offsets) != 2:
            raise ValueError('texel_offset_pixels must be an explicit finite pair')
        declared = list(map(_number, offsets))
        native_offsets = [_f32(float(value)) for value in declared]
        # Match the float runtime offset values; the following division by the
        # exact viewport dimensions remains nominal, not native rounded math.
        uv_offsets = [Fraction(value)/dimension for value, dimension in zip(native_offsets, viewport)]
        if b >= 0:
            widths = [Fraction(1, 2)/(a+b*aspect) for aspect in aspects]
            basis = 'axis_boundary_extrema'
        else:
            widths = [Fraction(1, 2)/(a+b*maximum)]*2
            basis = 'conservative_corner_radius_denominator'
        spans = [(Fraction(1, 2)-width+offset, Fraction(1, 2)+width+offset)
                 for width, offset in zip(widths, uv_offsets)]
        displayed = [_enclosure(span) for span in spans]
        coordinate_safe = [0 <= low and high <= 1 for low, high in spans]
        texture = None
        safe_window = None
        footprint_safe = None
        if 'texture_size' in context:
            texture = _size(context['texture_size'], 'texture_size')
            windows = [(Fraction(1, 2*dimension), 1-Fraction(1, 2*dimension)) for dimension in texture]
            safe_window = [_enclosure(window) for window in windows]
            footprint_safe = [low >= minimum and high <= maximum
                              for (low, high), (minimum, maximum) in zip(spans, windows)]
        result.update(status='conditional_radial_uv_envelope', viewport=viewport,
            native_aspect_xy=list(map(float, aspects)), texel_offset_pixels=list(map(float, declared)),
            native_float32_texel_offset_pixels=native_offsets, nominal_texel_offset_uv=[_enclosure((v, v)) for v in uv_offsets],
            texture_size=texture, nominal_uv_rectangle=displayed, envelope_basis=basis,
            coordinate_range_within_unit_window_xy=coordinate_safe, coordinate_wrap_possible=not all(coordinate_safe),
            linear_filter_safe_coordinate_window_xy=safe_window,
            linear_filter_footprint_within_texture_window_xy=footprint_safe,
            linear_filter_footprint_edge_crossing_possible=None if footprint_safe is None else not all(footprint_safe),
            finite_vertex_interpolation_preserves_convex_envelope_conditionally=True,
            source_provenance=provenance)
    except (ValueError, OverflowError, RecursionError, ZeroDivisionError) as error:
        result['unknown_reasons'].append(str(error))
    return result
