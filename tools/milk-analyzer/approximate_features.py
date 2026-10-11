"""Approximate feature vector, style scores and profile suitability from SDK facts.

Follows the research feature contract (motion, flash, brightness, palette,
feedback, audio, structure) and its transparent equations, but over an
understanding-SDK summary rather than strict hashed source-feature records.
Every feature carries an evidence label:

- ``source-estimate``: a magnitude derived from exact source facts (possibly
  with a declared typical fraction of a bound);
- ``mechanism-estimate``: a score assigned to a proven program mechanism;
- ``assumed``: an editable prior for a mechanism of unresolved magnitude;
- ``unknown``: no evidence; scores carry the full [0,1] component interval.

The strict scorer (``mood_scoring.py``) and its eligibility are unchanged. All
coefficients are initial engineering assumptions from the research notes and
remain editable; nothing here is calibrated perception or preference accuracy.
"""
import colorsys
import copy
import math

POLICY='approximate-feature-vector-v1'
STATIC='/analysis/visual_description/static_behaviour'
BASE='/analysis/visual_description'
BEAT_HZ=2.0
SLOW_HZ=0.3
WARM_AXIS_DEGREES=30.0
BANDS=(('Chill',1.,30.),('Normal',25.,75.),('Intense',70.,100.))
MECHANISM_STRUCTURE={
    'symmetry':{'angular_mirror_fold':.9,'cartesian_mirror_fold':.7,'polar_radial_sampling':.6,'parametric_radial_curve':.6,
                'circular_wave_primitive':.55,'radial_twist':.5,'angular_periodic_warp':.6,'radial_band':.55},
    'nonlinear_warp':{'nonlinear_feedback_map':.9,'polar_radial_sampling':.8,'gradient_driven_advection':.75,
                      'image_driven_advection':.7,'noise_driven_advection':.65,'radial_twist':.6,'uv_advection':.5,
                      'angular_periodic_warp':.5,'spatial_rotation':.45},
    'feedback_complexity':{'nonlinear_feedback_map':.9,'multi_copy_feedback_recursion':.8,'gradient_driven_advection':.75,
                           'image_driven_advection':.7,'radial_feedback_transform':.3},
    'organic':{'gradient_driven_advection':.8,'image_driven_advection':.7,'noise_driven_advection':.6,'uv_advection':.5},
    'geometric':{'polygon_shape_primitive':.45,'procedural_shape_instances':.75,'angular_mirror_fold':.6,
                 'cartesian_mirror_fold':.5,'spatial_oscillatory_bands':.5},
    'fractal':{'complex_quadratic_recurrence':.95,'mandelbox_recurrence':.95,'nonlinear_feedback_map':.85,
               'multi_copy_feedback_recursion':.6},
}
COMPOSITE_FACTOR=.7
DEFAULT_STRUCTURE={'symmetry':.2,'nonlinear_warp':.1,'feedback_complexity':.2,'organic':.15,'geometric':.15,'fractal':0.}


def _feature(value=None,interval=None,evidence='unknown',paths=(),note=None):
    if value is not None and interval is None:interval=[value,value]
    return {'value':value,'interval':interval,'evidence':evidence,'evidence_paths':list(paths)[:8],**({'note':note} if note else {})}


def _facts(summary):
    for group,rows in summary.get('facts',{}).items():
        for row in rows:yield group,row['path'],row['value']


def _motion(summary,rules):
    """Typical speed and beat-coupled share from the approximate driver set."""
    from approximate_mood import _drivers,_mean_radius,validate_rules
    context=next((v for _,p,v in _facts(summary) if p==STATIC+'/context'),{}) or {}
    fps=float(context.get('feedback_fps') or 30.);viewport=context.get('viewport') or [480,270]
    drivers=_drivers(summary,validate_rules(rules),fps,float(max(viewport)),_mean_radius(viewport))
    return drivers,fps


def _audio_coupled(summary):
    paths=set()
    for _,path,value in _facts(summary):
        if not isinstance(value,dict):continue
        if path.endswith('/mesh_field'):
            for row in value.get('patterns',[]):
                if row.get('audio_inputs') or row.get('amplitude_dependencies'):paths.add(path)
        elif '/motion/contributions/' in path and value.get('kind')=='geometry_audio_partial':paths.add(path)
    return paths


