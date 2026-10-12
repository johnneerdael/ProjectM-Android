"""Select presets for an editable user preference file (standard library only).

Reads ``preference-index.json`` written by corpus_understanding and a user
preference JSON, and returns ranked presets with reasons. Example preference:

    {"profiles": ["melodic-techno-v1"],          # mood/genre/viewing profiles (mood_profiles ids)
     "activity": [25, 60],                        # optional intensity window (1-100)
     "comfort": {"no_flashing": true, "min_smoothness": 80, "max_speed_vp_s": 0.3},
     "palette": "cold",                           # "warm", "cold" or null
     "prefer_tags": ["Psychedelic", "Hypnotic"],  # bonus per matching tag
     "avoid_tags": ["Flashing"],                  # penalty per matching tag
     "min_confidence": "medium",                  # "low", "medium" or "high"
     "feedback": {"liked": ["A.milk"], "disliked": ["B.milk"],
                  "too_fast": ["C.milk"], "too_flashy": [], "too_dark": [], "too_bright": []},
     "facets": ["chill", "no_strobe"],            # Mood facet option ids (OR within a group, AND across groups)
     "limit": 50}

Feedback works directly on the feature vectors: liked/disliked presets give a
similarity bonus/penalty (standardised feature distance, so it works even
where activity estimates are imperfect), and complaints tighten comfort rules
relative to the named preset (too_fast caps speed below it, too_flashy
enables no_flashing, too_dark/too_bright bound the display luma).

Facets select with the Mood facet semantics (preset_facets.select: OR within a
group, AND across groups, unknown option ids ignored) over each index entry's
``facets.options``; the facet pool is intersected with every other filter, and
the facet counts (option_counts, dimmed) are computed over the presets those
other filters keep. An entry without a facets block matches no facet request.

Comfort rules are hard filters. A preset whose evidence for a comfort rule is
unknown or only assumed is excluded under "no_flashing"; for numeric limits an
unknown value excludes, an estimate is compared with the limit. Scores and
profiles are editable research assumptions, not calibrated preferences.
"""
import json
import math

POLICY='preset-preference-selection-v1'
CONFIDENCE={'low':0,'medium':1,'high':2}
TAG_WEIGHT=8.0


def validate(preference):
    if not isinstance(preference,dict):raise ValueError('preference must be a JSON object')
    allowed={'profiles','activity','comfort','palette','prefer_tags','avoid_tags','min_confidence','limit','feedback','facets'}
    unknown=set(preference)-allowed
    if unknown:raise ValueError('unknown preference fields: '+', '.join(sorted(unknown)))
    activity=preference.get('activity')
    if activity is not None and (not isinstance(activity,list) or len(activity)!=2 or not 1<=activity[0]<=activity[1]<=100):
        raise ValueError('activity must be [low, high] within 1..100')
    if preference.get('palette') not in (None,'warm','cold'):raise ValueError('palette must be warm, cold or null')
    if preference.get('min_confidence','low') not in CONFIDENCE:raise ValueError('min_confidence must be low, medium or high')
    facets=preference.get('facets')
    if facets is not None and (not isinstance(facets,list) or not all(isinstance(f,str) for f in facets)):
        raise ValueError('facets must be a list of facet option ids')
    return preference


def _comfort(entry,comfort,reasons):
    features=entry['features'];evidence=entry['evidence']
    if comfort.get('no_flashing'):
        transitions=features.get('flash.coherent_transitions_hz')
        if transitions is None or evidence.get('flash.coherent_transitions_hz')=='unknown':
            reasons.append('flashing evidence unknown');return False
        if transitions>0:reasons.append('flashing %.2g transitions/s'%transitions);return False
        if 'Flashing' in entry['tags']:reasons.append('tagged Flashing');return False
    smooth=comfort.get('min_smoothness')
    if smooth is not None and (entry['scores'].get('smoothness') is None or entry['scores']['smoothness']<smooth):
        reasons.append('smoothness below %g'%smooth);return False
    speed=comfort.get('max_speed_vp_s')
    if speed is not None:
        value=features.get('motion.speed_p95_vp_s')
        if value is None:reasons.append('speed unknown');return False
        if value>speed:reasons.append('speed %.2g above %g'%(value,speed));return False
    luma=features.get('brightness.mean_encoded_luma')
    for bound,test in (('min_luma',lambda v,b:v>=b),('max_luma',lambda v,b:v<=b)):
        if comfort.get(bound) is not None and (luma is None or not test(luma,comfort[bound])):
            reasons.append('brightness outside '+bound);return False
    return True


