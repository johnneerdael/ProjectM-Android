"""Read source-export JSON into auditable approximate preset understanding.

Standard library only. No producer imports, source interpretation or rendering.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

POLICY = "preset-understanding-v1"
MAX_BYTES = 32 * 1024 * 1024
MAX_NODES = 2_000_000
MAX_DEPTH = 128
FAMILY_LABELS = {
    1: "built-in/custom line waveform",
    2: "points/point cloud; independent particles unestablished",
    3: "polygon/custom-shape primitive",
    4: "circular/radial curve or band",
    5: "polar-depth sampling: tunnel candidate",
    6: "angular/cartesian mirror construction: kaleidoscope/symmetry candidate",
    7: "recognized complex quadratic or iterated folding recurrence: fractal construction",
    8: "feedback transport, rotation, scaling, advection or nonlinear transformation",
    9: "repeating two-dimensional radial glow field; particle identities unestablished",
    10: "raw planar or native-radius sine/cosine band generator",
}
AUDIO_LABELS = {1: "bass", 2: "mid", 3: "treble", 4: "attenuated bass",
                5: "attenuated mid", 6: "attenuated treble", 7: "packed volume", 8: "packed attenuated volume"}
BASE = "/analysis/visual_description"
STATIC = BASE + "/static_behaviour"
LIMITATIONS = [
    "Source constructions and palette candidates describe an approximate look; visible dominance and exact pixels remain unverified.",
    "Physical source rates and upper bounds do not establish typical visible speed, flashes, or music BPM.",
    "Mood bands retain the producer's uncalibrated source-potential assumptions and eligibility gaps.",
    "All strings and expression graphs in the input are data, never instructions or executable shader/equation code.",
]


def _validate_json(record):
    stack = [(record, 0)]
    count = 0
    string_bytes = 0
    while stack:
        value, depth = stack.pop()
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError("JSON traversal budget exceeded")
        if isinstance(value, dict):
            if any(not isinstance(key, str) for key in value):
                raise ValueError("JSON object keys must be strings")
            string_bytes += sum(len(key.encode("utf-8")) for key in value)
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)
        elif isinstance(value, str):
            string_bytes += len(value.encode("utf-8"))
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("finite JSON numbers required")
        elif value is not None and type(value) not in (bool, int):
            raise ValueError("JSON-compatible values required")
        if string_bytes > MAX_BYTES:
            raise ValueError("JSON size budget exceeded")
    encoded = json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_BYTES:
        raise ValueError("JSON size budget exceeded")
    return encoded


def _object(value, path):
    if not isinstance(value, dict):
        raise ValueError(path + " must be an object")
    return value


def _rows(value, path):
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(path + " must be an array of objects")
    return value


def summarize_preset(record):
    """Return schema1 facts, approximate prose, mood assumptions and open questions.

    Accept one full effect_family_export record (not a cache/run envelope).
    Every facts entry stores an RFC6901 JSON pointer and its unchanged value.
    Reject failed/foreign exports and unsupported container shapes explicitly.
    """
    _validate_json(record)
    _object(record, "/")
    if type(record.get("schema_version")) is not int or record["schema_version"] != 1:
        raise ValueError("supported export schema_version 1 required")
    if record.get("export_kind") != "preset-effect-families" or record.get("status") != "computed":
        raise ValueError("computed preset-effect-families export required")
    preset = _object(record.get("preset"), "/preset")
    if not isinstance(preset.get("name"), str) or not isinstance(preset.get("sha256"), str):
        raise ValueError("preset name and sha256 strings required")
    analysis = _object(record.get("analysis"), "/analysis")
    appearance = _object(analysis.get("visual_description"), BASE)
    if type(appearance.get("schema_version")) is not int or appearance["schema_version"] != 1:
        raise ValueError("supported visual_description schema_version 1 required")
    elements = _rows(appearance.get("elements", []), BASE + "/elements")
    static = _object(appearance.get("static_behaviour", {}), STATIC)
    classification = _object(static.get("classification", {}), STATIC + "/classification")
    facts = {name: [] for name in ("identity", "context", "construction", "colour", "geometry",
             "shape_state", "motion", "flashing", "audio", "feedback", "mood", "uncertainty")}

    def fact(group, path, value, meaning):
        facts[group].append({"path": path, "value": copy.deepcopy(value), "interpretation": meaning})

    fact("identity", "/preset", preset, "Exact source preset identity supplied by the export")
    for key in ("provenance", "cache_key", "run_identity", "uses_rendered_reference", "appearance_accuracy_verified"):
        if key in record:
            fact("identity", "/" + key, record[key], "Original export identity or verification flag")
    for key in ("context", "context_sha256", "policy", "record_sha256", "output_model_complete"):
        if key in static:
            fact("context", STATIC + "/" + key, static[key], "Declared source-analysis context; not a device observation")
    for key in ('feedback_envelope','feedback_transfer','feedback_colour_sensitivity',
                'native_warp_recipe','native_warp_transport','native_radial_zoom','native_warp_displacement',
                'texture_colour_transfer','stage_programs','rand_stream'):
        if key in appearance:
            fact('feedback',BASE+'/'+key,appearance[key],
                 'Conditional history-colour or sampling operator; source injection/storage/final appearance remain separate')
    if 'affine_radial_feedback' in static:
        radial=_object(static['affine_radial_feedback'],STATIC+'/affine_radial_feedback')
        fact('feedback',STATIC+'/affine_radial_feedback',radial,
             'Nominal radial backward sampler and inverse fixed-feature map; no executed history or visible trajectory')
    if 'feedback_persistence' in static:
        persistence=_object(static['feedback_persistence'],STATIC+'/feedback_persistence')
        fact('feedback',STATIC+'/feedback_persistence',persistence,
             'Conditional RGBA8 stored-level decay orbit for a fixed uniform decay; not visible trail length')
    if 'motion_vectors' in static:
        fact('construction',STATIC+'/motion_vectors',_object(static['motion_vectors'],STATIC+'/motion_vectors'),
             'Native motion-vector drawing element: grid, colour and activation; visible contrast unverified')
    if 'borders' in static:
        fact('feedback',STATIC+'/borders',_object(static['borders'],STATIC+'/borders'),
             'Native borders and darken-centre: bands, per-frame retained gain and RGBA8 orbits; stored levels, not displayed brightness')
    if 'mesh_field' in static:
        fact('motion',STATIC+'/mesh_field',_object(static['mesh_field'],STATIC+'/mesh_field'),
             'Per-pixel warp control field structure: regions, affine terms and oscillators; not visible motion')
    for index,row in enumerate(_rows(_object(static.get('prominence',{}),STATIC+'/prominence').get('components',[]),
                                     STATIC+'/prominence/components')):
        legacy=(row.get('final_transfer') or {}).get('legacy_response') if isinstance(row,dict) else None
        if isinstance(legacy,dict) and legacy.get('native_control_ranges'):
            fact('colour',STATIC+'/prominence/components/'+str(index)+'/final_transfer/legacy_response',legacy,
                 'Native composite gamma/echo controls; final displayed brightness remains conditional')
            break
    geometry=appearance.get('sampling_geometry')
    if isinstance(geometry,dict):
        for stage,maps in (geometry.get('stages') or {}).items():
            for index,row in enumerate(maps or []):
                if not isinstance(row,dict):continue
                path=BASE+'/sampling_geometry/stages/'+stage+'/'+str(index)
                envelope=row.get('sample_value_offset_envelope') or {}
                for key,label in ((None,'source'),('scenario_offset_envelope','scenario')):
                    record=envelope if key is None else envelope.get(key) or {}
                    span=record.get('offset_range_uv') if isinstance(record,dict) else None
                    if (isinstance(span,list) and len(span)==2 and all(isinstance(axis,list) and len(axis)==2 and
                            all(type(v) in (int,float) for v in axis) for axis in span)):
                        fact('motion',path+'/sample_value_offset_envelope'+('' if key is None else '/'+key),record,
                             'Per-step lookup displacement bound driven by sampled colours (self-advection, '+label+' domains); typical displacement is smaller')
                        break
                motion=row.get('sampling_motion') or {}
                rates=motion.get('maximum_lookup_axis_speed_uv_per_second')
                if isinstance(rates,list) and len(rates)==2 and all(type(v) in (int,float) for v in rates):
                    fact('motion',path+'/sampling_motion',motion,'Time-driven lookup speed ceiling per axis (UV/s)')
    nonlinear=appearance.get('nonlinear_texture_colour_bounds')
    if isinstance(nonlinear,dict):
        for stage,row in (nonlinear.get('stages') or {}).items():
            palette=(row or {}).get('scalar_palette') if isinstance(row,dict) else None
            if isinstance(palette,dict) and palette.get('status')=='conditional_scalar_palette':
                fact('colour',BASE+'/nonlinear_texture_colour_bounds/stages/'+stage+'/scalar_palette',palette,
                     'Stage RGB as a palette of one sampled scalar; which scalar values occur is unverified')
        if isinstance(nonlinear.get('flat_field'),dict) and nonlinear['flat_field'].get('status')=='conditional_flat_field_state':
            fact('feedback',BASE+'/nonlinear_texture_colour_bounds/flat_field',nonlinear['flat_field'],
                 'Uniform-content steady state of the feedback loop; real content with edges and drawings differs')
    families=analysis.get('families')
    if isinstance(families,list):
        for index,row in enumerate(families):
            if isinstance(row,dict) and isinstance(row.get('mechanism'),str):
                fact('construction','/analysis/families/'+str(index),row,'Proven source program mechanism; visible prominence conditional')
    if 'radial_uv_envelope' in static:
        uv=_object(static['radial_uv_envelope'],STATIC+'/radial_uv_envelope')
        fact('feedback',STATIC+'/radial_uv_envelope',uv,
             'Conditional UV coordinate and separately declared linear-filter footprint envelopes; no observed sampler taps')
    components = []
    for index, element in enumerate(elements):
        path = BASE + "/elements/" + str(index)
        codes = element.get("family_codes", [])
        if not isinstance(codes, list) or any(type(code) is not int for code in codes):
            raise ValueError(path + "/family_codes must be an integer array")
        identity = element.get("id")
        if not isinstance(identity, str):
            raise ValueError(path + "/id must be a string")
        labels = [FAMILY_LABELS.get(code, "unknown family code " + str(code)) for code in codes]
        components.append({"id": identity, "path": path, "family_labels": labels,
                           "scope": "source construction; visible contribution conditional"})
        for key in ("id", "stage", "family_codes", "parameters", "mechanisms", "conditions", "legacy_ids"):
            if key in element:
                fact("construction", path + "/" + key, element[key], "Source component construction, not displayed dominance")
        parameters = _object(element.get("parameters", {}), path + "/parameters")
        if 'waveform_recipe' in element:
            waveform=_object(element['waveform_recipe'],path+'/waveform_recipe')
            fact('audio',path+'/waveform_recipe',waveform,
                 'Intrinsic native waveform inputs and source construction; explicit EEL audio routes are separate')
        if "source_curve_recipe" in parameters:
            recipe_path = path + "/parameters/source_curve_recipe"
            recipe = _object(parameters["source_curve_recipe"], recipe_path)
            fact("geometry", recipe_path, recipe,
                 "Analytic source custom-wave curve candidate; not displayed geometry or visible speed")
            if recipe.get("source_locus_relation") is not None:
                locus_path = recipe_path + "/source_locus_relation"
                locus = _object(recipe["source_locus_relation"], locus_path)
                fact("geometry", locus_path, locus,
                     "Conditional interior continuous source curve relation; parameter point speed is separate")
                if locus.get("fixed_angle_colour") is not None:
                    fixed_colour = _object(locus["fixed_angle_colour"], locus_path + "/fixed_angle_colour")
                    fact("colour", locus_path + "/fixed_angle_colour", fixed_colour,
                         "Raw source colour on a fixed-angle interior branch; no visible flash frequency")
            if recipe.get("spatial_vertex_colour") is not None:
                colours = _object(recipe["spatial_vertex_colour"], recipe_path + "/spatial_vertex_colour")
                fact("colour", recipe_path + "/spatial_vertex_colour", colours,
                     "Affine spatial vertex-colour ingredients along sample index; not temporal flashing")
        for key in ("geometry", "center_trajectory", "vertex_motion", "audio_area_response", "audio_center_response"):
            if key in element:
                fact("geometry", path + "/" + key, element[key], "Nominal source geometry/response with original units and nulls")
        for key in ("colour", "material", "wave_material", "native_colour_generators"):
            if key in element:
                fact("colour", path + "/" + key, element[key], "Source colour/material ingredients before final displayed composition")
        if "frame_recurrence" in element:
            fact("motion", path + "/frame_recurrence", element["frame_recurrence"],
                 "Per-frame state recurrence of the shape (per instance, persistent); stepping evaluates authored equations")
        for key, group in (("audio_routes", "audio"), ("motion_controls", "motion")):
            if key in element:
                for row_index, row in enumerate(_rows(element[key], path + "/" + key)):
                    fact(group, path + "/" + key + "/" + str(row_index), row,
                         "Causal source control or nominal rate; not a visible response measurement")
    for key, group, rows_key in (("colour", "colour", "components"), ("shape_state", "shape_state", "components"),
                                ("curve_projection", "geometry", "components"),
                                ("curve_feedback_relation", "feedback", "components"),
                                ("material_marker_motion", "motion", "components"),
                                ("radial_colour_field", "colour", "components"),
                                ("motion", "motion", "contributions"), ("flashing", "flashing", "records")):
        section = _object(static.get(key, {}), STATIC + "/" + key)
        for index, row in enumerate(_rows(section.get(rows_key, []), STATIC + "/" + key + "/" + rows_key)):
            if key == "colour":
                for palette_key in ("source_palette", "final_candidate_palette"):
                    palette_path = STATIC + "/colour/components/" + str(index) + "/" + palette_key
                    palette = _object(row.get(palette_key, {}), palette_path)
                    hues = palette.get("hue_families_possible", [])
                    if not isinstance(hues, list) or any(not isinstance(hue, str) for hue in hues):
                        raise ValueError(palette_path + "/hue_families_possible must be a string array")
            fact(group, STATIC + "/" + key + "/" + rows_key + "/" + str(index), row,
                 "Conditional source evidence; bounds and intervals are not observed typical values")
        for field in ("unknown_reasons", "unknown_contributors", "unresolved_contributors", "source_hazards", "conditions"):
            if field in section:
                fact("uncertainty", STATIC + "/" + key + "/" + field, section[field], "Open conditions retained from the producer")
    if "classification" in static:
        fact("mood", STATIC + "/classification", classification, "Uncalibrated preference mapping; provisional and eligible bands are separate")
    for key in ("status", "unknown_reasons", "execution_unknowns", "limitations", "mood_matches"):
        if key in appearance:
            fact("uncertainty", BASE + "/" + key, appearance[key], "Source conditions or source-only mood candidates")
    for key in ("producer_failures", "unknown_reasons", "limitations", "displayed_output"):
        if key in static:
            fact("uncertainty", STATIC + "/" + key, static[key], "Remaining source/output qualification conditions")
    for key in ("predicted_bands", "eligible_bands"):
        value = classification.get(key, [])
        if not isinstance(value, list) or any(not isinstance(band, str) for band in value):
            raise ValueError(STATIC + "/classification/" + key + " must be a string array")
    mood = {
        "provisional_source_potential_bands": copy.deepcopy(classification.get("predicted_bands", [])),
        "eligible_bands": copy.deepcopy(classification.get("eligible_bands", [])),
        "intensity": copy.deepcopy(classification.get("intensity")),
        "scope": "producer's conditional, uncalibrated source preference mapping",
        "actual_visible_mood_verified": False,
    }
    questions = [
        {"question": "Which source layers dominate the displayed image after opacity, clipping, feedback and final composition?",
         "evidence_paths": [item["path"] for item in facts["colour"] if item["path"].startswith(STATIC)]},
        {"question": "What visible motion and flashing does the actual AAR produce with the chosen audio and render context?",
         "evidence_paths": [item["path"] for item in facts["motion"] + facts["flashing"]]},
    ]
    unknown = classification.get("unknown_contributors", [])
    if unknown:
        questions.append({"question": "Can the unresolved mood contributors be bounded before assigning automatic groups?",
                          "evidence_paths": [STATIC + "/classification/unknown_contributors"]})
    if appearance.get("status") == "unknown" or not static:
        questions.append({"question": "Can the missing appearance/static behaviour evidence be produced?",
                          "evidence_paths": [BASE]})
    result = {"schema_version": 1, "policy": POLICY, "preset": copy.deepcopy(preset),
              "input_record_sha256": hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False,
                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest(),
              "uses_rendered_images": False, "uses_shader_execution": False, "uses_equation_execution": False,
              "actual_visible_appearance_verified": False, "components": components, "facts": facts,
              "mood": mood, "unresolved_questions": questions, "limitations": list(LIMITATIONS)}
    result["description"] = _description(result)
    return result


MECHANISM_TEXT={
    'builtin_wave_primitive':'a built-in audio waveform line',
    'custom_wave_primitive':'a custom line waveform',
    'point_cloud_primitive':'a custom waveform drawn as points',
    'procedural_point_motion':'points whose positions move with sample, time or audio',
    'parametric_radial_curve':'a parametric radial curve',
    'polygon_shape_primitive':'a filled or outlined polygon shape',
    'procedural_shape_instances':'repeated shape instances with instance-dependent geometry',
    'radial_band':'a ring-shaped band at a bounded radius',
    'periodic_radial_glow':'periodic radial glow spots',
    'spatial_oscillatory_bands':'spatially oscillating colour bands or stripes',
    'polar_radial_sampling':'angle/radius (polar or log-polar) texture sampling, a tunnel-like mapping',
    'angular_mirror_fold':'kaleidoscope-style mirrored angular sectors',
    'cartesian_mirror_fold':'mirror reflection of the sampled image across an axis',
    'radial_twist':'a radius-dependent swirl of the image',
    'spatial_rotation':'a spatially varying rotation of the image',
    'global_rotation':'a rotation of the sampled image',
    'angular_periodic_warp':'an angularly periodic warp of the feedback mesh',
    'image_driven_advection':'image content steering its own sampling coordinates (self-advection: flowing, smeared or fluid-like structure)',
    'gradient_driven_advection':'flow along image gradients from central differences (reaction-diffusion or fluid-like organic patterns)',
    'noise_driven_advection':'noise textures displacing the sampling coordinates (turbulent shimmer)',
    'neighbourhood_blur':'the previous frame averaged over neighbouring samples every frame (a soft spatial blur that accumulates through the feedback into haze and smeared streaks)',
    'gradient_relief':'the image shown through its local slopes (central differences: embossed relief or normal-map shading where edges and texture stand out and flat areas read as one level)',
    'repeat_tiling':'the image repeated in tiles across the screen (periodic wrap of the sampling coordinates; mirrored tiles when the wrap alternates)',
    'blur_difference_feedback':'a finer level of the fed-back image added and a coarser blur subtracted every frame (band-pass sharpening: seeds grow into splatter, cells or edge patterns that spread over the canvas)',
    'uv_advection':'a periodic spatial displacement field (ripples or wobble)',
    'multi_copy_feedback_recursion':'several scaled copies of the previous frame (recursive nested copies)',
    'nonlinear_feedback_map':'a nonlinear feedback map of the previous frame (fractal-like iteration)',
    'radial_feedback_transform':'a scaling of the previous frame inside the shader (zoom tunnel or expansion)',
    'complex_quadratic_recurrence':'a loop-iterated complex quadratic map (Julia/Mandelbrot-style fractal)',
}


def _fmt(value):
    return format(value,'.3g') if type(value) in (int,float) else 'unresolved'


def _region_text(row):
    region=row.get('region') or {}
    parts=[]
    for name,span in region.items():
        if not isinstance(span,list) or len(span)!=2:continue
        low,high=span
        if low is not None and high is not None:parts.append(_fmt(low)+'<'+name+'<'+_fmt(high))
        elif low is not None:parts.append(name+'>'+_fmt(low))
        elif high is not None:parts.append(name+'<'+_fmt(high))
    if not parts:return ''
    fraction=row.get('screen_fraction')
    return ' within '+' and '.join(parts)+(' ('+format(fraction*100,'.0f')+'% of the screen)' if type(fraction) in (int,float) else '')


def _span_text(span,unit='',digits='.3g'):
    if not isinstance(span,list) or len(span)!=2 or not all(type(v) in (int,float) for v in span):return 'unresolved'
    low,high=span
    return (format(low,digits) if abs(low-high)<=1e-9*max(1,abs(low)) else format(low,digits)+' to '+format(high,digits))+unit


def _mesh_field_sentence(field,decay=None):
    parts=[]
    for row in field.get('patterns',[]):
        if not isinstance(row,dict):continue
        kind=row.get('pattern');where=_region_text(row)
        if kind in ('uniform_zoom','radial_zoom_profile'):
            low,high=row['percent_per_step_range']
            span=sorted([abs(low),abs(high)])
            text=('the whole image '+str(row.get('content_motion'))+' by '+_fmt(span[0])+
                  ('-'+_fmt(span[1]) if span[0]!=span[1] else '')+'% per step')
            if kind=='radial_zoom_profile':text+=' (zoomexp makes the rate vary with radius)'
            if row.get('audio_inputs'):text+=' (driven by '+'/'.join(row['audio_inputs'])+')'
            parts.append(text)
        elif kind=='spatially_varying_zoom':
            parts.append('zoom varies across the screen with '+'/'.join(row.get('coordinates',[])))
        elif kind in ('uniform_rotation','spatially_varying_rotation'):
            parts.append(kind.replace('_',' ')+' '+_span_text(row.get('value_range_radians_per_step'),' rad')+' per step')
        elif kind in ('uniform_translation','translation_component'):
            axis='horizontal' if row.get('control')=='dx' else 'vertical'
            label=' drift ' if kind=='uniform_translation' else ' offset component (combined with zoom/rotation) '
            parts.append(axis+label+_span_text(row.get('translation_pixels_per_second_range'),' px/s')+where)
        elif kind and kind.startswith(('compression_toward_fixed_line','expansion_from_fixed_line','compression_or_expansion')):
            axis='x' if row.get('control')=='dx' else 'y'
            verb={'compression_toward_fixed_line':'compressed','expansion_from_fixed_line':'stretched'}.get(
                kind.split('_with_mirror')[0].split('+')[0],'compressed or stretched')
            scales=row.get('composed_feature_scale_per_step_range')
            text=('content is '+verb+' '+_span_text([abs(v) for v in scales] if isinstance(scales,list) else None,'x')+
                  ' per step toward '+axis+'='+_span_text(row.get('fixed_point_range'))+where)
            if '_with_mirror' in kind:text+=' with mirroring'
            fraction=row.get('thin_line_integrated_fraction_per_step')
            if type(fraction) in (int,float):
                text+=('; a thin line there keeps about '+_fmt(fraction)+'x of its integrated intensity per step'+
                       (' (x'+_fmt(decay)+' decay = '+_fmt(fraction*decay)+')' if type(decay) in (int,float) else '')+
                       ', so converging lines fade, with aliasing leaving beaded remnants')
            parts.append(text)
        elif kind and kind.endswith('shear'):parts.append('shear between axes'+where)
        elif kind in ('planar_travelling_wave','planar_standing_pattern'):
            osc=row.get('oscillator') or {}
            direction=osc.get('travel_direction_xy') or [0,0];speed=osc.get('phase_speed_pixels_per_second') or 0
            vector=[direction[0]*speed,direction[1]*speed]
            heading=('right' if vector[0]>0 else 'left') if abs(vector[0])>=abs(vector[1]) else ('down' if vector[1]>0 else 'up')
            text=('a ripple of wavelength '+format(osc.get('planar_wavelength_pixels') or 0,'.0f')+' px '+
                  ('travels '+heading+' at '+format(abs(speed),'.0f')+' px/s' if speed else 'stands still'))
            amplitude=row.get('amplitude_pixels_range')
            if isinstance(amplitude,list):text+=', displacing '+_fmt(min(map(abs,amplitude)))+'-'+_fmt(max(map(abs,amplitude)))+' px per step'
            if row.get('amplitude_dependencies'):text+=' ('+'/'.join(row['amplitude_dependencies'])+'-scaled)'
            parts.append(text+where)
        elif kind in ('radial_ring_wave','radial_standing_rings'):
            osc=row.get('oscillator') or {}
            speed=osc.get('radial_phase_speed_pixels_per_second') or 0
            parts.append('concentric ring ripples of wavelength '+format(osc.get('radial_wavelength_pixels') or 0,'.0f')+' px '+
                         ('moving '+('outward' if speed>0 else 'inward')+' at '+format(abs(speed),'.0f')+' px/s' if speed else 'standing'))
        elif kind in ('angular_lobes','angular_modulation_with_seam'):
            osc=row.get('oscillator') or {}
            label=(_fmt(osc.get('angular_lobes'))+'-lobed angular modulation' if kind=='angular_lobes' else
                   'angular modulation with non-integer coefficient '+_fmt(osc.get('angular_lobes'))+' (seam at the left axis)')
            parts.append(label+' rotating '+_fmt(osc.get('angular_rotation_radians_per_second'))+' rad/s')
    if not parts:return ''
    return ('Per-pixel warp field ('+str(field.get('policy'))+'): '+'; '.join(parts[:6])+
            '. These are per-step sampling-map facts (zoom about the screen centre); visible motion depends on content, decay and composition.')


def _composite_sentence(legacy):
    ranges=legacy.get('native_control_ranges') or {}
    def value(name):
        span=ranges.get(name)
        return span[0] if isinstance(span,list) and len(span)==2 and span[0]==span[1] else None
    parts=[]
    echo=legacy.get('echo_selection')=='active or possible native echo'
    weight=legacy.get('gamma_absolute_weight_sum_upper')
    if type(weight) in (int,float) and abs(weight-1)>1e-6:
        parts.append(('gamma redraws brighten the image up to '+_fmt(weight)+'x before clamping') if weight>1 else
                     ('gamma darkens the image to '+_fmt(weight)+'x'))
    alpha=value('echo_alpha');zoom=value('echo_zoom');orient=value('echo_orient')
    if echo and (alpha is None or alpha>0.001):
        size=('variable-size' if zoom is None else _fmt(zoom)+'x magnified' if zoom>1 else
              _fmt(zoom)+'x shrunk (sampling beyond the image edge)' if zoom<1 else 'same-size')
        text='the composite blends a '+size+' copy of the image about its centre at '+(
            format(alpha*100,'.0f')+'% opacity' if alpha is not None else 'variable opacity')
        if orient is not None and math.isfinite(orient):
            # Native C++ int % 4 truncates toward zero: odd mirrors U, >=2 mirrors V.
            code=int(math.fmod(math.trunc(orient),4))
            mirror=[name for flag,name in ((code%2!=0,'horizontally'),(code>=2,'vertically')) if flag]
            text+=' ('+('mirrored '+' and '.join(mirror) if mirror else 'no flip')+')'
        parts.append(text)
    if not parts:return ''
    return 'Composite: '+'; '.join(parts)+'.'


HUE_WINDOW_SECONDS=120.0
HUE_STEP_SECONDS=0.25


def _wave_hue_cycle(material):
    """Hue families visited by closed-form time-only wave colour over a declared window."""
    from time_expression import wave_colour,hue_family
    channels=material.get('channels') or {}
    try:
        counts={}
        steps=int(HUE_WINDOW_SECONDS/HUE_STEP_SECONDS)
        for index in range(steps+1):
            family=hue_family(wave_colour(channels,index*HUE_STEP_SECONDS,bool(material.get('normalization_enabled'))))
            counts[family]=counts.get(family,0)+1
    except (ValueError,KeyError,TypeError,OverflowError,ArithmeticError):
        return ''
    total=sum(counts.values())
    ranked=sorted(counts.items(),key=lambda item:-item[1])
    return ('closed-form colour over '+format(HUE_WINDOW_SECONDS,'g')+' s visits '+
            ', '.join(name+' '+format(100*count/total,'.0f')+'%' for name,count in ranked if count/total>=.03))


def _description(summary):
    sentences = ["Approximate source description of " + json.dumps(summary["preset"]["name"], ensure_ascii=False) + "."]
    constructions = []
    for component in summary["components"]:
        for label in component["family_labels"]:
            if label not in constructions:
                constructions.append(label)
    if constructions:
        sentences.append("Constructions: " + "; ".join(constructions) + ".")
    else:
        sentences.append("No supported construction label was recorded; the appearance remains open.")
    accents = []
    for item in summary["facts"]["colour"]:
        row = item["value"]
        if not item["path"].startswith(STATIC) or row.get("eligible_accent") is not True:
            continue
        hues = row.get("source_palette", {}).get("hue_families_possible", [])
        if 0 < len(hues) < 9:
            accents.append(str(row.get("component_id")) + " possible source " + "/".join(hues))
        elif len(hues) >= 9 and row.get("status") == "dynamic_source_colour":
            accents.append(str(row.get("component_id")) +
                           " dynamic source RGB admits broad hue possibilities (reached colours unverified)")
        elif not hues and row.get("status") in {"inherited_colour", "unknown_colour"}:
            accents.append(str(row.get("component_id")) + " source/feedback palette unresolved")
    if accents:
        sentences.append("Colour ingredients: " + "; ".join(accents[:5]) + ". Final palette/dominance remain conditional.")
    for item in summary['facts']['feedback']:
        row=item['value']
        if not isinstance(row,dict):continue
        if item['path'].endswith('/radial_uv_envelope'):
            if row.get('status')!='conditional_radial_uv_envelope':continue
            wrap=row.get('coordinate_wrap_possible')
            edge=row.get('linear_filter_footprint_edge_crossing_possible')
            text='Declared radial sampler: '+('nominal coordinate wrapping excluded' if wrap is False else
                'nominal coordinate wrapping possible' if wrap is True else 'coordinate wrapping unresolved')
            text+='; '+('nominal linear-filter footprint stays in the texture window' if edge is False else
                'nominal filter-footprint edge crossing possible' if edge is True else 'filter-footprint edge crossing unresolved')
            sentences.append(text+'; conditional source envelopes, not observed native texture taps.')
            continue
        if item['path'].endswith('/feedback_persistence'):
            if row.get('status') not in {'conditional_quantized_decay_orbit','conditional_quantized_decay_orbit_profile_dependent'}:continue
            def span(key):
                value=row.get(key)
                if not isinstance(value,list) or len(value)!=2:return None
                return str(value[0]) if value[0]==value[1] else str(value[0])+'-'+str(value[1])
            text=('Stored RGBA8 decay '+format(row.get('decay_gain'),'.6g')+': a full-white level ')
            half=span('steps_to_half_interval')
            text+=('halves within '+half+' steps and ' if half is not None else 'may never halve and ')
            text+=('stalls at stored level '+str(span('floor_level_interval'))+'/255 after '+
                   str(span('steps_to_floor_interval'))+' steps')
            stuck=row.get('largest_stuck_level_interval')
            if isinstance(stuck,list) and len(stuck)==2 and stuck[1]>0:
                text+='; stored levels up to '+str(span('largest_stuck_level_interval'))+'/255 never decay further'
            sentences.append(text+' (exact-real/float32/fp16 profiles, round-to-nearest, uniform neighbourhoods; '
                'truncating conversion, filtering, drawing and visible trail length unverified).')
            continue
        if '/curve_feedback_relation/components/' in item['path']:
            if row.get('status')!='conditional_local_curve_feedback_relation':continue
            spread=row.get('bilinear_diffusion_spread')
            if isinstance(spread,dict) and spread.get('status')=='conditional_bilinear_spread_bound':
                if spread.get('adjacent_layer_merge_possible') is True:
                    sentences.append(str(row.get('component_id'))+' bilinear feedback resampling can spread retained '
                        'layers enough that adjacent copies could merge into continuous bands (a possibility from a '
                        'spread ceiling; whole-texel offsets add none).')
            sweep=row.get('persistence_layer_sweep')
            if isinstance(sweep,dict) and sweep.get('status')=='conditional_persistence_layer_sweep':
                floors=[h for h in sweep.get('horizons',[]) if isinstance(h,dict) and h.get('horizon')=='floor_level']
                crossings=[h.get('gap_crossings_lower_bound') for h in floors if type(h.get('gap_crossings_lower_bound')) is int]
                if sweep.get('interturn_gap_crossed_before_floor') is True and crossings:
                    sentences.append(str(row.get('component_id'))+' retained layers drift past fresh ones and '
                        'cross at least '+str(min(crossings))+' inter-turn gaps before their '
                        'stored level reaches the floor: a conditional gap-filling hypothesis (density unverified).')
                elif sweep.get('interturn_gap_crossed_before_floor') is False:
                    sentences.append(str(row.get('component_id'))+' retained layers stay within one inter-turn gap '
                        'before reaching the stored floor; distinct echo layers are possible (density unverified).')
            reference=_object(row.get('reference_selection',{}),item['path']+'/reference_selection')
            sentences.append(str(row.get('component_id'))+' local relation at reference sample '+
                str(reference.get('source_sample'))+': nominal inter-turn pitch '+
                str(row.get('interturn_pitch_pixels_interval'))+' pixels, signed retained/fresh layer separation '+
                str(row.get('relative_old_minus_new_pixel_step_interval'))+
                ' pixels/step; diagnostic source geometry, not observed band thickness or final density.')
            composed=[]
            for step in _rows(row.get('nominal_n_step_relations',[]),item['path']+'/nominal_n_step_relations'):
                if step.get('status')!='conditional_closed_form_radial_relation':continue
                span=step.get('relative_old_minus_new_pixel_separation_interval')
                if isinstance(span,list) and len(span)==2 and all(type(value) in (int,float) for value in span):
                    composed.append(str(step.get('declared_steps'))+' declared steps: '+str([float(value) for value in span])+' pixels')
            if composed:
                sentences.append('Closed-form retained/fresh separation at the diagnostic reference: '+
                    '; '.join(composed[:4])+'; no frames evaluated; texture, wrap, clipping and visible thickness remain separate.')
            continue
        if item['path'].endswith('/affine_radial_feedback'):
            if row.get('status')!='conditional_affine_radial_sampler':continue
            regions=_rows(row.get('direction_regions',[]),item['path']+'/direction_regions')
            directions=[]
            for region in regions:
                feature=region.get('feature_direction')
                sampling=region.get('sampling_direction')
                if feature in {'inward','outward','neutral'} and sampling in {'inward','outward','neutral'}:
                    directions.append('retained feature '+feature+' / backward sampling '+sampling+
                                      ' within output-radius interval '+str(region.get('output_radius_interval')))
            if directions:
                sentences.append('Nominal radial feedback: '+'; '.join(directions)+
                                 '; one ideal sampling step before texel offsets, mesh interpolation, storage and composition; visible trajectories unverified.')
            continue
        if not item['path'].endswith('/feedback_envelope'):continue
        gain=row.get('maximum_colour_difference_gain')
        half=row.get('ideal_perturbation_half_life_upper_bound_evaluations')
        if type(gain) in (int,float):
            text='History-colour operator difference-gain ceiling '+format(gain,'.4g')+' per warp evaluation'
            if type(half) in (int,float):text+=', ideal colour-perturbation half-life ceiling '+format(half,'.4g')+' evaluations'
            sentences.append(text+'; drawing, storage, coordinates and observed persistence remain separate.')
    routes = []
    for item in summary["facts"]["audio"]:
        row = item["value"]
        if item['path'].endswith('/waveform_recipe'):
            inputs=row.get('audio_inputs',[])
            if not isinstance(inputs,list) or any(not isinstance(value,str) for value in inputs):
                raise ValueError(item['path']+'/audio_inputs must be a string array')
            if row.get('policy')=='source31-static-builtin-waveform-v1' and inputs:
                alpha=row.get('source_alpha_policy')
                sentences.append('Native '+str(row.get('form_name','waveform construction'))+
                    ' has intrinsic waveform inputs '+', '.join(inputs)+
                    ('; alpha policy: '+alpha if isinstance(alpha,str) and alpha else '')+
                    '; audio preprocessing/history, displayed contribution and band-specific strength unresolved.')
            continue
        routes.append(AUDIO_LABELS.get(row.get("input_code"), "unrecognized audio input") + " → " +
                      str(row.get("control", "unknown control")))
    if routes:
        sentences.append("Audio routes: " + "; ".join(dict.fromkeys(routes))[:600] + "; visible strength unresolved.")
    geometry = []
    for item in summary["facts"]["geometry"]:
        row = item["value"]
        if '/curve_projection/components/' in item['path'] and isinstance(row,dict):
            radius=row.get('nominal_radius_pixels_upper_bound')
            viewport=row.get('viewport')
            if type(radius) in (int,float) and isinstance(viewport,list) and len(viewport)==2:
                text=(str(row.get('component_id'))+' nominal radius ceiling '+format(radius,'.4g')+
                      ' pixels in declared '+str(viewport[0])+'×'+str(viewport[1])+' viewport')
                if row.get('possible_coordinate_clipping') is True:text+='; coordinate clipping is possible'
                sentences.append(text+'; coordinate bounds before rasterization and final displayed contribution.')
            continue
        if not item["path"].endswith("/geometry") or not isinstance(row, dict):
            continue
        component = summary["components"][int(item["path"].split("/")[-2])]["id"]
        values = []
        for key, label in (("effective_sides", "sides"), ("configured_instances", "configured instances"),
                           ("radius_ndc", "signed NDC radius")):
            if type(row.get(key)) in (int, float):
                values.append(label + " " + format(row[key], ".4g"))
        if values:
            geometry.append(component + " " + ", ".join(values))
    if geometry:
        sentences.append("Nominal unclipped geometry: " + "; ".join(geometry[:3]) + ".")
    curves = []
    spatial = []
    locus_colours = []
    for item in summary["facts"]["geometry"]:
        if not item["path"].endswith("/parameters/source_curve_recipe"):
            continue
        row = item["value"]
        names = {"circle_candidate": "circle candidate",
                 "affine_radius_polar_spiral_candidate": "spiral candidate",
                 "affine_radius_polar_curve_candidate": "affine-radius polar curve candidate"}
        if row.get("policy") != "source-parametric-wave-v1" or row.get("curve_class") not in names:
            continue
        component = summary["components"][int(item["path"].split("/")[-3])]["id"]
        terms = [component + " " + names[row["curve_class"]]]
        for key, unit in (("nominal_turns_across_sample_domain", "nominal turns across sample domain"),
                          ("nominal_phase_cycles_per_source_second", "nominal phase cycles/source-time second")):
            if type(row.get(key)) in (int, float):
                terms.append(format(row[key], ".4g") + " " + unit)
        speed = row.get("maximum_fixed_sample_source_coordinate_speed_per_second")
        if type(speed) in (int, float):
            terms.append("fixed-sample source-coordinate partial-speed ceiling " + format(speed, ".4g") +
                         " " + str(row.get("speed_unit", "source-coordinate units per source-time second")) +
                         " (parameter-point motion, not curve drift)")
        locus = row.get("source_locus_relation")
        if isinstance(locus, dict) and locus.get("policy") == "source-parametric-wave-locus-v1":
            if locus.get("continuous_full_circle_locus_stationary") is True:
                terms.append("continuous full-circle source locus is stationary even if parameter points move")
            radial = locus.get("fixed_angle_branch_radial_rate_source_coordinates_per_second")
            normal = locus.get("maximum_interior_geometric_normal_speed_source_coordinates_per_second")
            if type(radial) in (int, float):
                terms.append("signed fixed-angle radius rate " + format(radial, ".4g") +
                             " source coordinate units/source-time second")
            if type(normal) in (int, float):
                terms.append("interior geometric normal-speed ceiling " + format(normal, ".4g") +
                             " source coordinate units/source-time second")
            terms.append("finite endpoints, polylines, pixels and feedback remain unresolved")
            fixed_colour = locus.get("fixed_angle_colour")
            if isinstance(fixed_colour, dict):
                channels = _object(fixed_colour.get("channels", {}),
                                   item["path"] + "/source_locus_relation/fixed_angle_colour/channels")
                rates = []
                cycles = []
                for name in "rgb":
                    channel = channels.get(name)
                    if not isinstance(channel, dict):
                        continue
                    rate = channel.get("raw_source_colour_rate_per_second")
                    cycle = channel.get("nominal_raw_modulo_cycles_per_source_second")
                    if type(rate) in (int, float):
                        rates.append(name + "=" + format(rate, ".4g"))
                    if type(cycle) in (int, float):
                        cycles.append(name + "=" + format(cycle, ".4g"))
                if rates:
                    relation = component + " raw fixed-angle RGB rates " + "/".join(rates) + "/source-time second"
                    if cycles:
                        relation += "; nominal raw modulo cycles/source-time second " + "/".join(cycles)
                    locus_colours.append(relation + "; native events and visible flashing unresolved")
        curves.append(", ".join(terms))
        colour = row.get("spatial_vertex_colour")
        if isinstance(colour, dict) and colour.get("policy") == "source-custom-wave-spatial-colour-bands-v1":
            channels = _object(colour.get("channels", {}), item["path"] + "/spatial_vertex_colour/channels")
            affine = [name for name, channel in channels.items() if isinstance(channel, dict) and
                      isinstance(channel.get("affine_coefficients"), dict)]
            if affine:
                spatial.append(component + " spatial vertex-colour affine ingredients in " + "/".join(affine))
            joint=colour.get('joint_rgb_spatial_pattern')
            if isinstance(joint,dict) and joint.get('policy')=='source-affine-rgb-joint-spatial-period-v1' and joint.get('status')=='nominal_rgb_modulo_congruence':
                period=joint.get('nominal_joint_period_sample')
                winds=_object(joint.get('signed_channel_windings',{}),item['path']+'/spatial_vertex_colour/joint_rgb_spatial_pattern/signed_channel_windings')
                if type(period) in (int,float) and all(type(winds.get(name)) is int and len(str(winds[name]))<=32 for name in 'rgb'):
                    spatial.append(component+' nominal joint RGB congruence period '+format(period,'.4g')+
                        ' source-sample units with RGB winding '+'/'.join(name+'='+str(winds[name]) for name in 'rgb')+
                        '; fixed source time; native signed remainder, rounding and reached repetitions remain separate')
    if curves:
        sentences.append("Analytic source curves: " + "; ".join(curves[:3]) +
                         "; before native sampling, aspect projection, smoothing, clipping and feedback, not visible revolutions/speed.")
    if spatial:
        sentences.append("Spatial colour: " + "; ".join(spatial[:3]) +
                         "; source sample-index colour formulas, not temporal flashing or verified displayed colour bands.")
    if locus_colours:
        sentences.append("Interior source colour relation: " + "; ".join(locus_colours[:3]) + ".")
    rings=[]
    for item in summary['facts']['colour']:
        row=item['value']
        if '/radial_colour_field/components/' not in item['path'] or not isinstance(row,dict):continue
        if row.get('status')!='conditional_radius_locked_colour':continue
        periods=[]
        for name,channel in (row.get('channels') or {}).items():
            period=channel.get('radial_modulo_period_pixels') if isinstance(channel,dict) else None
            if type(period) in (int,float):periods.append(name+' every '+format(period,'.4g')+' px')
        pattern=row.get('concentric_ring_pattern')
        text=(str(row.get('component_id'))+' raw colour along the curve depends only on radius (radius-locked); '
              'where feedback fills the gaps this can read as concentric colour rings')
        if periods:text+=' (radial modulo period '+', '.join(periods)+' where raw labels stay nonnegative)'
        if pattern=='static_at_fixed_radius':text+='; colour is static at a fixed radius in the fresh drawing'
        elif pattern=='drifting_or_cycling':text+='; ring colours drift or cycle over time'
        sweep=row.get('sweep_front')
        if isinstance(sweep,dict) and sweep.get('status')=='conditional_rotating_refresh_front':
            text+=('; the curve sweeps each covered radius at '+format(sweep['revisit_cadence_hz'],'.3g')+
                   ' Hz as a rotating refresh front (local travelling change, not a whole-screen flash)')
            levels=sweep.get('stored_level_from_full_before_next_crossing_interval')
            if isinstance(levels,list) and len(levels)==2:
                text+=', a deposit falls to stored level '+str(levels[0])+'-'+str(levels[1])+'/255 before the next crossing without refill'
        elif isinstance(sweep,dict) and sweep.get('status')=='stationary_curve_at_fixed_radius':
            text+='; the curve point at each radius does not rotate'
        rings.append(text)
    if rings:
        sentences.append('Ring colour structure: '+'; '.join(rings[:3])+'. This holds for the continuous source curve; '
            'layering, smoothing and modulo/clamps can break it, and visible ring count is unverified.')
    decay=next((item['value'].get('decay_gain') for item in summary['facts']['feedback']
                if item['path'].endswith('/feedback_persistence') and isinstance(item['value'],dict)),None)
    for item in summary['facts']['motion']:
        if item['path'].endswith('/mesh_field') and isinstance(item['value'],dict):
            text=_mesh_field_sentence(item['value'],decay)
            if text:sentences.append(text)
    for item in summary['facts']['construction']:
        row=item['value']
        if (item['path'].endswith('/motion_vectors') and isinstance(row,dict) and row.get('status')=='described'
                and (row.get('vector_count') or 0)>0):
            rows=row.get('rows_screen_fraction_from_top') or []
            colour=row.get('colour_rgba') or []
            text=(str(row.get('vector_count'))+' motion vectors ('+('active' if row.get('activation')=='active' else 'possibly active')+
                  ') on '+str(len(row.get('columns_screen_fraction') or []))+' columns x '+str(len(rows))+' row'+('s' if len(rows)!=1 else ''))
            if len(rows)==1:text+=' at '+format(rows[0]*100,'.0f')+'% down the screen'
            if colour and all(type(v) in (int,float) for v in colour[:3]):text+=', colour '+str([round(v,3) for v in colour[:3]])
            sentences.append('Motion vectors: '+text+'; each points toward where the warp sampled content from and is drawn into '
                             'the feedback image, so it is then warped and decayed with other drawings.')
    for item in summary['facts']['colour']:
        row=item['value']
        if not item['path'].endswith('/wave_material') or not isinstance(row,dict):continue
        parts=[];varying=False
        for name,channel in (row.get('channels') or {}).items():
            curve=(channel or {}).get('raw_time_curve') or {}
            label=name.replace('wave_','')
            if curve.get('curve_kind')=='constant' and type(curve.get('constant_value')) in (int,float):
                parts.append(label+' constant '+_fmt(curve['constant_value']))
            elif isinstance(curve.get('nominal_value_range'),list):
                low,high=curve['nominal_value_range'];varying=True
                text=label+' '+_fmt(low)+'-'+_fmt(high)
                details=[]
                if type(curve.get('maximum_absolute_control_rate_per_second')) in (int,float):
                    details.append('at most '+_fmt(curve['maximum_absolute_control_rate_per_second'])+'/s')
                if type(curve.get('period_seconds')) in (int,float):details.append('period '+_fmt(curve['period_seconds'])+' s')
                parts.append(text+(' ('+', '.join(details)+')' if details else ''))
        cycle=_wave_hue_cycle(row)
        if cycle:parts.append(cycle)
        if varying:
            sentences.append('Built-in wave colour changes over time: '+'; '.join(parts)+
                ('; RGB is clamped then max-normalised, so the hue shifts while the brightest channel stays at full'
                 if row.get('normalization_enabled') else '')+'. Raw source curves, not observed displayed colours.')
    for item in summary['facts']['colour']:
        if item['path'].endswith('/legacy_response') and isinstance(item['value'],dict):
            text=_composite_sentence(item['value'])
            if text:sentences.append(text)
    for item in summary['facts']['feedback']:
        row=item['value']
        if not item['path'].endswith('/borders') or not isinstance(row,dict) or row.get('status')!='described':continue
        parts=[]
        for border in row.get('borders') or []:
            if not border.get('active'):continue
            text=(border['border']+' border'+(' covering '+format(100*border['screen_area_fraction'],'.1f')+'% of the screen'
                  if type(border.get('screen_area_fraction')) in (int,float) else ''))
            alpha=border.get('alpha_range');rgb=[c[0] if c and c[0]==c[1] else None for c in border.get('rgb_ranges') or []]
            if alpha and alpha[0]==alpha[1]:text+=' blends '+('black' if rgb==[0,0,0] else str([round(c,2) if c is not None else None for c in rgb]))+' at alpha '+_fmt(alpha[0])+' every frame'
            if type(border.get('combined_gain_with_decay')) in (int,float):
                text+=', so retained content there keeps '+_fmt(border['combined_gain_with_decay'])+' per frame'
                if type(border.get('seconds_to_half_from_full')) in (int,float):
                    text+=' (stored white halves in '+_fmt(border['seconds_to_half_from_full'])+' s, floor level '+str(border.get('floor_level_from_full'))+'/255)'
            parts.append(text)
        darken=row.get('darken_centre') or {}
        if darken.get('active'):parts.append('darken-centre diamond dims the screen centre by up to 3/32 per frame')
        if parts:sentences.append('Borders: '+'; '.join(parts)+'. Feedback-canvas operators; content moving through the band fades accordingly.')
    from mirror_symmetry import mirror_operators,sentence as mirror_sentence
    text=mirror_sentence(mirror_operators({item['path']:item['value'] for rows in summary['facts'].values() for item in rows}))
    if text:sentences.append(text)
    for item in summary['facts']['colour']:
        row=(item['value'].get('source_palette') or {}).get('point_colour_distribution') if isinstance(item['value'],dict) else None
        if not isinstance(row,dict) or row.get('status')!='closed_form_point_colours':continue
        component=item['value'].get('component_id') or item['path'].rsplit('/',1)[-1]
        shares=', '.join(name+' '+format(100*share,'.0f')+'%' for name,share in list((row.get('hue_family_shares') or {}).items())[:4])
        text=(str(component)+' points ('+str(row.get('sample_count'))+' per frame) are coloured '+shares+
              ', mean saturation '+_fmt(row.get('mean_saturation'))+', mean alpha '+_fmt(row.get('mean_alpha')))
        bounds=row.get('position_bounds') if row.get('positions_closed_form') else None
        if bounds:text+='; positions are closed-form in sample/time within x '+_fmt(bounds['x'][0])+'-'+_fmt(bounds['x'][1])+', y '+_fmt(bounds['y'][0])+'-'+_fmt(bounds['y'][1])
        elif row.get('positions_closed_form') and row.get('frame_inputs'):text+='; positions are closed-form in sample/time and the main per-frame state ('+', '.join(map(str,row['frame_inputs'][:6]))+(', ...' if len(row['frame_inputs'])>6 else '')+'), resolved by stepping the frame program'
        sentences.append(text+' (authored sample grid at declared times; audio held at midpoints; displayed coverage unresolved).')
    mechanisms=[]
    for item in summary['facts']['construction']:
        if item['path'].startswith('/analysis/families/') and isinstance(item['value'],dict):
            name=item['value'].get('mechanism');text=MECHANISM_TEXT.get(name)
            label=(text or name.replace('_',' '))+' ('+str(item['value'].get('stage'))+')'
            if label not in mechanisms:mechanisms.append(label)
    if mechanisms:
        sentences.append('Source mechanisms: '+'; '.join(mechanisms[:8])+'. Proven program constructions; how prominent each is on screen is conditional.')
    for item in summary['facts']['colour']:
        row=item['value']
        if not item['path'].endswith('/scalar_palette') or not isinstance(row,dict):continue
        stage=item['path'].split('/stages/')[1].split('/')[0]
        text=(stage.capitalize()+' colour is a palette of one sampled scalar, running through '+', '.join(row.get('hue_families') or [])+
              ' across its range')
        black,white=row.get('black_content_hue_family'),row.get('white_content_hue_family')
        if black and white:text+='; black content shows '+black+' and white content shows '+white
        sentences.append(text+'. Which scalar values occur depends on the feedback content.')
    for item in summary['facts']['feedback']:
        row=item['value']
        if not item['path'].endswith('/flat_field') or not isinstance(row,dict):continue
        from time_expression import hue_family
        behaviour=row.get('flat_region_behaviour');seconds=row.get('settle_seconds')
        text='Flat-field model: uniform regions '+{'decays_to_black':'decay to black','saturates_to_white':'saturate to white',
            'settles_on_colour':'settle','cycles':'cycle','still_changing':'keep changing'}.get(behaviour,str(behaviour))
        if type(seconds) in (int,float) and behaviour in ('settles_on_colour','decays_to_black','saturates_to_white'):
            text=text.replace('uniform regions','flat regions')+' in about '+format(seconds,'.2g')+' s'
        display=row.get('composite_rgb_at_state')
        if isinstance(display,list) and len(display)==3:
            text+=', displayed as '+hue_family(display)+' '+str([round(v,2) for v in display])
        start=row.get('composite_rgb_at_start')
        if isinstance(start,list) and len(start)==3:text+=' (black start displays as '+hue_family(start)+')'
        facts_all={i['path']:i['value'] for rows in summary['facts'].values() for i in rows}
        transfer=facts_all.get(BASE+'/feedback_transfer') or {}
        gain=transfer.get('uniform_content_gain')
        if type(gain) not in (int,float):gain=(facts_all.get(STATIC+'/feedback_persistence') or {}).get('decay_gain')
        drawing=any(p.startswith('/analysis/families/') and isinstance(v,dict) and v.get('stage')=='drawing' for p,v in facts_all.items())
        if drawing and (gain is None or gain>=.99):
            text+=('; feedback keeps %s of retained content per frame and elements are drawn, so drawn content accumulates and '
                   'this empty-canvas state does not describe the displayed picture'%('an unknown share' if gain is None else format(gain,'.3g')))
        sentences.append(text+'; edges, drawn elements and advection make real content differ.')
    markers=[]
    for item in summary['facts']['motion']:
        row=item['value']
        if '/material_marker_motion/components/' not in item['path'] or row.get('status')!='conditional_raw_material_marker':continue
        phase=row.get('marker_phase_rate_radians_per_second')
        source=row.get('maximum_marker_source_speed_per_second')
        if type(phase) not in (int,float) or type(source) not in (int,float):continue
        radial=row.get('marker_radius_rate_source_coordinates_per_second')
        radial_text=('radial '+str(radial)+' source units/s' if type(radial) in (int,float) else
                     'radial rate not representable in binary64 display')
        text=(str(row.get('component_id'))+' raw colour labels ride the source curve at '+str(phase)+
              ' rad/s ('+radial_text+'), label speed ceiling '+format(source,'.4g')+' source units/s')
        pixels=row.get('maximum_marker_pixels_speed_per_second')
        if type(pixels) in (int,float):text+=' or '+format(pixels,'.4g')+' declared-viewport pixels/s'
        locus=row.get('source_geometric_locus')
        normal=locus.get('maximum_interior_normal_source_speed_per_second') if isinstance(locus,dict) else None
        if type(normal) in (int,float):
            text+=', while the geometric locus normal drift ceiling is '+format(normal,'.4g')+' source units/s'
        markers.append(text)
    if markers:
        sentences.append('Material-labelled motion: '+'; '.join(markers[:3])+
            '. Labels and shape drift are separate source quantities; native colour modulo/clamps, '
            'interpolation and feedback can hide labels, so this is not visible speed.')
    physical = []
    for item in summary["facts"]["motion"]:
        row = item["value"]
        linear = row.get("signed_linear_rate_per_second")
        if type(linear) in (int, float) and linear != 0:
            physical.append(str(row.get("control")) + " nominal signed control rate " + format(linear, ".4g") +
                            " " + str(row.get("control_unit", "control units")) + "/second")
        elif row.get("kind") == "sampled_content_displacement_relation" or row.get("is_trajectory_speed") is False:
            distance = row.get("maximum_origin_output_distance_vp_per_feedback_step")
            if type(distance) in (int, float):
                physical.append(str(row.get("component_id")) + " sampling-origin displacement ceiling " +
                                format(distance, ".4g") + " viewport units/feedback step (not trajectory speed)")
        elif row.get("kind") in {"backward_sampling_displacement", "native_affine_component_transport"}:
            maximum = row.get("maximum_speed_vp_per_second")
            if type(maximum) in (int, float):
                physical.append(str(row.get("component_id")) + " sampling/component diagnostic ceiling " +
                                format(maximum, ".4g") + " viewport units/second (not whole-map content speed)")
        elif type(row.get("maximum_speed_vp_per_second")) in (int, float):
            physical.append(str(row.get("component_id")) + " nominal " + str(row.get("kind", "source transport")) +
                            " upper bound " + format(row["maximum_speed_vp_per_second"], ".4g") +
                            " viewport units/second (" + str(row.get("rate_kind", "source scope")) + ")")
    for item in summary["facts"]["flashing"]:
        row = item["value"]
        if type(row.get("cycle_rate_hz")) in (int, float) and row["cycle_rate_hz"] > 0:
            physical.append(str(row.get("component_id")) + " nominal brightness-cycle rate " +
                            format(row["cycle_rate_hz"], ".4g") + " Hz (displayed flash unverified)")
    if physical:
        sentences.append("Physical source facts: " + "; ".join(physical[:3]) + ".")
    if summary["facts"]["motion"] or summary["facts"]["flashing"]:
        sentences.append("Motion and brightness facts retain nominal rates/upper bounds and unresolved inputs; typical visible speed and flashing remain unverified.")
    mood = summary["mood"]
    if mood["eligible_bands"]:
        sentences.append("Conditional source mood eligibility: " + ", ".join(mood["eligible_bands"]) + " under the exported assumptions.")
    else:
        sentences.append("The strict source model records no eligible mood group; approximate LLM estimates remain separate.")
    if mood["provisional_source_potential_bands"]:
        sentences.append("Provisional source-potential mood: " + ", ".join(mood["provisional_source_potential_bands"]) + "; uncalibrated.")
    return " ".join(sentences)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output is not None and (args.output.resolve() == args.input_json.resolve() or
                args.output.exists() and args.output.samefile(args.input_json)):
            raise ValueError("output must differ from original input JSON")
        with args.input_json.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("JSON file size budget exceeded")
        record = json.loads(raw)
        result = summarize_preset(record)
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output is None:
            print(text, end="")
        else:
            args.output.write_text(text, encoding="utf-8")
        return 0
    except (OSError, ValueError, TypeError, RecursionError) as error:
        print("Preset understanding stopped: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