def _colour_samples(summary):
    """Representative colours with weights from palettes, flat fields, wave colours and anchors."""
    from time_expression import wave_colour
    samples=[];hue_rates=[];paths=[]
    for group,path,value in _facts(summary):
        if not isinstance(value,dict):continue
        if path.endswith('/scalar_palette') and value.get('samples'):
            for row in value['samples']:samples.append((row['clamped_rgb'],1/len(value['samples'])))
            paths.append(path)
        elif path.endswith('/flat_field') and isinstance(value.get('composite_rgb_at_state'),list):
            samples.append((value['composite_rgb_at_state'],2.));paths.append(path)
        elif path.endswith('/wave_material'):
            try:
                series=[wave_colour(value.get('channels') or {},t*.25,bool(value.get('normalization_enabled'))) for t in range(241)]
            except (ValueError,KeyError,TypeError,OverflowError,ArithmeticError):series=None
            if series:
                for rgb in series[::8]:samples.append((rgb,1/len(series[::8])))
                hues=[colorsys.rgb_to_hsv(*rgb) for rgb in series]
                for (h0,s0,v0),(h1,s1,v1) in zip(hues,hues[1:]):
                    if s0>=.15 and s1>=.15 and v0>=.05 and v1>=.05:
                        delta=abs(h1-h0);delta=min(delta,1-delta);hue_rates.append(delta/.25)
                paths.append(path)
        elif path.endswith('/spatial_vertex_colour') and isinstance(value.get('channels'),dict):
            # Affine raw labels C0+Cs*s along the curve at source time 0, native signed fmod then clamp.
            period=value.get('native_colour_modulo_period') or 1.
            coefficients=[]
            for name in 'rgb':
                exact=((value['channels'].get(name) or {}).get('affine_coefficients'))
                coefficients.append(exact)
            if all(isinstance(c,dict) for c in coefficients):
                for index in range(33):
                    sample=index/32
                    rgb=[min(1.,max(0.,math.fmod(c['constant']+c['sample']*sample,period))) for c in coefficients]
                    samples.append((rgb,1/33))
                paths.append(path)
        elif '/colour/components/' in path:
            points=(value.get('source_palette') or {}).get('point_colour_distribution') or {}
            if points.get('status')=='closed_form_point_colours' and points.get('representative_points'):
                # Many additive points: one unit of weight per wave, kept even for faint alpha.
                rows=points['representative_points'];weight=max(.25,min(1.,4*(points.get('mean_alpha') or 0)))
                for rgba in rows:samples.append((rgba[:3],weight/len(rows)))
                paths.append(path);continue
            for anchor in (value.get('source_palette') or {}).get('anchors',[]) or []:
                rgb=anchor.get('rgb') if isinstance(anchor,dict) else None
                if isinstance(rgb,list) and len(rgb)==3 and all(type(v) in (int,float) for v in rgb):
                    samples.append(([min(1,max(0,v)) for v in rgb],.5));paths.append(path)
    return samples,hue_rates,paths


def _palette(summary):
    samples,hue_rates,paths=_colour_samples(summary)
    out={}
    if not samples:
        for name in ('mean_saturation','effective_hue_bins','warm_cool','coloured_support'):out['palette.'+name]=_feature()
    else:
        total=sum(w for _,w in samples);sat=0.;bins=[0.]*12;warm=0.;coloured=0.
        for rgb,weight in samples:
            h,s,v=colorsys.rgb_to_hsv(*rgb);sat+=s*weight
            if s>=.15 and v>=.05:
                coloured+=weight;bins[int(h*12)%12]+=weight
                warm+=weight*s*math.cos(math.radians(h*360-WARM_AXIS_DEGREES))
        probabilities=[b/sum(bins) for b in bins if b] if sum(bins) else []
        entropy=-sum(p*math.log(p) for p in probabilities)
        out['palette.mean_saturation']=_feature(sat/total,evidence='source-estimate',paths=paths)
        out['palette.effective_hue_bins']=_feature(math.exp(entropy) if probabilities else 0.,evidence='source-estimate',paths=paths)
        out['palette.coloured_support']=_feature(coloured/total,evidence='source-estimate',paths=paths)
        out['palette.warm_cool']=(_feature(max(-1.,min(1.,warm/coloured)),evidence='source-estimate',paths=paths)
                                  if coloured else _feature(evidence='unknown',note='no coloured support'))
    if hue_rates:
        ordered=sorted(hue_rates);p95=ordered[min(len(ordered)-1,int(.95*len(ordered)))]
        out['palette.hue_rate_p95_cycles_s']=_feature(p95,evidence='source-estimate',paths=paths,
                                                      note='closed-form wave colour; other colour sources not included')
    else:out['palette.hue_rate_p95_cycles_s']=_feature()
    return out


