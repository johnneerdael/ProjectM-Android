"""Built-in waveform colour/opacity source model, not displayed flashing."""
import math

import numpy as np

from source_native_warp import _f32
from source_motion import motion_control

THRESHOLD=_f32(.01)
REFERENCE_TABLE=[(256,.07,.075),(512,.09,.15),(1024,.11,.22),(2048,.13,.33),(None,.15,.44)]


def _clamp(v):return min(1.,max(0.,v))


def normalization_boundary_difference(enabled,risk,clipped,alpha):
    """Limiting nominal RGB seam at max(clamped RGB)=threshold."""
    from fractions import Fraction
    from source_sampling_motion import _finite_round
    raw=[None]*3;blended=[None]*3;reasons=[]
    if risk is False:reasons.append('no possible normalization threshold crossing in supplied envelopes')
    elif enabled is not True or clipped is None:reasons.append('normalization enable or clipped RGB domains unresolved')
    elif risk is True:
        threshold=Fraction(THRESHOLD);factor=1/threshold-1
        raw=[_finite_round(min(Fraction(span[1]),threshold)*factor,upper=True) for span in clipped]
        span=alpha['final_alpha_envelope']
        if span is None:reasons.append('final waveform alpha domain unresolved')
        else:blended=[_finite_round(Fraction(span[1])*Fraction(value),upper=True) for value in raw]
    return {'policy':'source-wave-normalization-boundary-difference-v1',
        'possible_source_boundary_crossing':risk,'normalization_threshold':THRESHOLD,
        'maximum_nominal_rgb_boundary_difference':raw,
        'maximum_fixed_alpha_blended_rgb_boundary_difference':blended,
        'nominal_crossing_event_rate_hz':None,'visible_flash_strength':None,
        'native_event_difference_verified':False,'unknown_reasons':reasons,
        'conditions':['Nominal limiting difference between unnormalized C and normalized C/max(C) at max(C)=threshold',
            'Clamped RGB domain and normalization-enabled policy hold; enclosing ranges do not prove a simultaneous reached boundary',
            'Alpha weighting compares the same fixed alpha, geometry, sample coverage and destination in both states',
            'Native float32 division/quantization, varying alpha, draw gating, waveform footprint, storage, feedback and later passes remain separate',
            'This is neither an adjacent-frame difference nor a visible flash/beat frequency or mood certificate']}


def _channel(field,name):
    curve=motion_control(field,name,'wave colour/alpha component',application='built-in waveform material')
    span=curve['nominal_value_range'];native=None
    if span is not None:
        try:native=[_f32(v) for v in span]
        except ValueError:pass
    from time_expression import time_only
    expression=curve.get('expression')
    return {'raw_time_curve':{k:v for k,v in curve.items() if k not in {'expression','phase_expression'}},
            'time_only_expression':expression if time_only(expression) else None,
            'native_float32_endpoint_domain':native,'consumed':True,
            'unknown_reasons':[] if native is not None else ['no finite source/native channel envelope']}


