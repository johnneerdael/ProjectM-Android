package com.example.projectm.visualizer;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Instrumentation;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Rect;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import java.io.*;
import java.lang.reflect.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.zip.*;
import nl.neerdael.projectm.core.ProjectMJNI;
import org.json.*;

/** Real UI/GL/catalog journeys. Network delivery alone uses an explicitly injected file response. */
final class DistributionSetupTest {
    private static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);}
    private static Object field(Object value,String name)throws Exception{
        Field field=value.getClass().getDeclaredField(name);field.setAccessible(true);return field.get(value);
    }
    private static Object call(Object value,String name,Class<?>[] types,Object...args)throws Exception{
        Method method=value.getClass().getDeclaredMethod(name,types);method.setAccessible(true);return method.invoke(value,args);
    }
    private static void ui(Instrumentation test,Runnable action){
        Throwable[] failure={null};test.runOnMainSync(()->{try{action.run();}catch(Throwable error){failure[0]=error;}});
        if(failure[0]!=null)throw new AssertionError("UI assertion",failure[0]);
    }
    private static AlertDialog dialog(Object collection)throws Exception{return (AlertDialog)field(collection,"dialog");}
    private static AlertDialog awaitDialog(Instrumentation test,Object collection)throws Exception{
        long until=SystemClock.elapsedRealtime()+15000;
        while(SystemClock.elapsedRealtime()<until){AlertDialog value=dialog(collection);
            if(value!=null&&value.isShowing()){
                test.waitForIdleSync();SystemClock.sleep(200);
                if(dialog(collection)==value&&value.getButton(AlertDialog.BUTTON_NEGATIVE).isLaidOut())return value;
            }
            SystemClock.sleep(50);
        }
        throw new AssertionError("collection consent dialog missing");
    }
    private static void press(Instrumentation test,View view){
        Rect bounds=new Rect();ui(test,()->check(view.getGlobalVisibleRect(bounds)&&bounds.height()==view.getHeight(),"action is clipped"));
        if(BuildConfig.TOUCHSCREEN){
            int[] screen=new int[2];ui(test,()->view.getLocationOnScreen(screen));
            float x=screen[0]+view.getWidth()/2f,y=screen[1]+view.getHeight()/2f;
            long time=SystemClock.uptimeMillis();
            MotionEvent down=MotionEvent.obtain(time,time,MotionEvent.ACTION_DOWN,x,y,0);
            MotionEvent up=MotionEvent.obtain(time,time+50,MotionEvent.ACTION_UP,x,y,0);
            down.setSource(InputDevice.SOURCE_TOUCHSCREEN);up.setSource(InputDevice.SOURCE_TOUCHSCREEN);
            try{check(test.getUiAutomation().injectInputEvent(down,true)&&test.getUiAutomation().injectInputEvent(up,true),"touch action failed");}
            finally{down.recycle();up.recycle();}
        }else{test.setInTouchMode(false);ui(test,()->check(view.requestFocus(),"D-pad action not focusable"));test.sendKeyDownUpSync(KeyEvent.KEYCODE_DPAD_CENTER);}
        test.waitForIdleSync();SystemClock.sleep(100);
    }
    private static void counts(int all,int custom)throws Exception{
        long until=SystemClock.elapsedRealtime()+60000;
        while(SystemClock.elapsedRealtime()<until){
            if(!ProjectMJNI.isMusicCategoryPending()&&ProjectMJNI.getCategoryPresetCount("all")==all&&ProjectMJNI.getCategoryPresetCount("custom")==custom)return;
            SystemClock.sleep(50);
        }
        throw new AssertionError("catalog counts differ: All="+ProjectMJNI.getCategoryPresetCount("all")+", Custom="+ProjectMJNI.getCategoryPresetCount("custom"));
    }
    private static void phase(Object download,String expected)throws Exception{
        long until=SystemClock.elapsedRealtime()+120000;
        while(SystemClock.elapsedRealtime()<until){
            Object status=call(download,"status",new Class<?>[0]);String actual=(String)field(status,"phase");
            if(actual.equals(expected))return;
            if(actual.equals("error")||actual.equals("canceled"))throw new AssertionError("collection "+actual+": "+field(status,"error"));
            SystemClock.sleep(50);
        }
        Object status=call(download,"status",new Class<?>[0]);
        throw new AssertionError("collection did not reach "+expected+", actual="+field(status,"phase")+", error="+field(status,"error"));
    }
    private static File capture(Instrumentation test,String name)throws Exception{
        Bitmap bitmap=test.getUiAutomation().takeScreenshot();check(bitmap!=null,"screenshot unavailable");
        File file=new File(test.getTargetContext().getExternalFilesDir(null),name+".jpg");
        try(FileOutputStream out=new FileOutputStream(file)){check(bitmap.compress(Bitmap.CompressFormat.JPEG,90,out),"capture failed");}
        bitmap.recycle();return file;
    }
    private static void renderStarters(Instrumentation test,Activity activity,Bundle result)throws Exception{
        ui(test,()->{
            try{call(activity,"setAudioEnabled",new Class<?>[]{boolean.class},false);if(BuildConfig.TOUCHSCREEN)((PhoneAudioInput)field(activity,"phoneAudio")).pause();}
            catch(Exception error){throw new AssertionError(error);}
        });
        AtomicBoolean playing=new AtomicBoolean(true);
        Thread audio=new Thread(()->{
            byte[] pcm=new byte[1024];long offset=0;
            while(playing.get()){
                for(int i=0;i<pcm.length;i++){
                    double time=(offset+i)/44100.0;
                    double kick=.15+.85*Math.exp(-(time%.5)*14);
                    double hat=.15+.85*Math.exp(-(time%.25)*24);
                    pcm[i]=(byte)(128+65*kick*Math.sin(time*2*Math.PI*110)+40*hat*Math.sin(time*2*Math.PI*1760));
                }
                ProjectMJNI.addWaveform(pcm,pcm.length);offset+=pcm.length;SystemClock.sleep(16);
            }
        },"StarterQualificationAudio");audio.start();
        try{
            JSONObject selection;
            try(InputStream input=test.getTargetContext().getAssets().open("starter-selection.json")){
                ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[4096];int n;while((n=input.read(buffer))!=-1)out.write(buffer,0,n);
                selection=new JSONObject(out.toString("UTF-8"));
            }
            Set<String> expected=new HashSet<>();JSONArray presets=selection.getJSONArray("presets");
            for(int i=0;i<presets.length();i++)expected.add(presets.getJSONObject(i).getString("name"));
            check(expected.size()==20,"starter manifest count differs");
            Set<String> seen=new HashSet<>();JSONArray captures=new JSONArray();
            for(int attempt=0;attempt<60&&seen.size()<20;attempt++){
                long until=SystemClock.elapsedRealtime()+15000;
                while(ProjectMJNI.getCurrentPresetName().isEmpty()&&SystemClock.elapsedRealtime()<until)SystemClock.sleep(50);
                String name=ProjectMJNI.getCurrentPresetName();check(expected.contains(name),"unexpected starter "+name);
                long serial=ProjectMJNI.getRenderedFrameSerial();until=SystemClock.elapsedRealtime()+15000;
                float peak=0;
                while(ProjectMJNI.getRenderedFrameSerial()<serial+90&&SystemClock.elapsedRealtime()<until){peak=Math.max(peak,ProjectMJNI.getAudioLevel());SystemClock.sleep(50);}
                check(ProjectMJNI.getRenderedFrameSerial()>=serial+90,"preset stopped rendering: "+name);
                check(peak>.1f,"synthetic audio did not reach preset: "+name);
                check(name.equals(ProjectMJNI.getCurrentPresetName()),"unexpected automatic starter change");
                if(seen.add(name)){
                    Bitmap screen=test.getUiAutomation().takeScreenshot();int bright=0;
                    for(int y=screen.getHeight()/5;y<screen.getHeight()*4/5;y+=16)for(int x=screen.getWidth()/5;x<screen.getWidth()*4/5;x+=16){
                        int c=screen.getPixel(x,y);if(Color.red(c)+Color.green(c)+Color.blue(c)>24)bright++;
                    }
                    screen.recycle();if(bright<5)capture(test,"fdroid-blank-starter");check(bright>=5,"starter stayed blank: "+name+", audio peak="+peak);
                    String image="fdroid-starter-"+seen.size();capture(test,image);
                    JSONObject record=new JSONObject();record.put("name",name);record.put("frames",ProjectMJNI.getRenderedFrameSerial()-serial);record.put("audio_peak",peak);record.put("image",image+".jpg");captures.put(record);
                }
                if(seen.size()<20){int counter=ProjectMJNI.getPresetChangeCounter();ProjectMJNI.nextPreset(true);until=SystemClock.elapsedRealtime()+10000;
                    while(ProjectMJNI.getPresetChangeCounter()==counter&&SystemClock.elapsedRealtime()<until)SystemClock.sleep(25);
                    check(ProjectMJNI.getPresetChangeCounter()!=counter,"next preset not applied");SystemClock.sleep(300);}
            }
            check(seen.equals(expected),"not every starter was rendered: "+seen.size());
            try(FileOutputStream out=new FileOutputStream(new File(test.getTargetContext().getExternalFilesDir(null),"starter-runtime.json"))){out.write(captures.toString(2).getBytes(StandardCharsets.UTF_8));}
            result.putInt("rendered_starters",seen.size());
        }finally{playing.set(false);audio.join(2000);ProjectMJNI.addWaveform(new byte[0],0);}
    }
    private static void injectArchive(Object download,File archive)throws Exception{
        check(archive.isFile(),"push full archive as external-files/official-test.zip first");
        Class<?> factory=Class.forName("com.example.projectm.visualizer.OfficialPresetDownload$ConnectionFactory");
        Object transport=Proxy.newProxyInstance(factory.getClassLoader(),new Class<?>[]{factory},(proxy,method,args)->new HttpURLConnection((URL)args[0]){
            public void connect(){}public void disconnect(){}public boolean usingProxy(){return false;}
            public int getResponseCode(){return 200;}
            public String getHeaderField(String name){return name.equals("Content-Length")?String.valueOf(archive.length()):null;}
            public InputStream getInputStream()throws IOException{return new FilterInputStream(new FileInputStream(archive)){
                public int read(byte[] b,int off,int len)throws IOException{SystemClock.sleep(3);return super.read(b,off,len);}
            };}
        });
        Field connections=download.getClass().getDeclaredField("connections");connections.setAccessible(true);connections.set(download,transport);
    }
    private static void custom(Instrumentation test)throws Exception{
        File root=new File(test.getTargetContext().getNoBackupFilesDir(),"custom-presets"),zip=new File(test.getTargetContext().getCacheDir(),"distribution-custom.zip");
        try(ZipOutputStream out=new ZipOutputStream(new FileOutputStream(zip))){for(int i=0;i<2;i++){
            out.putNextEntry(new ZipEntry("custom-"+i+".milk"));out.write("[preset00]\nfDecay=0.98\nfWaveAlpha=1\n".getBytes(StandardCharsets.UTF_8));out.closeEntry();}}
        CustomPresetPack.Pack pack=CustomPresetPack.prepare(root,zip,()->false,n->{});CustomPresetPack.activate(root,pack);
        long request=ProjectMJNI.setCustomPresetPack(pack.directory.getAbsolutePath());
        CustomPresetPack.awaitStatus(request,2,ProjectMJNI::getCustomPresetPackStatus,()->false,30000);zip.delete();
    }
    static void run(Instrumentation test,String setupCase){
        Bundle result=new Bundle();Activity activity=null;int code=Activity.RESULT_CANCELED;
        try{
            check(BuildConfig.FDROID&&test.getTargetContext().getPackageName().endsWith(".setuptest"),"requires isolated F-Droid setup APK");
            SharedPreferences prefs=test.getTargetContext().getSharedPreferences("projectm_settings",0);
            prefs.edit().putBoolean("track_access_explained",true).putBoolean("auto_change_enabled",false)
                    .putBoolean("blank_detection_v3",false).putBoolean("skip_slow_presets",false)
                    .putInt("resolution_mode",720).putString("music_category","all").commit();
            boolean starters=setupCase.equals("fdroid_starters");
            if(starters)prefs.edit().putBoolean("official_collection_offer_shown",false).commit();
            activity=test.startActivitySync(new Intent(test.getTargetContext(),MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            Object collection=field(activity,"officialCollection"),download=field(collection,"download");
            ProjectMJNI.setAutoChange(false);ProjectMJNI.setBlankDetection(false);ProjectMJNI.resetSkippedPresets();
            File root=new File(test.getTargetContext().getNoBackupFilesDir(),"official-presets");
            if(starters){
                phase(download,"idle");counts(20,0);
                check(ProjectMJNI.getCategoryPresetCount("chill")==7&&ProjectMJNI.getCategoryPresetCount("normal")==10&&ProjectMJNI.getCategoryPresetCount("intense")==2,"starter mood counts differ");
                AlertDialog consent=awaitDialog(test,collection);capture(test,"fdroid-consent");
                check(consent.getButton(AlertDialog.BUTTON_POSITIVE).isShown()&&consent.getButton(AlertDialog.BUTTON_NEGATIVE).isShown(),"both choices must be visible");
                press(test,consent.getButton(AlertDialog.BUTTON_NEGATIVE));check(CustomPresetPack.current(root)==null&&!new File(root,"download.zip").exists(),"decline created collection files");
                renderStarters(test,activity,result);
            }else if(setupCase.equals("fdroid_pack")){
                phase(download,"idle");counts(20,0);injectArchive(download,new File(test.getTargetContext().getExternalFilesDir(null),"official-test.zip"));
                ui(test,()->{try{call(collection,"open",new Class<?>[0]);}catch(Exception error){throw new AssertionError(error);}});
                long before=ProjectMJNI.getRenderedFrameSerial();press(test,awaitDialog(test,collection).getButton(AlertDialog.BUTTON_POSITIVE));
                phase(download,"installed");counts(9606,0);check(ProjectMJNI.getRenderedFrameSerial()>before+30,"rendering stalled during collection install");
                check(CustomPresetPack.current(root)!=null&&!new File(root,"download.zip").exists(),"durable collection or partial archive state differs");
                custom(test);counts(9608,2);capture(test,"fdroid-full-custom");result.putString("delivery","synthetic file-backed HTTPS adapter; real checksum/extraction/consent/native publication");
            }else if(setupCase.equals("fdroid_pack_restart")){
                phase(download,"installed");counts(9608,2);check(CustomPresetPack.current(root)!=null,"cold restart lost full collection");
                SystemClock.sleep(3500);check(dialog(collection)==null,"installed collection prompted again");capture(test,"fdroid-pack-restarted");
            }else if(setupCase.equals("fdroid_pack_removed")){
                phase(download,"installed");counts(9608,2);File previous=CustomPresetPack.current(root);
                ui(test,()->{try{call(collection,"open",new Class<?>[0]);}catch(Exception error){throw new AssertionError(error);}});
                press(test,awaitDialog(test,collection).getButton(AlertDialog.BUTTON_NEUTRAL));phase(download,"idle");counts(22,2);
                check(CustomPresetPack.current(root)==null,"removed collection pointer survives");
                check(!ProjectMJNI.isOfficialPresetPackInUse(previous.getAbsolutePath())||previous.isDirectory(),"native reader lost leased files");
                long until=SystemClock.elapsedRealtime()+30000;while(previous.exists()&&SystemClock.elapsedRealtime()<until)SystemClock.sleep(100);
                check(!previous.exists(),"retired collection was not reclaimed");capture(test,"fdroid-pack-removed");
            }else throw new AssertionError("unknown distribution setup case");
            result.putString("distribution", "PASS: "+setupCase+", "+(BuildConfig.TOUCHSCREEN?"phone touch":"TV D-pad"));code=Activity.RESULT_OK;
        }catch(Throwable failure){result.putString("failure",android.util.Log.getStackTraceString(failure));}
        finally{if(activity!=null){Activity target=activity;ui(test,target::finish);}test.finish(code,result);}
    }
}
