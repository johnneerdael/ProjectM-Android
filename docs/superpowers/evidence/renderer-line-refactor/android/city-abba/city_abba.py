from pathlib import Path
import hashlib,importlib.util,json
base=Path('/Users/jneerdael/Scripts/Projectm-TV/.worktrees/renderer-line-refactor/tools/native-trails/run_validation.py')
spec=importlib.util.spec_from_file_location('city_abba_runner',base);runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
runner.PROFILES=[('baseline_a0','baseline-native',3840,2160,1024,768,-1),('candidate_b0','candidate-native',3840,2160,1024,768,-1),('candidate_b1','candidate-native',3840,2160,1024,768,-1),('baseline_a1','baseline-native',3840,2160,1024,768,-1)]
work=Path('/tmp/projectmtv-line-refactor/city-abba');work.mkdir(exist_ok=False)
(work/'caller.json').write_text(json.dumps({'caller_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'purpose':'one supplementary isolated ABBA cycle after noisy single-run City legacy timing; unchanged instrumented AARs; cache disabled; emulator serialized engine timing only'},indent=2)+'\n')
runner.run(work,Path('/tmp/projectmtv-line-refactor/android-workers-cache-off'),Path('/tmp/projectmtv-line-refactor/city-only.txt'),'emulator-5674',None)
rows=json.loads((work/'progress.json').read_text())['finished']
assert len(rows)==4 and len({tuple(r['frame_hashes']) for r in rows})==1
results={role:[r['frame_mean_ms'] for r in rows if r['profile'].startswith(role)] for role in ['baseline','candidate']}
results['mean']={role:sum(results[role])/2 for role in ['baseline','candidate']}
(work/'summary.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results),flush=True)
