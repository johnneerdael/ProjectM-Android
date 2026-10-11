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
    assert zoom['value_range']==[pytest.approx(.93),pytest.approx(.98)]
    assert zoom['content_motion']=='contracts toward the zoom centre'
    assert set(zoom['audio_inputs'])=={'bass','bass_att'}
    band=[row for row in pattern(value,'compression_toward_fixed_line','dy') if row['region'].get('y')==[.35,.65]][0]
    assert band['feature_scale_per_step']==pytest.approx(.5)
    assert band['fixed_point']==pytest.approx(.501)
    assert band['screen_fraction']==pytest.approx(.3/.5625)
    assert band['thin_line_peak_gain_per_step']==pytest.approx(.5)
    assert zoom['thin_line_peak_gain_per_step_range']==[pytest.approx(.93),pytest.approx(.98)]
    wave=pattern(value,'planar_travelling_wave','dy')[0]
    osc=wave['oscillator']
    assert osc['planar_wavelength_units']==pytest.approx(2*math.pi/30)
    assert osc['travel_direction_xy']==[-1.0,0.0]
    assert osc['phase_speed_units_per_second']==pytest.approx(-4/30)
    assert osc['phase_speed_pixels_per_second']==pytest.approx(-4/30*480)
    assert wave['amplitude_dependencies']==['bass','bass_att']
    assert value['visible_motion_speed'] is None


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
    assert dx['translation_pixels_per_step']==pytest.approx(4.8)
    assert dx['translation_pixels_per_second']==pytest.approx(144)
    dy=pattern(value,'uniform_translation','dy')[0]
    assert dy['translation_pixels_per_step']==pytest.approx(-.96)


def test_radial_ring_wave_and_angular_lobes():
    value=field(synthetic('rot=.02*sin(rad*20-time*3);zoom=1+.01*cos(ang*6+time);'))
    ring=pattern(value,'radial_ring_wave','rot')[0]['oscillator']
    assert ring['radial_wavelength_rad_units']==pytest.approx(2*math.pi/20)
    assert ring['radial_phase_speed_pixels_per_second']==pytest.approx(3/20*240)
    lobes=pattern(value,'angular_lobes','zoom')[0]['oscillator']
    assert lobes['angular_lobes']==6
    assert lobes['angular_lobes_integer'] is True
    assert lobes['angular_rotation_radians_per_second']==pytest.approx(-1/6)


def test_expansion_and_mirror_from_same_axis_coefficients():
    value=field(synthetic('dx=.1*(x-.5);dy=3*(y-.5);'))
    dx=pattern(value,'expansion_from_fixed_line','dx')[0]
    assert dx['feature_scale_per_step']==pytest.approx(1/.9)
    assert dx['thin_line_peak_gain_per_step']==1.0
    dy=pattern(value,'compression_toward_fixed_line_with_mirror','dy')[0]
    assert dy['feature_scale_per_step']==pytest.approx(-.5)
    assert dy['fixed_point']==pytest.approx(.5)


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
