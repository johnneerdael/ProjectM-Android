"""Native outer/inner borders and the darken-centre diamond as feedback operators.

MilkDrop2 DrawSprites (milkdropfs.cpp) runs after shapes and waves, into the
canvas that becomes the next frame's feedback input:

- darken centre (``darken_center``): a triangle fan of half-size 0.05 NDC
  (x scaled by aspectY) whose centre vertex is black with alpha 3/32 and whose
  rim is alpha 0;
- borders: when alpha > 0.001 each border is four 90-degree rotations of the
  quad (in,in),(out,out),(out,-out),(in,-in) in NDC, alpha-blended "over" with a
  constant colour. Outer: in=1-ob_size, out=1; inner: in=1-ob_size-ib_size,
  out=1-ob_size. The union is the square annulus in<=max(|x|,|y|)<=out, which
  covers out^2-in^2 of the viewport (both axes are normalized, so this is a
  screen fraction). A negative inner radius makes a self-intersecting fan and
  is left unresolved.

A pixel inside a border band evolves per frame as c' = (1-a) d c + a rgb with
warp decay d, so the retained-content gain there is d(1-a) and the steady
level is a rgb / (1 - d(1-a)). The RGBA8 orbit applies the existing warp level
map and then the border blend with round-to-nearest conversion (float32 values,
exact ties reported). Bands, gains and floors are source facts about stored
levels; visible brightness, actual trail length and mood remain conditional.
"""
import math

import numpy as np

POLICY='source-border-feedback-operators-v1'
NAMES=('ob_size','ob_r','ob_g','ob_b','ob_a','ib_size','ib_r','ib_g','ib_b','ib_a','darken_center')
LEVELS=255
DARKEN_ALPHA=3/32
DARKEN_HALF_SIZE=.05


def _round(value):
    floor=math.floor(value);remainder=value-floor
    return floor+1 if remainder>.5 else floor


def _orbit(decay,alpha,colour):
    """Stored-level orbit from full white: warp decay (float32), then border blend."""
    from source_feedback_persistence import _level_map
    warp=_level_map(decay,'float32')
    one=np.float32(1);a=np.float32(alpha);fill=np.float32(colour)*a
    level=LEVELS;orbit=[level];seen={level}
    for _ in range(4*LEVELS):
        stored,tie=warp[level]
        if tie:return None
        blended=float(np.float32(stored/LEVELS)*(one-a)+fill)*LEVELS
        level=min(LEVELS,max(0,_round(blended)))
        if level in seen:
            orbit.append(level);break
        orbit.append(level);seen.add(level)
    return orbit


def _constant(span):
    return float(span[0]) if span is not None and span[0]==span[1] else None


def border_operators(analysis,context,persistence):
    from source_control_bounds import scalar_value_envelope
    from source_motion_behaviour import _effective_domains
    result={'policy':POLICY,'status':'unknown','control_ranges':{},'borders':[],'darken_centre':None,
        'uses_equation_execution':False,'uses_rendered_images':False,'native_numeric_certified':False,'unknown_reasons':[],
        'conditions':['Order after shapes and waves, into the feedback canvas (MilkDrop2 DrawSprites; projectM-TV keeps the fan geometry)',
            'Bands are square annuli in NDC; screen fractions assume both axes are normalized to the viewport',
            'Per-frame gain d(1-a) and RGBA8 orbits hold for retained content that stays inside the band; motion carries content across bands',
            'Stored levels, not displayed brightness; composite echo/gamma and later drawing are separate']}
    try:
        main=getattr(analysis,'main',{}) or {}
        domains=dict(_effective_domains(analysis,context))
        for name in NAMES:
            field=main.get(name)
            if field is None:raise ValueError('border control '+name+' is absent')
            span=scalar_value_envelope(field,input_domains=domains).get('nominal_value_range')
            result['control_ranges'][name]=None if span is None else [float(span[0]),float(span[1])]
        ranges=result['control_ranges']
        decay=(persistence or {}).get('decay_gain')
        decay=float(decay) if type(decay) in (int,float) and 0<decay<=1 else None
        outer=_constant(ranges['ob_size']);inner=_constant(ranges['ib_size'])
        for label,prefix,bounds in (('outer','ob_',None if outer is None else (1-outer,1.)),
                                    ('inner','ib_',None if outer is None or inner is None else (1-outer-inner,1-outer))):
            alpha=ranges[prefix+'a'];rgb=[ranges[prefix+c] for c in 'rgb']
            row={'border':label,'alpha_range':alpha,'rgb_ranges':rgb,'active':None,'ndc_band':None,
                 'screen_area_fraction':None,'inverted_inner_radius':None,'retained_gain_per_frame':None,
                 'combined_gain_with_decay':None,'steady_level_rgb':None,'level_orbit_from_full':None,
                 'steps_to_half_from_full':None,'floor_level_from_full':None,'seconds_to_half_from_full':None}
            if alpha is not None and alpha[1]<=.001:
                row['active']=False;result['borders'].append(row);continue
            row['active']=True if alpha is not None and alpha[0]>.001 else None
            if bounds is not None:
                low,high=bounds
                row['ndc_band']=[low,high]
                row['inverted_inner_radius']=low<0
                if 0<=low<=high:row['screen_area_fraction']=min(1.,high*high)-min(1.,low*low)
            a=_constant(alpha);colour=[_constant(span) for span in rgb]
            if a is not None and row['active']:
                a=min(1.,a);row['retained_gain_per_frame']=1-a
                if decay is not None:
                    gain=decay*(1-a);row['combined_gain_with_decay']=gain
                    if None not in colour:
                        row['steady_level_rgb']=[min(1.,a*max(0.,min(1.,c))/(1-gain)) if gain<1 else None for c in colour]
                        orbit=_orbit(decay,a,max(0.,min(1.,min(colour))))
                        if orbit is not None:
                            row['level_orbit_from_full']=orbit if len(orbit)<=64 else orbit[:32]+orbit[-32:]
                            row['floor_level_from_full']=orbit[-1]
                            row['steps_to_half_from_full']=next((i for i,level in enumerate(orbit) if 2*level<=LEVELS),None)
                            fps=(context or {}).get('feedback_fps')
                            if row['steps_to_half_from_full'] is not None and type(fps) in (int,float) and fps>0:
                                row['seconds_to_half_from_full']=row['steps_to_half_from_full']/fps
            result['borders'].append(row)
        darken=ranges['darken_center']
        if darken is not None and darken[1]!=0:
            aspect=None
            viewport=(context or {}).get('viewport')
            if isinstance(viewport,list) and len(viewport)==2 and min(viewport)>0:
                aspect=min(1.,viewport[1]/viewport[0])
            result['darken_centre']={'active':True if darken[0]!=0 else None,'centre_alpha':DARKEN_ALPHA,
                'half_size_ndc':[DARKEN_HALF_SIZE*aspect if aspect else None,DARKEN_HALF_SIZE],
                'centre_retained_gain_per_frame':1-DARKEN_ALPHA,
                'combined_centre_gain_with_decay':None if decay is None else decay*(1-DARKEN_ALPHA),
                'note':'alpha falls linearly from 3/32 at the centre to 0 at the diamond rim'}
        result['status']='described'
    except (ValueError,ArithmeticError,RecursionError,TypeError) as error:
        result['unknown_reasons'].append(str(error))
    return result
