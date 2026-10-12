"""Source-only understanding and approximate mood grouping for a whole preset pack.

For every preset: parse with the pinned native reader, export static source
facts (no rendering, no frame simulation), summarise them with the
understanding SDK and estimate the editable approximate activity/mood. Results
are compact per-preset JSON files (resumable by preset hash) plus an aggregate
report with band collections. Strict source eligibility is kept separately;
approximate bands are assumption-based preference groups, not calibrated moods.
"""
import argparse
import base64
import collections
import gzip
import multiprocessing
import hashlib
import json
from pathlib import Path
import signal
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
POLICY='source-corpus-understanding-v1'


def _initialize():
    if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))


class _Timeout(Exception):
    pass


def _alarm(signum,frame):
    raise _Timeout('per-preset time budget exceeded')


def work(path,options,expected_models):
    _initialize()
    from effect_family_export import export_preset,loaded_model_hashes
    from preset_understanding import summarize_preset
    from approximate_mood import approximate_mood
    started=time.perf_counter()
    raw=Path(path).read_bytes()
    row={'name':Path(path).name,'sha256':hashlib.sha256(raw).hexdigest(),'status':'error'}
    try:
        signal.signal(signal.SIGALRM,_alarm);signal.alarm(int(options['timeout']))
        if loaded_model_hashes()!=expected_models:raise ValueError('worker model identity changed')
        record,_=export_preset(path,reader=options['reader'],input_scenario=options['input_scenario'],
                               behaviour_context=options['behaviour_context'])
        if record.get('status')!='computed':
            row.update(status=record.get('status','error'),error=record.get('error'))
            return row
        summary=summarize_preset(record)
        display=_display_estimate(summary,options.get('display_model'))
        mood=approximate_mood(summary,options.get('rules'),display)
        # Compressed SDK summary allows offline rescoring without re-export.
        packed=base64.b64encode(gzip.compress(json.dumps(summary,separators=(',',':')).encode(),compresslevel=6)).decode()
        row['preference']=_preference_row(summary,options.get('rules'),display)
        row.update(status='computed',description=summary['description'],summary_gzip_base64=packed,
            approximate_mood=_mood_row(mood),
            drivers=[{k:d[k] for k in ('dimension','kind','value','reason','evidence_path')} for d in mood['drivers']],
            record_sha256=record.get('record_sha256'))
    except BaseException as error:
        if isinstance(error,KeyboardInterrupt):raise
        row.update(status='timeout' if isinstance(error,_Timeout) else 'error',error_type=type(error).__name__,error=str(error)[:500])
    finally:
        try:signal.alarm(0)
        except _Timeout:pass
        row['elapsed_seconds']=round(time.perf_counter()-started,3)
    return row


def _display_estimate(summary,model_path=None):
    """Source-calibrated display estimate when a calibrated display model is available."""
    from calibrated_display import load,predict
    model=load(model_path)
    return predict(summary,model) if model is not None else None


def _star_work(arguments):
    return work(*arguments)


def _preference_row(summary,rules=None,display=None):
    """Compact multi-axis record for preference selection (approximate_features) with Mood facets.

    Facets use the measured facet bundle row for a bundled preset, otherwise the source-calibrated
    display statistics passed in (preset_recipe.facets_block); no simulation output is read."""
    from approximate_features import describe
    from preset_recipe import facets_block
    record=describe(summary,rules)
    return {'facets':facets_block(summary,{'statistics':display} if display is not None else {}),'scores':{k:v['value'] for k,v in record['scores'].items()},
            'score_intervals':{k:v['interval'] for k,v in record['scores'].items()},
            'features':{k:{'value':v['value'],'interval':v['interval'],'evidence':v['evidence']} for k,v in record['features'].items()},
            'tags':[t['tag'] for t in record['tags']],'possible_tags':[t['tag'] for t in record['possible_tags']],
            'activity_bands':record['activity_bands'],
            'possible_activity_bands':record['possible_activity_bands'],'confidence':record['confidence'],
            'profiles':record['profiles']}


def _mood_row(mood):
    return {k:mood.get(k) for k in ('activity_estimate','activity_interval','bands','possible_bands','confidence',
                                    'prior_driver_share','components','strict_eligible_bands','abstained','unresolved_driver_count',
                                    'band_source','display_activity')}


def rescore(output,rules=None,display_model=None):
    """Recompute approximate moods from saved summaries; rows keep their identity."""
    _initialize()
    from approximate_mood import approximate_mood
    for path in sorted((output/'results').glob('*.json')):
        row=json.loads(path.read_text())
        if row.get('status')!='computed' or 'summary_gzip_base64' not in row:continue
        summary=json.loads(gzip.decompress(base64.b64decode(row['summary_gzip_base64'])))
        display=_display_estimate(summary,display_model)
        mood=approximate_mood(summary,rules,display)
        row['approximate_mood']=_mood_row(mood)
        row['preference']=_preference_row(summary,rules,display)
        row['drivers']=[{k:d[k] for k in ('dimension','kind','value','reason','evidence_path')} for d in mood['drivers']]
        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(row)+'\n');temporary.replace(path)
    return report(output)


