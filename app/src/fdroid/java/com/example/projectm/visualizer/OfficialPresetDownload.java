package com.example.projectm.visualizer;

import android.content.Context;
import android.os.Handler;
import nl.neerdael.projectm.core.ProjectMJNI;
import java.io.*;
import java.net.*;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** One process-owned collection job; UI listeners attach only while their activity is resumed. */
final class OfficialPresetDownload {
    interface ConnectionFactory { HttpURLConnection open(URL url) throws IOException; }
    interface ByteProgress { void updated(long bytes); }
    interface NativeIndex {
        long prepare(String directory); int status(long request); boolean commit(long request);
        void discard(long request); boolean inUse(String directory);
    }
    interface Listener { void onStatus(Status status); }
    static final class Status {
        final String phase, identity, error; final long bytes, total;
        Status(String phase,long bytes,long total,String identity,String error) {
            this.phase=phase;this.bytes=bytes;this.total=total;this.identity=identity;this.error=error;
        }
        boolean busy() { return !(phase.equals("idle")||phase.equals("installed")||phase.equals("canceled")||phase.equals("error")); }
    }
    private static OfficialPresetDownload instance;
    private final File root;
    private final ConnectionFactory connections;
    private final ExecutorService worker=Executors.newSingleThreadExecutor(task->{Thread t=new Thread(task,"OfficialPresets");t.setDaemon(true);return t;});
    private volatile Status status=new Status("idle",0,0,"",null);
    private volatile OfficialPresetPack.Descriptor descriptor;
    private volatile Handler main;
    private volatile Listener listener;
    private volatile HttpURLConnection activeConnection;
    private final AtomicBoolean canceled=new AtomicBoolean();
    private boolean running;
    private long listenerGeneration;