SIMILARITY_FEATURES=('motion.speed_p95_vp_s','motion.acceleration_p95_vp_s2','flash.coherent_transitions_hz','flash.coherent_delta_peak',
    'palette.mean_saturation','palette.effective_hue_bins','palette.warm_cool','palette.hue_rate_p95_cycles_s',
    'brightness.mean_encoded_luma','feedback.half_life_s','structure.symmetry','structure.nonlinear_warp',
    'structure.feedback_complexity','structure.organic','structure.geometric','structure.fractal')
SIMILARITY_WEIGHT=20.0


def _standardiser(index):
    stats={}
    for name in SIMILARITY_FEATURES:
        values=[e['features'].get(name) for e in index['presets'] if e['features'].get(name) is not None]
        if len(values)<2:continue
        mean=sum(values)/len(values);spread=math.sqrt(sum((v-mean)**2 for v in values)/len(values)) or 1.
        stats[name]=(mean,spread)
    return stats


def _vector(entry,stats):
    return {name:(entry['features'][name]-mean)/spread for name,(mean,spread) in stats.items() if entry['features'].get(name) is not None}


def _similarity(a,b):
    shared=set(a)&set(b)
    if len(shared)<4:return None
    distance=math.sqrt(sum((a[k]-b[k])**2 for k in shared)/len(shared))
    return math.exp(-distance)


def _apply_feedback(index,preference):
    """Turn feedback into comfort tightening and liked/disliked reference vectors."""
    feedback=preference.get('feedback') or {}
    by_name={e['name']:e for e in index['presets']}
    comfort=dict(preference.get('comfort') or {});notes=[]
    for name in feedback.get('too_fast',[]):
        speed=(by_name.get(name) or {}).get('features',{}).get('motion.speed_p95_vp_s')
        if speed is not None:
            comfort['max_speed_vp_s']=min(comfort.get('max_speed_vp_s',math.inf),speed*.8);notes.append('speed capped below '+name)
    if feedback.get('too_flashy'):comfort['no_flashing']=True;notes.append('no flashing (feedback)')
    for key,bound in (('too_dark','min_luma'),('too_bright','max_luma')):
        for name in feedback.get(key,[]):
            luma=(by_name.get(name) or {}).get('features',{}).get('brightness.mean_encoded_luma')
            if luma is not None:
                comfort[bound]=max(comfort.get(bound,-math.inf),luma*1.2) if bound=='min_luma' else min(comfort.get(bound,math.inf),luma*.8)
                notes.append(bound+' from '+name)
    stats=_standardiser(index)
    liked=[_vector(by_name[n],stats) for n in feedback.get('liked',[]) if n in by_name]
    disliked=[_vector(by_name[n],stats) for n in feedback.get('disliked',[]) if n in by_name]
    exclude=set(feedback.get('disliked',[]))|set(feedback.get('too_fast',[]))|set(feedback.get('too_flashy',[]))
    return comfort,stats,liked,disliked,exclude,notes


