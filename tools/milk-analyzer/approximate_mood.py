"""Approximate, editable activity/mood estimate from an understanding-SDK summary.

This layer is deliberately separate from strict source eligibility
(``static_behaviour.classification.eligible_bands``). It reads only a
``preset-understanding-v1`` summary (exact fact pointers) and combines labelled
drivers into a 1-100 activity estimate:

- ``source`` drivers carry a magnitude derived from source facts (per-pixel warp
  patterns, curve sweep cadence, transport speeds, brightness cycles, colour
  rates);
- ``prior`` drivers only know that a mechanism is present (for example a
  time-driven shader motion field of unresolved speed) and use an editable
  assumed magnitude.

Confidence falls as prior-only or unresolved contributions dominate, so missing
evidence never silently becomes Chill. Weights and references are assumptions
for preference grouping, not calibrated perception, and every rule is editable.
"""
import copy
import json
import math

POLICY='approximate-activity-mood-v1'
BANDS=(('Chill',1.,30.),('Normal',25.,75.),('Intense',70.,100.))
RULES={
    'base':5.,'motion_weight':45.,'flash_weight':35.,'audio_weight':10.,'colour_weight':5.,
    'motion_reference_vp_s':1.0,'flash_reference':0.6,'colour_reference_per_s':1.0,
    'audio_route_step':0.34,'sweep_reference_hz':2.0,
    'prior_shader_motion_vp_s':0.3,'prior_geometry_motion_vp_s':0.15,'prior_audio_geometry_vp_s':0.2,
    'prior_flash_hz_contrast':0.15,
}
STATIC='/analysis/visual_description/static_behaviour'


def validate_rules(overrides=None):
    rules=copy.deepcopy(RULES)
    for key,value in (overrides or {}).items():
        if key not in RULES:raise ValueError('unknown approximate mood rule '+key)
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:
            raise ValueError('finite nonnegative approximate mood rule required: '+key)
        rules[key]=float(value)
    return rules


def _facts(summary):
    for group,rows in summary.get('facts',{}).items():
        for row in rows:yield group,row['path'],row['value']


def _mid(span):
    return (span[0]+span[1])/2 if isinstance(span,list) and len(span)==2 and all(type(v) in (int,float) for v in span) else None


