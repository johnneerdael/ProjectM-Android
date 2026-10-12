"""Machine-readable visual recipe and mood record for one preset.

``build_recipe(summary, source=None)`` turns an understanding-SDK summary (and
optionally the native reader's parsed source) into one JSON document:

- ``render``: an engine-neutral description of the effect - feedback loop
  (decay, persistence floor, warp patterns, shader mechanisms, flat-field
  colour), drawn layers (waves, custom curves, shapes, motion vectors) with
  their constant parameters and control formulas, and the composite (echo,
  gamma, scalar palette). It is meant for building a similar effect in another
  engine (WebGL, for example) without reference visuals; it is not a
  pixel-exact specification.
- ``mood``: the approximate feature vector, research scores, tags and editable
  profile suitability (approximate_features.describe).
- ``intent``: the generic effect list and music-reactivity map - the primary
  input for an 'alike' rebuild in a newer engine at higher fidelity.
- ``program`` (optional, off by default): parsed equation ASTs and authored
  shader source, only for users who want an exact port.

Expressions use the exporter's serialised graph form {root, nodes[op, args,
detail]}; inputs named time/bass/mid/treb/... are runtime inputs, other inputs
are persistent preset variables whose update equations live in ``program``.
Every record keeps ``evidence`` JSON pointers into the source export.
"""
import copy

POLICY='preset-visual-recipe-v1'
BASE='/analysis/visual_description'
STATIC=BASE+'/static_behaviour'
CONVENTIONS={
    'coordinates':'per-pixel x/y in [0,1] measured along the long viewport side (y=0 top); short axis spans a centred sub-range',
    'feedback':'each frame the previous image is resampled through the warp map, multiplied by decay, then layers are drawn on top; the composite displays the result',
    'warp_map':'source = 0.5+(p-0.5)/zoom^(zoomexp^(2*rad-1)), stretched/rotated about (cx,cy), minus (dx,dy); content therefore moves +dx right, +dy down',
    'time':'seconds since preset start; audio inputs bass/mid/treb are ~1 on average (attenuated *_att variants are smoothed)',
    'expressions':'serialised graphs {root,nodes}; EEL semantics follow projectm-eval (int=floor, x/0=0 when |d|<1e-5)',
    'fidelity':'approximate recipe for a similar effect, not a pixel-exact specification',
}


def _facts(summary):
    out={}
    for group,rows in summary.get('facts',{}).items():
        for row in rows:out[row['path']]=row['value']
    return out


def _element_indices(facts):
    indices=set()
    for path in facts:
        if path.startswith(BASE+'/elements/'):
            part=path[len(BASE+'/elements/'):].split('/')[0]
            if part.isdigit():indices.add(int(part))
    return sorted(indices)


def _control(row):
    keep=('control','control_unit','curve_kind','constant_value','offset_value','amplitude_value','period_seconds',
          'frequency_hz','nominal_value_range','signed_linear_rate_per_second','maximum_absolute_control_rate_per_second','expression')
    return {k:copy.deepcopy(row.get(k)) for k in keep if row.get(k) is not None}


def _curve(recipe):
    if not isinstance(recipe,dict):return None
    keep=('curve_class','centre_source_xy','radius_affine_coefficients','phase_affine_coefficients','axis_trig_functions',
          'nominal_turns_across_sample_domain','nominal_phase_cycles_per_source_second')
    out={k:copy.deepcopy(recipe.get(k)) for k in keep if recipe.get(k) is not None}
    colours=(recipe.get('spatial_vertex_colour') or {}).get('channels') or {}
    out['vertex_colour_affine']={name:(colours.get(name) or {}).get('affine_coefficients') for name in 'rgba' if colours.get(name)}
    domain=recipe.get('sample_domain') or {}
    if domain.get('effective_samples'):out['samples']=domain['effective_samples']
    return out