def report(output):
    rows=[json.loads(p.read_text()) for p in sorted((output/'results').glob('*.json'))]
    computed=[r for r in rows if r['status']=='computed']
    bands=collections.Counter();confidence=collections.Counter();collections_by_band=collections.defaultdict(list)
    abstained=0
    for row in computed:
        mood=row['approximate_mood'];confidence[mood['confidence']]+=1
        abstained+=not mood['bands']
        for band in mood['bands']:
            bands[band]+=1;collections_by_band[band].append({'name':row['name'],'activity':mood['activity_estimate'],
                                                             'confidence':mood['confidence']})
    for band in collections_by_band:collections_by_band[band].sort(key=lambda r:r['activity'])
    summary={'policy':POLICY,'presets':len(rows),'status':dict(collections.Counter(r['status'] for r in rows)),
        'approximate_band_counts':dict(bands),'confidence_counts':dict(confidence),'abstained_presets':abstained,
        'strict_eligible_presets':sum(1 for r in computed if r['approximate_mood'].get('strict_eligible_bands')),
        'activity_histogram':dict(sorted(collections.Counter(int(r['approximate_mood']['activity_estimate']//10)*10 for r in computed).items())),
        'calibrated':False,'uses_rendered_images':False,
        'notes':['Approximate bands are editable assumption-based preference groups, not calibrated moods',
                 'Confidence reflects the share of prior-only drivers; low-confidence presets need more source mathematics']}
    index={'policy':'preset-preference-index-v1','presets':[
        {'name':r['name'],'sha256':r['sha256'],**{k:r['preference'].get(k) for k in ('scores','tags','possible_tags','activity_bands','confidence','profiles')},
         **({'facets':r['preference']['facets']} if r['preference'].get('facets') is not None else {}),
         'features':{k:v['value'] for k,v in r['preference']['features'].items()},
         'evidence':{k:v['evidence'] for k,v in r['preference']['features'].items()}}
        for r in computed if 'preference' in r],'calibrated':False}
    (output/'preference-index.json').write_text(json.dumps(index,separators=(',',':'))+'\n')
    tags=collections.Counter(t for r in computed for t in (r.get('preference') or {}).get('tags',[]))
    summary['tag_counts']=dict(tags.most_common())
    (output/'report.json').write_text(json.dumps(summary,indent=2)+'\n')
    (output/'collections.json').write_text(json.dumps(collections_by_band,indent=1)+'\n')
    return summary


def main(argv=None):
    _initialize()
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--presets',type=Path,default=ROOT/'core/src/main/assets/presets')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reader',type=Path,default=ROOT/'build/preset-corpus/source34/adapters/milk-native-reader')
    parser.add_argument('--input-scenario',type=Path)
    parser.add_argument('--behaviour-context',type=Path)
    parser.add_argument('--rules',type=Path,help='approximate mood rule overrides (JSON)')
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--timeout',type=int,default=180)
    parser.add_argument('--limit',type=int)
    parser.add_argument('--report-only',action='store_true')
    parser.add_argument('--rescore',action='store_true',help='recompute approximate moods from saved summaries')
    parser.add_argument('--display-model',type=Path,help='source-calibrated display model (calibrated_display JSON tree model)')
    args=parser.parse_args(argv)
    display_model=str(args.display_model.resolve()) if args.display_model else None
    if args.report_only:
        print(json.dumps(report(args.output),indent=2));return
    if args.rescore:
        rules=json.loads(args.rules.read_text()) if args.rules else None
        print(json.dumps(rescore(args.output,rules,display_model),indent=2));return
    from effect_family_export import loaded_model_hashes
    models=loaded_model_hashes()
    options={'reader':str(args.reader.resolve()),'timeout':args.timeout,
             'input_scenario':json.loads(args.input_scenario.read_text()) if args.input_scenario else None,
             'behaviour_context':json.loads(args.behaviour_context.read_text()) if args.behaviour_context else None,
             'rules':json.loads(args.rules.read_text()) if args.rules else None,
             **({'display_model':display_model} if display_model else {})}
    (args.output/'results').mkdir(parents=True,exist_ok=True)
    manifest_path=args.output/'run-manifest.json'
    manifest={'policy':POLICY,'model_modules':models,'options':{k:v for k,v in options.items() if k!='timeout'},
              'reader_sha256':hashlib.sha256(Path(options['reader']).read_bytes()).hexdigest(),
              'presets_directory':str(args.presets)}
    if manifest_path.exists():
        previous=json.loads(manifest_path.read_text())
        if previous!=manifest:raise SystemExit('run identity changed; use a new output directory')
    else:manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    paths=sorted(p for p in args.presets.iterdir() if p.suffix=='.milk')
    if args.limit:paths=paths[:args.limit]
    # Resume only rows computed for the same preset bytes; errors/timeouts retry.
    done={}
    for result in (args.output/'results').glob('*.json'):
        row=json.loads(result.read_text())
        if row.get('status')=='computed':done[row['name']]=row.get('sha256')
    pending=[p for p in paths if done.get(p.name)!=hashlib.sha256(p.read_bytes()).hexdigest()]
    print(json.dumps({'event':'ready','presets':len(paths),'pending':len(pending)}),flush=True)
    completed=0
    # multiprocessing.Pool recycles workers safely; ProcessPoolExecutor with
    # max_tasks_per_child deadlocked once every worker had been retired.
    tasks=[(str(path),options,models) for path in pending]
    with multiprocessing.get_context('spawn').Pool(args.workers,maxtasksperchild=200) as pool:
        for row in pool.imap_unordered(_star_work,tasks,chunksize=4):
            key=hashlib.sha256(row['name'].encode()).hexdigest()[:20]
            target=args.output/'results'/(key+'.json')
            temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(row)+'\n');temporary.replace(target)
            completed+=1
            if completed%200==0:print(json.dumps({'event':'progress','completed':completed,'pending':len(pending)}),flush=True)
    print(json.dumps({'event':'finished',**report(args.output)}),flush=True)


if __name__=='__main__':
    main()
