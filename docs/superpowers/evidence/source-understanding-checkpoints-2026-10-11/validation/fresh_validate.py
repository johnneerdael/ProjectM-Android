import json,sys,collections
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
def run(name):
    sys.path.insert(0,str(ROOT/'tools/milk-analyzer'))
    from effect_family_export import export_preset
    from preset_understanding import summarize_preset
    from approximate_mood import approximate_mood
    context=json.loads(Path(sys.argv[1] if len(sys.argv)>1 else ROOT/'build/preset-corpus/spiral-layer-spacing-context-2026-10-11.json').read_text())
    record,_=export_preset(ROOT/'core/src/main/assets/presets'/name,reader=ROOT/'build/preset-corpus/source34/adapters/milk-native-reader',
        input_scenario=json.loads((ROOT/'build/preset-corpus/source-sample-offset-scenario.json').read_text()),behaviour_context=context)
    mood=approximate_mood(summarize_preset(record))
    return name,mood
def main():
    obs=json.loads((ROOT/'build/validation-activity-2026-10-11/observations.json').read_text())
    names=[n for n,o in obs.items() if o['status']=='observed']
    with ProcessPoolExecutor(8) as pool:moods=dict(pool.map(run,names))
    rank=lambda a:np.argsort(np.argsort(np.array(a)))
    sp=lambda a,b:float(np.corrcoef(rank(a),rank(b))[0,1])
    flow=np.array([obs[n]['mean_flow_screen_widths_per_s'] for n in names]);diff=np.array([obs[n]['mean_abs_frame_difference'] for n in names]);jumps=np.array([obs[n]['global_brightness_jumps_per_10s'] for n in names])
    observed=flow/np.median(flow)+diff/np.median(diff)+np.minimum(jumps,60)/20
    est=[moods[n]['activity_estimate'] for n in names]
    motion=[moods[n]['components']['motion'] for n in names]
    print('n',len(names),'est~observed %.2f est~flow %.2f motion~flow %.2f est~jumps %.2f'%(sp(est,observed),sp(est,flow),sp(motion,flow),sp(est,jumps)))
    conf=[i for i,n in enumerate(names) if moods[n]['confidence']!='low']
    print('confident n',len(conf),'est~observed %.2f'%sp([est[i] for i in conf],[observed[i] for i in conf]) if len(conf)>3 else '')
    adv=sum(1 for n in names if any('self-advection' in d['reason'] or 'lookup motion' in d['reason'] for d in moods[n]['drivers']))
    print('presets with advection/lookup source drivers',adv)
    json.dump({n:{k:moods[n][k] for k in ('activity_estimate','confidence','components','bands')} for n in names},open(ROOT/'build/validation-activity-2026-10-11/fresh-moods.json','w'),indent=1)


if __name__=='__main__':
    main()
