package com.example.projectm.visualizer;

import org.json.*;
import java.io.*;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import java.util.zip.*;

/** Source-bound official collection validation, composed with the existing bounded extractor. */
final class OfficialPresetPack {
    private static final long MAX_ARCHIVE = 512L * 1024 * 1024;
    private static final long MAX_EXPANDED = 2L * 1024 * 1024 * 1024;
    private static final int MAX_MANIFEST = 8 * 1024 * 1024;
    private static final String[] GENRES = {"chill", "normal", "intense"};

    static final class Descriptor {
        final String identity, sha256, url;
        final long bytes, expandedBytes;
        final int presetCount, textureCount;
        private Descriptor(JSONObject json) throws Exception {
            if (integer(json, "schema_version", 1, 1) != 1) throw new IOException("Unsupported collection descriptor");
            identity = hash(json.getString("collection_id"));
            sha256 = hash(json.getString("archive_sha256"));
            url = json.getString("archive_url");
            URI uri = new URI(url);
            if (!"https".equals(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null || uri.getFragment() != null)
                throw new IOException("Collection download requires HTTPS");
            bytes = integer(json, "compressed_bytes", 1, MAX_ARCHIVE);
            expandedBytes = integer(json, "expanded_bytes", 1, MAX_EXPANDED);
            presetCount = (int) integer(json, "preset_count", 1, 50000);
            textureCount = (int) integer(json, "texture_count", 0, 5000);
        }
        static Descriptor read(InputStream input) throws IOException {
            try { return new Descriptor(new JSONObject(new String(readBytes(input, 8192), StandardCharsets.UTF_8))); }
            catch (Exception invalid) { throw new IOException("Invalid collection descriptor", invalid); }
        }
    }

