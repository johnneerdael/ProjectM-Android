package com.example.projectm.visualizer;

import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
import java.lang.reflect.*;
import java.lang.reflect.Proxy;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.atomic.AtomicInteger;

public class OfficialPresetDownloadTest {
    private Class<?> component() {
        Class<?> c=null;try{c=Class.forName("com.example.projectm.visualizer.OfficialPresetDownload");}catch(ClassNotFoundException missing){}
        assertNotNull("verified collection transfer is missing",c);return c;
    }
    static class Connection extends HttpURLConnection {
        final int response;final String redirect;final byte[] bytes;boolean disconnected;
        Connection(URL u,int status,String location,byte[] bytes){super(u);response=status;redirect=location;this.bytes=bytes;}
        public int getResponseCode(){return response;}
        public String getHeaderField(String name){return name.equals("Location")?redirect:null;}
        public long getContentLengthLong(){return bytes.length;}
        public InputStream getInputStream(){return new ByteArrayInputStream(bytes);}
        public void connect(){}public void disconnect(){disconnected=true;}public boolean usingProxy(){return false;}
    }
    private Object descriptor(byte[] bytes,long size)throws Exception {
        Class<?> c=Class.forName("com.example.projectm.visualizer.OfficialPresetPack$Descriptor");
        String json="{\"schema_version\":1,\"collection_id\":\""+OfficialPresetPackTest.sha(new byte[0])+"\",\"archive_sha256\":\""+OfficialPresetPackTest.sha(bytes)+"\",\"archive_url\":\"https://github.com/collection.zip\",\"compressed_bytes\":"+size+",\"expanded_bytes\":1,\"preset_count\":1,\"texture_count\":0}";
        return c.getDeclaredMethod("read",InputStream.class).invoke(null,new ByteArrayInputStream(json.getBytes(StandardCharsets.UTF_8)));
    }
    private void transfer(Class<?> c,Object d,File out,Object factory,boolean canceled)throws Exception {
        Class<?> f=Class.forName(c.getName()+"$ConnectionFactory");Class<?> p=Class.forName(c.getName()+"$ByteProgress");
        Object progress=Proxy.newProxyInstance(getClass().getClassLoader(),new Class<?>[]{p},(proxy,method,args)->null);
        c.getDeclaredMethod("downloadArchive",d.getClass(),File.class,f,CustomPresetPack.Cancellation.class,p)
                .invoke(null,d,out,factory,(CustomPresetPack.Cancellation)()->canceled,progress);
    }
    @Test public void redirectsAreHttpsOnlyAndConnectionsClose()throws Exception {
        Class<?> c=component();Class<?> f=Class.forName(c.getName()+"$ConnectionFactory");byte[] bytes={1,2,3};
        for(boolean bad:new boolean[]{false,true}) {
            AtomicInteger opened=new AtomicInteger();Connection[] connections=new Connection[2];
            Object factory=Proxy.newProxyInstance(getClass().getClassLoader(),new Class<?>[]{f},(proxy,method,args)->{
                int i=opened.getAndIncrement();return connections[i]=new Connection((URL)args[0],i==0?302:200,i==0?(bad?"http":"https")+"://release-assets.githubusercontent.com/collection.zip":null,i==0?new byte[0]:bytes);
            });
            File out=Files.createTempFile("transfer",".zip").toFile();
            try {
                if(bad){try{transfer(c,descriptor(bytes,3),out,factory,false);fail("HTTP redirect accepted");}catch(InvocationTargetException expected){assertTrue(expected.getCause() instanceof IOException);}}
                else{transfer(c,descriptor(bytes,3),out,factory,false);assertArrayEquals(bytes,Files.readAllBytes(out.toPath()));}
                assertTrue(connections[0].disconnected);if(!bad)assertTrue(connections[1].disconnected);
            }finally{out.delete();}
        }
    }
    @Test public void cancellationAndOversizeDoNotLeaveArchive()throws Exception {
        Class<?> c=component();Class<?> f=Class.forName(c.getName()+"$ConnectionFactory");byte[] bytes={1,2,3};
        for(boolean cancel:new boolean[]{false,true}) {
            AtomicInteger opened=new AtomicInteger();
            Object factory=Proxy.newProxyInstance(getClass().getClassLoader(),new Class<?>[]{f},(proxy,method,args)->{opened.incrementAndGet();return new Connection((URL)args[0],200,null,bytes);});
            File out=Files.createTempFile("canceled",".zip").toFile();
            try {
                try{transfer(c,descriptor(bytes,2),out,factory,cancel);fail("invalid transfer accepted");}catch(InvocationTargetException expected){assertTrue(expected.getCause() instanceof IOException);}
                assertFalse(out.exists());if(cancel)assertEquals(0,opened.get());
            }finally{out.delete();}
        }
    }
    @Test public void noConnectionIsOpenedWithoutExplicitStart()throws Exception {
        AtomicInteger opened=new AtomicInteger();File root=Files.createTempDirectory("no-consent").toFile();
        try {
            OfficialPresetDownload value=new OfficialPresetDownload(root,url->{opened.incrementAndGet();throw new IOException("no consent");});
            assertEquals("idle",value.status().phase);value.cancel();
            assertEquals(0,opened.get());assertFalse(value.status().busy());
        }finally{CustomPresetPack.delete(root);}
    }
    @Test public void cancelDisconnectsBlockedConnectionImmediately()throws Exception {
        File root=Files.createTempDirectory("cancel-socket").toFile();
        java.util.concurrent.CountDownLatch opened=new java.util.concurrent.CountDownLatch(1),release=new java.util.concurrent.CountDownLatch(1);
        Connection connection=new Connection(new URL("https://github.com/collection.zip"),200,null,new byte[]{1}) {
            public int getResponseCode(){opened.countDown();try{release.await(5,java.util.concurrent.TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}return 200;}
            public void disconnect(){super.disconnect();release.countDown();}
        };
        try {
            OfficialPresetDownload download=new OfficialPresetDownload(root,url->connection);
            download.start((OfficialPresetPack.Descriptor)descriptor(new byte[]{1},1),new OfficialPresetDownload.NativeIndex(){
                public long prepare(String p){return 1;}public int status(long r){return 1;}public boolean commit(long r){return true;}public void discard(long r){}public boolean inUse(String p){return false;}
            });
            assertTrue(opened.await(5,java.util.concurrent.TimeUnit.SECONDS));download.cancel();
            assertTrue("cancel must release a blocked network socket",connection.disconnected);
        }finally{release.countDown();Thread.sleep(50);CustomPresetPack.delete(root);}
    }

    @Test public void finalFailureIsAnnouncedOnlyAfterCleanupAllowsRetry()throws Exception {
        File parent=Files.createTempDirectory("official-retry").toFile(),root=new File(parent,"store");
        java.util.concurrent.CountDownLatch cleanup=new java.util.concurrent.CountDownLatch(1),release=new java.util.concurrent.CountDownLatch(1);
        try {
            OfficialPresetPackTest fixture=new OfficialPresetPackTest();
            File archive=fixture.archive(parent,false,false);
            OfficialPresetPack.Descriptor d=(OfficialPresetPack.Descriptor)fixture.descriptor(OfficialPresetPack.class,archive,fixture.expanded(archive),null);
            byte[] bytes=Files.readAllBytes(archive.toPath());
            OfficialPresetDownload download=new OfficialPresetDownload(root,url->new Connection(url,200,null,bytes));
            download.start(d,new OfficialPresetDownload.NativeIndex(){
                public long prepare(String p){return 1;}public int status(long r){return 1;}
                public boolean commit(long r){return false;}public void discard(long r){}
                public boolean inUse(String p){cleanup.countDown();try{release.await(5,java.util.concurrent.TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}return false;}
            });
            assertTrue(cleanup.await(5,java.util.concurrent.TimeUnit.SECONDS));
            assertTrue("retry must wait until failed generation cleanup completes",download.status().busy());
            release.countDown();
            long deadline=System.currentTimeMillis()+5000;
            while(download.status().busy()&&System.currentTimeMillis()<deadline)Thread.sleep(10);
            assertEquals("error",download.status().phase);
        }finally{release.countDown();Thread.sleep(50);CustomPresetPack.delete(parent);}
    }

    @Test public void cancelBeforePublicationRollsBackAndFinalPublicationFinishes()throws Exception {
        File parent=Files.createTempDirectory("official-commit-cancel").toFile();
        try {
            OfficialPresetPackTest fixture=new OfficialPresetPackTest();File archive=fixture.archive(parent,false,false);
            OfficialPresetPack.Descriptor d=(OfficialPresetPack.Descriptor)fixture.descriptor(OfficialPresetPack.class,archive,fixture.expanded(archive),null);
            byte[] bytes=Files.readAllBytes(archive.toPath());
            for(boolean duringCommit:new boolean[]{false,true}){
                File root=new File(parent,"store-"+duringCommit);
                CustomPresetPack.Pack previous=OfficialPresetPack.prepare(root,archive,d,()->false,n->{});CustomPresetPack.activate(root,previous);
                OfficialPresetDownload download=new OfficialPresetDownload(root,url->new Connection(url,200,null,bytes));
                AtomicInteger commits=new AtomicInteger();
                download.start(d,new OfficialPresetDownload.NativeIndex(){
                    public long prepare(String p){return 1;}
                    public int status(long r){if(!duringCommit)download.cancel();return 1;}
                    public boolean commit(long r){commits.incrementAndGet();download.cancel();return true;}
                    public void discard(long r){}public boolean inUse(String p){return false;}
                });
                long until=System.currentTimeMillis()+5000;while(download.status().busy()&&System.currentTimeMillis()<until)Thread.sleep(10);
                assertEquals(duringCommit?"installed":"canceled",download.status().phase);
                assertEquals(duringCommit?1:0,commits.get());
                File current=OfficialPresetPack.current(root);assertNotNull(current);
                if(duringCommit)assertNotEquals(previous.directory,current);else assertEquals(previous.directory,current);
                assertFalse(new File(root,"download.zip").exists());
            }
        }finally{CustomPresetPack.delete(parent);}
    }

    @Test public void cleanupCannotDeleteStagingBeforeNativeOwnership()throws Exception {
        File parent=Files.createTempDirectory("official-cleanup-race").toFile(),root=new File(parent,"store");
        java.util.concurrent.atomic.AtomicBoolean survived=new java.util.concurrent.atomic.AtomicBoolean();
        java.util.concurrent.atomic.AtomicReference<java.util.concurrent.Future<?>> cleanup=new java.util.concurrent.atomic.AtomicReference<>();
        try {
            OfficialPresetPackTest fixture=new OfficialPresetPackTest();File archive=fixture.archive(parent,false,false);
            OfficialPresetPack.Descriptor d=(OfficialPresetPack.Descriptor)fixture.descriptor(OfficialPresetPack.class,archive,fixture.expanded(archive),null);
            byte[] bytes=Files.readAllBytes(archive.toPath());
            OfficialPresetDownload download=new OfficialPresetDownload(root,url->new Connection(url,200,null,bytes));
            download.start(d,new OfficialPresetDownload.NativeIndex(){
                public long prepare(String path){
                    java.util.concurrent.Future<?> job=CustomPresetPack.scheduleCleanup(root,directory->false);cleanup.set(job);
                    try{job.get(200,java.util.concurrent.TimeUnit.MILLISECONDS);}
                    catch(java.util.concurrent.TimeoutException protectedStaging){}
                    catch(Exception failed){throw new RuntimeException(failed);}
                    survived.set(new File(path,"official-presets.idx").isFile());return 1;
                }
                public int status(long request){return 1;}public boolean commit(long request){return true;}
                public void discard(long request){}public boolean inUse(String path){return false;}
            });
            long until=System.currentTimeMillis()+5000;while(download.status().busy()&&System.currentTimeMillis()<until)Thread.sleep(10);
            assertTrue("cleanup deleted staging before native ownership",survived.get());
            assertEquals("installed",download.status().phase);
            cleanup.get().get(5,java.util.concurrent.TimeUnit.SECONDS);
            assertNotNull("the published generation must survive cleanup",OfficialPresetPack.current(root));
        }finally{CustomPresetPack.delete(parent);}
    }

    @Test public void truncatedTransferNeverLeavesAnArchive()throws Exception {
        File file=Files.createTempFile("official-truncated",".zip").toFile();byte[] bytes={1,2,3};
        try{
            Class<?> c=component(),f=Class.forName(c.getName()+"$ConnectionFactory");
            Object factory=Proxy.newProxyInstance(getClass().getClassLoader(),new Class<?>[]{f},(proxy,method,args)->new Connection((URL)args[0],200,null,bytes));
            try{transfer(c,descriptor(bytes,4),file,factory,false);fail("truncated archive accepted");}
            catch(InvocationTargetException expected){assertTrue(expected.getCause().getMessage().contains("ended early"));}
            assertFalse(file.exists());
        }finally{file.delete();}
    }
    @Test public void startupRecoveryRemovesInterruptedFilesAndPreservesActiveGeneration()throws Exception {
        File parent=Files.createTempDirectory("official-killed-download").toFile(),root=new File(parent,"store");
        try {
            OfficialPresetPackTest fixture=new OfficialPresetPackTest();File archive=fixture.archive(parent,false,false);
            OfficialPresetPack.Descriptor descriptor=(OfficialPresetPack.Descriptor)fixture.descriptor(OfficialPresetPack.class,archive,fixture.expanded(archive),null);
            CustomPresetPack.Pack pack=OfficialPresetPack.prepare(root,archive,descriptor,()->false,n->{});CustomPresetPack.activate(root,pack);
            Files.write(new File(root,"download.zip").toPath(),new byte[65536]);
            Files.write(new File(root,"current.tmp").toPath(),"interrupted pointer".getBytes(StandardCharsets.UTF_8));
            Method recover=OfficialPresetDownload.class.getDeclaredMethod("recoverFiles",File.class);recover.invoke(null,root);
            assertFalse(new File(root,"download.zip").exists());assertFalse(new File(root,"current.tmp").exists());
            assertEquals(pack.directory,OfficialPresetPack.current(root));assertTrue(new File(pack.directory,"official-presets.idx").isFile());
        }finally{CustomPresetPack.delete(parent);}
    }

    // The Mood attribute source follows committed(): the generation the native engine has actually
    // committed, never the durable pointer alone.
    private static java.util.concurrent.Callable<InputStream> descriptorSource()throws Exception {
        String json="{\"schema_version\":1,\"collection_id\":\""+OfficialPresetPackTest.sha("collection".getBytes())+"\",\"archive_sha256\":\""+OfficialPresetPackTest.sha(new byte[]{1})+"\",\"archive_url\":\"https://github.com/collection.zip\",\"compressed_bytes\":1,\"expanded_bytes\":1,\"preset_count\":2,\"texture_count\":0}";
        return ()->new ByteArrayInputStream(json.getBytes(StandardCharsets.UTF_8));
    }
    /** Scripted auto-apply restore: status() reports the native request state. */
    private abstract static class Restore implements OfficialPresetDownload.RestoreIndex {
        final AtomicInteger discards=new AtomicInteger();final java.util.List<String> applied=new java.util.ArrayList<>();
        volatile boolean pending;
        public long apply(String directory){applied.add(directory);return 7;}
        public void discard(long request){discards.incrementAndGet();}
        public boolean inUse(String directory){return false;}
        public void pending(boolean value){pending=value;}
    }
    private static void settle(OfficialPresetDownload download)throws Exception {
        long until=System.currentTimeMillis()+5000;
        while(download.status().busy()&&System.currentTimeMillis()<until)Thread.sleep(10);
        assertFalse("operation did not settle",download.status().busy());
    }
    private static File installed(File parent,File root)throws Exception {
        OfficialPresetPackTest fixture=new OfficialPresetPackTest();File archive=fixture.archive(parent,false,false);
        OfficialPresetPack.Descriptor d=(OfficialPresetPack.Descriptor)fixture.descriptor(OfficialPresetPack.class,archive,fixture.expanded(archive),null);
        CustomPresetPack.Pack pack=OfficialPresetPack.prepare(root,archive,d,()->false,n->{});CustomPresetPack.activate(root,pack);
        return pack.directory;
    }
    @Test public void restoreTimeoutOrFailureWithAValidPointerFallsBackToBundledAttributes()throws Exception {
        for(boolean timeout:new boolean[]{true,false}) {
            File parent=Files.createTempDirectory("official-restore-failed").toFile(),root=new File(parent,"store");
            try {
                File generation=installed(parent,root);
                OfficialPresetDownload download=new OfficialPresetDownload(root,url->{throw new IOException("no transfer");});
                Restore index=new Restore(){
                    public int status(long request){return timeout?(discards.get()==0?0:-1):-1;}
                };
                download.restore(descriptorSource(),index,timeout?100:5000);
                settle(download);
                assertEquals(java.util.Collections.singletonList(generation.getAbsolutePath()),index.applied);
                assertEquals("the unapplied request is discarded",1,index.discards.get());
                assertFalse("restore-pending cleared",index.pending);
                assertEquals("error",download.status().phase);
                assertEquals("nothing committed: the status names no collection","",download.status().identity);
                assertNull("the engine keeps the starters",download.committed());
                assertNull("Mood uses the bundled starter attributes",OfficialCollection.attributesFile(download.committed()));
                assertEquals("the durable pointer remains for the next start",generation,OfficialPresetPack.current(root));
            }finally{CustomPresetPack.delete(parent);}
        }
    }
    @Test public void restoreCommittedOnlyWhenTheEngineAppliedTheRequest()throws Exception {
        for(boolean late:new boolean[]{false,true}) {
            File parent=Files.createTempDirectory("official-restore-ok").toFile(),root=new File(parent,"store");
            try {
                File generation=installed(parent,root);
                OfficialPresetDownload download=new OfficialPresetDownload(root,url->{throw new IOException("no transfer");});
                // late: the engine committed after the wait expired; discard is then a no-op and the
                // request still reports applied, so the pack is the committed one.
                Restore index=new Restore(){
                    public int status(long request){return !late||discards.get()>0?2:0;}
                };
                download.restore(descriptorSource(),index,late?100:5000);
                settle(download);
                assertEquals("installed",download.status().phase);
                assertEquals(OfficialPresetPackTest.sha("collection".getBytes()),download.status().identity);
                assertEquals(generation,download.committed());
                assertEquals(new File(generation,"preset-attributes/attributes.tsv"),OfficialCollection.attributesFile(download.committed()));
            }finally{CustomPresetPack.delete(parent);}
        }
    }
    @Test public void pendingRestoreKeepsTheBundledSourceUntilItSettles()throws Exception {
        File parent=Files.createTempDirectory("official-restore-pending").toFile(),root=new File(parent,"store");
        java.util.concurrent.CountDownLatch release=new java.util.concurrent.CountDownLatch(1),waiting=new java.util.concurrent.CountDownLatch(1);
        try {
            File generation=installed(parent,root);
            OfficialPresetDownload download=new OfficialPresetDownload(root,url->{throw new IOException("no transfer");});
            Restore index=new Restore(){
                public int status(long request){
                    waiting.countDown();
                    try{return release.await(5,java.util.concurrent.TimeUnit.SECONDS)?2:0;}
                    catch(InterruptedException e){Thread.currentThread().interrupt();return 0;}
                }
            };
            download.restore(descriptorSource(),index,10000);
            assertTrue(waiting.await(5,java.util.concurrent.TimeUnit.SECONDS));
            assertTrue(download.status().busy());
            assertNull("no switch while the restore is pending",download.committed());
            release.countDown();settle(download);
            assertEquals(generation,download.committed());
        }finally{release.countDown();Thread.sleep(50);CustomPresetPack.delete(parent);}
    }
    @Test public void installAndRemoveMoveTheCommittedGenerationOnlyOnNativeCommit()throws Exception {
        File parent=Files.createTempDirectory("official-install-committed").toFile(),root=new File(parent,"store");
        try {
            File previous=installed(parent,root);
            OfficialPresetPackTest fixture=new OfficialPresetPackTest();File archive=fixture.archive(new File(parent,"next-archive"){{mkdirs();}},false,false);
            OfficialPresetPack.Descriptor d=(OfficialPresetPack.Descriptor)fixture.descriptor(OfficialPresetPack.class,archive,fixture.expanded(archive),null);
            byte[] bytes=Files.readAllBytes(archive.toPath());
            OfficialPresetDownload download=new OfficialPresetDownload(root,url->new Connection(url,200,null,bytes));
            download.restore(descriptorSource(),new Restore(){public int status(long r){return 2;}},5000);
            settle(download);assertEquals(previous,download.committed());
            java.util.concurrent.CountDownLatch committing=new java.util.concurrent.CountDownLatch(1),release=new java.util.concurrent.CountDownLatch(1);
            java.util.concurrent.atomic.AtomicBoolean accept=new java.util.concurrent.atomic.AtomicBoolean();
            java.util.concurrent.atomic.AtomicReference<File> pendingObserved=new java.util.concurrent.atomic.AtomicReference<>();
            OfficialPresetDownload.NativeIndex index=new OfficialPresetDownload.NativeIndex(){
                public long prepare(String p){return 1;}public int status(long r){return 1;}
                public boolean commit(long r){
                    pendingObserved.set(download.committed());committing.countDown();
                    try{release.await(5,java.util.concurrent.TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}
                    return accept.get();
                }
                public void discard(long r){}public boolean inUse(String p){return false;}
            };
            // Failed commit: the engine keeps the previous collection, and so does Mood.
            download.start(d,index);assertTrue(committing.await(5,java.util.concurrent.TimeUnit.SECONDS));
            assertEquals("pending install keeps the previous source",previous,pendingObserved.get());
            release.countDown();settle(download);
            assertEquals("error",download.status().phase);assertEquals(previous,download.committed());
            // Successful commit: the new generation.
            accept.set(true);download.start(d,index);settle(download);
            assertEquals("installed",download.status().phase);
            File next=download.committed();assertNotNull(next);assertNotEquals(previous,next);
            assertEquals(OfficialPresetPack.current(root),next);
            // Removal: bundled starters once the engine committed the empty collection.
            download.remove(index);settle(download);
            assertEquals("idle",download.status().phase);assertNull(download.committed());
        }finally{CustomPresetPack.delete(parent);}
    }
}