def _drivers(summary,rules,fps,scale):
    drivers=[];priors=set()
    def add(dimension,kind,value,path,reason,upper=None,component=None):
        if kind=='prior':
            # One prior per mechanism and component: repeated unresolved
            # contributions do not accumulate an invented magnitude.
            key=(dimension,reason,component)
            if key in priors:return
            priors.add(key)
        drivers.append({'dimension':dimension,'kind':kind,'value':value,'upper':value if upper is None else upper,
                        'evidence_path':path,'reason':reason})
    seen_components=set()
    for group,path,value in _facts(summary):
        if not isinstance(value,dict):continue
        if path.endswith('/mesh_field'):
            for row in value.get('patterns',[]):
                kind=row.get('pattern')
                if kind in ('uniform_zoom','radial_zoom_profile'):
                    low,high=(abs(v)/100 for v in row['percent_per_step_range'])
                    speeds=sorted([low*.5*fps,high*.5*fps])
                    add('motion','source',(speeds[0]+speeds[1])/2,path,'uniform zoom edge flow (half-width)',speeds[1])
                    if row.get('audio_inputs'):add('audio','source',1.0,path,'audio-driven zoom: '+'/'.join(row['audio_inputs']))
                elif kind in ('uniform_rotation','spatially_varying_rotation'):
                    span=row.get('value_range_radians_per_step')
                    if isinstance(span,list):
                        magnitudes=sorted(abs(v) for v in span) if span[0]*span[1]>=0 else [0.0,max(abs(v) for v in span)]
                        add('motion','source',(magnitudes[0]+magnitudes[1])/2*.5*fps,path,'rotation edge speed (half-width)',
                            magnitudes[1]*.5*fps)
                elif kind in ('uniform_translation','translation_component'):
                    span=row.get('translation_pixels_per_second_range')
                    if isinstance(span,list) and all(type(v) in (int,float) for v in span):
                        speeds=sorted(abs(v) for v in span) if span[0]*span[1]>=0 else [0.0,max(map(abs,span))]
                        fraction=row.get('screen_fraction') or 1
                        add('motion','source',(speeds[0]+speeds[1])/2/scale*fraction,path,'translation drift',speeds[1]/scale*fraction)
                elif kind in ('planar_travelling_wave','radial_ring_wave'):
                    osc=row.get('oscillator') or {}
                    speed=abs(osc.get('phase_speed_pixels_per_second') or osc.get('radial_phase_speed_pixels_per_second') or 0)/scale
                    amplitude=row.get('amplitude_pixels_range')
                    weight=min(1.,max(map(abs,amplitude))/10) if isinstance(amplitude,list) else .5
                    add('motion','source',speed*weight*(row.get('screen_fraction') or 1),path,kind.replace('_',' '))
                    if row.get('amplitude_dependencies') and set(row['amplitude_dependencies'])&{'bass','bass_att','mid','mid_att','treb','treb_att'}:
                        add('audio','source',1.0,path,'audio-scaled ripple amplitude')
                elif kind=='angular_lobes':
                    rate=abs((row.get('oscillator') or {}).get('angular_rotation_radians_per_second') or 0)
                    add('motion','source',rate*.5,path,'rotating angular lobes')
        elif '/radial_colour_field/components/' in path:
            sweep=value.get('sweep_front') or {}
            if sweep.get('status')=='conditional_rotating_refresh_front':
                hz=sweep.get('revisit_cadence_hz') or 0
                add('motion','source',min(1.,hz/rules['sweep_reference_hz'])*rules['motion_reference_vp_s']*.5,path,
                    'rotating curve refresh front '+format(hz,'.3g')+' Hz')
        elif '/motion/contributions/' in path:
            kind=value.get('kind');component=value.get('component_id')
            span=value.get('speed_interval_vp_per_second')
            known=isinstance(span,list) and len(span)==2 and span[1] is not None and value.get('estimate_kind') not in (None,'unknown')
            if kind in ('backward_sampling_displacement','sampled_content_displacement_relation','native_affine_component_transport',
                        'forward_content_transport'):
                continue  # native warp is described by mesh_field patterns
            if known and kind=='geometry_trajectory':
                add('motion','source',span[1]*.5,path,'geometry trajectory (half of upper bound)',span[1])
            elif kind=='procedural_shader_motion' and component not in seen_components:
                seen_components.add(component)
                add('motion','prior',rules['prior_shader_motion_vp_s'],path,'time-driven shader field of unresolved speed',component=component)
            elif kind=='geometry_audio_partial':
                add('audio','source',1.0,path,'audio-driven geometry ('+str(value.get('audio_input'))+')')
                add('motion','prior',rules['prior_audio_geometry_vp_s'],path,'audio-driven geometry of unresolved speed',component=component)
            elif kind in ('geometry_trajectory','geometry_state_update') and not known:
                add('motion','prior',rules['prior_geometry_motion_vp_s'],path,'moving geometry of unresolved speed',component=component)
        elif '/flashing/records/' in path:
            hz=value.get('cycle_rate_hz');delta=value.get('brightness_delta_range')
            if type(hz) in (int,float) and hz>0:
                contrast=max(delta) if isinstance(delta,list) and delta and all(type(v) in (int,float) for v in delta) else .5
                add('flash','source',hz*contrast,path,'brightness cycle '+format(hz,'.3g')+' Hz')
            elif value.get('kind') in ('shader_brightness_change','shape_material_brightness_change') and value.get('maximum_brightness_change_per_second') not in (0,0.0):
                add('flash','prior',rules['prior_flash_hz_contrast'],path,'brightness change of unresolved rate',component=value.get('component_id'))
        elif path.endswith('/wave_material'):
            rates=[((c or {}).get('raw_time_curve') or {}).get('maximum_absolute_control_rate_per_second') for c in (value.get('channels') or {}).values()]
            rates=[r for r in rates if type(r) in (int,float)]
            if rates:add('colour','source',max(rates),path,'built-in wave colour change rate ceiling')
        elif group=='audio' and '/audio_routes/' in path:
            add('audio','source',1.0,path,'authored audio route to '+str(value.get('control')))
    return drivers