def select(index,preference):
    """Rank presets for one preference; returns selected and excluded counts with reasons."""
    preference=validate(preference)
    profiles=preference.get('profiles') or []
    activity=preference.get('activity')
    comfort,stats,liked,disliked,feedback_excluded,feedback_notes=_apply_feedback(index,preference)
    prefer=set(preference.get('prefer_tags') or []);avoid=set(preference.get('avoid_tags') or [])
    minimum=CONFIDENCE[preference.get('min_confidence','low')]
    palette=preference.get('palette')
    ranked=[];excluded={}
    for entry in index['presets']:
        reasons=[]
        if entry['name'] in feedback_excluded:excluded['rejected in feedback']=excluded.get('rejected in feedback',0)+1;continue
        if CONFIDENCE.get(entry.get('confidence'),0)<minimum:excluded['confidence below '+preference['min_confidence']]=excluded.get('confidence below '+preference['min_confidence'],0)+1;continue
        if not _comfort(entry,comfort,reasons):
            key=reasons[0].split(' ')[0]+' comfort rule';excluded[key]=excluded.get(key,0)+1;continue
        intensity=entry['scores'].get('intensity')
        if activity and (intensity is None or not activity[0]<=intensity<=activity[1]):
            excluded['outside activity window']=excluded.get('outside activity window',0)+1;continue
        if palette:
            tag='Warm' if palette=='warm' else 'Cold'
            if tag not in entry['tags']:excluded['palette not '+palette]=excluded.get('palette not '+palette,0)+1;continue
        suitabilities=[(entry['profiles'].get(name) or {}).get('suitability') for name in profiles]
        known=[v for v in suitabilities if v is not None]
        if profiles and not known:excluded['profile suitability unknown']=excluded.get('profile suitability unknown',0)+1;continue
        base=sum(known)/len(known) if known else 50.
        violated=[c for name in profiles for c in (entry['profiles'].get(name) or {}).get('constraints_violated',[])]
        # Avoided tags also count when only assumed (conservative); preferred tags need estimates.
        possible=set(entry.get('possible_tags') or [])
        score=(base+TAG_WEIGHT*len(prefer & set(entry['tags']))-TAG_WEIGHT*len(avoid & set(entry['tags']))
               -TAG_WEIGHT/2*len(avoid & possible)-10*len(violated))
        why=['profile suitability %.0f'%base] if known else []
        why+=['tag '+t for t in sorted(prefer & set(entry['tags']))]+['avoided tag '+t for t in sorted(avoid & set(entry['tags']))]
        why+=['possibly '+t for t in sorted(avoid & possible)]
        why+=['profile constraint '+c for c in violated]
        if liked or disliked:
            vector=_vector(entry,stats)
            like=max([_similarity(vector,v) or 0. for v in liked],default=0.)
            dislike=max([_similarity(vector,v) or 0. for v in disliked],default=0.)
            score+=SIMILARITY_WEIGHT*(like-dislike)
            if like>.5:why.append('similar to a liked preset (%.2f)'%like)
            if dislike>.5:why.append('similar to a disliked preset (%.2f)'%dislike)
        ranked.append({'name':entry['name'],'score':round(score,1),'intensity':intensity,
                       'smoothness':entry['scores'].get('smoothness'),'tags':entry['tags'],'confidence':entry.get('confidence'),'reasons':why})
    facets=None
    if preference.get('facets') is not None:
        import preset_facets
        definition=preset_facets.load_definition()
        kept={r['name'] for r in ranked}
        rows=[{'name':e['name'],'options':list((e.get('facets') or {}).get('options') or [])} for e in index['presets']]
        result=preset_facets.select(rows,preference['facets'],definition,excluded=[r['name'] for r in rows if r['name'] not in kept])
        pool=set(result['pool'])
        missed=sum(1 for r in ranked if r['name'] not in pool)
        if missed:excluded['not in the facet selection']=missed
        ranked=[r for r in ranked if r['name'] in pool]
        facets={k:result[k] for k in ('selected','ignored','count','option_counts','dimmed')}
    ranked.sort(key=lambda r:(-r['score'],r['name']))
    limit=preference.get('limit',50)
    extra={'facets':facets} if facets is not None else {}
    return {'policy':POLICY,**extra,'preference':preference,'feedback_applied':feedback_notes,'effective_comfort':comfort,
            'candidates':len(index['presets']),'matched':len(ranked),
            'excluded':dict(sorted(excluded.items(),key=lambda item:-item[1])),'selected':ranked[:limit],
            'calibrated':False,'note':'Approximate source-based preferences; strict certified eligibility is separate'}


def main(argv=None):
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('index',type=Path,help='preference-index.json from corpus_understanding')
    parser.add_argument('preference',type=Path,help='user preference JSON')
    args=parser.parse_args(argv)
    result=select(json.loads(args.index.read_text()),json.loads(args.preference.read_text()))
    print(json.dumps(result,indent=1))


if __name__=='__main__':
    main()