def feature_vector(summary,rules=None):
    """Return {feature name: {value, interval, evidence, evidence_paths}}."""
    drivers,fps=_motion(summary,rules)
    coupled=_audio_coupled(summary)
    vector={}
    motion=[d for d in drivers if d['dimension']=='motion']
    source=[d for d in motion if d['kind']=='source'];prior=[d for d in motion if d['kind']=='prior']
    unresolved=any(d['kind']=='unresolved' for d in motion)
    rss=lambda values:math.sqrt(sum(v*v for v in values))
    known=rss([d['value'] for d in source]);assumed=max([d['value'] for d in prior],default=0.)
    speed=math.hypot(known,assumed)
    upper=math.hypot(rss([d['upper'] for d in source]),max([d['upper'] for d in prior],default=0.))
    if unresolved:upper=max(upper,1.)
    evidence='source-estimate' if source and not prior and not unresolved else 'assumed' if not source else 'source-estimate+assumed'
    paths=[d['evidence_path'] for d in motion]
    vector['motion.speed_p95_vp_s']=(_feature(speed,[known,max(upper,speed)],evidence,paths) if motion else
                                     _feature(note='no motion evidence: interval spans the full scale'))
    beat=rss([d['value'] for d in motion if d['evidence_path'] in coupled])
    steady=math.sqrt(max(0.,speed*speed-beat*beat))
    acceleration=beat*2*math.pi*BEAT_HZ+steady*2*math.pi*SLOW_HZ
    jerk=beat*(2*math.pi*BEAT_HZ)**2+steady*(2*math.pi*SLOW_HZ)**2
    vector['motion.acceleration_p95_vp_s2']=_feature(acceleration,evidence='assumed',paths=paths,
        note='speed times assumed angular rate: beat-coupled %.1f Hz, other %.1f Hz'%(BEAT_HZ,SLOW_HZ))
    vector['motion.jerk_p95_vp_s3']=_feature(jerk,evidence='assumed',paths=paths,note='speed times squared assumed angular rate')
    from approximate_mood import is_brightness_control
    switches=[];brightness_elements=0;brightness_paths=[]
    for _,path,value in _facts(summary):
        if not isinstance(value,dict):continue
        if '/audio_routes/' in path:
            if value.get('switch_triggers'):switches.append(path)
            if is_brightness_control(value.get('control') or ''):
                brightness_paths.append(path)
    brightness_elements=len({p.split('/audio_routes/')[0] for p in brightness_paths})
    vector['motion.discontinuities_hz']=(_feature(BEAT_HZ,evidence='assumed',paths=switches,note='audio-triggered switches at an assumed beat rate')
        if switches else _feature(0.,evidence='source-estimate',note='no audio switch site found; absence is not proof'))
    flash=[d for d in drivers if d['dimension']=='flash']
    cycles=[];cycle_paths=[]
    for _,path,value in _facts(summary):
        if '/flashing/records/' in path and isinstance(value,dict) and type(value.get('cycle_rate_hz')) in (int,float) and value['cycle_rate_hz']>0:
            delta=value.get('brightness_delta_range')
            contrast=max(delta) if isinstance(delta,list) and delta and all(type(v) in (int,float) for v in delta) else None
            cycles.append((2*value['cycle_rate_hz'],contrast));cycle_paths.append(path)
    transitions=sum(c[0] for c in cycles);delta=max([c[1] for c in cycles if c[1] is not None],default=0.)
    evidence_flash='source-estimate' if cycles else 'unknown'
    if brightness_elements:
        from approximate_mood import brightness_coverage
        coverage=brightness_coverage(summary,{p.split('/audio_routes/')[0] for p in brightness_paths})
        transitions+=BEAT_HZ*2*min(1.,coverage);delta=max(delta,min(.3,.15*coverage))
        evidence_flash='assumed' if not cycles else 'source-estimate+assumed'
    unresolved_flash=any(d['kind'] in ('unresolved','prior') for d in flash)
    vector['flash.coherent_transitions_hz']=_feature(transitions,[transitions,max(transitions,4. if unresolved_flash else transitions)],
        evidence_flash if (cycles or brightness_elements) else ('unknown' if unresolved_flash else 'source-estimate'),cycle_paths+brightness_paths)
    vector['flash.coherent_delta_peak']=_feature(delta,[delta,max(delta,.3 if unresolved_flash else delta)],
        evidence_flash if (cycles or brightness_elements) else ('unknown' if unresolved_flash else 'source-estimate'),cycle_paths+brightness_paths)
    vector['brightness.jump_p95']=_feature(delta*.5,[delta*.5,max(delta*.5,.3 if unresolved_flash else delta*.5)],'assumed',cycle_paths+brightness_paths)
    from audio_series import audio_drawing_series
    try:series=audio_drawing_series(summary)
    except (ValueError,OSError,KeyError,TypeError):series=None
    if series is not None:
        # Audio-driven drawing evaluated per frame over the declared reference bands (E[f(bands)]).
        note='declared reference band sequence; fresh drawing per frame (feedback and composite excluded)'
        vector['brightness.audio_drawing_mean']=_feature(series['mean'],evidence='source-estimate+declared-audio',note=note)
        vector['brightness.audio_drawing_jump_p95']=_feature(series['delta_p95'],evidence='source-estimate+declared-audio',note=note)
        if series['transitions_hz']>0:
            current=vector['flash.coherent_transitions_hz']
            value=max(current['value'] or 0.,series['transitions_hz'])
            vector['flash.coherent_transitions_hz']=_feature(value,[value,max(value,current['interval'][1])],'source-estimate+declared-audio',
                                                             current['evidence_paths'],note=note)
    else:
        vector['brightness.audio_drawing_mean']=_feature(note='no closed-form audio-driven drawing')
        vector['brightness.audio_drawing_jump_p95']=_feature(note='no closed-form audio-driven drawing')
    vector['audio.bass_peak_rgb_effect']=(_feature(min(.15,.05*coverage),evidence='assumed',paths=brightness_paths,
        note='per audio-brightness element; displayed gain unresolved') if brightness_elements else _feature(0.,evidence='assumed',note='no audio brightness route'))
    vector.update(_palette(summary))
    luma=None
    for _,path,value in _facts(summary):
        if path.endswith('/flat_field') and isinstance(value,dict) and isinstance(value.get('composite_rgb_at_state'),list):
            r,g,b=value['composite_rgb_at_state'];luma=(.2126*r+.7152*g+.0722*b,path)
    vector['brightness.mean_encoded_luma']=_feature(luma[0],evidence='source-estimate',paths=[luma[1]],note='flat-field display colour') if luma else _feature()
    half=None
    for _,path,value in _facts(summary):
        if path.endswith('/feedback_persistence') and isinstance(value,dict):
            span=value.get('steps_to_half_interval')
            if isinstance(span,list) and len(span)==2:half=([v/fps for v in span],path)
    if half is None:
        transfer=next((v for _,p,v in _facts(summary) if p.endswith('/visual_description/feedback_transfer') and isinstance(v,dict)),None) or {}
        gain=transfer.get('uniform_content_gain')
        known=transfer.get('constant_offset_rgb') or transfer.get('constant_offset_rgb_excluding_injection')
        if type(gain) in (int,float) and 0<gain<1:
            offset=min(known) if isinstance(known,list) and known and None not in known else 0.
            level,steps=1.,0
            while level>.5 and steps<10000:level=gain*level+offset;steps+=1
            half=([steps/fps,steps/fps],'/analysis/visual_description/feedback_transfer')
    borders=next((v for _,p,v in _facts(summary) if p.endswith('/static_behaviour/borders') and isinstance(v,dict)),None)
    band=None
    for row in (borders or {}).get('borders') or []:
        if row.get('active') and type(row.get('screen_area_fraction')) in (int,float) and type(row.get('steps_to_half_from_full')) in (int,float):
            if band is None or row['screen_area_fraction']>band[0]:band=(row['screen_area_fraction'],row['steps_to_half_from_full']/fps)
    if band and band[0]>=.5:
        # A border band covering most of the screen sets the typical trail half-life there.
        other=sum(half[0])/2 if half else band[1]
        vector['feedback.half_life_s']=_feature(band[1],[min(band[1],other),max(band[1],other)],'source-estimate',
            ([half[1]] if half else [])+[STATIC+'/borders'],note='border band covers %.0f%% of the screen'%(100*band[0]))
    else:
        vector['feedback.half_life_s']=_feature(sum(half[0])/2,half[0],'source-estimate',[half[1]]) if half else _feature()
    mechanisms={}
    for _,path,value in _facts(summary):
        if path.startswith('/analysis/families/') and isinstance(value,dict):
            # Composite-stage constructions do not accumulate through feedback: weaker evidence.
            factor=COMPOSITE_FACTOR if value.get('stage')=='composite' else 1.
            name=value.get('mechanism')
            if name not in mechanisms or mechanisms[name][0]<factor:mechanisms[name]=(factor,path)
    for name,table in MECHANISM_STRUCTURE.items():
        hits=[(table[m]*factor,p) for m,(factor,p) in mechanisms.items() if m in table]
        if hits:
            score=max(h[0] for h in hits);score=min(1.,score+.05*(len(hits)-1))
            vector['structure.'+name]=_feature(score,evidence='mechanism-estimate',paths=[p for _,p in hits])
        else:vector['structure.'+name]=_feature(DEFAULT_STRUCTURE[name],[0.,DEFAULT_STRUCTURE[name]*2 if DEFAULT_STRUCTURE[name] else .3],'assumed',
                                               note='no supporting mechanism found')
    from mirror_symmetry import mirror_operators
    mirrors=mirror_operators({path:value for _,path,value in _facts(summary)})
    current=vector['structure.symmetry']
    if mirrors['symmetry_score']>0 and (current['evidence']=='assumed' or mirrors['symmetry_score']>current['value']):
        vector['structure.symmetry']=_feature(round(mirrors['symmetry_score'],4),evidence='source-estimate',
            paths=[r['evidence'] for r in mirrors['operators']],note='%d-fold mirror operators (upper estimate)'%mirrors['fold'])
    return vector


