from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys
root=Path('/tmp/projectmtv-line-refactor')
role=sys.argv[1];old=root/'android-workers'/role;new=root/'android-workers-cache-off'/role
new.mkdir(parents=True,exist_ok=False)
worker=new/'worker';shutil.copytree(old/'source/tools/core-corpus/android-worker',worker,ignore=shutil.ignore_patterns('build','.gradle','.cxx','local.properties'))
p=worker/'app/src/main/java/nl/neerdael/projectmtv/corpus/CorpusInstrumentation.java';s=p.read_text()
assert s.count('ProjectMJNI.setAutoChange(false);')==1
s=s.replace('ProjectMJNI.setAutoChange(false);','ProjectMJNI.setShaderBinaryCache(false);\n        ProjectMJNI.setAutoChange(false);')
s=s.replace('.put("blankDetection", false)', '.put("blankDetection", false).put("shaderBinaryCache", false)')
p.write_text(s)
aar=new/(role+'.aar');shutil.copy2(old/(role+'.aar'),aar)
identity=json.loads((old/'identity.json').read_text());identity['original_builder_sha256']=identity['builder_sha256'];identity['builder_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
identity['aar_reused_from_identity_sha256']=hashlib.sha256((old/'identity.json').read_bytes()).hexdigest()
identity['validation_settings']={'shaderBinaryCache':False,'reason':'isolate baseline API36 surface initialization GL_INVALID_OPERATION; preserve strict GL checks'}
identity['worker_java_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
identity['worker_gradle_sha256']=hashlib.sha256((worker/'app/build.gradle').read_bytes()).hexdigest()
with (new/'worker-build.log').open('w') as log:
 subprocess.run(['/Users/jneerdael/Scripts/Projectm-TV/.worktrees/renderer-line-refactor/gradlew','-p',str(worker),':app:assembleDebug','--console=plain','-PcoreAar='+str(aar),'-PcorpusApplicationId='+identity['package']],check=True,stdout=log,stderr=subprocess.STDOUT)
apk=new/(role+'.apk');shutil.copy2(worker/'app/build/outputs/apk/debug/app-debug.apk',apk)
identity.update(aar=str(aar),apk=str(apk),apk_sha256=hashlib.sha256(apk.read_bytes()).hexdigest())
(new/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
print('Built cache-off worker',role,flush=True)