def approximate_mood(summary,rules=None):
    """Return an approximate activity estimate with labelled drivers and confidence."""
    if not isinstance(summary,dict) or summary.get('policy')!='preset-understanding-v1':
        raise ValueError('preset-understanding-v1 summary required')
    rules=validate_rules(rules)
    context=next((v for _,p,v in _facts(summary) if p==STATIC+'/context'),{}) or {}
    fps=float(context.get('feedback_fps') or 30.)
    viewport=context.get('viewport') or [480,270]
    scale=float(max(viewport))
    drivers=_drivers(summary,rules,fps,scale)
    def total(dimension,kind=None,key='value'):
        source=[d[key] for d in drivers if d['dimension']==dimension and d['kind']=='source']
        prior=[d[key] for d in drivers if d['dimension']==dimension and d['kind']=='prior']
        # Source magnitudes combine (RSS for motion, sum otherwise); priors only
        # contribute their largest assumed magnitude.
        known=math.sqrt(sum(v*v for v in source)) if dimension=='motion' else sum(source)
        assumed=max(prior,default=0.)
        return math.sqrt(known*known+assumed*assumed) if dimension=='motion' else known+assumed
    def score(key):
        motion=min(1.,total('motion',key=key)/rules['motion_reference_vp_s'])
        flash=min(1.,total('flash',key=key)/rules['flash_reference'])
        audio=min(1.,len({d['reason'] for d in drivers if d['dimension']=='audio'})*rules['audio_route_step'])
        colour=min(1.,total('colour',key=key)/rules['colour_reference_per_s'])
        value=(rules['base']+rules['motion_weight']*motion+rules['flash_weight']*flash+
               rules['audio_weight']*audio+rules['colour_weight']*colour)
        return max(1.,min(100.,value)),{'motion':motion,'flash':flash,'audio':audio,'colour':colour}
    estimate,components=score('value');upper,_=score('upper')
    source_only=[d for d in drivers if d['kind']=='source']
    # Lower estimate: drop prior-only drivers (their mechanisms might be weak).
    kept=drivers[:];drivers[:]=source_only;low=score('value')[0];drivers[:]=kept
    prior_share=0. if not drivers else sum(1 for d in drivers if d['kind']=='prior')/len(drivers)
    confidence='high' if drivers and prior_share==0 else 'medium' if prior_share<.5 else 'low'
    if not drivers:confidence='low'
    interval=[min(low,estimate),max(upper,estimate)]
    bands=[name for name,a,b in BANDS if a<=estimate<=b]
    possible=[name for name,a,b in BANDS if interval[0]<=b and interval[1]>=a]
    return {'policy':POLICY,'activity_estimate':round(estimate,1),'activity_interval':[round(v,1) for v in interval],
        'bands':bands,'possible_bands':possible,'confidence':confidence,'prior_driver_share':round(prior_share,3),
        'components':{k:round(v,3) for k,v in components.items()},'drivers':drivers,'rules':rules,
        'strict_eligible_bands':next((v.get('eligible_bands') for _,p,v in _facts(summary) if p==STATIC+'/classification'),None),
        'calibrated':False,'uses_rendered_images':False,
        'limitations':['Assumed editable weights and priors for preference grouping; not calibrated against viewers',
            'Prior drivers stand in for mechanisms whose magnitude the source analysis has not resolved',
            'Strict eligible bands are reported separately and are unaffected by this estimate']}


def main(argv=None):
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('summary',type=Path);parser.add_argument('--rules',type=Path)
    args=parser.parse_args(argv)
    rules=json.loads(args.rules.read_text()) if args.rules else None
    print(json.dumps(approximate_mood(json.loads(args.summary.read_text()),rules),indent=2))


if __name__=='__main__':
    main()