def _span(vector,name,scale=1.,offset=0.):
    feature=vector.get(name) or {}
    interval=feature.get('interval')
    if not interval or interval[0] is None:return (0.,1.)
    return tuple(min(1.,max(0.,(v-offset)/scale)) for v in interval)


def _mid(span):return (span[0]+span[1])/2


def scores(vector):
    """Research scoring equations over feature intervals; returns value and interval per score."""
    M,A,J=_span(vector,'motion.speed_p95_vp_s',.75),_span(vector,'motion.acceleration_p95_vp_s2',3.),_span(vector,'motion.jerk_p95_vp_s3',15.)
    T,D=_span(vector,'flash.coherent_transitions_hz',4.),_span(vector,'flash.coherent_delta_peak',.30)
    F=(T[0]*D[0],T[1]*D[1])
    B,R,Q=_span(vector,'brightness.jump_p95',.30),_span(vector,'audio.bass_peak_rgb_effect',.20),_span(vector,'motion.discontinuities_hz',2.)
    def intensity(i):
        base=1+99*(.28*M[i]+.12*A[i]+.08*J[i]+.32*F[i]+.12*B[i]+.08*R[i])
        return max(base,1+99*F[i])
    smooth=lambda i:100*(1-.35*A[1-i]-.45*J[1-i]-.20*Q[1-i])
    warm=vector.get('palette.warm_cool') or {}
    hue=_span(vector,'palette.effective_hue_bins',7.,1.);rate=_span(vector,'palette.hue_rate_p95_cycles_s',.5)
    S=lambda name:_span(vector,'structure.'+name)
    psych=lambda i:100*(.20*hue[i]+.25*S('nonlinear_warp')[i]+.25*S('feedback_complexity')[i]+.20*S('symmetry')[i]+.10*rate[i])
    result={'intensity':[intensity(0),intensity(1)],'smoothness':[smooth(0),smooth(1)],'psychedelic':[psych(0),psych(1)]}
    if warm.get('interval') and warm['interval'][0] is not None:
        result['warm']=[50*(1+warm['interval'][0]),50*(1+warm['interval'][1])]
        result['cold']=[50*(1-warm['interval'][1]),50*(1-warm['interval'][0])]
    else:result['warm']=result['cold']=[0.,100.]
    out={}
    for name,(low,high) in result.items():
        low,high=sorted((max(0.,min(100.,low)),max(0.,min(100.,high))))
        point={'intensity':intensity,'smoothness':None,'psychedelic':None}.get(name)
        out[name]={'interval':[round(low,2),round(high,2)]}
    # Point estimates from feature values (interval midpoints are not the estimate).
    value=lambda name,scale=1.,offset=0.:min(1.,max(0.,((vector.get(name) or {}).get('value') or 0.)-offset)/scale) if (vector.get(name) or {}).get('value') is not None else None
    m,a,j=value('motion.speed_p95_vp_s',.75) or 0.,value('motion.acceleration_p95_vp_s2',3.) or 0.,value('motion.jerk_p95_vp_s3',15.) or 0.
    f=(value('flash.coherent_transitions_hz',4.) or 0.)*(value('flash.coherent_delta_peak',.3) or 0.)
    b,r,q=value('brightness.jump_p95',.3) or 0.,value('audio.bass_peak_rgb_effect',.2) or 0.,value('motion.discontinuities_hz',2.) or 0.
    out['intensity']['value']=round(max(1+99*(.28*m+.12*a+.08*j+.32*f+.12*b+.08*r),1+99*f),2)
    out['smoothness']['value']=round(100*(1-.35*a-.45*j-.20*q),2)
    hv=value('palette.effective_hue_bins',7.,1.) or 0.;rv=value('palette.hue_rate_p95_cycles_s',.5) or 0.
    sv=lambda name:value('structure.'+name) or 0.
    out['psychedelic']['value']=round(100*(.20*hv+.25*sv('nonlinear_warp')+.25*sv('feedback_complexity')+.20*sv('symmetry')+.10*rv),2)
    wc=warm.get('value')
    out['warm']['value']=None if wc is None else round(50*(1+wc),2)
    out['cold']['value']=None if wc is None else round(50*(1-wc),2)
    return out