    private static long integer(JSONObject json, String name, long minimum, long maximum) throws Exception {
        Object value = json.get(name);
        if (!(value instanceof Number)) throw new IOException("Invalid numeric field: " + name);
        Number n = (Number) value; long result = n.longValue();
        if (n.doubleValue() != (double) result || result < minimum || result > maximum)
            throw new IOException("Out-of-range field: " + name);
        return result;
    }
    private static String hash(String value) throws IOException {
        if (!value.matches("[a-f0-9]{64}")) throw new IOException("Invalid SHA-256");
        return value;
    }
    static String sha256(InputStream input, CustomPresetPack.Cancellation cancellation) throws IOException {
        return sha256(input, cancellation, MAX_ARCHIVE);
    }
    private static String sha256(InputStream input, CustomPresetPack.Cancellation cancellation, long maximum) throws IOException {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256"); byte[] buffer = new byte[32768]; int n; long bytes = 0;
            while ((n = input.read(buffer)) != -1) {
                canceled(cancellation); bytes += n;
                if (bytes > maximum) throw new IOException("Collection file exceeds expected size");
                digest.update(buffer, 0, n);
            }
            StringBuilder result = new StringBuilder(64);
            for (byte b : digest.digest()) result.append(String.format(Locale.ROOT, "%02x", b & 255));
            return result.toString();
        } catch (NoSuchAlgorithmException impossible) { throw new IOException(impossible); }
    }
    static void canceled(CustomPresetPack.Cancellation cancellation) throws IOException {
        if (Thread.currentThread().isInterrupted() || cancellation.canceled()) throw new IOException("Collection operation canceled");
    }
    private static byte[] readBytes(InputStream input, int maximum) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream(); byte[] buffer = new byte[32768]; int n;
        while ((n = input.read(buffer)) != -1) {
            if (out.size() + (long) n > maximum) throw new IOException("Collection metadata is too large");
            out.write(buffer, 0, n);
        }
        return out.toByteArray();
    }
    private static String safe(String name) throws IOException {
        if (name.isEmpty() || name.startsWith("/") || name.contains("\\") || name.contains(":")) throw new IOException("Unsafe collection path");
        for (String part : name.split("/", -1)) if (part.isEmpty() || part.equals(".") || part.equals("..")) throw new IOException("Unsafe collection path");
        for (int i = 0; i < name.length(); i++) if (name.charAt(i) < 32 || name.charAt(i) == 127) throw new IOException("Unsafe collection path");
        if (name.getBytes(StandardCharsets.UTF_8).length > 1024) throw new IOException("Collection path is too long");
        return name;
    }
    private static JSONObject jsonEntry(ZipFile zip, String name) throws Exception {
        ZipEntry entry = zip.getEntry(name);
        if (entry == null || entry.isDirectory() || entry.getSize() > MAX_MANIFEST) throw new IOException("Missing collection metadata: " + name);
        try (InputStream input = zip.getInputStream(entry)) { return new JSONObject(new String(readBytes(input, MAX_MANIFEST), StandardCharsets.UTF_8)); }
    }

    static CustomPresetPack.Pack prepare(File root, File archive, Descriptor descriptor,
            CustomPresetPack.Cancellation cancellation, CustomPresetPack.Progress progress) throws IOException {
        if (archive.length() != descriptor.bytes) throw new IOException("Collection download size differs");
        try (InputStream input = new FileInputStream(archive)) {
            if (!sha256(input, cancellation).equals(descriptor.sha256)) throw new IOException("Collection download checksum differs");
        }
        if (!root.isDirectory() && !root.mkdirs()) throw new IOException("Cannot create collection storage");
        if (root.getUsableSpace() < descriptor.expandedBytes + 16L * 1024 * 1024) throw new IOException("Not enough storage for the collection");
        CustomPresetPack.Pack pack = null;
        try (ZipFile zip = new ZipFile(archive)) {
            JSONObject manifest = jsonEntry(zip, "manifest.json");
            if (integer(manifest, "schema_version", 1, 1) != 1 || !descriptor.identity.equals(manifest.getString("collection_id")))
                throw new IOException("Collection identity differs");
            JSONArray records = manifest.getJSONArray("files");
            if (records.length() > 60000) throw new IOException("Too many collection files");
            HashMap<String, JSONObject> expected = new HashMap<>();
            for (int i = 0; i < records.length(); i++) {
                JSONObject record = records.getJSONObject(i); String path = safe(record.getString("path"));
                if (path.equals("manifest.json") || expected.put(path, record) != null) throw new IOException("Duplicate collection file");
                hash(record.getString("sha256")); integer(record, "bytes", 0, 64L * 1024 * 1024);
            }
            long expanded = 0; int presets = 0, textures = 0, entries = 0;
            HashSet<String> seen = new HashSet<>();
            Enumeration<? extends ZipEntry> all = zip.entries();
            while (all.hasMoreElements()) {
                canceled(cancellation); ZipEntry entry = all.nextElement();
                String path = safe(entry.getName());
                if (++entries > 60001 || entry.isDirectory() || !seen.add(path) || entry.getSize() < 0)
                    throw new IOException("Invalid collection ZIP entry");
                expanded += entry.getSize();
                if (expanded > descriptor.expandedBytes) throw new IOException("Collection expanded size exceeds descriptor");
                if (path.equals("manifest.json")) continue;
                JSONObject record = expected.get(path);
                if (record == null || record.getLong("bytes") != entry.getSize()) throw new IOException("Unexpected collection file");
                try (InputStream input = zip.getInputStream(entry)) {
                    if (!sha256(input, cancellation, entry.getSize()).equals(record.getString("sha256"))) throw new IOException("Collection file checksum differs");
                }
                if (path.startsWith("presets/")) {
                    if (!path.endsWith(".milk") || path.substring(8).contains("/") || entry.getSize() > 8L*1024*1024) throw new IOException("Invalid official preset");
                    presets++;
                } else if (path.startsWith("textures/")) {
                    if (path.substring(9).contains("/") || !path.toLowerCase(Locale.ROOT).matches(".*\\.(jpg|jpeg|png|tga|bmp|dib|dds)")) throw new IOException("Invalid official texture");
                    textures++;
                } else if (!(path.equals("presets.idx") || path.startsWith("preset-genres/") || path.equals("LICENSE") || path.startsWith("LICENSES/") || path.equals("docs/THIRD_PARTY.md")))
                    throw new IOException("Unexpected collection metadata");
            }
            if (seen.size() != expected.size()+1 || presets != descriptor.presetCount || textures != descriptor.textureCount || expanded != descriptor.expandedBytes)
                throw new IOException("Collection counts or sizes differ");
            Map<String,Integer> weights = weights(zip, "presets.idx", descriptor.presetCount);
            for (String genre : GENRES) {
                Map<String,Integer> members = weights(zip, "preset-genres/genres/"+genre+".idx", -1);
                for (Map.Entry<String,Integer> member : members.entrySet()) if (!member.getValue().equals(weights.get(member.getKey()))) throw new IOException("Invalid official mood metadata");
            }
            pack = CustomPresetPack.prepare(root, archive, cancellation, progress);
            File sourceIndex = new File(pack.directory, "presets.idx");
            File officialIndex = new File(pack.directory, "official-presets.idx");
            JSONObject hashes = new JSONObject();
            try (BufferedReader input = new BufferedReader(new InputStreamReader(new FileInputStream(sourceIndex), StandardCharsets.UTF_8));
                 Writer output = new OutputStreamWriter(new FileOutputStream(officialIndex), StandardCharsets.UTF_8)) {
                String row; int count = 0;
                while ((row = input.readLine()) != null) {
                    String[] parts = row.split("\t", -1);
                    if (parts.length != 2 || !parts[1].startsWith("presets/")) throw new IOException("Invalid installed preset index");
                    String name = parts[1].substring(8); Integer weight = weights.get(name);
                    if (weight == null) throw new IOException("Missing official preset weight");
                    hashes.put(parts[0], expected.get(parts[1]).getString("sha256"));
                    output.write(parts[0]+"\t"+name+"\t"+weight+"\n"); count++;
                }
                if (count != descriptor.presetCount) throw new IOException("Installed preset count differs");
            }
            for (String name : expected.keySet()) {
                if (name.startsWith("presets/")) continue;
                if (name.startsWith("textures/")) { hashes.put(name, expected.get(name).getString("sha256")); continue; }
                String storage = name.equals("presets.idx") ? "source-presets.idx" : name;
                File target = new File(pack.directory, storage);
                if (!target.getParentFile().isDirectory() && !target.getParentFile().mkdirs()) throw new IOException("Cannot create collection metadata directory");
                try (InputStream input = zip.getInputStream(zip.getEntry(name)); OutputStream out = new FileOutputStream(target)) {
                    byte[] buffer = new byte[32768]; int n;
                    while ((n=input.read(buffer))!=-1) { canceled(cancellation); out.write(buffer,0,n); }
                }
                hashes.put(storage, expected.get(name).getString("sha256"));
            }
            try (InputStream input = new FileInputStream(officialIndex)) { hashes.put("official-presets.idx",sha256(input,cancellation)); }
            try (InputStream input = new FileInputStream(sourceIndex)) { hashes.put("presets.idx",sha256(input,cancellation)); }
            JSONObject marker = new JSONObject();
            marker.put("schema_version",1); marker.put("collection_id",descriptor.identity);marker.put("archive_sha256",descriptor.sha256);
            marker.put("preset_count",descriptor.presetCount);marker.put("texture_count",descriptor.textureCount);marker.put("files",hashes);
            try (FileOutputStream out = new FileOutputStream(new File(pack.directory,"installed.json"))) {
                out.write(marker.toString().getBytes(StandardCharsets.UTF_8));out.getFD().sync();
            }
            canceled(cancellation);
            return pack;
        } catch (Exception invalid) {
            if (pack != null) CustomPresetPack.delete(pack.directory);
            if (invalid instanceof IOException) throw (IOException) invalid;
            throw new IOException("Invalid official collection", invalid);
        }
    }
    private static Map<String,Integer> weights(ZipFile zip,String path,int expectedCount)throws IOException {
        HashMap<String,Integer> result = new HashMap<>(); ZipEntry entry=zip.getEntry(path);
        if(entry==null||entry.getSize()>MAX_MANIFEST)throw new IOException("Missing collection index");
        byte[] bytes;
        try(InputStream input=zip.getInputStream(entry)){bytes=readBytes(input,MAX_MANIFEST);}
        try(BufferedReader reader=new BufferedReader(new InputStreamReader(new ByteArrayInputStream(bytes),StandardCharsets.UTF_8))) {
            String row;
            while((row=reader.readLine())!=null) {
                String[] parts=row.split("\t",-1);
                if(parts.length!=2||row.length()>2048||result.size()>=50000||!safe(parts[0]).endsWith(".milk")||parts[0].contains("/")||!parts[1].matches("[0-9]{1,6}"))throw new IOException("Invalid collection index row");
                if(result.put(parts[0],Integer.parseInt(parts[1]))!=null)throw new IOException("Duplicate collection index name");
            }
        }
        if(expectedCount>=0&&result.size()!=expectedCount)throw new IOException("Collection index count differs");
        return result;
    }
    static File current(File root) {
        File directory=CustomPresetPack.current(root);if(directory==null)return null;
        try(InputStream input=new FileInputStream(new File(directory,"installed.json"))) {
            JSONObject marker=new JSONObject(new String(readBytes(input,MAX_MANIFEST),StandardCharsets.UTF_8));
            integer(marker,"schema_version",1,1);hash(marker.getString("collection_id"));hash(marker.getString("archive_sha256"));
            JSONObject files=marker.getJSONObject("files");
            if(!files.has("official-presets.idx")||!files.has("presets.idx")||files.length()>60000)return null;
            int presets=0,textures=0;long expanded=0;
            Iterator<String> names=files.keys();
            while(names.hasNext()) {
                String name=safe(names.next());
                File stored=new File(directory,name);long bytes=stored.length();expanded+=bytes;
                if(bytes>64L*1024*1024||expanded>MAX_EXPANDED)return null;
                if(name.endsWith(".milk"))presets++;
                if(name.startsWith("textures/"))textures++;
                try(InputStream file=new FileInputStream(stored)) { if(!sha256(file,()->false,bytes).equals(hash(files.getString(name))))return null; }
            }
            if(presets!=integer(marker,"preset_count",1,50000)||textures!=integer(marker,"texture_count",0,5000))return null;
            return directory;
        }catch(Exception corrupt){return null;}
    }
    static String identity(File generation) throws IOException {
        try(InputStream in=new FileInputStream(new File(generation,"installed.json"))) {
            return hash(new JSONObject(new String(readBytes(in,MAX_MANIFEST),StandardCharsets.UTF_8)).getString("collection_id"));
        }catch(Exception invalid){throw new IOException("Cannot read installed collection",invalid);}
    }
    private OfficialPresetPack() { }
}
