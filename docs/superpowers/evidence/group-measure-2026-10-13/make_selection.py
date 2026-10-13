import random, json, hashlib, pathlib
d = pathlib.Path('../../core/src/main/assets/presets'); names = sorted(p.name for p in d.glob('*.milk'))
pick = sorted(random.Random(20261013).sample(names, 200))
json.dump({'seed': 20261013, 'pool_count': len(names), 'policy': 'frozen before any measurement; no rerolling',
           'presets': [{'name': n, 'sha256': hashlib.sha256((d / n).read_bytes()).hexdigest()} for n in pick]},
          open('selection.json', 'w'), indent=1)
print(len(pick))
