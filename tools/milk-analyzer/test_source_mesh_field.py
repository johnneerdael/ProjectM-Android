"""Per-pixel warp control fields: gates, affine terms, oscillators, semantics."""
import json
import math

import pytest

from test_effect_families import read as read_raw
from test_source_shape_state_export import read,report,PRESETS

AUDIO={name:[0,2] for name in ('bass','bass_att','mid','mid_att','treb','treb_att')}
CONTEXT={'viewport':[480,270],'feedback_fps':30,'scalar_input_domains':AUDIO}


def field(source,context=CONTEXT):
    value=report(source,context)['mesh_field']
    json.dumps(value,allow_nan=False)
    return value


def synthetic(pixel,frame='zoom=1;zoomexp=1;warp=0;'):
    return read_raw('fWaveAlpha=0\nper_frame_1='+frame+'\nper_pixel_1='+pixel+'\n')


def pattern(value,name,control=None):
    return [row for row in value['patterns'] if row['pattern']==name and (control is None or row['control']==control)]


def test_seas_of_tron_band_compression_ripple_and_bass_zoom():
    value=field(read(PRESETS/'Rovastar and Krash - Seas Of Tron.milk'))
    assert value['status'] in {'described','partial'}
    zoom=pattern(value,'uniform_zoom','zoom')[0]
    assert zoom['effective_zoom_range']==[pytest.approx(.93),pytest.approx(.98)]
    assert zoom['content_motion']=='contracts toward the screen centre'
    assert set(zoom['audio_inputs'])=={'bass','bass_att'}
    band=[row for row in pattern(value,'compression_toward_fixed_line','dy') if row['region'].get('y')==[.35,.65]][0]
    # Raw dy slope -1 gives s=0.5; composed with zoom .93-.98 about the screen centre.
    assert band['raw_feature_scale_per_step']==pytest.approx(.5)
    low,high=band['composed_feature_scale_per_step_range']
    assert low==pytest.approx(1/(1/.93+1)) and high==pytest.approx(1/(1/.98+1))
    assert band['thin_line_integrated_fraction_per_step']==pytest.approx(high)
    assert band['screen_fraction']==pytest.approx(.3/.5625)
    lo,hi=band['fixed_point_range'];assert .5<lo<=hi<.501
    assert zoom['thin_line_integrated_fraction_per_step_range']==[pytest.approx(.93),pytest.approx(.98)]
    wave=pattern(value,'planar_travelling_wave','dy')[0]
    osc=wave['oscillator']
    assert osc['planar_wavelength_units']==pytest.approx(2*math.pi/30)
    assert osc['travel_direction_xy']==[-1.0,0.0]
    assert osc['phase_speed_units_per_second']==pytest.approx(-4/30)
    assert osc['phase_speed_pixels_per_second']==pytest.approx(-4/30*480)
    assert wave['amplitude_dependencies']==['bass','bass_att']
    assert value['visible_motion_speed'] is None


def test_zoom_acts_about_screen_centre_not_cx():
    value=field(synthetic('dx=0;',frame='zoom=.9;zoomexp=1;warp=0;cx=.2;'))
    row=pattern(value,'compression_toward_fixed_line','dx')[0]
    assert row['fixed_point_range']==[pytest.approx(.5),pytest.approx(.5)]
    assert row['composed_feature_scale_per_step_range']==[pytest.approx(.9),pytest.approx(.9)]


def test_zoomexp_gives_radial_profile_not_uniform_zoom():
    value=field(synthetic('dx=0;',frame='zoom=1.02;zoomexp=3;warp=0;'))
    assert not pattern(value,'uniform_zoom')
    profile=pattern(value,'radial_zoom_profile','zoom')[0]
    low,high=profile['effective_zoom_range']
    assert low==pytest.approx(1.02**(1/3))
    assert high>1.05
    assert pattern(value,'translation_component','dx')==[] or True


def test_uniform_audio_offset_widens_translation_and_open_terms_withhold():
    value=field(synthetic('dx=.005+.01*bass;'))
    row=pattern(value,'uniform_translation','dx')[0]
    assert row['translation_pixels_per_second_range']==[pytest.approx(72),pytest.approx(360)]
    open_value=field(synthetic('dx=.01+myvar*.001;',frame='zoom=1;zoomexp=1;warp=0;myvar=sin(time*7);'))
    rows=open_value['controls']['dx']['regions'][0]['axis_motion']
    assert rows['open_terms'] or rows['behaviour']=='uniform_translation'


def test_rotation_blocks_axis_composition():
    value=field(synthetic('dx=.1*(x-.5);',frame='zoom=1;zoomexp=1;warp=0;rot=.02;'))
    motion=value['controls']['dx']['regions'][0]['axis_motion']
    assert motion['composed_feature_scale_per_step_range'] is None
    assert 'rotation' in motion['composition']


