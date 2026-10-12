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
}