def _layer(facts,index):
    path=BASE+'/elements/%d'%index
    identity=facts.get(path+'/id')
    stage=facts.get(path+'/stage')
    parameters=copy.deepcopy(facts.get(path+'/parameters') or {})
    layer={'id':identity,'stage':stage,'mechanisms':copy.deepcopy(facts.get(path+'/mechanisms') or []),
           'evidence':[path]}
    curve=parameters.pop('source_curve_recipe',None)
    layer['constants']={k:v for k,v in parameters.items() if isinstance(v,(int,float,str,bool)) and v is not None}
    if curve is not None:layer['analytic_curve']=_curve(curve)
    controls=[_control(v) for p,v in sorted(facts.items()) if p.startswith(path+'/motion_controls/') and isinstance(v,dict)]
    if controls:layer['controls']=controls
    geometry=facts.get(path+'/geometry')
    if isinstance(geometry,dict):
        layer['geometry']={k:geometry.get(k) for k in ('radius_ndc','effective_sides','configured_instances','center_source_xy') if geometry.get(k) is not None}
    trajectory=facts.get(path+'/center_trajectory')
    if isinstance(trajectory,dict):
        layer['centre_path']={k:copy.deepcopy(trajectory.get(k)) for k in ('path_kind','center_source_xy','period_seconds',
            'semiaxis_lengths_source_units','angular_rate_rad_per_second','maximum_source_speed_units_per_second') if trajectory.get(k) is not None}
        axes=[_control(axis) for axis in trajectory.get('axis_curves') or [] if isinstance(axis,dict)]
        if axes:layer['centre_axes']=axes
    waveform=facts.get(path+'/waveform_recipe')
    if isinstance(waveform,dict):
        layer['builtin_wave']={k:copy.deepcopy(waveform.get(k)) for k in ('form_name','effective_mode','audio_inputs','wave_x','wave_y',
            'line_angle_rad','separation_normal_offset','base_radius_model_units','sample_radial_gain','nominal_rotation_rad_per_second',
            'dots','thick','additive','path_topology') if waveform.get(k) is not None}
    material=facts.get(path+'/wave_material')
    if isinstance(material,dict):
        channels={}
        for name,channel in (material.get('channels') or {}).items():
            curve_row=(channel or {}).get('raw_time_curve') or {}
            channels[name]={'time_expression':copy.deepcopy(channel.get('time_only_expression')),
                            **{k:curve_row.get(k) for k in ('curve_kind','constant_value','nominal_value_range','period_seconds') if curve_row.get(k) is not None}}
        layer['colour']={'channels':channels,'max_normalised':bool(material.get('normalization_enabled')),
                         'blend':material.get('blend_mode')}
    elif isinstance(facts.get(path+'/colour'),dict):
        layer['colour']=copy.deepcopy(facts[path+'/colour'])
    for colour_path,colour_row in facts.items():
        if not colour_path.startswith(STATIC+'/colour/components/') or not isinstance(colour_row,dict):continue
        if colour_row.get('component_id')!=identity:continue
        points=(colour_row.get('source_palette') or {}).get('point_colour_distribution') or {}
        if points.get('status')=='closed_form_point_colours':
            layer['point_cloud']={'points_per_frame':points.get('sample_count'),'sample_grid':'sample=j/(N-1)',
                **{k:copy.deepcopy(points.get(k)) for k in ('hue_family_shares','mean_rgb','mean_alpha','mean_saturation',
                   'held_inputs','positions_closed_form','position_bounds','frame_inputs','programs')},
                'coordinates':'MilkDrop source x right, y down, nominal [0,1]; colours native modulo 256/255 then clamp',
                'evidence':colour_path}
        break
    routes=[{'input_code':v.get('input_code'),'target':v.get('control'),'linear_gain':v.get('linear_gain'),
             'threshold_or_clamp':v.get('has_threshold_or_clamp'),'expression':copy.deepcopy(v.get('expression'))}
            for p,v in sorted(facts.items()) if p.startswith(path+'/audio_routes/') and isinstance(v,dict)]
    if routes:layer['audio']=routes
    return layer


