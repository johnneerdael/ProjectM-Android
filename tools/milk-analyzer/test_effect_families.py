"""Source-only semantic family controls; the native reader only parses source."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
READER = ROOT / 'build/preset-corpus/source31/adapters/milk-native-reader'
PRESETS = ROOT / 'core/src/main/assets/presets'


def analyze(source, **kwargs):
    assert importlib.util.find_spec('effect_families'), 'source-only family analyzer is missing'
    from effect_families import analyze_families
    return analyze_families(source, **kwargs)


def read(raw):
    if isinstance(raw, str):
        raw = ('MILKDROP_PRESET_VERSION=201\n[preset00]\n' + raw).encode()
    assert READER.is_file(), 'exact source31 parsing adapter required'
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'source.milk'
        path.write_bytes(raw)
        source = json.loads(subprocess.check_output([str(READER), str(path)]))
    source['preset_sha256'] = hashlib.sha256(raw).hexdigest()
    # Same lookup binding as forecast.load_source; the native reader emits the
    # lowercase payload, while its caller binds the engine-specific contract.
    source['parser_inputs']['setting_lookup_policy'] = 'native-case-insensitive-v1'
    source['numbered_source'] = raw.decode(errors='replace')
    return source


def shader(code, stage='comp'):
    return read('PSVERSION_' + ('COMP' if stage == 'comp' else 'WARP') + '=2\n' +
                stage + '_1=`' + code + '\n')


def families(record):
    return {row['mechanism'] for row in record['families']}


def rows(record, mechanism):
    return [row for row in record['families'] if row['mechanism'] == mechanism]


def test_live_polar_sample_reports_conditional_mechanism_and_provenance():
    source = shader('shader_body {float2 p=uv-.5;float r=length(p)+.05;'
                    'float a=atan2(p.y,p.x);ret=GetPixel(float2(a/6.28,.2/r+time));}')
    record = analyze(source)
    row = rows(record, 'polar_radial_sampling')[0]
    assert row['parameters']['radial_mapping'] == 'reciprocal_radius'
    assert row['appearance']['status'] == 'conditional'
    assert row['contribution']['status'] == 'live'
    assert row['evidence'][0]['section'] == 'comp_'
    assert row['evidence'][0]['source_keys'] == ['comp_1']
    assert record['preset_sha256'] == source['preset_sha256']
    assert record['uses_shader_execution'] is False
    assert record['uses_equation_execution'] is False
    json.dumps(record, allow_nan=False)


@pytest.mark.parametrize('body', [
    'float2 dead=float2(ang,1/rad);ret=GetPixel(uv);',
    'float2 p=float2(ang,1/rad);p=uv;ret=GetPixel(p);',
    'ret=GetPixel(float2(ang,1/rad))*0;',
    'if(0){ret=GetPixel(float2(ang,1/rad));}else{ret=GetPixel(uv);}',
])
def test_dead_overwritten_zero_mask_and_unselected_polar_forms_are_suppressed(body):
    assert 'polar_radial_sampling' not in families(analyze(shader('shader_body {' + body + '}')))


@pytest.mark.parametrize('code', [
    'shader_body {ret=float4(1,0,0,GetPixel(float2(ang,1/rad)).r);}',
    'shader_body {ret=float4(1,0,0,tex2D(sampler_main,float2(ang,1/rad)).a);}',
    'float4 colour(float2 p){return float4(1,0,0,GetPixel(p).r);}'
    'shader_body {ret=colour(float2(ang,1/rad));}',
    'shader_body {ret=(float3)float4(1,0,0,GetPixel(float2(ang,1/rad)).r);}',
    'shader_body {float4 colour=float4(1,0,0,0);for(int n=0;n<2;n++)'
    '{colour.w+=GetPixel(float2(ang,1/rad)).r;}ret=colour;}',
])
def test_discarded_fourth_return_lane_cannot_supply_polar_family(code):
    # Native ret is float3; assigning float4 implicitly drops its fourth lane.
    source = shader(code)
    assert source['sections']['comp_']['status'] == 'parsed'
    assert 'polar_radial_sampling' not in families(analyze(source))


def test_discarded_composite_fourth_lane_cannot_preserve_warp_or_drawing():
    source = read('PSVERSION_WARP=2\nPSVERSION_COMP=2\nfWaveAlpha=1\n'
        'shapecode_0_enabled=1\nshapecode_0_sides=6\n'
        'warp_1=`shader_body {ret=GetPixel(float2(ang,1/rad));}\n'
        'comp_1=`shader_body {ret=float4(1,0,0,GetPixel(uv).r);}\n')
    assert not families(analyze(source))


@pytest.mark.parametrize('prefix', [
    'while(bass>0){}',
    'float values[1]={1};values[int(time)]=1;',
])
def test_discarded_fourth_lane_keeps_loop_and_domain_effect_uncertainty(prefix):
    record = analyze(shader('shader_body {' + prefix +
        'ret=float4(1,0,0,GetPixel(float2(ang,1/rad)).r);}'))
    assert not families(record)
    assert any('termination/domain' in row['reason'] for row in record['unknowns'])


@pytest.mark.parametrize('code', [
    'shader_body {ret=float4(GetPixel(float2(ang,1/rad)).r,0,0,1);}',
    'float4 colour(float2 p){return float4(GetPixel(p).r,0,0,1);}'
    'shader_body {ret=colour(float2(ang,1/rad));}',
    'shader_body {float4 colour=0;for(int n=0;n<2;n++)'
    '{colour.x+=GetPixel(float2(ang,1/rad)).r;}ret=colour;}',
    'float live;float4 colour(float2 p){live=GetPixel(p).r;return 1;}'
    'shader_body {float4 unused=colour(float2(ang,1/rad));ret=float4(live,0,0,unused.a);}',
    'shader_body {ret=normalize(float4(1,0,0,GetPixel(float2(ang,1/rad)).r));}',
    'shader_body {ret=float4(1,0,0,GetPixel(float2(ang,1/rad)).r).a;}',
])
def test_consumed_rgb_lanes_and_helper_side_effects_keep_polar_family(code):
    source = shader(code)
    assert source['sections']['comp_']['status'] == 'parsed'
    assert 'polar_radial_sampling' in families(analyze(source))


def test_live_composite_rgb_keeps_connected_warp_and_drawing():
    source = read('PSVERSION_WARP=2\nPSVERSION_COMP=2\nfWaveAlpha=1\n'
        'shapecode_0_enabled=1\nshapecode_0_sides=6\n'
        'warp_1=`shader_body {ret=GetPixel(float2(ang,1/rad));}\n'
        'comp_1=`shader_body {ret=float4(GetPixel(uv).r,0,0,1);}\n')
    record = analyze(source)
    assert any(row['stage'] == 'warp' for row in record['families'])
    assert any(row['stage'] == 'drawing' for row in record['families'])


def test_unused_helper_and_filename_cannot_supply_families():
    source = shader('float2 tunnel(float2 p){return float2(ang,1/rad);}'
                    'shader_body {ret=GetPixel(uv);}')
    source['filename'] = 'julia mandelbrot tunnel kaleidoscope particle.milk'
    assert 'polar_radial_sampling' not in families(analyze(source))
    assert 'complex_quadratic_recurrence' not in families(analyze(source))


@pytest.mark.parametrize('initial,c,subtype', [
    ('uv-.5', 'float2(.2,.3)', 'julia_style'),
    ('float2(0,0)', 'uv-.5', 'mandelbrot_style'),
    ('uv', 'uv', 'unclassified'),
])
def test_complex_loop_classification_uses_initial_state_and_parameter_plane(initial,c,subtype):
    source = shader('float2 renamed(float2 beginning,float2 parameter){float2 orbit=beginning;'
                    'for(int k=0;k<8&&dot(orbit,orbit)<4;k++){'
                    'float realpart=orbit.x*orbit.x-orbit.y*orbit.y;'
                    'float imaginary=2*orbit.x*orbit.y;orbit=float2(realpart,imaginary)+parameter;}'
                    'return orbit;}shader_body {float2 p=renamed(' + initial + ',' + c + ');'
                    'ret=dot(p,p)>4?0:1;}')
    row = rows(analyze(source), 'complex_quadratic_recurrence')[0]
    assert row['parameters']['subtype'] == subtype
    assert row['parameters']['norm_bailout'] is True


def test_quadratic_map_without_loop_is_temporal_feedback_not_escape_recurrence():
    record = analyze(shader('shader_body {float2 p=uv-.5;'
        'float2 z=float2(p.x*p.x-p.y*p.y,2*p.x*p.y)+float2(.1,.2);'
        'ret=GetPixel(frac(z))*.94;}', 'warp'))
    assert 'nonlinear_feedback_map' in families(record)
    assert 'complex_quadratic_recurrence' not in families(record)


def test_live_angular_fold_and_image_displacement_are_separate():
    record = analyze(shader('shader_body {float a=abs(frac(ang/6.28*7+time*.05)*2-1);'
        'float2 p=.5+rad*.5*float2(cos(a),sin(a));'
        'p+=(GetPixel(p).xy-.37)*.02;ret=GetPixel(p);}'))
    assert {'angular_mirror_fold','image_driven_advection'} <= families(record)
    assert rows(record, 'angular_mirror_fold')[0]['parameters']['sector_count'] == 7


def test_zoom_only_has_no_tunnel_or_mirror_claim():
    record = analyze(read('zoom=1.03\nfWaveAlpha=0\nper_pixel_1=zoom=1.01+rad*.02;\n'))
    assert 'radial_feedback_transform' in families(record)
    assert not {'polar_radial_sampling','angular_mirror_fold'} & families(record)


def test_custom_radial_curve_and_procedural_points_respect_component_gates():
    body = ('fWaveAlpha=0\nwavecode_0_enabled=1\nwavecode_0_samples=32\n'
        'wavecode_0_bUseDots=0\nwavecode_0_a=1\n'
        'wave_0_per_point1=phase=sample*6.28-time;r=bass*.1+.2;'
        'x=.5+r*cos(phase);y=.5+r*sin(phase);\n'
        'wavecode_1_enabled=1\nwavecode_1_samples=64\nwavecode_1_bUseDots=1\n'
        'wavecode_1_a=1\nwave_1_per_point1=x=sample+sin(time)*.1;y=sample;\n')
    record = analyze(read(body))
    assert {'parametric_radial_curve','point_cloud_primitive','procedural_point_motion'} <= families(record)
    assert 'sample' in rows(record, 'parametric_radial_curve')[0]['input_dependencies']
    for mutation in [body.replace('_enabled=1','_enabled=0'),
                     body.replace('_a=1','_a=0'),
                     body.replace('_samples=32','_samples=1').replace('_samples=64','_samples=1')]:
        assert not {'parametric_radial_curve','point_cloud_primitive'} & families(analyze(read(mutation)))


def test_final_point_alpha_and_hidden_shape_suppress_primitives():
    source = read('fWaveAlpha=0\nwavecode_0_enabled=1\nwavecode_0_samples=64\n'
        'wavecode_0_bUseDots=1\nwavecode_0_a=1\nwave_0_per_point1=x=sample;y=sample;a=0;\n'
        'shapecode_0_enabled=1\nshapecode_0_a=0\nshapecode_0_a2=0\nshapecode_0_border_a=0\n')
    assert not {'point_cloud_primitive','polygon_shape_primitive'} & families(analyze(source))


def test_native_spatial_rotation_and_angular_modulation_trace_eel_temporaries():
    source = read('fWaveAlpha=.5\nnWaveMode=0\nper_pixel_1=v=rad*11;'
                  'r=.16*sin(time*-3.3+v)*(1.3-rad);rot=rot+r;'
                  'zoom=zoom+.04*sin(time*1.2+ang*6.28*3);\n')
    assert {'radial_twist','angular_periodic_warp','circular_wave_primitive'} <= families(analyze(source))
    source = read('fWaveAlpha=0\nper_pixel_1=v=sin(rad);rot=rot+v;rot=0;zoom=1;\n')
    assert 'radial_twist' not in families(analyze(source))


WITNESSES = [
    ('cope - mandelbrot (32 iterations) - mrt mangler.milk',
     '7ccf489af88159857a7a3a862b2f429b7e6140131f300922c8b935ff4fdc7efc',
     {'complex_quadratic_recurrence','polar_radial_sampling'}),
    ('Geiss - Confetti (Kaleidoscope Mix).milk',
     '319d04bf16ff3d00bd06840d32256f5652163031575646001df0b2fea24d8392',
     {'angular_mirror_fold','image_driven_advection'}),
    ('Geiss - Mega Swirl 3.milk',
     '7333edeb0985f99ac8555e446828fab2443d0a5d8b6a3a70238454d911b17617',
     {'radial_twist','circular_wave_primitive'}),
    ('martin - mandelbox explorer v1 nz+.milk',
     'db14c689cde46b655a86bfb568dfc82758547e9ad56caa8037fd2b4ba90c00e8',
     {'mandelbox_recurrence'}),
    ('flexi - a julia fractal for hexcollie.milk',
     '80c573e6a7b19baf7127292bf1ee3f53ae61c3ccbfd78dc66139db5fec022a66',
     {'nonlinear_feedback_map'}),
    ('Flexi - fractal descent gnesse.milk',
     '3ec8fe71ad9e9434ff6ab69747edc60ae2789cdab886197095c50f153b0b1aa8',
     {'nonlinear_feedback_map','multi_copy_feedback_recursion','cartesian_mirror_fold'}),
    ('EoS - particle storm.milk',
     '28e6f9fd6d6bb60c6ac077b9e18a308f9494252d5e2a495dfebf41d9eb2c766d',
     {'point_cloud_primitive','procedural_point_motion'}),
    ('Shifter-yak(yetanotherkaleidoscope)00.milk',
     '1970c734a0923def72c7b4e7cfce0588ecfe6ad1a3345928d8b9f8e5e13fab00',
     {'parametric_radial_curve','angular_periodic_warp'}),
]


@pytest.mark.parametrize('name,digest,expected', WITNESSES)
def test_exact_pack_witness(name,digest,expected):
    raw = (PRESETS / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    record = analyze(read(raw))
    assert expected <= families(record), (families(record),record['unknowns'])
    if name.startswith('cope '):
        assert rows(record,'complex_quadratic_recurrence')[0]['parameters']['subtype'] == 'julia_style'
    if name.startswith('Shifter-'):
        assert 'angular_mirror_fold' not in families(record)
    if name.startswith('flexi - a '):
        assert 'point_cloud_primitive' not in families(record)


def test_exact_overwritten_tunnel_witness_still_reports_mandelbox():
    raw = (PRESETS / 'martin - mandelbox stepper.milk').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'f4ac404bd9e548c503a8c4938ff161e68dd598e1095bfa2260008495c3b1a0a7'
    record = analyze(read(raw))
    assert 'mandelbox_recurrence' in families(record)
    assert 'polar_radial_sampling' not in families(record)


def test_unknown_and_inactive_shader_stages_do_not_fabricate_absence_or_output():
    source = shader('shader_body {ret=GetPixel(float2(ang,1/rad));}')
    source['sections']['comp_']['status'] = 'unknown'
    record = analyze(source)
    assert record['unknowns']
    assert 'polar_radial_sampling' not in families(record)
    source = shader('shader_body {ret=GetPixel(float2(ang,1/rad));}')
    source['values']['psversion_comp'] = '0'
    assert 'polar_radial_sampling' not in families(analyze(source))


def test_clean_api_errors():
    with pytest.raises(ValueError, match='profile'):
        analyze(read(''), profile='fake')
    with pytest.raises(ValueError, match='parsed source'):
        analyze('tunnel')


def test_constant_final_composite_discards_prior_warp_and_drawing_families():
    source = read('PSVERSION_WARP=2\nPSVERSION_COMP=2\nfWaveAlpha=1\n'
        'warp_1=`shader_body {float2 p=uv-.5;ret=GetPixel(float2(p.x*p.x-p.y*p.y,2*p.x*p.y));}\n'
        'comp_1=`shader_body {ret=0;}\n')
    assert not families(analyze(source))


def test_unused_loop_body_mechanism_is_control_uncertainty_not_live_family():
    record = analyze(shader('shader_body {float2 z=uv;for(int n=0;n<8;n++)'
        '{z=float2(z.x*z.x-z.y*z.y,2*z.x*z.y);}ret=1;}'))
    assert 'complex_quadratic_recurrence' not in families(record)
    assert record['unknowns']


def test_uv_orig_only_custom_warp_discards_native_spatial_twist():
    source = read('PSVERSION_WARP=2\nfWaveAlpha=0\n'
        'per_pixel_1=rot=sin(rad*4);\nwarp_1=`shader_body {ret=GetPixel(uv_orig);}\n')
    assert 'radial_twist' not in families(analyze(source))


def test_abs_of_image_color_is_not_cartesian_domain_reflection():
    record = analyze(shader('shader_body {float2 offset=abs(GetPixel(uv).xy);'
                            'ret=GetPixel(uv+offset*.01);}'))
    assert 'image_driven_advection' in families(record)
    assert 'cartesian_mirror_fold' not in families(record)


def test_wrong_state_box_fold_and_unrelated_norm_cannot_be_mandelbox():
    record = analyze(shader('shader_body {float2 z=uv;for(int n=0;n<8;n++){'
        'float2 reflected=2*clamp(z,-1,1)-z;float d=dot(uv,uv);'
        'z=2.6*reflected*clamp(1/d,0,1)+uv;}ret=length(z);}'))
    assert 'mandelbox_recurrence' not in families(record)
    assert 'iterated_spatial_fold' in families(record)


def test_valid_box_fold_without_affine_expansion_is_only_iterated_fold():
    record = analyze(shader('shader_body {float2 z=uv;for(int n=0;n<8;n++){'
        'z=2*clamp(z,-1,1)-z;float d=dot(z,z);z*=clamp(1/d,0,1);}'
        'ret=length(z);}'))
    assert 'mandelbox_recurrence' not in families(record)
    assert 'iterated_spatial_fold' in families(record)


def test_radial_band_and_log_projection_are_source_mechanisms():
    record = analyze(shader('shader_body {float r=length(uv-.5);'
        'float band=1-smoothstep(.01,.02,abs(r-.25));'
        'ret=GetPixel(float2(ang,log(rad)))*band;}'))
    assert {'radial_band','polar_radial_sampling'} <= families(record)
    assert rows(record,'polar_radial_sampling')[0]['parameters']['radial_mapping'] == 'log_radius'


def test_explicit_centered_rotation_distinguishes_global_rotation_from_swirl():
    base = 'shader_body {float2 p=uv-.5;float a=ANGLE;'
    end = 'float2 v=float2(p.x*cos(a)-p.y*sin(a),p.x*sin(a)+p.y*cos(a));ret=GetPixel(v+.5);}'
    global_record = analyze(shader(base.replace('ANGLE','time')+end))
    swirl_record = analyze(shader(base.replace('ANGLE','length(p)*3+time')+end))
    assert 'global_rotation' in families(global_record)
    assert 'radial_twist' not in families(global_record)
    assert 'radial_twist' in families(swirl_record)


def test_noise_advection_and_central_gradient_are_distinct():
    noise = analyze(shader('shader_body {float2 v=tex2D(sampler_noise_hq,uv+time*.01).xy-.5;'
                            'ret=GetPixel(uv+v*.01);}'))
    assert 'noise_driven_advection' in families(noise)
    gradient = analyze(shader('shader_body {float e=.001;'
        'float x=GetPixel(uv+float2(e,0)).x-GetPixel(uv-float2(e,0)).x;'
        'float y=GetPixel(uv+float2(0,e)).x-GetPixel(uv-float2(0,e)).x;'
        'ret=GetPixel(uv+float2(x,y)*.01);}'))
    assert 'gradient_driven_advection' in families(gradient)


def test_nonradial_single_axis_trig_is_not_a_radial_curve():
    record = analyze(read('fWaveAlpha=0\nwavecode_0_enabled=1\nwavecode_0_a=1\n'
        'wave_0_per_point1=p=sample*6.28;x=cos(p)+sin(p);y=.5;\n'))
    assert 'parametric_radial_curve' not in families(record)


def test_dynamic_dots_are_conditional_instead_of_default_false():
    record = analyze(read('fWaveAlpha=0\nwavecode_0_enabled=1\nwavecode_0_a=1\n'
        'wave_0_per_frame1=usedots=above(bass,1);\nwave_0_per_point1=x=sample;y=sample;\n'))
    assert {'point_cloud_primitive','custom_wave_primitive'} <= families(record)
    assert 'custom point mode is selected' in rows(record,'point_cloud_primitive')[0]['conditions']


def test_escape_count_output_keeps_recurrence_that_drives_loop_condition():
    record = analyze(shader('shader_body {float2 z=uv-.5;int count=0;'
        'while(count<8&&dot(z,z)<4){z=float2(z.x*z.x-z.y*z.y,2*z.x*z.y)+float2(.2,.3);count++;}'
        'ret=count*.125;}'))
    assert 'complex_quadratic_recurrence' in families(record)


def test_zero_iteration_loop_has_no_recurrence_contribution():
    record = analyze(shader('shader_body {float2 z=uv;for(int n=0;n<0;n++)'
        '{z=float2(z.x*z.x-z.y*z.y,2*z.x*z.y);}ret=length(z);}'))
    assert 'complex_quadratic_recurrence' not in families(record)


def test_box_fold_sphere_with_translation_but_no_expansion_is_not_mandelbox():
    record = analyze(shader('shader_body {float2 z=uv;for(int n=0;n<8;n++){'
        'z=2*clamp(z,-1,1)-z;float d=dot(z,z);z=z*clamp(1/d,0,1)+uv;}'
        'ret=length(z);}'))
    assert 'mandelbox_recurrence' not in families(record)
    assert 'iterated_spatial_fold' in families(record)


def test_dynamic_shape_zero_instances_and_unknown_radius_have_honest_gates():
    zero = analyze(read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_num_inst=0\n'))
    assert 'polygon_shape_primitive' not in families(zero)
    # megabuf starts zeroed and no block writes it: the radius is exactly 0, so nothing is drawn.
    unwritten = analyze(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=rad=megabuf(0);\n'))
    assert not rows(unwritten,'polygon_shape_primitive')
    # Frame code writes it: the radius is a memory read of frame-written content, a drawn shape.
    written = analyze(read('fWaveAlpha=0\nshapecode_0_enabled=1\nper_frame_1=megabuf(0)=.2;\n'
        'shape_0_per_frame1=rad=megabuf(0);\n'))
    assert rows(written,'polygon_shape_primitive')


def test_prepared_compatibility_rejection_suppresses_custom_program():
    source = shader('shader_body {ret=GetPixel(float2(ang,1/rad));}')
    section = source['sections']['comp_']
    code = section['source']
    compatibility = {'composite': {'source_sha256':hashlib.sha256(code.encode()).hexdigest(),
        'request':{'code':code,'stage':'composite','profile':'gles300'},
        'translation':{'engine_archive_sha256':source['parser_inputs']['engine_archive_sha256']},
        'offline_accepted':False}}
    assert 'polar_radial_sampling' not in families(analyze(source,compatibility=compatibility))
    compatibility['composite']['offline_accepted'] = True
    assert 'polar_radial_sampling' in families(analyze(source,compatibility=compatibility))


def test_temp_and_helper_renaming_preserve_mathematical_classification():
    original = 'float2 mapper(float2 p){float2 q=float2(p.x*p.x-p.y*p.y,2*p.x*p.y);return q;}'
    body = 'shader_body {ret=GetPixel(mapper(uv-.5));}'
    renamed = original.replace('mapper','function123').replace(' p',' local17').replace('p.','local17.').replace(' q',' stored19').replace('return q','return stored19')
    result = analyze(shader(original+body,'warp'))
    other = analyze(shader(renamed+body.replace('mapper','function123'),'warp'))
    assert 'nonlinear_feedback_map' in families(result)
    assert families(result) == families(other)


def test_repeated_analysis_is_stable_and_does_not_mutate_the_input():
    source = shader('shader_body {ret=GetPixel(float2(ang,1/rad));}')
    before = json.dumps(source, sort_keys=True)
    first = analyze(source)
    second = analyze(source)
    assert first == second
    assert json.dumps(source, sort_keys=True) == before


def test_changing_loop_carried_parameter_abstains_from_julia_mandelbrot_subtype():
    record = analyze(shader('shader_body {float2 z=uv;float2 c=0;for(int n=0;n<8;n++){'
        'z=float2(z.x*z.x-z.y*z.y,2*z.x*z.y)+c;c+=uv*.01;}ret=length(z);}'))
    row = rows(record,'complex_quadratic_recurrence')[0]
    assert row['parameters']['subtype'] == 'unclassified'


def test_centered_disk_without_ring_distance_is_not_a_radial_band():
    record = analyze(shader('shader_body {ret=1-smoothstep(.01,.02,abs(length(uv-.5)));}'))
    assert 'radial_band' not in families(record)


def test_temporal_box_fold_sample_is_nonlinear_feedback_without_escape_loop():
    record = analyze(shader('shader_body {float2 z=uv-.5;z=2*clamp(z,-1,1)-z;'
                            'ret=GetPixel(z+.5);}', 'warp'))
    assert 'nonlinear_feedback_map' in families(record)
    assert not {'mandelbox_recurrence','complex_quadratic_recurrence'} & families(record)


def test_section_evidence_excludes_numbering_gaps_and_duplicate_records():
    source = read('PSVERSION_COMP=2\ncomp_1=`shader_body {ret=GetPixel(float2(ang,1/rad));}\n'
                  'comp_1=`// duplicate\ncomp_3=`// unconsumed gap\n')
    row = rows(analyze(source),'polar_radial_sampling')[0]
    assert row['evidence'][0]['source_keys'] == ['comp_1']
    assert len(row['evidence'][0]['source_locations']) == 1


@pytest.mark.parametrize('unused', ['float2(ang,1/rad)', 'GetPixel(float2(ang,1/rad)).xy'])
def test_unused_loop_carried_slots_do_not_leak_into_live_sample_coordinates(unused):
    record = analyze(shader('shader_body {float2 unused='+unused+';float2 z=uv;'
        'for(int n=0;n<8;n++){z+=.1;unused+=.1;}ret=GetPixel(z);}'))
    assert 'polar_radial_sampling' not in families(record)
    assert 'image_driven_advection' not in families(record)


def test_temporal_abs_and_wrapping_do_not_fold_an_angular_coordinate():
    record = analyze(shader('shader_body {float a=ang+abs(time)+frac(time);'
                            'ret=GetPixel(float2(cos(a),sin(a)));}'))
    assert 'angular_mirror_fold' not in families(record)


def test_both_trig_terms_on_one_sampling_axis_do_not_prove_twist():
    record = analyze(shader('shader_body {float a=rad;ret=GetPixel(float2(cos(a)+sin(a),uv.y));}'))
    assert 'radial_twist' not in families(record)


def test_cancelling_affine_offsets_do_not_prove_feedback_scale():
    record = analyze(shader('shader_body {ret=GetPixel(uv+uv*2-uv*2);}', 'warp'))
    assert 'radial_feedback_transform' not in families(record)


def test_consuming_only_real_complex_lane_does_not_prove_complex_map():
    record = analyze(shader('shader_body {float2 p=uv-.5;'
        'float2 z=float2(p.x*p.x-p.y*p.y,2*p.x*p.y);ret=GetPixel(float2(z.x,uv.y));}', 'warp'))
    assert 'nonlinear_feedback_map' not in families(record)
    assert 'radial_feedback_transform' not in families(record)


def test_dynamic_outer_sample_mask_is_carried_in_causal_evidence():
    record = analyze(shader('shader_body {ret=GetPixel(float2(ang,1/rad))*time;}'))
    row = rows(record,'polar_radial_sampling')[0]
    assert '_c2' in row['input_dependencies']
    assert 'runtime output multiplier/mask retains this construction' in row['conditions']


def test_one_loop_vector_lane_cannot_leak_dead_coordinate_texture():
    record = analyze(shader('shader_body {float2 z=float2(uv.x,GetPixel(float2(ang,1/rad)).x);'
        'for(int n=0;n<8;n++){z+=.1;}ret=GetPixel(float2(z.x,uv.y));}'))
    assert 'polar_radial_sampling' not in families(record)
    assert 'image_driven_advection' not in families(record)


@pytest.mark.parametrize('repetitions',[14,22])
def test_shared_linear_dag_uses_bounded_normalization_work(repetitions):
    record = analyze(shader('shader_body {float2 p=uv;'+'p=p+p;'*repetitions+'ret=GetPixel(p);}', 'warp'))
    assert rows(record,'radial_feedback_transform')[0]['parameters']['sampling_scale'] == 2**repetitions
    assert record['analysis_work']['field_visits'] < 30000
    assert record['analysis_work']['normalized_term_nodes'] < 1000
    assert record['analysis_work']['budget_exhausted'] is False


def test_work_budget_returns_explicit_unknown_and_no_partly_proven_stage(monkeypatch):
    import effect_families
    monkeypatch.setattr(effect_families,'MAX_FIELD_VISITS',10)
    record = analyze(shader('shader_body {float2 p=uv;'+'p=p+p;'*14+'ret=GetPixel(p);}', 'warp'))
    assert record['analysis_work']['budget_exhausted'] is True
    assert any('budget' in row['reason'] for row in record['unknowns'])
    assert not any(row['stage']=='warp' for row in record['families'])


def test_semantic_analysis_releases_per_call_graph_cache():
    import effect_families
    analyze(shader('shader_body {ret=GetPixel(uv);}'))
    assert effect_families._CACHE.get() is None


def test_conditional_tunnel_output_preserves_branch_dependencies():
    record = analyze(shader('shader_body {ret=time>1?GetPixel(float2(ang,1/rad)):0;}'))
    row = rows(record,'polar_radial_sampling')[0]
    assert '_c2' in row['input_dependencies']
    assert 'runtime branch/mask selects this construction' in row['conditions']


def test_polar_reconstruction_and_rotation_alone_are_not_vector_advection():
    polar = analyze(shader('shader_body {float a=ang+time;'
        'ret=GetPixel(.5+rad*float2(cos(a),sin(a)));}'))
    assert 'uv_advection' not in families(polar)
    flow = analyze(shader('shader_body {ret=GetPixel(uv+float2(sin(uv.y*4+time),cos(uv.x*4+time))*.01);}'))
    assert 'uv_advection' in families(flow)


def test_independent_threaded_calls_keep_cache_and_records_isolated():
    from concurrent.futures import ThreadPoolExecutor
    source = shader('shader_body {ret=GetPixel(float2(ang,1/rad));}')
    expected = analyze(source)
    with ThreadPoolExecutor(max_workers=2) as executor:
        records = list(executor.map(lambda _: analyze(source), range(4)))
    assert all(record == expected for record in records)


def test_dead_loop_vector_fold_lane_does_not_supply_recurrence_family():
    record = analyze(shader('shader_body {float2 z=uv;for(int n=0;n<8;n++){'
        'z=float2(z.x+.1,2*clamp(z.y,-1,1)-z.y);}ret=z.x;}'))
    assert 'iterated_spatial_fold' not in families(record)
    assert 'mandelbox_recurrence' not in families(record)


def test_zero_iteration_loop_projects_its_initial_state_before_tracing():
    record = analyze(shader('shader_body {float2 z=float2(uv.x,GetPixel(float2(ang,1/rad)).x);'
        'for(int n=0;n<0;n++){z+=.1;}ret=z.x;}'))
    assert 'polar_radial_sampling' not in families(record)


def test_live_scalar_fold_lane_keeps_narrow_iterated_fold_evidence():
    record = analyze(shader('shader_body {float2 z=uv;for(int n=0;n<8;n++){'
        'z=float2(z.x+.1,2*clamp(z.y,-1,1)-z.y);}ret=z.y;}'))
    assert 'iterated_spatial_fold' in families(record)


def test_single_returned_quadratic_lane_keeps_cross_lane_recurrence_dependencies():
    record = analyze(shader('shader_body {float2 z=uv;for(int n=0;n<8;n++){'
        'z=float2(z.x*z.x-z.y*z.y,2*z.x*z.y)+float2(.2,.3);}ret=z.x;}'))
    assert 'complex_quadratic_recurrence' in families(record)


@pytest.mark.parametrize('body,forbidden', [
    ('float a=(ang-ang)+uv.x;ret=GetPixel(float2(a,1/rad));', 'polar_radial_sampling'),
    ('float2 p=uv-.5;float2 z=float2(p.x*p.x-p.y*p.y,2*p.x*p.y);ret=GetPixel(uv+(z-z));',
     'nonlinear_feedback_map'),
])
def test_cancelled_mechanisms_are_withheld_with_explicit_finite_domain_uncertainty(body,forbidden):
    record = analyze(shader('shader_body {'+body+'}', 'warp'))
    assert forbidden not in families(record)
    assert any('finite' in row['reason'] for row in record['unknowns'])


def test_warp_difference_of_blurs_is_band_pass_feedback():
    # ret.x = main - (blur3 - blur1): a finer level added and a coarser one subtracted on the fed-back
    # image sharpens features between the two blur scales and grows patterns (Flexi's splatter).
    record = analyze(shader('shader_body {ret=0; ret.x=GetPixel(uv).x-(GetBlur3(uv).x-GetBlur1(uv).x);}', 'warp'))
    row, = rows(record, 'blur_difference_feedback')
    assert row['stage'] == 'warp'
    assert row['parameters']['lanes'] == [0]
    assert row['parameters']['fine_levels'] == [0, 1] and row['parameters']['coarse_levels'] == [3]
    assert abs(row['parameters']['flat_gain_by_lane'][0] - 1.) < 1e-9


def test_unsharp_mask_counts_and_softening_or_plain_blur_does_not():
    unsharp = analyze(shader('shader_body {ret=GetPixel(uv)+(GetPixel(uv)-GetBlur1(uv))*0.3;}', 'warp'))
    assert rows(unsharp, 'blur_difference_feedback')[0]['parameters']['lanes'] == [0, 1, 2]
    soften = analyze(shader('shader_body {ret=GetPixel(uv)*0.5+GetBlur2(uv)*0.5;}', 'warp'))
    plain = analyze(shader('shader_body {ret=GetBlur1(uv);}', 'warp'))
    composite = analyze(shader('shader_body {ret=GetPixel(uv)-(GetBlur3(uv)-GetBlur1(uv));}', 'comp'))
    assert not rows(soften, 'blur_difference_feedback') and not rows(plain, 'blur_difference_feedback')
    assert not rows(composite, 'blur_difference_feedback')  # no feedback: the composite is display only


def test_frac_of_sample_coordinates_is_repeat_tiling_and_parity_flip_mirrors_it():
    mirrored = analyze(shader('shader_body {uv=3*uv; float2 m=floor(frac(uv*0.5)*2); uv=frac(uv)*(1-m)+m*frac(1-uv);'
                              'ret=GetPixel(uv);}', 'comp'))
    row, = rows(mirrored, 'repeat_tiling')
    assert row['parameters']['mirrored'] is True and row['stage'] == 'composite'
    plain = analyze(shader('shader_body {ret=GetPixel(frac(uv*4));}', 'comp'))
    assert rows(plain, 'repeat_tiling')[0]['parameters']['mirrored'] is False
    assert not rows(analyze(shader('shader_body {ret=GetPixel(uv*0.5+0.25);}', 'comp')), 'repeat_tiling')


def test_symmetric_offset_samples_of_the_previous_image_are_a_neighbourhood_blur():
    taps = '+'.join('GetPixel(uv+float2(%s,%s))' % pair for pair in
                    (('.01*b', '0'), ('-.01*b', '0'), ('0', '.01*b'), ('0', '-.01*b')))
    varying = analyze(shader('shader_body {float b=sin(bass*90)*rad; ret=0.25*(%s);}' % taps, 'warp'))
    row, = rows(varying, 'neighbourhood_blur')
    assert row['parameters']['taps'] == 4 and row['parameters']['radius_spatial'] is True
    assert row['parameters']['radius_audio'] is True and row['stage'] == 'warp'
    # Offsets that cancel in pairs displace nothing on average: no ripple claim from the taps.
    assert not rows(varying, 'uv_advection')
    wobble = analyze(shader('shader_body {ret=GetPixel(uv+float2(.01*sin(uv.y*20),0));}', 'warp'))
    assert rows(wobble, 'uv_advection') and not rows(wobble, 'neighbourhood_blur')
    fixed = analyze(shader('shader_body {ret=0.25*(GetPixel(uv+float2(.003,0))+GetPixel(uv-float2(.003,0))'
                           '+GetPixel(uv+float2(0,.003))+GetPixel(uv-float2(0,.003)));}', 'warp'))
    assert rows(fixed, 'neighbourhood_blur')[0]['parameters'] == {'taps': 4, 'radius_spatial': False, 'radius_audio': False,
                                                                 'radius_time': False, 'offsets': [.003]}
    # One shifted copy is drift and two scaled copies are recursion, not a blur.
    assert not rows(analyze(shader('shader_body {ret=GetPixel(uv+float2(.01,0));}', 'warp')), 'neighbourhood_blur')
    assert not rows(analyze(shader('shader_body {ret=.5*(GetPixel(uv*.5+.25)+GetPixel(uv*.7+.15));}', 'warp')), 'neighbourhood_blur')


def test_central_differences_of_the_image_in_the_composite_are_gradient_relief():
    relief = analyze(shader('shader_body {float2 d=texsize.zw; float gx=GetPixel(uv+float2(d.x,0))*1+GetBlur1(uv+float2(d.x,0))*.4'
                            '-GetPixel(uv-float2(d.x,0))*1-GetBlur1(uv-float2(d.x,0))*.4;'
                            'float gy=GetPixel(uv+float2(0,d.y))-GetPixel(uv-float2(0,d.y));'
                            'ret=0.5+0.5*normalize(float3(gx,gy,0.14));}', 'comp'))
    row, = rows(relief, 'gradient_relief')
    assert row['parameters'] == {'directions': 2} and row['stage'] == 'composite'
    one_axis = analyze(shader('shader_body {ret=GetPixel(uv)+(GetPixel(uv+float2(.002,0))-GetPixel(uv-float2(.002,0)));}', 'comp'))
    assert rows(one_axis, 'gradient_relief')[0]['parameters'] == {'directions': 1}
    # A sum of opposite taps is a blur and a difference of unrelated points is not a gradient.
    assert not rows(analyze(shader('shader_body {ret=GetPixel(uv+float2(.002,0))+GetPixel(uv-float2(.002,0));}', 'comp')), 'gradient_relief')
    assert not rows(analyze(shader('shader_body {ret=GetPixel(uv)-GetPixel(uv*.5);}', 'comp')), 'gradient_relief')
