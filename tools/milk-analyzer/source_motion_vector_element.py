"""Static description of the native motion-vector drawing element.

The engine enables vectors when mv_a>=0.0001 (legacy bMotionVectorsOn maps to
mv_a=1) and both integer grid counts are positive (at most 64x48). Grid
positions follow motion_vectors.motion_geometry: (i+.25)/(n+frac+.25-1) plus the
signed mv_dx/mv_dy offset, keeping .0001<pos<.9999; rows are measured from the
bottom, so the screen fraction from the top is 1-pos. Each vector is a line from
its grid point toward the previous-frame sampling position, scaled by mv_l,
drawn into the feedback canvas (so it is later warped and decayed). Values come
from declared envelopes of the per-frame controls; no frames are executed.
"""
import math

import numpy as np

POLICY='source-motion-vector-element-v1'
NAMES=('mv_a','mv_x','mv_y','mv_dx','mv_dy','mv_l','mv_r','mv_g','mv_b')


def _positions(count_value,offset,sign,maximum):
    count=int(count_value);divert=np.float32(count_value)-np.float32(count)
    if count>maximum:count,divert=maximum,np.float32(0)
    if count<=0:return []
    divert=np.clip(divert,np.float32(0),np.float32(1))
    denominator=np.float32(count)+divert+np.float32(.25)-np.float32(1)
    pos=(np.arange(count,dtype=np.float32)+np.float32(.25))/denominator+np.float32(sign)*np.float32(offset)
    return [float(v) for v in pos if np.float32(.0001)<v<np.float32(.9999)]


def motion_vector_element(analysis,context=None):
    from source_control_bounds import scalar_value_envelope
    from source_motion_behaviour import _effective_domains
    result={'policy':POLICY,'status':'unknown','activation':None,'control_ranges':{},'columns_screen_fraction':None,
        'rows_screen_fraction_from_top':None,'vector_count':None,'colour_rgba':None,'length_scale':None,
        'drawn_into_feedback':True,'visible_contrast':None,'visible_motion_speed':None,
        'uses_equation_execution':False,'uses_rendered_images':False,'unknown_reasons':[],
        'conditions':['Activation needs mv_a>=0.0001 and positive integer grid counts; legacy bMotionVectorsOn maps to mv_a=1',
            'Grid positions follow the engine formula with signed offsets; rows are measured from the bottom',
            'Each vector points from its grid point toward the previous-frame sampling position, scaled by mv_l, with a minimum length of about 1.25 pixels',
            'Vectors are drawn into the feedback canvas and then warped/decayed with other drawings; visible contrast is unverified']}
    try:
        main=getattr(analysis,'main',{}) or {}
        domains=dict(_effective_domains(analysis,context))
        for name in NAMES:
            field=main.get(name)
            if field is None:raise ValueError('motion-vector control '+name+' is absent')
            span=scalar_value_envelope(field,input_domains=domains).get('nominal_value_range')
            result['control_ranges'][name]=None if span is None else [float(span[0]),float(span[1])]
        ranges=result['control_ranges']
        alpha=ranges['mv_a']
        if alpha is not None and alpha[1]<float(np.float32(.0001)):
            result.update(status='inactive',activation='inactive');return result
        counts=[ranges['mv_x'],ranges['mv_y']]
        if any(span is None or span[0]!=span[1] for span in counts):
            result.update(status='partial',activation='possible');result['unknown_reasons'].append('grid counts are not constant')
            return result
        if any(span[0]<1 for span in counts):
            result.update(status='inactive',activation='inactive');return result
        offsets=[ranges['mv_dx'],ranges['mv_dy']]
        if any(span is None or span[0]!=span[1] for span in offsets):
            result.update(status='partial',activation='possible' if alpha is None or alpha[0]<.0001 else 'active')
            result['unknown_reasons'].append('grid offsets are not constant');return result
        columns=_positions(counts[0][0],offsets[0][0],1,64)
        rows=_positions(counts[1][0],offsets[1][0],-1,48)
        colour=[ranges[name] for name in ('mv_r','mv_g','mv_b','mv_a')]
        activation='active' if alpha is not None and alpha[0]>=float(np.float32(.0001)) else 'possible'
        if not columns or not rows:activation='inactive_no_points_in_bounds'
        result.update(status='described',activation=activation,
            columns_screen_fraction=columns,rows_screen_fraction_from_top=[1-v for v in rows],
            vector_count=len(columns)*len(rows),
            colour_rgba=[None if span is None else (span[0] if span[0]==span[1] else span) for span in colour],
            length_scale=ranges['mv_l'])
    except (ValueError,ArithmeticError,RecursionError,TypeError) as error:
        result['unknown_reasons'].append(str(error))
    return result