AUDIO_NAMES={1:'bass',2:'mid',3:'treb',4:'bass_att',5:'mid_att',6:'treb_att',7:'vol',8:'vol_att'}


def _render(facts):
    persistence=facts.get(STATIC+'/feedback_persistence') or {}
    mesh=facts.get(STATIC+'/mesh_field') or {}
    flat=facts.get(BASE+'/nonlinear_texture_colour_bounds/flat_field') or {}
    advection=[{'stage':p.split('/stages/')[1].split('/')[0],'offset_range_uv':v.get('offset_range_uv'),'evidence':p}
               for p,v in facts.items() if '/sample_value_offset_envelope' in p and isinstance(v,dict)]
    mechanisms=[{'mechanism':v.get('mechanism'),'stage':v.get('stage'),'parameters':copy.deepcopy(v.get('parameters')),'evidence':p}
                for p,v in sorted(facts.items()) if p.startswith('/analysis/families/') and isinstance(v,dict)]
    feedback={'decay':persistence.get('decay_gain'),
        'stored_level_halving_steps':persistence.get('steps_to_half_interval'),
        'stored_level_floor':persistence.get('floor_level_interval'),
        'warp_patterns':copy.deepcopy(mesh.get('patterns') or []),
        'warp_controls':{name:{'uniform':row.get('uniform_across_mesh'),'value_range':row.get('value_range'),'terms':copy.deepcopy(row.get('terms'))}
                         for name,row in (mesh.get('controls') or {}).items() if row.get('status')=='described'},
        'shader_advection':advection,
        'flat_field':{k:flat.get(k) for k in ('state_rgb','flat_region_behaviour','settle_seconds','composite_rgb_at_state') if flat.get(k) is not None} or None,
        'evidence':[p for p in (STATIC+'/feedback_persistence',STATIC+'/mesh_field',BASE+'/nonlinear_texture_colour_bounds/flat_field') if p in facts]}
    composite={}
    for path,value in facts.items():
        if path.endswith('/legacy_response') and isinstance(value,dict):
            ranges=value.get('native_control_ranges') or {}
            composite['gamma_weight']=value.get('gamma_absolute_weight_sum_upper')
            composite['echo']={'active':value.get('echo_selection')=='active or possible native echo',
                               'alpha':ranges.get('echo_alpha'),'zoom':ranges.get('echo_zoom'),'orientation':ranges.get('echo_orient')}
            composite.setdefault('evidence',[]).append(path)
            break
    palette=facts.get(BASE+'/nonlinear_texture_colour_bounds/stages/composite/scalar_palette')
    if isinstance(palette,dict):
        composite['scalar_palette']={'ramp':[{'scalar':row['scalar'],'rgb':row['clamped_rgb']} for row in palette.get('samples') or []],
            'black_content_rgb':palette.get('black_content_rgb'),'white_content_rgb':palette.get('white_content_rgb')}
        composite.setdefault('evidence',[]).append(BASE+'/nonlinear_texture_colour_bounds/stages/composite/scalar_palette')
    vectors=facts.get(STATIC+'/motion_vectors')
    layers=[_layer(facts,index) for index in _element_indices(facts)]
    if isinstance(vectors,dict) and vectors.get('vector_count'):
        layers.append({'id':'motion_vectors','stage':'drawing','columns':vectors.get('columns_screen_fraction'),
                       'rows_from_top':vectors.get('rows_screen_fraction_from_top'),'colour_rgba':vectors.get('colour_rgba'),
                       'length_scale':vectors.get('length_scale'),'evidence':[STATIC+'/motion_vectors']})
    bindings=[{'layer':layer['id'],'input':AUDIO_NAMES.get(route['input_code'],route['input_code']),'target':route['target'],
               'linear_gain':route['linear_gain']} for layer in layers for route in layer.get('audio',[])]
    from mirror_symmetry import mirror_operators
    return {'feedback':feedback,'layers':layers,'composite':composite,'mechanisms':mechanisms,'audio_bindings':bindings,
            'mirrors':mirror_operators(facts)}


