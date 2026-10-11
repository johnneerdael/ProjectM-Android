"""Seeded emulator captures for validating approximate activity (review evidence only).

Selects presets with a frozen seed, captures 10 s at 320x180 through the
published AAR in the task-owned emulator with the declared synthetic audio, and
measures simple observed activity from frames: mean absolute frame difference,
mean dense optical-flow speed (screen widths/second) and count of global
brightness jumps. These observations validate the source-only approximate
estimate; they never feed production classification.
"""
import hashlib,json,random,subprocess,sys
from pathlib import Path
import numpy as np
import cv2

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
PRESETS=ROOT/'core/src/main/assets/presets'
AUDIO=ROOT/'build/preset-corpus/preset-understanding-checkpoint-2026-10-11'
W,H,FRAMES=320,180,300


def measure(frames):
    grey=[cv2.cvtColor(f,cv2.COLOR_RGB2GRAY) for f in frames]
    diffs=[float(np.abs(grey[i+1].astype(float)-grey[i].astype(float)).mean()/255) for i in range(len(grey)-1)]
    flows=[]
    for i in range(60,len(grey)-1,3):
        flow=cv2.calcOpticalFlowFarneback(grey[i],grey[i+1],None,.5,3,15,3,5,1.2,0)
        flows.append(float(np.hypot(flow[...,0],flow[...,1]).mean())*30/W)
    lum=np.array([g.mean()/255 for g in grey])
    jumps=int(np.sum(np.abs(np.diff(lum[60:]))>.08))
    return {'mean_abs_frame_difference':float(np.mean(diffs[60:])),'mean_flow_screen_widths_per_s':float(np.mean(flows)),
            'global_brightness_jumps_per_10s':jumps,'mean_luminance':float(lum[60:].mean())}


def main():
    count=int(sys.argv[1]) if len(sys.argv)>1 else 30
    names=sorted(p.name for p in PRESETS.iterdir() if p.suffix=='.milk')
    seed=2026101199
    chosen=random.Random(seed).sample(names,count)
    selection={'seed':seed,'pool_count':len(names),'presets':chosen,
               'pool_sha256':hashlib.sha256('\n'.join(names).encode()).hexdigest()}
    (OUT/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    pcm=OUT/'audio.f32';wav=OUT/'audio.wav'
    if not pcm.exists():pcm.write_bytes((AUDIO/'synthetic.f32').read_bytes());wav.write_bytes((AUDIO/'synthetic.wav').read_bytes())
    results=json.loads((OUT/'observations.json').read_text()) if (OUT/'observations.json').exists() else {}
    for index,name in enumerate(chosen):
        if name in results:continue
        target=OUT/'captures'/('%03d'%index)
        if target.exists():
            import shutil;shutil.rmtree(target)
        process=subprocess.run([str(ROOT/'build/preset-lab-venv/bin/python'),str(ROOT/'tools/milk-analyzer/emulator_checkpoint_capture.py'),
            '--serial','emulator-5610','--preset',str(PRESETS/name),'--output',str(target),'--pcm',str(pcm),'--wav',str(wav),
            '--width',str(W),'--height',str(H),'--frames',str(FRAMES),'--screenshot-frame','149'],capture_output=True,text=True,timeout=900)
        if process.returncode:
            results[name]={'status':'capture_failed','error':process.stderr[-400:]}
        else:
            frames=np.fromfile(target/'frames.rgb.u8',np.uint8).reshape(FRAMES,H,W,3)
            results[name]={'status':'observed',**measure(frames)}
            (target/'frames.rgb.u8').unlink()
        (OUT/'observations.json').write_text(json.dumps(results,indent=1)+'\n')
        print(json.dumps({'index':index,'name':name[:60],**{k:v for k,v in results[name].items() if k!='error'}}),flush=True)


if __name__=='__main__':
    main()