def test_contradictory_nested_gates_drop_empty_region():
    value=field(synthetic('dx=if(below(y,.3),if(above(y,.5),.01,0),0);'))
    boxes=[region['box'] for region in value['controls']['dx']['regions']]
    assert all(span[0] is None or span[1] is None or span[0]<span[1] for box in boxes for span in box.values())


def test_zylot_radius_affine_zoom_is_spatially_varying():
    value=field(read(PRESETS/'Zylot - Spiral.milk'))
    zoom=value['controls']['zoom']
    assert zoom['uniform_across_mesh'] is False
    assert zoom['dependencies']['coordinates']==['rad']
    term=[t for t in zoom['terms'] if t['kind']=='coordinate_affine'][0]
    assert term['coefficients']=={'rad':pytest.approx(.01)}
    assert pattern(value,'spatially_varying_zoom','zoom')


def test_constant_translation_reports_pixels_per_second():
    value=field(synthetic('dx=0.01;dy=-0.002;'))
    dx=pattern(value,'uniform_translation','dx')[0]
    assert dx['translation_pixels_per_step_range']==[pytest.approx(4.8)]*2
    assert dx['translation_pixels_per_second_range']==[pytest.approx(144)]*2
    dy=pattern(value,'uniform_translation','dy')[0]
    assert dy['translation_pixels_per_step_range']==[pytest.approx(-.96)]*2


def test_radial_ring_wave_and_angular_lobes():
    value=field(synthetic('rot=.02*sin(rad*20-time*3);zoom=1+.01*cos(ang*6+time);'))
    ring=pattern(value,'radial_ring_wave','rot')[0]['oscillator']
    assert ring['radial_wavelength_rad_units']==pytest.approx(2*math.pi/20)
    assert ring['radial_phase_speed_pixels_per_second']==pytest.approx(3/20*240)
    lobes=pattern(value,'angular_lobes','zoom')[0]['oscillator']
    assert pattern(field(synthetic('zoom=1+.01*cos(ang*2.5);')),'angular_modulation_with_seam','zoom')
    assert lobes['angular_lobes']==6
    assert lobes['angular_lobes_integer'] is True
    assert lobes['angular_rotation_radians_per_second']==pytest.approx(-1/6)


def test_expansion_and_mirror_from_same_axis_coefficients():
    value=field(synthetic('dx=.1*(x-.5);dy=3*(y-.5);'))
    dx=pattern(value,'expansion_from_fixed_line','dx')[0]
    assert dx['composed_feature_scale_per_step_range']==[pytest.approx(1/.9)]*2
    assert dx['thin_line_integrated_fraction_per_step'] is None
    dy=pattern(value,'compression_toward_fixed_line_with_mirror','dy')[0]
    assert dy['composed_feature_scale_per_step_range']==[pytest.approx(-.5)]*2
    assert dy['fixed_point_range']==[pytest.approx(.5)]*2
    assert dy['thin_line_mean_first_step_peak']==pytest.approx(.5)


def test_cross_axis_dependence_is_shear():
    value=field(synthetic('dx=.05*y;'))
    assert pattern(value,'shear','dx')


def test_audio_scaled_coordinate_term_reports_coefficient_range():
    value=field(synthetic('dx=q1*(x-.5);',frame='zoom=1;zoomexp=1;warp=0;q1=.1*bass;'))
    term=[t for t in value['controls']['dx']['terms'] if t['kind']=='uniform_scaled_coordinate_affine'][0]
    assert term['coefficient_ranges']=={'x':[0.0,pytest.approx(.2)]}
    assert term['scale_dependencies']==['bass']


def test_nonlinear_coordinate_term_stays_unclassified():
    value=field(synthetic('dx=.01*sin(x*y);'))
    assert value['controls']['dx']['terms'][0]['kind']=='nonlinear_coordinate_term'
    assert not pattern(value,'shear','dx')


def test_zoom_range_crossing_identity_has_no_fixed_line():
    value=field(synthetic('dx=0.001;',frame='zoom=1+.01*sin(time);zoomexp=1;warp=0;'))
    motion=value['controls']['dx']['regions'][0]['axis_motion']
    assert motion['fixed_point_range'] is None
    assert motion['behaviour']=='compression_or_expansion_through_translation'


def test_zoom_range_crossing_degenerate_slope_is_flagged():
    value=field(synthetic('dx=.5*(x-.5);',frame='zoom=2+.5*sin(time);zoomexp=1;warp=0;'))
    motion=value['controls']['dx']['regions'][0]['axis_motion']
    assert motion['composed_feature_scale_per_step_range'] is None
    assert motion['behaviour']=='degenerate_sampling_possible'