def _program(source):
    sections={}
    for name,section in (source or {}).get('sections',{}).items():
        if not isinstance(section,dict) or not section.get('active'):continue
        sections[name]={'source':section.get('source'),'ast':section.get('tree'),'status':section.get('status')}
    return {'sections':sections,'settings':copy.deepcopy((source or {}).get('values') or {}),
            'dialect':'MilkDrop 2.25c equations (projectm-eval semantics) and HLSL shader bodies as authored'}


def build_recipe(summary,source=None,*,rules=None,profiles=None,include_program=False):
    from approximate_features import describe
    facts=_facts(summary)
    recipe={'policy':POLICY,'preset':copy.deepcopy(summary.get('preset')),'conventions':CONVENTIONS,
        'description':summary.get('description'),'render':_render(facts),
        'mood':describe(summary,rules,profiles),'uses_rendered_images':False,
        'limitations':['Engine-neutral approximate recipe; drawn content, audio and native rounding make real frames differ',
                       'Mood values are editable research assumptions, not calibrated preferences']}
    display=_display_estimate(summary)
    if display is not None:recipe['display_estimate']=display
    recipe['intent']=intent(recipe)
    if source is not None and include_program:recipe['program']=_program(source)
    return recipe


def _display_estimate(summary):
    """Source-calibrated display statistics and activity bands (additive; None without a model)."""
    from calibrated_display import load,predict
    model=load()
    if model is None:return None
    values=predict(summary,model)
    from display_activity import classify
    activity=classify({k:{'value':v['value'],'interval':v['interval']} for k,v in values.items()},remap=True)
    return {'policy':'source-calibrated-display-estimate-v1','statistics':values,'activity':activity,
            'reference':'engine ruler: pinned patched projectM-TV, 480x270, 300 frames at 30 fps, checkpoint audio, frames 60-299',
            'note':'Calibrated from static source facts; intervals are the 10th-90th percentile out-of-fold residuals; not a rendered measurement of this preset'}


def main(argv=None):
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('summary',type=Path,help='preset-understanding-v1 summary JSON')
    parser.add_argument('--source',type=Path,help='native reader source JSON for the program section')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--include-program',action='store_true',help='also embed parsed equations/shaders (exact port; optional)')
    args=parser.parse_args(argv)
    recipe=build_recipe(json.loads(args.summary.read_text()),json.loads(args.source.read_text()) if args.source else None,
                        include_program=args.include_program)
    text=json.dumps(recipe,indent=1,allow_nan=False)
    if args.output:args.output.write_text(text+'\n')
    else:print(text)



SHADER_EFFECTS={
    'angular_mirror_fold':('kaleidoscope',{'sectors':'sector_count'}),
    'cartesian_mirror_fold':('mirror',{}),
    'polar_radial_sampling':('polar_tunnel',{'radial_mapping':'radial_mapping'}),
    'radial_twist':('swirl',{}),
    'global_rotation':('rotation',{}),
    'spatial_rotation':('spatial_rotation',{}),
    'image_driven_advection':('self_advection',{}),
    'gradient_driven_advection':('reaction_diffusion_flow',{}),
    'noise_driven_advection':('noise_turbulence',{}),
    'uv_advection':('periodic_wobble',{}),
    'multi_copy_feedback_recursion':('recursive_copies',{'copies':'copies','scales':'sampling_scales'}),
    'nonlinear_feedback_map':('fractal_feedback',{'construction':'construction'}),
    'complex_quadratic_recurrence':('julia_fractal',{}),
    'mandelbox_recurrence':('mandelbox_fractal',{}),
    'radial_feedback_transform':('feedback_scale',{'scale':'sampling_scale'}),
    'periodic_radial_glow':('glow_spots',{}),
    'spatial_oscillatory_bands':('stripes',{}),
    'angular_periodic_warp':('angular_warp',{}),
}


