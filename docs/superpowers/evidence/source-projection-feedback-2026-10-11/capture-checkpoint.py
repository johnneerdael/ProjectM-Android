"""One isolated public-JNI capture; never changes installed apps or preferences."""
import argparse,hashlib,json,shlex,subprocess,sys,threading,uuid,wave,zipfile
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path('tools/milk-analyzer').resolve()))
from core_backend import read_header,read_frames
from java_runtime import verify_runtime_classes

ROOT=Path('build/preset-corpus/preset-understanding-checkpoint-2026-10-11').resolve()
RUNTIME=Path('build/preset-corpus/runtime34').resolve()
AAR=Path('build/preset-corpus/published34/projectM-TV-core-2.3.34.aar').resolve()
ADB='/Users/jneerdael/Library/Android/sdk/platform-tools/adb'
parser=argparse.ArgumentParser(description='Emulator-only full-AAR checkpoint capture')
parser.add_argument('--serial',help='Task-owned emulator-NNNN serial; physical devices are refused')
parser.add_argument('--prepare-only',action='store_true')
args=parser.parse_args()
SERIAL=args.serial
if SERIAL is not None and not (SERIAL.startswith('emulator-') and SERIAL[9:].isdigit()):
    parser.error('Only an emulator-NNNN serial is accepted')
if not args.prepare_only and SERIAL is None:
    parser.error('--serial emulator-NNNN is required for capture')
WIDTH,HEIGHT,FRAMES,FPS=480,270,300,30
REMOTE='/data/local/tmp/projectmtv-understanding-'+uuid.uuid4().hex
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
selection=json.loads((ROOT/'random-selection.json').read_text())
prediction=ROOT/'random-description.json'
assert sha(prediction)==selection['description_file_sha256']
description=json.loads(prediction.read_text())
name=description['preset']['name']
preset=Path('core/src/main/assets/presets')/name
assert sha(preset)==description['preset']['sha256']
assert not (ROOT/'render-metadata.json').exists(),'checkpoint already captured; retain original'
java=verify_runtime_classes(AAR,RUNTIME,RUNTIME/'dex/classes.dex')
with zipfile.ZipFile(AAR) as archive:
    assert hashlib.sha256(archive.read('jni/arm64-v8a/libprojectmtv.so')).hexdigest()==sha(RUNTIME/'libprojectmtv.so')

def adb(*args):
    return subprocess.run([ADB,'-s',SERIAL,*args],check=True,capture_output=True,timeout=60)