def tags(vector,score):
    """Style/mood tags from the research rules; each carries the evidence it used."""
    v=lambda name:(vector.get(name) or {}).get('value')
    rows=[]
    def tag(name,condition,used):
        if not condition:return
        basis={(vector.get(f) or {}).get('evidence','') for f in used if not f.startswith('score.') and not f.endswith('*')}
        if any(f.endswith('*') for f in used):
            prefix=used[[f.endswith('*') for f in used].index(True)][:-1]
            basis|={v.get('evidence','') for k,v in vector.items() if k.startswith(prefix)}
        assumed=bool(basis) and all(b.startswith('assumed') or b=='unknown' for b in basis)
        rows.append({'tag':name,'features':used,'basis':'assumed' if assumed else 'estimated'})
    tag('Smooth',score['smoothness']['value']>=80,['score.smoothness'])
    wc=v('palette.warm_cool');support=v('palette.coloured_support') or 0
    tag('Warm',wc is not None and wc>=.4 and support>=.2,['palette.warm_cool','palette.coloured_support'])
    tag('Cold',wc is not None and wc<=-.4 and support>=.2,['palette.warm_cool','palette.coloured_support'])
    structural=sum(1 for n in ('nonlinear_warp','feedback_complexity','symmetry') if (v('structure.'+n) or 0)>=.6)
    tag('Psychedelic',score['psychedelic']['value']>=60 and structural>=2,['score.psychedelic','structure.*'])
    tag('Hypnotic',(v('structure.symmetry') or 0)>=.55 and (v('motion.discontinuities_hz') or 0)==0 and score['smoothness']['value']>=75,
        ['structure.symmetry','motion.discontinuities_hz','score.smoothness'])
    tag('Geometric',(v('structure.geometric') or 0)>=.6,['structure.geometric'])
    tag('Organic / Liquid',(v('structure.organic') or 0)>=.6,['structure.organic'])
    tag('Fractal',(v('structure.fractal') or 0)>=.8,['structure.fractal'])
    luma=v('brightness.mean_encoded_luma')
    tag('Dark',luma is not None and luma<=.2,['brightness.mean_encoded_luma'])
    tag('Bright / Vibrant',luma is not None and luma>=.3 and (v('palette.mean_saturation') or 0)>=.65,['brightness.mean_encoded_luma','palette.mean_saturation'])
    tag('Reactive',(v('audio.bass_peak_rgb_effect') or 0)>=.05 or (v('motion.discontinuities_hz') or 0)>0,['audio.bass_peak_rgb_effect','motion.discontinuities_hz'])
    tag('Flashing',(v('flash.coherent_transitions_hz') or 0)*(v('flash.coherent_delta_peak') or 0)>=.2,['flash.*'])
    return rows