def wave_material(analysis,recipe):
    from source_appearance import _phase_literal,_expression
    from scene_equations import _scalar
    main=analysis.main;mode=recipe['effective_mode']
    channels={name:_channel(main[name],name) for name in ('wave_r','wave_g','wave_b','wave_a')}
    enabled_value=_phase_literal(main['wave_brighten']);enabled=None if enabled_value is None else enabled_value!=0
    ranges=[channels[name]['native_float32_endpoint_domain'] for name in ('wave_r','wave_g','wave_b')]
    clipped=None if any(span is None for span in ranges) else [[_clamp(v) for v in span] for span in ranges]
    maximum=None if clipped is None else [max(span[i] for span in clipped) for i in (0,1)]
    risk=None;rgb=None;constant=None
    if enabled is False:risk=False;rgb=clipped
    elif enabled is True and maximum is not None:
        if maximum[1]<=THRESHOLD:rgb=clipped;risk=False
        elif maximum[0]>THRESHOLD:
            rgb=[[max(0.,span[0]/maximum[1]),min(1.,span[1]/maximum[0])] for span in clipped];risk=False
        else:
            rgb=[[min(span[0],span[0]/maximum[1]),min(1.,span[1]/THRESHOLD)] for span in clipped];risk=True
    if clipped is not None and all(span[0]==span[1] for span in clipped) and enabled is not None:
        constant=[span[0] for span in clipped]
        if enabled and maximum[0]>THRESHOLD:
            constant=[float(np.float32(np.float32(v)/np.float32(maximum[0]))) for v in constant]
        rgb=[[v,v] for v in constant];risk=False
    if risk is True and all(channels[name]['raw_time_curve']['maximum_absolute_control_rate_per_second']==0 and
            channels[name]['raw_time_curve']['nominal_continuity']!='unknown' for name in ('wave_r','wave_g','wave_b')):risk=False
    replaced=mode==3
    channels['wave_a']['consumed']=not replaced if mode is not None else None
    mod=bool(_scalar(analysis.values,'bModWaveAlphaByVolume',0,'bool'))
    start=end=denominator=None;reasons=[]
    try:
        start=_scalar(analysis.values,'fModWaveAlphaStart',.75,'float');end=_scalar(analysis.values,'fModWaveAlphaEnd',.95,'float')
        denominator=_f32(end-start)
    except ValueError:
        if mod:reasons.append('volume ramp configuration/subtraction lacks a finite native domain')
    if mod and denominator==0:reasons.append('volume ramp denominator is zero in native float32')
    alpha={'authored_alpha_replaced':replaced if mode is not None else None,
        'mode_gain':None if mode in {2,3,5,None} else 1.25 if mode==1 else 1.,
        'reference_size_input':'MaximizeColorsTextureSize(viewport, authored line reference)',
        'reference_table':[{'maximum_size':size,'mode2_or5_gain':_f32(gain),'mode3_base_alpha':_f32(base)} for size,gain,base in REFERENCE_TABLE],
        'mode3_formula':'reference_base_alpha * float32(1.3) * pow(native_audioData.treb,2)',
        'audio_input':'native_audioData.treb' if mode==3 else None,
        'alpha_envelope_without_volume_modulation':None,'final_alpha_envelope':None,
        'volume_ramp':{'enabled':mod,'input':'native_audioData.vol','start':start,'end':end,
            'native_denominator':denominator,'ramp_clamped_before_multiplication':False,
            'formula':'(native_audioData.vol-start)/(end-start)',
            'domain_status':'unknown' if reasons else 'finite denominator' if mod else 'disabled'},
        'final_operation':'multiply mode-adjusted alpha by volume ramp if enabled; comparison-clamp0..1 afterwards',
        'unknown_reasons':reasons}
    raw=channels['wave_a']['native_float32_endpoint_domain']
    if mode is not None and mode!=3 and raw is not None:
        gains=[row[1] for row in REFERENCE_TABLE] if mode in {2,5} else [alpha['mode_gain']]
        with np.errstate(over='ignore',invalid='ignore'):
            candidates=[float(np.float32(np.float32(a)*np.float32(g))) for a in raw for g in gains]
        if all(math.isfinite(v) for v in candidates):
            span=[_clamp(min(candidates)),_clamp(max(candidates))]
            alpha['alpha_envelope_without_volume_modulation']=span
            if not mod:alpha['final_alpha_envelope']=span
        else:reasons.append('mode-adjusted alpha lacks a finite native endpoint domain')
    return {'policy':'source-native-builtin-wave-material-v1','channels':channels,
        'colour_conversion':'float32 clamp0..1 then optional maximum normalization',
        'normalization_enabled':enabled,'normalization_flag_expression':_expression(main['wave_brighten']),
        'normalization_gate':{'comparison':'max(clamped RGB)>threshold','threshold':THRESHOLD,'maximum_domain':maximum},
        'normalization_boundary_difference':normalization_boundary_difference(enabled,risk,clipped,alpha),
        'possible_normalization_gate_jump':risk,'rgb_component_envelopes':rgb,'constant_vertex_rgb':constant,
        'alpha_recipe':alpha,'native_draw_gate':{'comparison':'final_alpha < threshold skips draw','threshold':_f32(.004),
            'paths':['quad_lines','hardware_lines_or_points'],'before_scaled_dot_alpha':True},
        'blend_mode':None if recipe['additive'] is None else 'source_alpha_additive' if recipe['additive'] else 'source_alpha_over',
        'visible_flashing':None,'visible_flash_frequency_hz':None,'final_palette_verified':False,
        'uses_equation_execution':False,'uses_rendered_images':False,
        'conditions':['Raw source envelopes require finite inputs/intermediates and supported control formulas',
                      'Wave colours clamp, not shape modulo; normalization gate and dynamic enable may change colour abruptly',
                      'Envelopes are independent nominal component bounds; dynamic normalization native division rounding remains separate',
                      'Mode3 consumes native audioData treble, not an authored replacement of the EEL treb variable',
                      'Opacity mode/reference-size and unbounded volume ramp precede final clamp; missing audio/history stays unresolved',
                      'Wave path coverage, alpha, draw mode, feedback and later shaders determine visibility; no mood or no-flash certificate']}
