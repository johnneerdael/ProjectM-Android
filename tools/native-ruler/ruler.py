"""Corpus calibration ruler: render each preset with the pinned patched engine (macOS GLES, SwiftShader)
and measure displayed brightness, flashing, motion and colour. These are calibration targets for the
source-only analysis; they are never source-classification inputs."""
import argparse,colorsys,hashlib,json,os,subprocess,sys,tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2,numpy as np
import ruler_cache
ROOT=Path(__file__).resolve().parents[2]
RULER=ROOT/'build/native-ruler/native-ruler'
SWIFTSHADER=Path.home()/'Library/Android/sdk/emulator/lib64/gles_angle'
PCM=None
TEXTURES=ROOT/'core/src/main/assets/textures'
W,H,FRAMES=480,270,300
MEASURE_VERSION=1  # bump when measure() changes
IDENT={}  # pcm/binary/swiftshader/texture-tree identities, set once in main
HUES=('red','orange','yellow','green','cyan','blue','purple','pink')
EDGES=(15,45,75,165,195,255,285,345)


def hue_name(h):
    d=h*360
    for name,edge in zip(HUES,EDGES):
        if d<edge:return name
    return 'red'


def measure(path):
    frames=np.fromfile(path,np.uint8).reshape(-1,H,W,3)
    grey=np.stack([cv2.cvtColor(cv2.resize(f,(320,180),interpolation=cv2.INTER_AREA),cv2.COLOR_RGB2GRAY) for f in frames])
    lum=grey.reshape(len(grey),-1).mean(1)/255
    diffs=np.abs(np.diff(grey.astype(np.int16),axis=0)).reshape(len(grey)-1,-1).mean(1)/255
    flows=[]
    for i in range(60,len(grey)-1,3):
        flow=cv2.calcOpticalFlowFarneback(grey[i],grey[i+1],None,.5,3,15,3,5,1.2,0)
        flows.append(float(np.hypot(flow[...,0],flow[...,1]).mean())*30/320)
    tail=frames[60::10].astype(np.float32)/255
    hsv=np.stack([cv2.cvtColor(f,cv2.COLOR_RGB2HSV) for f in tail]).reshape(-1,3)
    sat=hsv[:,1];val=hsv[:,2];hue=hsv[:,0]/360.
    coloured=(sat>=.15)&(val>=.05)
    shares={}
    if coloured.any():
        names=[hue_name(h) for h in hue[coloured][::7]]
        for n in names:shares[n]=shares.get(n,0)+1/len(names)
    warm=float(np.mean(sat[coloured]*np.cos(np.radians(hue[coloured]*360-30)))) if coloured.any() else None
    return {'mean_luminance':float(lum[60:].mean()),'luminance_p10_p90':[float(np.percentile(lum[60:],10)),float(np.percentile(lum[60:],90))],
            'mean_abs_frame_difference':float(diffs[60:].mean()),'mean_flow_screen_widths_per_s':float(np.mean(flows)),
            'global_brightness_jumps_per_10s':int(np.sum(np.abs(np.diff(lum[60:]))>.08)),
            'mean_saturation':float(sat.mean()),'coloured_share':float(coloured.mean()),'warm_cool':warm,
            'hue_shares':{k:round(v,3) for k,v in sorted(shares.items(),key=lambda kv:-kv[1])},
            'black_frame_share':float(np.mean(lum[60:]<.02)),'white_frame_share':float(np.mean(lum[60:]>.9))}