def _fit(x,target,scale):
    low,high=target
    distance=max(low-x,0,x-high)/scale
    return math.exp(-.5*distance*distance)


def suitability(vector,score,profiles=None):
    """Research suitability formula against editable profiles (mood_profiles.PROFILES by default)."""
    from mood_profiles import PROFILES
    profiles=PROFILES if profiles is None else profiles
    out={}
    for name,profile in profiles.items():
        total=0.;weights=0.;missing=0.
        for preference in profile['preferences']:
            feature=preference['feature']
            if feature.startswith('score.'):x=(score.get(feature[6:]) or {}).get('value')
            else:x=(vector.get(feature) or {}).get('value')
            if x is None:missing+=preference['weight'];continue
            total+=preference['weight']*_fit(x,preference['target'],preference['scale']);weights+=preference['weight']
        constraints=[]
        for rule in profile.get('constraints',[]):
            feature=rule['feature'].replace('_upper_bound_','_p95_')
            entry=vector.get(feature) or {}
            upper=(entry.get('interval') or [None,None])[1];x=entry.get('value')
            state='unknown' if x is None else 'violated' if x>rule.get('maximum',math.inf) else 'estimated_pass' if (upper or x)<=rule.get('maximum',math.inf) else 'uncertain'
            constraints.append({'feature':rule['feature'],'state':state})
        coverage=weights/(weights+missing) if weights+missing else 0.
        out[name]={'suitability':round(100*total/weights,1) if weights else None,'preference_coverage':round(coverage,2),
                   'constraints_violated':[c['feature'] for c in constraints if c['state']=='violated'],
                   'constraints_unresolved':[c['feature'] for c in constraints if c['state'] in ('unknown','uncertain')]}
    return out