with zipfile.ZipFile(ROOT/'selection.apk','w',zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('assets/presets.idx',name+'\t0\n')
    archive.writestr('assets/presets/'+name,preset.read_bytes())
t=np.arange(44100*10)/44100
phase=t%(60/110)
pcm=(.12*np.sin(2*np.pi*220*t)+.10*np.sin(2*np.pi*330*t)+
     .32*np.sin(2*np.pi*55*t)*np.exp(-6*phase)+
     .035*np.random.default_rng(2026101101).standard_normal(t.size)*np.exp(-25*phase))
pcm=np.clip(pcm,-1,1).astype('<f4');pcm.tofile(ROOT/'synthetic.f32')
with wave.open(str(ROOT/'synthetic.wav'),'wb') as wav:
    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(44100)
    wav.writeframes(np.clip(np.rint(pcm*32767),-32768,32767).astype('<i2').tobytes())
(ROOT/'config.json').write_text(json.dumps({'width':WIDTH,'height':HEIGHT,'trails':0})+'\n')
files={'published-core.aar':AAR,'libprojectmtv.so':RUNTIME/'libprojectmtv.so',
       'classes.dex':RUNTIME/'dex/classes.dex','libbackendclock.so':RUNTIME/'libbackendclock.so',
       'selection.apk':ROOT/'selection.apk','synthetic.f32':ROOT/'synthetic.f32','config.json':ROOT/'config.json'}
freeze={'preset':description['preset'],'prediction_sha256':sha(prediction),'selection_sha256':sha(ROOT/'random-selection.json'),
    'files':{key:sha(p) for key,p in files.items()},'java_proof':java,'serial':SERIAL,'remote':REMOTE,
    'schedule':{'frames':FRAMES,'fps':FPS,'width':WIDTH,'height':HEIGHT,'seconds':10,'pcm_sample_rate':44100},
    'audio':'reproducible synthetic110BPM bass pulse,220/330Hz pads and seeded high-frequency noise; JNI receives quantized U8 waveform',
    'source_context_difference':'prediction reference1920x1080; capture480x270 at same16:9 aspect; no numerical/pixelmatch credit',
    'purpose':'human effect-understanding review, separate from source classification'}
freeze['corrected_description_sha256']=sha(ROOT/'random-description-v2-before-capture.json')
freeze['interpretation_sha256']=sha(ROOT/'random-interpretation-v2-before-capture.json')
freeze['prediction_image_sha256']=sha(ROOT/'prediction-image.png')
for filename in ('enriched-description-v5-before-capture.json','prediction-image-v5.png',
                 'prediction-illustration-v5-prompt.txt','prediction-illustration-v5-identity.json'):
    freeze[filename+'_sha256']=sha(ROOT/filename)
(ROOT/'capture-freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
if args.prepare_only:
    print(json.dumps({'remote':REMOTE,'files':{k:str(v) for k,v in files.items()},'prepared':True}))
    raise SystemExit(0)
assert adb('shell','getprop','ro.kernel.qemu').stdout.decode().strip()=='1','Physical device refused'
assert adb('shell','getprop','ro.product.cpu.abi').stdout.decode().strip()=='arm64-v8a'
adb('shell','mkdir','-p',REMOTE+'/work/textures')
for filename,path in files.items():
    adb('push',str(path),REMOTE+'/'+filename)
    assert adb('shell','sha256sum',REMOTE+'/'+filename).stdout.decode().split()[0]==sha(path)
output=REMOTE+'/checkpoint'
command=shlex.join(['env','CLASSPATH='+REMOTE+'/classes.dex','LD_PRELOAD='+REMOTE+'/libbackendclock.so',
    'PROJECTMTV_TEST_RANDOM_SEED=12345','PROJECTMTV_TEST_CORE_PATH='+REMOTE+'/libprojectmtv.so',
    'PROJECTMTV_TEST_RANDOM_LOG='+output+'.random.jsonl','app_process','-Djava.library.path='+REMOTE,
    '/system/bin','nl.neerdael.projectm.analysis.CoreBackendRunner',REMOTE+'/libprojectmtv.so',
    REMOTE+'/published-core.aar|'+REMOTE+'/selection.apk',REMOTE+'/work',output,
    REMOTE+'/libbackendclock.so',REMOTE+'/synthetic.f32',str(FRAMES),'stream',REMOTE+'/config.json'])
with (ROOT/'capture-stderr.txt').open('wb') as err:
    process=subprocess.Popen([ADB,'-s',SERIAL,'exec-out',command],stdout=subprocess.PIPE,stderr=err)
    timer=threading.Timer(180,process.kill);timer.start()
    try:
        header=read_header(process.stdout,expected_frames=FRAMES,width=WIDTH,height=HEIGHT)
        with (ROOT/'frames.rgb.u8').open('wb') as raw:
            for frame in read_frames(process.stdout,expected_frames=FRAMES,width=WIDTH,height=HEIGHT,header=header):raw.write(frame.tobytes())
        code=process.wait(timeout=30)
        if code:raise RuntimeError('native capture failed; see capture-stderr.txt')
    finally:
        timer.cancel()
        if process.poll() is None:process.kill();process.wait(timeout=10)
for suffix,name in [('.json','render-metadata.json'),('.log','native.log'),('.java.log','java.log'),('.random.jsonl','random.jsonl')]:
    adb('pull',output+suffix,str(ROOT/name))
metadata=json.loads((ROOT/'render-metadata.json').read_text())
assert metadata['preset']==preset.name and metadata['indexed_count']==1
assert metadata['frames']==metadata['rendered_frame_serial_delta']==FRAMES
assert (ROOT/'frames.rgb.u8').stat().st_size==WIDTH*HEIGHT*3*FRAMES
assert sha(prediction)==freeze['prediction_sha256']
subprocess.run(['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{WIDTH}x{HEIGHT}',
    '-framerate',str(FPS),'-i',str(ROOT/'frames.rgb.u8'),'-i',str(ROOT/'synthetic.wav'),'-c:v','libx264',
    '-preset','fast','-crf','24','-pix_fmt','yuv420p','-c:a','aac','-t','10','-shortest',str(ROOT/'clip-10s.mp4')],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{WIDTH}x{HEIGHT}',
    '-framerate',str(FPS),'-i',str(ROOT/'frames.rgb.u8'),'-vf','select=eq(n\\,149)','-frames:v','1',str(ROOT/'screenshot-5s.png')],check=True)
freeze['outputs']={p.name:sha(p) for p in [ROOT/'clip-10s.mp4',ROOT/'screenshot-5s.png',ROOT/'render-metadata.json',ROOT/'frames.rgb.u8']}
(ROOT/'capture-result.json').write_text(json.dumps(freeze,indent=2)+'\n')
print(json.dumps({'preset':preset.name,'video':str(ROOT/'clip-10s.mp4'),'screenshot':str(ROOT/'screenshot-5s.png'),
    'frames':FRAMES,'seconds':10,'source_prediction_unchanged':True}),flush=True)