def _reactivity(render):
    """Band -> effect parameter map; strengths are relative classes, not calibrated gains."""
    from approximate_mood import is_brightness_control
    rows={}
    for binding in render['audio_bindings']:
        band=str(binding['input']);smoothed=band.endswith('_att');base=band.replace('_att','')
        target=str(binding['target'])
        kind='brightness' if is_brightness_control(target) else 'motion'
        key=(base,binding['layer'],target)
        row=rows.setdefault(key,{'band':base,'layer':binding['layer'],'target':target,'kind':kind,
                                 'smoothed':smoothed,'linear_gain':binding.get('linear_gain'),'response':'continuous'})
        row['smoothed']=row['smoothed'] and smoothed
    for layer in render['layers']:
        for route in layer.get('audio',[]):
            band=AUDIO_NAMES.get(route['input_code'],'').replace('_att','')
            row=rows.get((band,layer['id'],route['target']))
            if row is not None and route.get('threshold_or_clamp'):row['response']='threshold_or_clamped'
    for pattern in render['feedback']['warp_patterns']:
        for name in (pattern.get('audio_inputs') or [])+(pattern.get('amplitude_dependencies') or []):
            base=str(name).replace('_att','')
            if base in ('bass','mid','treb','vol'):
                rows.setdefault((base,'feedback',pattern['pattern']),{'band':base,'layer':'feedback','target':pattern['pattern'],
                    'kind':'motion','smoothed':str(name).endswith('_att'),'linear_gain':None,'response':'continuous'})
    for layer in render['layers']:
        wave=layer.get('builtin_wave') or {}
        if wave.get('audio_inputs'):
            rows[('waveform',layer['id'],'shape')]={'band':'waveform','layer':layer['id'],'target':'line shape follows the audio waveform',
                'kind':'shape','smoothed':False,'linear_gain':None,'response':'continuous','inputs':wave['audio_inputs']}
    return sorted(rows.values(),key=lambda r:(r['band'],r['layer'],r['target']))


