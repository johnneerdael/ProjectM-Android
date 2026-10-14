"""Source custom-shape vertex materials; no pixel/image/shader execution."""
import math
import numpy as np
from primitives import colour_modulo


def _flag(field):
    from effect_families import _number
    number=_number(field)
    if number is None or not -(2**31)-1<number<2**31:return None
    return math.trunc(number)!=0


def _flag_expression(field):
    from source_appearance import _expression
    try:return _expression(field)
    except ValueError:return None  # export budget exceeded: the flag stays an unknown


def shape_material(controls,requested_image):
    from source_appearance import _phase_literal,_expression
    groups={'centre':['r','g','b','a'],'perimeter':['r2','g2','b2','a2'],
            'border':['border_r','border_g','border_b','border_a']}
    source={};converted={};programs={};unknowns=[]
    for group,names in groups.items():
        values=[_phase_literal(controls[name]) for name in names]
        source[group]=values;programs[group]={name:_expression(controls[name]) for name in names}
        rgba=[]
        for name,value in zip(names,values):
            if value is None:
                rgba.append(None);unknowns.append(name+' is dynamic or not a supported constant');continue
            try:
                with np.errstate(over='ignore',invalid='ignore'):rgba.append(float(colour_modulo(value)))
            except ValueError:
                rgba.append(None);unknowns.append(name+' lacks a finite native colour conversion')
        converted[group]=rgba
    additive=_flag(controls['additive']);textured=_flag(controls['textured'])
    border_alpha=_phase_literal(controls['border_a'])
    if additive is None:unknowns.append('blend mode is not a known native integer style')
    if textured is None:unknowns.append('textured style is not a known native integer style')
    role='unresolved_textured_style' if textured is None else 'untextured_vertex_gradient' if not textured else \
         'named_image_request' if requested_image else 'previous_main'
    return {'policy':'source-custom-shape-material-v1',
        'gradient_kind':'centre_to_perimeter_triangle_fan_vertex_rgba',
        'source_rgba':source,'centre_vertex_rgba':converted['centre'],
        'perimeter_vertex_rgba':converted['perimeter'],'border_vertex_rgba':converted['border'],
        'border_draw_enabled':None if border_alpha is None else border_alpha>float(np.float32(.0001)),
        'border_enable_threshold':float(np.float32(.0001)),
        'thick_outline':_flag(controls['thick']) if 'thick' in controls else None,
        'channel_expressions':programs,
        # CustomShape::Draw reads these after each instance's per-frame code (a beat can switch the blend).
        'flag_expressions':{name:_flag_expression(controls[key]) for name,key in (('additive','additive'),('textured','textured')) if key in controls},
        'colour_conversion':'qualified native float32 euclidean modulo256/255 before interpolation/storage',
        'blend_mode':None if additive is None else 'source_alpha_additive' if additive else 'source_alpha_over',
        'source_blend_factor':'source_alpha',
        'destination_blend_factor':None if additive is None else 'one' if additive else 'one_minus_source_alpha',
        'texture':{'role':role,'requested_name':requested_image if requested_image else None,
                   'fallback_role':'previous_main' if textured is not False else None,
                   'actual_asset_sha256':None,'actual_binding_verified':False,
                   'tex_zoom_source':_phase_literal(controls['tex_zoom']),
                   'tex_angle_source_rad':_phase_literal(controls['tex_ang']),
                   'tex_zoom_expression':_expression(controls['tex_zoom']),
                   'tex_angle_expression':_expression(controls['tex_ang'])},
        'final_palette_verified':False,'visible_colour_contribution':None,'unknown_reasons':unknowns,
        'conditions':['Vertex colours interpolate through the polygon fan; borders use their separate colour',
                      'Texture lookup/fallback and sampler/render-context transforms remain unresolved',
                      'Texture multiplication, alpha conversion/blending, clipping and later shaders determine displayed colours'],
        'uses_rendered_images':False,'uses_equation_execution':False,'uses_shader_execution':False}


def shape_fill_contribution(geometry,material):
    """Integrate a nominal untextured fan's source colour and blend alpha.

    Each triangle has one centre and two equal perimeter colours. Its uniform
    barycentric moments are E[lambda_i]=1/3, E[lambda_i^2]=1/6 and
    E[lambda_i*lambda_j]=1/12. Colour*alpha needs the second moments.
    """
    reasons=[];mean_alpha=None;rgb=[None]*3
    if material['texture']['role']!='untextured_vertex_gradient':
        reasons.append('texture colour/alpha is unresolved; vertex colour alone is not the fill')
    else:
        centre=material['centre_vertex_rgba'];edge=material['perimeter_vertex_rgba']
        a0,a1=centre[3],edge[3]
        if any(a is None or not math.isfinite(a) or not 0<=a<=1 for a in (a0,a1)):
            reasons.append('alpha gradient is dynamic, nonfinite or outside the unclamped [0,1] domain')
        else:
            mean_alpha=(a0+2*a1)/3
            for i,(c,p) in enumerate(zip(centre[:3],edge[:3])):
                if any(v is None or not math.isfinite(v) or not 0<=v<=1 for v in (c,p)):
                    reasons.append('RGB channel '+str(i)+' is dynamic or outside the unclamped [0,1] domain')
                else:rgb[i]=((a0+a1)*c+(a0+3*a1)*p)/6
    area=geometry['nominal_area_fraction_per_aspect_y']
    if area is None:reasons.append('nominal polygon area is unresolved')
    alpha_area=None if area is None or mean_alpha is None else area*mean_alpha
    rgb_area=[None if area is None or v is None else area*v for v in rgb]
    instances=geometry['configured_instances']
    return {'policy':'source-custom-shape-fill-integrals-v1',
        'mean_fill_alpha':mean_alpha,'mean_source_rgb_times_alpha':rgb,
        'nominal_alpha_area_fraction_per_aspect_y':alpha_area,
        'nominal_source_rgb_integral_per_aspect_y':rgb_area,
        'summed_nominal_alpha_area_fraction_per_aspect_y':None if alpha_area is None else alpha_area*instances,
        'summed_nominal_source_rgb_integral_per_aspect_y':[None if v is None else v*instances for v in rgb_area],
        'blend_mode':material['blend_mode'],
        'instance_aggregation':'sum of nominal per-instance integrals; overlaps counted repeatedly',
        'border_included':False,'visible_screen_contribution':None,
        'unknown_reasons':reasons,
        'conditions':['Unclipped nominal filled regular polygon with linear centre/perimeter vertex RGBA interpolation',
                      'Multiply area coefficients by the declared target aspectY; no aspect is assumed',
                      'Source RGB times alpha is the incoming blend term, not the resulting stored/display colour',
                      'Bounds, rasterization, overlap, destination colour, borders and later feedback/composite remain separate'],
        'uses_rendered_images':False,'uses_equation_execution':False,'uses_shader_execution':False}
