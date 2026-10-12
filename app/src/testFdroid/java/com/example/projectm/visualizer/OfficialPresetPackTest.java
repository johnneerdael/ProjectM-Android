package com.example.projectm.visualizer;

import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;

public class OfficialPresetPackTest {
    private Class<?> component() {
        Class<?> value = null;
        try { value = Class.forName("com.example.projectm.visualizer.OfficialPresetPack"); }
        catch (ClassNotFoundException missing) { }
        assertNotNull("verified official archive installer is missing", value);
        return value;
    }
    static String sha(byte[] bytes) throws Exception {
        StringBuilder out = new StringBuilder();
        for (byte b : MessageDigest.getInstance("SHA-256").digest(bytes)) out.append(String.format(Locale.ROOT, "%02x", b & 255));
        return out.toString();
    }
    Object descriptor(Class<?> c, File archive, long expanded, String override) throws Exception {
        String json = "{\"schema_version\":1,\"collection_id\":\"" + sha("collection".getBytes()) + "\","
                + "\"archive_url\":\"https://github.com/example/collection.zip\",\"archive_sha256\":\""
                + (override == null ? sha(Files.readAllBytes(archive.toPath())) : override) + "\",\"compressed_bytes\":" + archive.length()
                + ",\"expanded_bytes\":" + expanded + ",\"preset_count\":2,\"texture_count\":0}";
        Class<?> d = Class.forName(c.getName() + "$Descriptor");
        return d.getDeclaredMethod("read", InputStream.class).invoke(null, new ByteArrayInputStream(json.getBytes(StandardCharsets.UTF_8)));
    }
    File archive(File parent, boolean badMetadata, boolean extra) throws Exception {
        Map<String,byte[]> files = new LinkedHashMap<>();
        files.put("presets/one.milk", "[preset00]\nper_frame_1=q1=bass;\n".getBytes());
        files.put("presets/two.milk", "[preset00]\nper_frame_1=q1=mid;\n".getBytes());
        files.put("presets.idx", "one.milk\t17\ntwo.milk\t3\n".getBytes());
        for (String g : new String[]{"chill","normal","intense"}) files.put("preset-genres/genres/"+g+".idx", (badMetadata ? "unknown.milk\t3\n" : "one.milk\t17\n").getBytes());
        files.put("preset-genres/manifest.json", "{}".getBytes());
        files.put("preset-genres/presets.jsonl", "{}\n".getBytes());
        files.put("LICENSE", "notice".getBytes());
        files.put("LICENSES/CC0-1.0.txt", "notice".getBytes());
        files.put("docs/THIRD_PARTY.md", "notice".getBytes());
        StringBuilder manifest = new StringBuilder("{\"schema_version\":1,\"collection_id\":\""+sha("collection".getBytes())+"\",\"files\":[");
        for (Map.Entry<String,byte[]> e:files.entrySet()) {
            if(manifest.charAt(manifest.length()-1)!='[')manifest.append(',');
            manifest.append("{\"path\":\"").append(e.getKey()).append("\",\"bytes\":").append(e.getValue().length).append(",\"sha256\":\"").append(sha(e.getValue())).append("\"}");
        }
        files.put("manifest.json",manifest.append("]}").toString().getBytes(StandardCharsets.UTF_8));
        File archive = new File(parent,"collection.zip");
        try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(archive))) {
            for(Map.Entry<String,byte[]> e:files.entrySet()){zip.putNextEntry(new ZipEntry(e.getKey()));zip.write(e.getValue());zip.closeEntry();}
            if(extra){zip.putNextEntry(new ZipEntry("unexpected.txt"));zip.write(1);zip.closeEntry();}
        }
        return archive;
    }
    long expanded(File archive)throws Exception {
        try(ZipFile zip=new ZipFile(archive)){long sum=0;Enumeration<? extends ZipEntry> entries=zip.entries();while(entries.hasMoreElements())sum+=entries.nextElement().getSize();return sum;}
    }
    private CustomPresetPack.Pack prepare(Class<?> c,File root,File zip,Object descriptor)throws Exception {
        return (CustomPresetPack.Pack)c.getDeclaredMethod("prepare",File.class,File.class,descriptor.getClass(),CustomPresetPack.Cancellation.class,CustomPresetPack.Progress.class)
                .invoke(null,root,zip,descriptor,(CustomPresetPack.Cancellation)()->false,(CustomPresetPack.Progress)n->{});
    }
    @Test public void officialWeightsAndMoodsPreserveCanonicalNames()throws Exception {
        Class<?> c=component();File parent=Files.createTempDirectory("official-pack").toFile();
        try {
            File zip=archive(parent,false,false);File root=new File(parent,"official");
            Object d=descriptor(c,zip,expanded(zip),null);CustomPresetPack.Pack pack=prepare(c,root,zip,d);
            String index=new String(Files.readAllBytes(new File(pack.directory,"official-presets.idx").toPath()),StandardCharsets.UTF_8);
            assertTrue(index.contains("\tone.milk\t17\n"));assertTrue(index.contains("\ttwo.milk\t3\n"));
            CustomPresetPack.activate(root,pack);
            assertEquals(pack.directory,c.getDeclaredMethod("current",File.class).invoke(null,root));
            assertFalse(new File(parent,"custom/current").exists());
            new File(pack.directory,"installed.json").delete();
            assertNull(c.getDeclaredMethod("current",File.class).invoke(null,root));
        }finally{CustomPresetPack.delete(parent);}
    }
    @Test public void badDigestExtraFilesAndBadMoodsNeverPublish()throws Exception {
        Class<?> c=component();File parent=Files.createTempDirectory("official-reject").toFile();
        try {
            for(int mode=0;mode<3;mode++) {
                File zip=archive(parent,mode==2,mode==1);File root=new File(parent,"root");
                Object d=descriptor(c,zip,expanded(zip),mode==0?sha("wrong".getBytes()):null);
                try{prepare(c,root,zip,d);fail("corrupt official pack accepted");}catch(InvocationTargetException expected){assertTrue(expected.getCause() instanceof IOException);}
                assertFalse(new File(root,"current").exists());
            }
        }finally{CustomPresetPack.delete(parent);}
    }
    @Test public void descriptorRejectsPlainHttpAndFractionalSizes()throws Exception {
        Class<?> c=component();Class<?> d=Class.forName(c.getName()+"$Descriptor");
        for(String json:new String[]{"{}","{\"schema_version\":1,\"archive_url\":\"http://example.com/pack.zip\"}","{\"schema_version\":1,\"compressed_bytes\":1.5}"}) {
            try{d.getDeclaredMethod("read",InputStream.class).invoke(null,new ByteArrayInputStream(json.getBytes(StandardCharsets.UTF_8)));fail("invalid descriptor accepted");}
            catch(InvocationTargetException expected){assertTrue(expected.getCause() instanceof IOException);}
        }
    }
    @Test public void failedNativePublicationRestoresPreviousDurablePointer()throws Exception {
        Class<?> c=component();File parent=Files.createTempDirectory("official-rollback").toFile();
        try {
            File zip=archive(parent,false,false),root=new File(parent,"official");
            OfficialPresetPack.Descriptor d=(OfficialPresetPack.Descriptor)descriptor(c,zip,expanded(zip),null);
            CustomPresetPack.Pack previous=prepare(c,root,zip,d);CustomPresetPack.activate(root,previous);
            byte[] bytes=Files.readAllBytes(zip.toPath());
            OfficialPresetDownload download=new OfficialPresetDownload(root,url->new OfficialPresetDownloadTest.Connection(url,200,null,bytes));
            download.start(d,new OfficialPresetDownload.NativeIndex(){
                public long prepare(String dir){return 1;}public int status(long request){return 1;}
                public boolean commit(long request){return false;}public void discard(long request){}
                public boolean inUse(String dir){return false;}
            });
            long deadline=System.currentTimeMillis()+10000;
            while(download.status().busy()&&System.currentTimeMillis()<deadline)Thread.sleep(10);
            assertEquals("error",download.status().phase);
            assertEquals(previous.directory,OfficialPresetPack.current(root));
            assertFalse(new File(root,"download.zip").exists());
        }finally{CustomPresetPack.delete(parent);}
    }
    @Test public void corruptInstalledIndexFallsBackWithoutChangingCustomStore()throws Exception {
        Class<?> c=component();File parent=Files.createTempDirectory("official-corrupt").toFile();
        try {
            File zip=archive(parent,false,false),root=new File(parent,"official");
            CustomPresetPack.Pack pack=prepare(c,root,zip,descriptor(c,zip,expanded(zip),null));CustomPresetPack.activate(root,pack);
            Files.write(new File(pack.directory,"official-presets.idx").toPath(),"corrupt".getBytes());
            assertNull(OfficialPresetPack.current(root));
            assertFalse(new File(parent,"custom/current").exists());
        }finally{CustomPresetPack.delete(parent);}
    }

    @Test public void missingOrChangedInstalledPresetFallsBack()throws Exception {
        Class<?> c=component();File parent=Files.createTempDirectory("official-files").toFile();
        try {
            for(boolean remove:new boolean[]{false,true}) {
                File zip=archive(parent,false,false),root=new File(parent,"root-"+remove);
                CustomPresetPack.Pack pack=prepare(c,root,zip,descriptor(c,zip,expanded(zip),null));CustomPresetPack.activate(root,pack);
                File preset=new File(pack.directory,"0/0.milk");
                if(remove)assertTrue(preset.delete());else Files.write(preset.toPath(),"corrupt".getBytes(StandardCharsets.UTF_8));
                assertNull("restore must validate native preset files",OfficialPresetPack.current(root));
            }
        }finally{CustomPresetPack.delete(parent);}
    }

    @Test public void diskFailureAndExtractionCancellationKeepPreviousCollection()throws Exception {
        File parent=Files.createTempDirectory("official-faults").toFile(),root=new File(parent,"store");
        try {
            File zip=archive(parent,false,false);
            OfficialPresetPack.Descriptor d=(OfficialPresetPack.Descriptor)descriptor(OfficialPresetPack.class,zip,expanded(zip),null);
            CustomPresetPack.Pack previous=OfficialPresetPack.prepare(root,zip,d,()->false,n->{});CustomPresetPack.activate(root,previous);
            File lowSpace=new File(root.getPath()){@Override public long getUsableSpace(){return 0;}};
            try{OfficialPresetPack.prepare(lowSpace,zip,d,()->false,n->{});fail("insufficient space accepted");}
            catch(IOException expected){assertTrue(expected.getMessage().contains("storage"));}
            assertEquals(previous.directory,OfficialPresetPack.current(root));
            java.util.concurrent.atomic.AtomicBoolean canceled=new java.util.concurrent.atomic.AtomicBoolean();
            try{OfficialPresetPack.prepare(root,zip,d,canceled::get,n->canceled.set(true));fail("canceled extraction accepted");}
            catch(IOException expected){assertTrue(expected.getMessage().contains("canceled"));}
            assertEquals(previous.directory,OfficialPresetPack.current(root));
            assertEquals(1,Arrays.stream(root.listFiles()).filter(File::isDirectory).count());
        }finally{CustomPresetPack.delete(parent);}
    }
}
