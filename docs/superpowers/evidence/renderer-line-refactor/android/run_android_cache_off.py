from pathlib import Path
import hashlib, importlib.util, json, sys
root=Path('/Users/jneerdael/Scripts/Projectm-TV/.worktrees/renderer-line-refactor')
p=root/'tools/native-trails/run_validation.py'
spec=importlib.util.spec_from_file_location('line_refactor_runner',p); runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
runner.PROFILES=[
 ('baseline_legacy','baseline-native',3840,2160,1024,768,-1),
 ('candidate_legacy','candidate-native',3840,2160,1024,768,-1),
 ('baseline_standard','baseline-native',3840,2160,1280,720,0),
 ('candidate_standard','candidate-native',3840,2160,1280,720,0),
]
for role in ['baseline-native','candidate-native']:
 identity=json.loads((Path('/tmp/projectmtv-line-refactor/android-workers-cache-off')/role/'identity.json').read_text())
 assert identity.get('validation_settings',{}).get('shaderBinaryCache') is False
work=Path(sys.argv[1]);work.mkdir(parents=True,exist_ok=False)
(work/'caller.json').write_text(json.dumps({'orchestrator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'base_runner_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'shaderBinaryCache':False,'scope':'same settings before/after architecture refactor; explicit baseline/candidate Native off and Standard; instrumented actual core AAR; emulator engine timing, not physical-TV app FPS'},indent=2)+'\n')
selected=sys.argv[2:] or None
runner.run(work,Path('/tmp/projectmtv-line-refactor/android-workers-cache-off'),Path('/tmp/projectmtv-line-refactor/device-presets.txt'),'emulator-5674',selected)
rows=json.loads((work/'progress.json').read_text())['finished']
for row in rows:
 if row['profile'].endswith('standard'):
  status=str(row['trail_status']).lower();assert 'standard' in status and '1280×720' in status and 'fallback' not in status,(row['preset'],status)
if not selected:
 pairs=[]
 for preset in dict.fromkeys(r['preset'] for r in rows):
  for mode in ['legacy','standard']:
   a=next(r for r in rows if r['preset']==preset and r['profile']=='baseline_'+mode)
   b=next(r for r in rows if r['preset']==preset and r['profile']=='candidate_'+mode)
   same=a['frame_hashes']==b['frame_hashes'];pairs.append({'preset':preset,'mode':mode,'rgb_identical':same,'baseline_ms':a['frame_mean_ms'],'candidate_ms':b['frame_mean_ms']})
   assert same,(preset,mode,'selected RGB mismatch')
 (work/'comparisons.json').write_text(json.dumps(pairs,indent=2)+'\n')
 print('PASSED',len(pairs),'paired Android cases with',len(pairs)*8,'exact selected RGB frame pairs',flush=True)