def intent(recipe):
    """Generic, engine-neutral effect list plus music-reactivity map for an 'alike' rebuild."""
    render=recipe['render'];mood=recipe['mood'];features=mood['features']
    effects=[]
    fb=render['feedback']
    half=features.get('feedback.half_life_s',{}).get('value')
    effects.append({'effect':'trails','half_life_s':half,'decay_per_frame':fb.get('decay'),
                    'faint_residue':bool(fb.get('stored_level_floor') and max(fb['stored_level_floor'])>0)})
    for pattern in fb['warp_patterns']:
        kind=pattern.get('pattern');row={'effect':None,'region':pattern.get('region') or None}
        if kind in ('uniform_zoom','radial_zoom_profile'):
            row.update(effect='zoom_flow',percent_per_frame=pattern.get('percent_per_step_range'),direction=pattern.get('content_motion'))
        elif kind in ('uniform_rotation','spatially_varying_rotation'):row.update(effect='rotation_flow',radians_per_frame=pattern.get('value_range_radians_per_step'))
        elif kind in ('uniform_translation','translation_component'):row.update(effect='drift',axis=pattern.get('control'),pixels_per_second=pattern.get('translation_pixels_per_second_range'))
        elif kind and kind.startswith(('compression','expansion')):
            row.update(effect='squeeze' if kind.startswith('compression') else 'stretch',axis=pattern.get('control'),
                       scale_per_frame=pattern.get('composed_feature_scale_per_step_range'),toward=pattern.get('fixed_point_range'))
        elif kind in ('planar_travelling_wave','radial_ring_wave','angular_lobes','angular_modulation_with_seam'):
            osc=pattern.get('oscillator') or {}
            row.update(effect={'planar_travelling_wave':'ripple','radial_ring_wave':'ring_ripple'}.get(kind,'angular_lobes'),
                       wavelength_px=osc.get('planar_wavelength_pixels') or osc.get('radial_wavelength_pixels'),
                       speed_px_s=osc.get('phase_speed_pixels_per_second') or osc.get('radial_phase_speed_pixels_per_second'),
                       direction=osc.get('travel_direction_xy'),lobes=osc.get('angular_lobes'),amplitude_px=pattern.get('amplitude_pixels_range'))
        if row['effect']:effects.append({k:v for k,v in row.items() if v is not None})
    for item in render['mechanisms']:
        mapped=SHADER_EFFECTS.get(item['mechanism'])
        if mapped and item.get('stage') in ('warp','composite'):
            name,params=mapped;values=item.get('parameters') or {}
            effects.append({'effect':name,'stage':item['stage'],**{k:values.get(v) for k,v in params.items() if values.get(v) is not None}})
    for layer in render['layers']:
        if layer['id']=='motion_vectors':
            effects.append({'effect':'vector_grid','columns':len(layer.get('columns') or []),'rows':len(layer.get('rows_from_top') or [])});continue
        if layer.get('builtin_wave'):
            wave=layer['builtin_wave'];effects.append({'effect':'audio_waveform','form':wave.get('form_name'),
                'position':[wave.get('wave_x'),wave.get('wave_y')],'colour_cycles':bool(layer.get('colour',{}).get('channels'))})
        elif layer.get('analytic_curve'):effects.append({'effect':'parametric_curve',**layer['analytic_curve']})
        elif str(layer['id']).startswith('shape'):
            geometry=layer.get('geometry') or {}
            effects.append({'effect':'shapes','sides':geometry.get('effective_sides') or layer['constants'].get('sides'),
                            'instances':geometry.get('configured_instances') or layer['constants'].get('instances'),
                            'radius':geometry.get('radius_ndc'),'moving':bool(layer.get('controls') or layer.get('centre_axes'))})
        elif str(layer['id']).startswith('wave_'):
            cloud=layer.get('point_cloud') or {}
            effects.append({'effect':'custom_waveform','layer':layer['id'],
                **({'points_per_frame':cloud.get('points_per_frame'),'hue_family_shares':cloud.get('hue_family_shares'),
                    'mean_alpha':cloud.get('mean_alpha'),'closed_form_positions':cloud.get('positions_closed_form'),
                    'position_bounds':cloud.get('position_bounds')} if cloud else {})})
    composite=render['composite']
    if composite.get('echo',{}).get('active'):effects.append({'effect':'echo_double','alpha':composite['echo'].get('alpha'),'zoom':composite['echo'].get('zoom')})
    if composite.get('scalar_palette'):effects.append({'effect':'palette_map','ramp':composite['scalar_palette']['ramp'][::4]})
    mirrors=render.get('mirrors') or {}
    if mirrors.get('operators'):
        effects.append({'effect':'mirror_symmetry','fold':mirrors.get('fold'),'flips':mirrors.get('flip_directions'),
                        'score_upper':mirrors.get('symmetry_score'),'operators':[r['operator']+':'+r['flip'] for r in mirrors['operators']]})
    palette={'warm_cool':features.get('palette.warm_cool',{}).get('value'),'saturation':features.get('palette.mean_saturation',{}).get('value'),
             'hue_variety_bins':features.get('palette.effective_hue_bins',{}).get('value'),
             'hue_cycle_per_s':features.get('palette.hue_rate_p95_cycles_s',{}).get('value'),
             'background_rgb':(fb.get('flat_field') or {}).get('composite_rgb_at_state')}
    return {'effects':effects,'reactivity':_reactivity(render),'palette':palette,
            'energy':{'intensity':mood['scores']['intensity']['value'],'smoothness':mood['scores']['smoothness']['value'],
                      'tags':[t['tag'] for t in mood['tags']]},
            'guidance':'Rebuild the listed effects at any resolution and frame rate in a modern engine; keep the reactivity map (which band drives which parameter, continuous or thresholded, smoothed or raw) and the palette/energy character. Exact pixels are not a goal.'}


if __name__=='__main__':
    main()