def describe(summary,rules=None,profiles=None):
    """Full approximate record: features, scores, activity bands, tags and profile suitability."""
    if not isinstance(summary,dict) or summary.get('policy')!='preset-understanding-v1':
        raise ValueError('preset-understanding-v1 summary required')
    vector=feature_vector(summary,rules)
    score=scores(vector)
    value=score['intensity']['value'];interval=score['intensity']['interval']
    bands=[name for name,a,b in BANDS if a<=value<=b]
    possible=[name for name,a,b in BANDS if interval[0]<=b and interval[1]>=a]
    unknown=[n for n,f in vector.items() if f['evidence']=='unknown']
    assumed=[n for n,f in vector.items() if f['evidence'].startswith('assumed') or f['evidence'].endswith('assumed')]
    # Activity confidence depends on the intensity interval only; missing palette
    # evidence limits palette preferences, not the activity band.
    width=interval[1]-interval[0]
    activity_unknown='motion.speed_p95_vp_s' in unknown
    confidence='high' if width<=15 and not activity_unknown else 'medium' if width<=50 and not activity_unknown else 'low'
    return {'policy':POLICY,'features':vector,'scores':score,'activity_bands':bands if confidence!='low' else [],
        'possible_activity_bands':possible,'confidence':confidence,'unknown_features':unknown,'assumed_features':assumed,
        'tags':[t for t in tags(vector,score) if t['basis']=='estimated'],
        'possible_tags':[t for t in tags(vector,score) if t['basis']=='assumed'],'profiles':suitability(vector,score,profiles),'calibrated':False,'uses_rendered_images':False,
        'limitations':['Initial research equations and editable assumptions over SDK facts; not calibrated against viewers',
                       'Acceleration/jerk use assumed angular rates; structure scores come from proven mechanisms, not measured appearance',
                       'Strict source eligibility (mood_scoring.py) is separate and unchanged']}
