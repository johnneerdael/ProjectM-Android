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

Unrecognised or unresolved evidence is recorded as ``unresolved`` drivers that
saturate the upper estimate in their dimension. Confidence is low without any
source motion/flash magnitude or when priors and unresolved drivers are at
least half of all drivers; low confidence assigns no band (only possible
bands), so missing evidence never silently becomes Chill. Weights and references are assumptions
for preference grouping, not calibrated perception, and every rule is editable.
"""
import copy
import json
import math
import re

POLICY='approximate-activity-mood-v1'
BANDS=(('Chill',1.,30.),('Normal',25.,75.),('Intense',70.,100.))
RULES={
    'base':5.,'motion_weight':45.,'flash_weight':35.,'audio_weight':10.,'colour_weight':5.,
    'motion_reference_vp_s':1.0,'flash_reference':0.6,'colour_reference_per_s':1.0,
    'audio_route_step':0.34,'sweep_reference_hz':2.0,
    'prior_shader_motion_vp_s':0.3,'prior_geometry_motion_vp_s':0.15,'prior_audio_geometry_vp_s':0.2,
    'prior_shader_lookup_motion_vp_s':0.2,'prior_audio_brightness_hz_contrast':0.3,
    'audio_brightness_element_reference':1.0,'audio_brightness_element_cap':6.0,
    'advection_typical_fraction':0.25,
    'prior_flash_hz_contrast':0.15,
    # Source-calibrated display activity (quantile-remapped) decides the band when its interval is at
    # most this wide (activity percentile units; 1.0 = always). Out-of-fold over the bundled pack (r6
    # fit): primary band accuracy 0.85 at width <= 0.6 (22% of presets), 0.69 at <= 0.8 (55%), 0.64
    # overall (chance 0.33); Chill/Intense swaps 1.4%. Confidence is labelled from the width.
    'display_activity_max_width':1.0,'display_high_width':0.6,'display_medium_width':0.8,
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


AUDIO_CODES={1:'bass',2:'mid',3:'treb',4:'bass',5:'mid',6:'treb'}
MOTION_CAP=10.0
BRIGHTNESS_CONTROLS=('colour','color','opacity','alpha','brightness','border','gamma','decay')
CHANNEL_CONTROLS={'r','g','b','a','r2','g2','b2','a2'}


def is_brightness_control(name):
    """Colour/opacity controls by word (``outline_opacity``, ``border_a``, ``wave_r``), not by prefix."""
    words=[w for w in re.split(r'[^a-z0-9]+',str(name).lower()) if w]
    return any(w in BRIGHTNESS_CONTROLS or w in CHANNEL_CONTROLS for w in words)
KNOWN_PATTERNS={'uniform_zoom','radial_zoom_profile','uniform_rotation','spatially_varying_rotation',
    'uniform_translation','translation_component','planar_travelling_wave','planar_standing_pattern',
    'radial_ring_wave','radial_standing_rings','angular_lobes','angular_modulation_with_seam'}
KNOWN_MOTION={'backward_sampling_displacement','sampled_content_displacement_relation','native_affine_component_transport',
    'forward_content_transport','geometry_trajectory','procedural_shader_motion','geometry_audio_partial','geometry_state_update',
    'authored_sampling_time_partial','native_stage_selection','composite_sample_access'}


def _band(name):
    name=str(name or '')
    for band in ('bass','mid','treb','vol'):
        if name.startswith(band):return band
    return None


def _mean_radius(viewport):
    """Mean distance from the screen centre in long-side units (zoom/rotation flow average)."""
    width,height=viewport;longest=max(width,height)
    steps=48;total=0.
    for i in range(steps):
        for j in range(steps):
            x=((i+.5)/steps-.5)*width/longest;y=((j+.5)/steps-.5)*height/longest
            total+=math.hypot(x,y)
    return total/(steps*steps)


STAGE_COVERAGE={'composite':1.0,'warp':0.7}


def brightness_coverage(summary,elements):
    """Screen coverage weight of audio-driven brightness: composite/warp stages act on the
    whole image; drawn elements count by instance coverage (editable assumptions)."""
    facts={row['path']:row['value'] for rows in summary.get('facts',{}).values() for row in rows}
    stages={}
    for element in elements:
        stage=facts.get(element+'/stage')
        if stage in STAGE_COVERAGE:weight=STAGE_COVERAGE[stage]
        else:
            instances=(facts.get(element+'/parameters') or {}).get('instances') or 1
            weight=.2 if instances<8 else .4 if instances<64 else .6
        stages[stage]=max(stages.get(stage,0.),weight)
    return min(2.,sum(stages.values()))


def point_cloud_speeds(record,fps,*,points=64,times=(1.,3.,5.,8.,13.,21.)):
    """Median and 95th-percentile on-screen point speed (viewport widths/s) of a closed-form point cloud.

    Positions are MilkDrop source units (x spans the width; y the same scale);
    one-frame finite differences at declared times, audio held at the record's
    midpoints. Branch switches in the formulas produce jumps; the median is
    robust to them, the p95 keeps them as an upper estimate.
    """
    from time_expression import evaluate_inputs
    programs=record.get('programs') or {};count=int(record.get('sample_count') or 0)
    if count<1 or programs.get('x') is None or programs.get('y') is None:return None
    held=record.get('held_inputs') or {};step=1/fps;speeds=[]
    indices=sorted({round(i*(count-1)/max(1,points-1)) for i in range(points)})
    try:
        for time in times:
            for j in indices:
                sample=j/(count-1) if count>1 else 0.
                a={**held,'time':time,'sample':sample};b={**held,'time':time+step,'sample':sample}
                x0,y0=evaluate_inputs(programs['x'],a),evaluate_inputs(programs['y'],a)
                if not (0<=x0<=1 and .5-.5*VISIBLE_Y<=y0<=.5+.5*VISIBLE_Y):continue
                x1,y1=evaluate_inputs(programs['x'],b),evaluate_inputs(programs['y'],b)
                speeds.append(math.hypot(x1-x0,y1-y0)/step)
    except ValueError:return None
    if not speeds:return None
    speeds.sort()
    return speeds[len(speeds)//2],speeds[min(len(speeds)-1,int(.95*len(speeds)))]


VISIBLE_Y=270/480  # visible source-y span for the declared 16:9 viewport (long-side units)


def _drivers(summary,rules,fps,scale,radius=.5):
    drivers=[];priors=set();components_with_evidence={};brightness_elements=set()
    def add(dimension,kind,value,path,reason,upper=None,component=None):
        if component:components_with_evidence[component]=True
        if kind=='prior':
            # One prior per mechanism and component: repeated unresolved
            # contributions do not accumulate an invented magnitude.
            key=(dimension,reason,component)
            if key in priors:return
            priors.add(key)
        if dimension=='motion' and (value>MOTION_CAP or (upper is not None and upper>MOTION_CAP) or value!=value):
            # Beyond ~10 screen widths/s motion is perceptually saturated; avoid overflow.
            reason+=' (clamped at %g screen widths/s)'%MOTION_CAP
            value=min(value,MOTION_CAP) if value==value else MOTION_CAP
            upper=None if upper is None else min(upper,MOTION_CAP)
        drivers.append({'dimension':dimension,'kind':kind,'value':value,
                        'upper':(2*value if kind=='prior' else value) if upper is None else upper,
                        'evidence_path':path,'reason':reason})
    seen_components=set()
    for group,path,value in _facts(summary):
        if not isinstance(value,dict):continue
        if path.endswith('/mesh_field'):
            components_with_evidence['mesh_warp']=True
            if value.get('status')!='described':
                add('motion','unresolved',0.,path,'per-pixel warp field partly unresolved')
            for row in value.get('patterns',[]):
                kind=row.get('pattern')
                if kind not in KNOWN_PATTERNS and not str(kind).startswith(('compression','expansion')):
                    add('motion','unresolved',0.,path,'unscored warp pattern '+str(kind));continue
                if kind in ('uniform_zoom','radial_zoom_profile'):
                    low,high=(abs(v)/100 for v in row['percent_per_step_range'])
                    speeds=sorted([low*radius*fps,high*radius*fps])
                    mean=row.get('screen_mean_percent_per_step')
                    if type(mean) in (int,float):
                        add('motion','source',abs(mean)/100*radius*fps,path,'radial zoom screen-mean flow',speeds[1])
                    else:add('motion','source',(speeds[0]+speeds[1])/2,path,'uniform zoom mean flow',speeds[1])
                    for band in {_band(name) for name in row.get('audio_inputs') or []}-{None}:add('audio','source',1.0,path,band)
                elif kind in ('uniform_rotation','spatially_varying_rotation'):
                    span=row.get('value_range_radians_per_step')
                    if isinstance(span,list):
                        magnitudes=sorted(abs(v) for v in span) if span[0]*span[1]>=0 else [0.0,max(abs(v) for v in span)]
                        add('motion','source',(magnitudes[0]+magnitudes[1])/2*radius*fps,path,'rotation mean flow',
                            magnitudes[1]*radius*fps)
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
                    for band in {_band(name) for name in row.get('amplitude_dependencies') or []}-{None}:
                        add('audio','source',1.0,path,band)
                elif kind=='angular_lobes':
                    rate=abs((row.get('oscillator') or {}).get('angular_rotation_radians_per_second') or 0)
                    add('motion','source',rate*.5,path,'rotating angular lobes')
        elif '/sample_value_offset_envelope' in path and '/stages/warp/' in path and isinstance(value.get('offset_range_uv'),list):
            bound=max(max(abs(v) for v in axis) for axis in value['offset_range_uv'])
            speed=bound*fps
            add('motion','source',speed*rules['advection_typical_fraction'],path,'self-advection displacement (typical fraction of bound)',
                speed,component='shader_warp')
        elif path.endswith('/sampling_motion') and '/sampling_geometry/stages/' in path:
            rates=value['maximum_lookup_axis_speed_uv_per_second']
            speed=math.hypot(*rates)
            stage=path.split('/sampling_geometry/stages/')[1].split('/')[0]
            add('motion','source',speed*.5,path,'time-driven lookup motion (half of ceiling)',speed,component='shader_'+stage)
        elif '/colour/components/' in path and ((value.get('source_palette') or {}).get('point_colour_distribution') or {}).get('positions_closed_form'):
            speeds=point_cloud_speeds(value['source_palette']['point_colour_distribution'],fps)
            if speeds:
                component=value.get('component_id')
                add('motion','source',speeds[0],path,'closed-form point cloud motion (median visible point speed)',speeds[1],component=component)
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
            if component:components_with_evidence.setdefault(component,False)
            if kind in ('backward_sampling_displacement','sampled_content_displacement_relation','native_affine_component_transport',
                        'forward_content_transport','native_stage_selection','composite_sample_access'):
                continue  # native warp is described by mesh_field; selection/access records carry no motion magnitude
            if kind=='authored_sampling_time_partial':
                if known:add('motion','source',span[1]*.5,path,'time-moving shader lookup (half of upper bound)',span[1],component=component)
                else:add('motion','prior',rules['prior_shader_lookup_motion_vp_s'],path,'time-moving shader lookup of unresolved speed',component=component)
                continue
            if known and kind=='geometry_trajectory':
                add('motion','source',span[1]*.5,path,'geometry trajectory (half of upper bound)',span[1])
            elif kind=='procedural_shader_motion' and component not in seen_components:
                seen_components.add(component)
                add('motion','prior',rules['prior_shader_motion_vp_s'],path,'time-driven shader field of unresolved speed',component=component)
            elif kind=='geometry_audio_partial':
                band=_band(value.get('audio_input'))
                if band:add('audio','source',1.0,path,band)
                add('motion','prior',rules['prior_audio_geometry_vp_s'],path,'audio-driven geometry of unresolved speed',component=component)
            elif kind in ('geometry_trajectory','geometry_state_update') and not known:
                add('motion','prior',rules['prior_geometry_motion_vp_s'],path,'moving geometry of unresolved speed',component=component)
            elif kind not in KNOWN_MOTION:
                add('motion','unresolved',0.,path,'unscored motion kind '+str(kind))
        elif '/flashing/records/' in path:
            hz=value.get('cycle_rate_hz');delta=value.get('brightness_delta_range')
            if type(hz) in (int,float) and hz>0:
                contrast=max(delta) if isinstance(delta,list) and delta and all(type(v) in (int,float) for v in delta) else .5
                add('flash','source',hz*contrast,path,'brightness cycle '+format(hz,'.3g')+' Hz')
            elif value.get('kind') in ('shader_brightness_change','shape_material_brightness_change') and value.get('maximum_brightness_change_per_second') not in (0,0.0):
                add('flash','prior',rules['prior_flash_hz_contrast'],path,'brightness change of unresolved rate',component=value.get('component_id'))
            elif value.get('maximum_brightness_change_per_second') not in (0,0.0):
                add('flash','unresolved',0.,path,'unscored brightness record '+str(value.get('kind')))
        elif path.endswith('/wave_material'):
            rates=[((c or {}).get('raw_time_curve') or {}).get('maximum_absolute_control_rate_per_second') for c in (value.get('channels') or {}).values()]
            rates=[r for r in rates if type(r) in (int,float)]
            if rates:add('colour','source',max(rates),path,'built-in wave colour change rate ceiling')
        elif group=='audio' and '/audio_routes/' in path:
            band=AUDIO_CODES.get(value.get('input_code'))
            if band:add('audio','source',1.0,path,band)
            control=str(value.get('control') or '')
            if band and is_brightness_control(control):
                # Audio steering brightness/colour pulses with the music (beat-driven flashing);
                # its displayed contrast is unresolved, so the magnitude is an editable prior.
                brightness_elements.add(path.split('/audio_routes/')[0])
        elif path.endswith('/classification') and isinstance(value.get('unknown_contributors'),list):
            for row in value['unknown_contributors']:
                component=row.get('component_id')
                if component and component!='preset-output':components_with_evidence.setdefault(component,False)
    if brightness_elements:
        coverage=brightness_coverage(summary,brightness_elements)
        add('flash','prior',rules['prior_audio_brightness_hz_contrast']*coverage/rules['audio_brightness_element_reference'],
            STATIC+'/classification','audio-driven brightness/colour, stage coverage %.2f'%coverage)
    # A component the strict model could not bound, with no approximate driver
    # (source or prior) of its own, is uncovered evidence.
    for component,covered in components_with_evidence.items():
        if not covered and not component.startswith('mesh_warp'):
            add('motion','unresolved',0.,STATIC+'/classification','no approximate driver for '+component)
    return drivers


def _display_activity(display,rules):
    """Activity bands from a display estimate (calibrated_display.predict output), or None."""
    if not display:return None
    from display_activity import classify
    estimate={name:{'value':entry.get('value'),'interval':entry.get('interval')} for name,entry in display.items() if isinstance(entry,dict)}
    evidence={entry.get('evidence') for entry in display.values() if isinstance(entry,dict)}
    result=classify(estimate,remap=evidence=={'source-calibrated'})
    if result is None:return None
    width=result['activity_interval'][1]-result['activity_interval'][0]
    result.update(evidence=sorted(e for e in evidence if e),interval_width=round(width,4),
                  decides=width<=rules['display_activity_max_width'])
    return result


def approximate_mood(summary,rules=None,display=None):
    """Return an approximate activity estimate with labelled drivers and confidence.

    display (optional) is a source-calibrated display estimate ({metric: {'value','interval',
    'evidence'}}, calibrated_display.predict). Its activity percentile (display_activity) decides the
    band when its interval is narrow enough; otherwise the source-model estimate below is used.
    """
    if not isinstance(summary,dict) or summary.get('policy')!='preset-understanding-v1':
        raise ValueError('preset-understanding-v1 summary required')
    rules=validate_rules(rules)
    context=next((v for _,p,v in _facts(summary) if p==STATIC+'/context'),{}) or {}
    fps=float(context.get('feedback_fps') or 30.)
    viewport=context.get('viewport') or [480,270]
    scale=float(max(viewport))
    drivers=_drivers(summary,rules,fps,scale,_mean_radius(viewport))
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
        if key=='upper':
            # Unresolved evidence could be strong: the upper estimate saturates it.
            if any(d['kind']=='unresolved' and d['dimension']=='motion' for d in drivers):motion=1.
            if any(d['kind']=='unresolved' and d['dimension']=='flash' for d in drivers):flash=1.
        audio=min(1.,len({d['reason'] for d in drivers if d['dimension']=='audio'})*rules['audio_route_step'])
        colour=min(1.,total('colour',key=key)/rules['colour_reference_per_s'])
        value=(rules['base']+rules['motion_weight']*motion+rules['flash_weight']*flash+
               rules['audio_weight']*audio+rules['colour_weight']*colour)
        return max(1.,min(100.,value)),{'motion':motion,'flash':flash,'audio':audio,'colour':colour}
    estimate,components=score('value');upper,_=score('upper')
    source_only=[d for d in drivers if d['kind']=='source']
    # Lower estimate: drop prior-only drivers (their mechanisms might be weak).
    kept=drivers[:];drivers[:]=source_only;low=score('value')[0];drivers[:]=kept
    uncertain=[d for d in drivers if d['kind'] in ('prior','unresolved')]
    prior_share=0. if not drivers else len(uncertain)/len(drivers)
    has_source=any(d['dimension'] in ('motion','flash') and d['kind']=='source' for d in drivers)
    if not has_source:confidence='low'
    elif prior_share==0:confidence='high'
    elif prior_share<.5:confidence='medium'
    else:confidence='low'
    interval=[min(low,estimate),max(upper,estimate)]
    possible=[name for name,a,b in BANDS if interval[0]<=b and interval[1]>=a]
    # Low confidence abstains: no band is assigned, only possible bands.
    bands=[] if confidence=='low' else [name for name,a,b in BANDS if a<=estimate<=b]
    band_source='source-model' if bands else None
    calibrated=_display_activity(display,rules)
    if calibrated and calibrated['decides']:
        bands=calibrated['bands'];possible=calibrated['possible_bands'];band_source='source-calibrated-display'
        width=calibrated['interval_width']
        confidence='high' if width<=rules['display_high_width'] else 'medium' if width<=rules['display_medium_width'] else 'low'
    return {'policy':POLICY,'activity_estimate':round(estimate,1),'activity_interval':[round(v,1) for v in interval],
        'bands':bands,'possible_bands':possible,'confidence':confidence,'prior_driver_share':round(prior_share,3),
        'band_source':band_source,'display_activity':calibrated,
        'abstained':not bands,'unresolved_driver_count':sum(1 for d in drivers if d['kind']=='unresolved'),
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