def one(preset,out):
    target=out/'results'/(preset.stem+'.json')
    identity=ruler_cache.run_identity(hashlib.sha256(preset.read_bytes()).hexdigest(),IDENT['pcm'],IDENT['binary'],IDENT['swiftshader'],IDENT['textures'],
        {'size':[W,H],'frames':FRAMES,'window':60,'measure_version':MEASURE_VERSION})
    if ruler_cache.can_reuse(target,identity):return preset.name,'cached'
    # a missing result, or one whose recorded inputs differ (or that predates identities), is re-rendered
    with tempfile.TemporaryDirectory(dir=out/'tmp') as work:
        prefix=Path(work)/'r'
        try:
            # SwiftShader reads SwiftShader.ini from the working directory: one render thread per preset
            # avoids thread-pool thrash when many presets render in parallel (same output, measured).
            (Path(work)/'SwiftShader.ini').write_text('[Processor]\nThreadCount=1\n')
            done=subprocess.run([str(RULER),str(SWIFTSHADER),str(preset),str(PCM),str(prefix),str(FRAMES),str(W),str(H),str(TEXTURES)],
                                capture_output=True,text=True,timeout=300,cwd=work)
            if done.returncode:row={'status':'render_error','error':done.stderr.strip()[-300:]}
            else:
                row={'status':'measured',**measure(str(prefix)+'.rgb.u8')}
                for tag in ('mid','last'):
                    raw=Path(str(prefix)+f'.{tag}.rgb.u8')
                    if raw.exists():
                        img=np.fromfile(raw,np.uint8).reshape(H,W,3)
                        cv2.imwrite(str(out/'thumbs'/f'{preset.stem}.{tag}.jpg'),cv2.cvtColor(cv2.resize(img,(160,90),interpolation=cv2.INTER_AREA),cv2.COLOR_RGB2BGR),[cv2.IMWRITE_JPEG_QUALITY,80])
        except subprocess.TimeoutExpired:row={'status':'timeout'}
        except Exception as error:row={'status':'error','error':str(error)[:300]}
    row.update(identity=identity,preset=preset.name,preset_sha256=hashlib.sha256(preset.read_bytes()).hexdigest(),
               ruler={'engine':'pinned patched source34 (macOS GLES, SwiftShader)','size':[W,H],'frames':FRAMES,'audio':'checkpoint synthetic PCM, U8 ingress'},
               scope='calibration target; never a source-classification input')
    target.write_text(json.dumps(row))
    return preset.name,row['status']


if __name__=='__main__':
    ap=argparse.ArgumentParser(description='Render presets with the native ruler and measure them.')
    ap.add_argument('--pcm',required=True,type=Path,help='synthetic float32 PCM file')
    ap.add_argument('--output',required=True,type=Path,help='output directory (results/, thumbs/, tmp/)')
    ap.add_argument('--swiftshader',type=Path,default=SWIFTSHADER,help='SwiftShader directory (default: Android SDK emulator/lib64/gles_angle)')
    ap.add_argument('--presets',type=Path,default=ROOT/'core/src/main/assets/presets')
    ap.add_argument('--workers',type=int,default=6)
    ap.add_argument('--preset',action='append',default=[],help='limit to this preset file name (repeatable)')
    args=ap.parse_args()
    PCM=args.pcm.resolve();SWIFTSHADER,presets,out=ruler_cache.resolve_paths(args.swiftshader,args.presets,args.output);workers=args.workers
    IDENT.update(pcm=ruler_cache.file_sha256(PCM),binary=ruler_cache.file_sha256(RULER),swiftshader=ruler_cache.tree_identity(SWIFTSHADER),textures=ruler_cache.tree_identity(TEXTURES))
    for sub in ('results','thumbs','tmp'):(out/sub).mkdir(parents=True,exist_ok=True)
    names=sorted(p for p in presets.iterdir() if p.suffix=='.milk' and (not args.preset or p.name in args.preset))
    counts={};done=0
    with ThreadPoolExecutor(workers) as pool:
        for name,status in pool.map(lambda p:one(p,out),names):
            counts[status]=counts.get(status,0)+1;done+=1
            if done%100==0:print(json.dumps({'completed':done,'total':len(names),'counts':counts}),flush=True)
    print(json.dumps({'completed':done,'counts':counts}),flush=True)
