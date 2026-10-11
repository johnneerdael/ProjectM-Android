"""Emulator-only published-AAR checkpoint capture for human effect review.

Renders one bundled preset through the unchanged published core JNI inside a
task-owned Android emulator, with declared PCM, then writes a screenshot and a
10-second clip muxed with the same audio. Physical devices are refused before
any ADB operation. Files frozen before capture (description, prediction image)
are hashed into the result so later edits are detectable. Captured frames are
review evidence only; they never feed source classification.
"""
import argparse,hashlib,json,shlex,shutil,subprocess,sys,threading,uuid,zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from core_backend import read_header,read_frames
from java_runtime import verify_runtime_classes

ROOT=HERE.parents[1]
ADB=str(Path.home()/'Library/Android/sdk/platform-tools/adb')
FPS=30
PCM_FRAME_SAMPLES=1470


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def emulator_serial(value):
    if not (value.startswith('emulator-') and value[9:].isdigit()):
        raise argparse.ArgumentTypeError('only an emulator-NNNN serial is accepted')
    return value


def selection_overlay(path,name,preset_bytes):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo('assets/presets.idx',date_time=(1980,1,1,0,0,0)),name+'\t0\n')
        archive.writestr(zipfile.ZipInfo('assets/presets/'+name,date_time=(1980,1,1,0,0,0)),preset_bytes)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--serial',type=emulator_serial,required=True)
    parser.add_argument('--preset',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='new directory; must not exist')
    parser.add_argument('--pcm',type=Path,required=True,help='mono float32 LE PCM, 1470 samples per frame')
    parser.add_argument('--wav',type=Path,required=True,help='the same audio for muxing')
    parser.add_argument('--frozen',type=Path,action='append',default=[],
                        help='prediction files frozen before capture (repeatable)')
    parser.add_argument('--runtime',type=Path,default=ROOT/'build/preset-corpus/runtime34')
    parser.add_argument('--aar',type=Path,default=ROOT/'build/preset-corpus/published34/projectM-TV-core-2.3.34.aar')
    parser.add_argument('--width',type=int,default=480);parser.add_argument('--height',type=int,default=270)
    parser.add_argument('--frames',type=int,default=300);parser.add_argument('--trails',type=int,default=0)
    parser.add_argument('--screenshot-frame',type=int,default=149)
    parser.add_argument('--copy-to',type=Path,help='directory receiving screenshot/clip copies for human review')
    args=parser.parse_args(argv)
    if args.output.exists():parser.error('output exists; captures are never overwritten')
    if not 0<=args.screenshot_frame<args.frames:parser.error('screenshot frame outside schedule')
    if args.pcm.stat().st_size!=args.frames*PCM_FRAME_SAMPLES*4:parser.error('PCM length does not match the frame schedule')
    for path in args.frozen:
        if not path.is_file():parser.error(f'frozen prediction file missing: {path}')
    preset_bytes=args.preset.read_bytes();name=args.preset.name
    frozen={str(path):sha(path) for path in args.frozen}
    java=verify_runtime_classes(args.aar,args.runtime,args.runtime/'dex/classes.dex')
    with zipfile.ZipFile(args.aar) as archive:
        if hashlib.sha256(archive.read('jni/arm64-v8a/libprojectmtv.so')).hexdigest()!=sha(args.runtime/'libprojectmtv.so'):
            raise SystemExit('runtime library is not the AAR arm64-v8a library')
    out=args.output;out.mkdir(parents=True)
    selection_overlay(out/'selection.apk',name,preset_bytes)
    (out/'config.json').write_text(json.dumps({'width':args.width,'height':args.height,'trails':args.trails})+'\n')
    files={'published-core.aar':args.aar,'libprojectmtv.so':args.runtime/'libprojectmtv.so',
           'classes.dex':args.runtime/'dex/classes.dex','libbackendclock.so':args.runtime/'libbackendclock.so',
           'selection.apk':out/'selection.apk','audio.f32':args.pcm,'config.json':out/'config.json'}
    def adb(*command):
        return subprocess.run([ADB,'-s',args.serial,*command],check=True,capture_output=True,timeout=120)
    if adb('shell','getprop','ro.kernel.qemu').stdout.decode().strip()!='1':raise SystemExit('physical device refused')
    abi=adb('shell','getprop','ro.product.cpu.abi').stdout.decode().strip()
    if abi!='arm64-v8a':raise SystemExit('arm64-v8a emulator required, got '+abi)
    remote='/data/local/tmp/projectmtv-checkpoint-'+uuid.uuid4().hex
    record={'policy':'emulator-checkpoint-capture-v1','preset':{'name':name,'sha256':hashlib.sha256(preset_bytes).hexdigest()},
        'frozen_before_capture':frozen,'files':{key:sha(path) for key,path in files.items()},'wav_sha256':sha(args.wav),
        'java_proof':java,'serial':args.serial,'emulator':{'ro.kernel.qemu':'1','abi':abi,
            'build_fingerprint':adb('shell','getprop','ro.build.fingerprint').stdout.decode().strip()},
        'schedule':{'frames':args.frames,'fps':FPS,'width':args.width,'height':args.height,'trails':args.trails,
                    'pcm_sample_rate':44100,'pcm_transport':'float32 quantized by the runner to U8 JNI waveform'},
        'scope':'published AAR JNI in an Android emulator; review evidence only, never a classification input'}
    (out/'capture-freeze.json').write_text(json.dumps(record,indent=2)+'\n')
    try:
        adb('shell','mkdir','-p',remote+'/work/textures')
        for filename,path in files.items():
            adb('push',str(path),remote+'/'+filename)
            if adb('shell','sha256sum',remote+'/'+filename).stdout.decode().split()[0]!=sha(path):
                raise SystemExit('pushed file hash mismatch: '+filename)
        prefix=remote+'/capture'
        command=shlex.join(['env','CLASSPATH='+remote+'/classes.dex','LD_PRELOAD='+remote+'/libbackendclock.so',
            'PROJECTMTV_TEST_RANDOM_SEED=12345','PROJECTMTV_TEST_CORE_PATH='+remote+'/libprojectmtv.so',
            'app_process','-Djava.library.path='+remote,'/system/bin','nl.neerdael.projectm.analysis.CoreBackendRunner',
            remote+'/libprojectmtv.so',remote+'/published-core.aar|'+remote+'/selection.apk',remote+'/work',prefix,
            remote+'/libbackendclock.so',remote+'/audio.f32',str(args.frames),'stream',remote+'/config.json'])
        with (out/'capture-stderr.txt').open('wb') as err:
            process=subprocess.Popen([ADB,'-s',args.serial,'exec-out',command],stdout=subprocess.PIPE,stderr=err)
            timer=threading.Timer(600,process.kill);timer.start()
            try:
                header=read_header(process.stdout,expected_frames=args.frames,width=args.width,height=args.height)
                with (out/'frames.rgb.u8').open('wb') as raw:
                    for frame in read_frames(process.stdout,expected_frames=args.frames,width=args.width,
                                             height=args.height,header=header):raw.write(frame.tobytes())
                if process.wait(timeout=60):raise SystemExit('native capture failed; see capture-stderr.txt')
            finally:
                timer.cancel()
                if process.poll() is None:process.kill();process.wait(timeout=10)
        for suffix,local in [('.json','render-metadata.json'),('.log','native.log'),('.java.log','java.log')]:
            adb('pull',prefix+suffix,str(out/local))
    finally:
        subprocess.run([ADB,'-s',args.serial,'shell','rm','-rf',remote],capture_output=True,timeout=60)
    metadata=json.loads((out/'render-metadata.json').read_text())
    if metadata['preset']!=name or metadata['indexed_count']!=1:raise SystemExit('core did not render the selected preset')
    if not metadata['frames']==metadata['rendered_frame_serial_delta']==args.frames:raise SystemExit('rendered frame count mismatch')
    if {str(path):sha(path) for path in args.frozen}!=frozen:raise SystemExit('a frozen prediction file changed during capture')
    raw=['-f','rawvideo','-pixel_format','rgb24','-video_size',f'{args.width}x{args.height}','-framerate',str(FPS),'-i',str(out/'frames.rgb.u8')]
    seconds=args.frames/FPS
    subprocess.run(['ffmpeg','-v','error','-y',*raw,'-i',str(args.wav),'-c:v','libx264','-preset','fast','-crf','22',
        '-pix_fmt','yuv420p','-c:a','aac','-t',format(seconds,'g'),'-shortest',str(out/'clip.mp4')],check=True)
    subprocess.run(['ffmpeg','-v','error','-y',*raw,'-vf',f'select=eq(n\\,{args.screenshot_frame})','-frames:v','1',
        str(out/'screenshot.png')],check=True)
    record['render_metadata']=metadata
    record['outputs']={p.name:sha(p) for p in [out/'clip.mp4',out/'screenshot.png',out/'frames.rgb.u8',out/'render-metadata.json']}
    if args.copy_to is not None:
        args.copy_to.mkdir(parents=True,exist_ok=True)
        stem=args.preset.stem+'-'+out.name
        for source,suffix in [(out/'screenshot.png','-screenshot.png'),(out/'clip.mp4','-clip.mp4')]:
            target=args.copy_to/(stem+suffix)
            if target.exists():raise SystemExit('review copy exists; not overwritten: '+str(target))
            shutil.copyfile(source,target)
        record['review_copies']=str(args.copy_to)
    (out/'capture-result.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'preset':name,'output':str(out),'frames':args.frames,'renderer':metadata.get('renderer')}))


if __name__=='__main__':
    main()
