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
MAX_NODES = 500_000
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
                'native_warp_recipe','native_warp_transport','native_radial_zoom','native_warp_displacement'):
        if key in appearance:
            fact('feedback',BASE+'/'+key,appearance[key],
                 'Conditional history-colour or sampling operator; source injection/storage/final appearance remain separate')
    if 'affine_radial_feedback' in static:
        radial=_object(static['affine_radial_feedback'],STATIC+'/affine_radial_feedback')
        fact('feedback',STATIC+'/affine_radial_feedback',radial,
             'Nominal radial backward sampler and inverse fixed-feature map; no executed history or visible trajectory')
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
        for key in ("colour", "material", "wave_material"):
            if key in element:
                fact("colour", path + "/" + key, element[key], "Source colour/material ingredients before final displayed composition")
        for key, group in (("audio_routes", "audio"), ("motion_controls", "motion")):
            if key in element:
                for row_index, row in enumerate(_rows(element[key], path + "/" + key)):
                    fact(group, path + "/" + key + "/" + str(row_index), row,
                         "Causal source control or nominal rate; not a visible response measurement")
    for key, group, rows_key in (("colour", "colour", "components"), ("shape_state", "shape_state", "components"),
                                ("curve_projection", "geometry", "components"),
                                ("curve_feedback_relation", "feedback", "components"),
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
        if '/curve_feedback_relation/components/' in item['path']:
            if row.get('status')!='conditional_local_curve_feedback_relation':continue
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
