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
     "limit": 50}

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
    allowed={'profiles','activity','comfort','palette','prefer_tags','avoid_tags','min_confidence','limit'}
    unknown=set(preference)-allowed
    if unknown:raise ValueError('unknown preference fields: '+', '.join(sorted(unknown)))
    activity=preference.get('activity')
    if activity is not None and (not isinstance(activity,list) or len(activity)!=2 or not 1<=activity[0]<=activity[1]<=100):
        raise ValueError('activity must be [low, high] within 1..100')
    if preference.get('palette') not in (None,'warm','cold'):raise ValueError('palette must be warm, cold or null')
    if preference.get('min_confidence','low') not in CONFIDENCE:raise ValueError('min_confidence must be low, medium or high')
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
    return True


def select(index,preference):
    """Rank presets for one preference; returns selected and excluded counts with reasons."""
    preference=validate(preference)
    profiles=preference.get('profiles') or []
    activity=preference.get('activity');comfort=preference.get('comfort') or {}
    prefer=set(preference.get('prefer_tags') or []);avoid=set(preference.get('avoid_tags') or [])
    minimum=CONFIDENCE[preference.get('min_confidence','low')]
    palette=preference.get('palette')
    ranked=[];excluded={}
    for entry in index['presets']:
        reasons=[]
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
        ranked.append({'name':entry['name'],'score':round(score,1),'intensity':intensity,
                       'smoothness':entry['scores'].get('smoothness'),'tags':entry['tags'],'confidence':entry.get('confidence'),'reasons':why})
    ranked.sort(key=lambda r:(-r['score'],r['name']))
    limit=preference.get('limit',50)
    return {'policy':POLICY,'preference':preference,'candidates':len(index['presets']),'matched':len(ranked),
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
