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
}