    OfficialPresetDownload(File root,ConnectionFactory connections){this.root=root;this.connections=connections;}
    static synchronized OfficialPresetDownload get(Context context) {
        if(instance==null) {
            Context app=context.getApplicationContext();
            instance=new OfficialPresetDownload(new File(app.getNoBackupFilesDir(),"official-presets"),url->(HttpURLConnection)url.openConnection());
            instance.restore(app);
        }
        return instance;
    }
    OfficialPresetPack.Descriptor descriptor(){return descriptor;}
    Status status(){return status;}
    synchronized void attach(Handler handler,Listener callback){main=handler;listener=callback;listenerGeneration++;announce(status);}
    synchronized void detach(Listener callback){if(listener==callback){listener=null;main=null;listenerGeneration++;}}
    private synchronized void announce(Status value) {
        Handler handler=main;Listener callback=listener;long generation=listenerGeneration;
        if(handler!=null&&callback!=null)handler.post(()->{synchronized(OfficialPresetDownload.this){if(generation!=listenerGeneration||callback!=listener)return;}callback.onStatus(value);});
    }
    private void publish(String phase,long bytes,long total,String identity,String error){status=new Status(phase,bytes,total,identity,error);announce(status);}
    private void restore(Context context) {
        synchronized(this){running=true;publish("restoring",0,0,"",null);}
        worker.execute(()->{
            String identity="";
            try {
                try(InputStream in=context.getAssets().open("official-pack.json")){descriptor=OfficialPresetPack.Descriptor.read(in);}
                File current=OfficialPresetPack.current(root);
                if(current!=null) {
                    identity=OfficialPresetPack.identity(current);
                    long request=ProjectMJNI.setOfficialPresetPack(current.getAbsolutePath());
                    CustomPresetPack.awaitStatus(request,2,ProjectMJNI::getOfficialPresetPackStatus,()->false,30000);
                }else if(CustomPresetPack.current(root)!=null)CustomPresetPack.restore(root,null);
                publish(identity.isEmpty()?"idle":"installed",0,0,identity,null);
                CustomPresetPack.scheduleCleanup(root,d->ProjectMJNI.isOfficialPresetPackInUse(d.getAbsolutePath()));
            }catch(Exception error){publish("error",0,0,identity,message(error));}
            finally{synchronized(this){running=false;}}
        });
    }
    synchronized void start(OfficialPresetPack.Descriptor next,NativeIndex index) {
        if(running||next==null)return;
        running=true;canceled.set(false);String previousIdentity=status.identity;
        publish("downloading",0,next.bytes,previousIdentity,null);
        worker.execute(()->install(next,index,previousIdentity));
    }
    synchronized void cancel(){
        if(status.phase.equals("committing"))return;
        canceled.set(true);
        HttpURLConnection connection=activeConnection;
        if(connection!=null)connection.disconnect();
    }
    private void install(OfficialPresetPack.Descriptor next,NativeIndex index,String previousIdentity) {
        File archive=new File(root,"download.zip");CustomPresetPack.Pack pack=null;long request=0;boolean committed=false;
        File previous=OfficialPresetPack.current(root);
        try {
            if(!root.isDirectory()&&!root.mkdirs())throw new IOException("Cannot create collection storage");
            if(root.getUsableSpace()<next.bytes+next.expandedBytes+16L*1024*1024)throw new IOException("Not enough storage for the collection");
            downloadArchive(next,archive,url->{
                HttpURLConnection connection=connections.open(url);activeConnection=connection;
                if(canceled.get()){connection.disconnect();throw new IOException("Collection operation canceled");}
                return connection;
            },canceled::get,n->publish("downloading",n,next.bytes,previousIdentity,null));
            publish("verifying",next.bytes,next.bytes,previousIdentity,null);
            pack=OfficialPresetPack.prepare(root,archive,next,canceled::get,n->publish("extracting",n,next.presetCount,previousIdentity,null));
            OfficialPresetPack.canceled(canceled::get);
            publish("indexing",0,0,previousIdentity,null);
            request=index.prepare(pack.directory.getAbsolutePath());
            CustomPresetPack.awaitStatus(request,1,index::status,canceled::get,30000);
            synchronized(this){OfficialPresetPack.canceled(canceled::get);publish("committing",0,0,previousIdentity,null);}
            synchronized(CustomPresetPack.STORE_LOCK) {
                CustomPresetPack.activate(root,pack);
                try {
                    if(!index.commit(request))throw new IOException("Collection changed while preparing; retry the download");
                    committed=true;
                }finally{if(!committed)CustomPresetPack.restore(root,previous);}
            }
            publish("installed",next.bytes,next.bytes,next.identity,null);
        }catch(Exception error){publish(canceled.get()?"canceled":"error",0,0,previousIdentity,message(error));}
        finally {
            activeConnection=null;
            archive.delete();
            if(!committed&&request!=0)index.discard(request);
            if(!committed&&pack!=null&&!index.inUse(pack.directory.getAbsolutePath()))CustomPresetPack.delete(pack.directory);
            CustomPresetPack.scheduleCleanup(root,d->index.inUse(d.getAbsolutePath()));
            synchronized(this){running=false;}
        }
    }
    synchronized void remove(NativeIndex index) {
        if(running)return;running=true;canceled.set(false);String identity=status.identity;
        publish("indexing",0,0,identity,null);
        worker.execute(()->{
            long request=0;boolean committed=false;File previous=OfficialPresetPack.current(root);
            try {
                request=index.prepare("");CustomPresetPack.awaitStatus(request,1,index::status,canceled::get,30000);
                synchronized(this){OfficialPresetPack.canceled(canceled::get);publish("committing",0,0,identity,null);}
                synchronized(CustomPresetPack.STORE_LOCK) {
                    CustomPresetPack.restore(root,null);
                    try{if(!index.commit(request))throw new IOException("Collection changed while removing; retry");committed=true;}
                    finally{if(!committed)CustomPresetPack.restore(root,previous);}
                }
                publish("idle",0,0,"",null);
            }catch(Exception error){publish(canceled.get()?"canceled":"error",0,0,identity,message(error));}
            finally{if(!committed&&request!=0)index.discard(request);CustomPresetPack.scheduleCleanup(root,d->index.inUse(d.getAbsolutePath()));synchronized(this){running=false;}}
        });
    }
    static void downloadArchive(OfficialPresetPack.Descriptor descriptor,File target,ConnectionFactory factory,
            CustomPresetPack.Cancellation cancellation,ByteProgress progress)throws IOException {
        boolean success=false;
        try {
            URL url=new URL(descriptor.url);
            for(int hop=0;hop<=5;hop++) {
                OfficialPresetPack.canceled(cancellation);
                if(!url.getProtocol().equals("https")||url.getUserInfo()!=null)throw new IOException("Collection redirect requires HTTPS");
                HttpURLConnection connection=factory.open(url);
                try {
                    connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(20000);connection.setReadTimeout(20000);
                    connection.setRequestProperty("Accept-Encoding","identity");
                    int response=connection.getResponseCode();
                    if(response==301||response==302||response==303||response==307||response==308) {
                        String location=connection.getHeaderField("Location");if(location==null)throw new IOException("Missing collection redirect");
                        url=new URL(url,location);continue;
                    }
                    if(response!=200)throw new IOException("Collection server returned HTTP "+response);
                    String length=connection.getHeaderField("Content-Length");
                    if(length!=null)try{if(Long.parseLong(length)!=descriptor.bytes)throw new IOException("Collection download size differs");}catch(NumberFormatException invalid){throw new IOException("Invalid collection size",invalid);}
                    MessageDigest digest;
                    try{digest=MessageDigest.getInstance("SHA-256");}catch(Exception unavailable){throw new IOException(unavailable);}
                    long received=0,lastProgress=0;
                    try(InputStream input=connection.getInputStream();FileOutputStream output=new FileOutputStream(target)) {
                        byte[] buffer=new byte[32768];int n;
                        while((n=input.read(buffer))!=-1) {
                            OfficialPresetPack.canceled(cancellation);received+=n;
                            if(received>descriptor.bytes)throw new IOException("Collection exceeds expected download size");
                            digest.update(buffer,0,n);output.write(buffer,0,n);
                            if(received-lastProgress>=262144||received==descriptor.bytes){progress.updated(received);lastProgress=received;}
                        }
                        if(received!=descriptor.bytes)throw new IOException("Collection download ended early");
                        StringBuilder actual=new StringBuilder();for(byte b:digest.digest())actual.append(String.format(Locale.ROOT,"%02x",b&255));
                        if(!actual.toString().equals(descriptor.sha256))throw new IOException("Collection download checksum differs");
                        output.getFD().sync();success=true;return;
                    }
                }finally{connection.disconnect();}
            }
            throw new IOException("Too many collection redirects");
        }finally{if(!success)target.delete();}
    }
    private static String message(Exception error){return error.getMessage()==null?"Collection operation failed":error.getMessage();}
}
