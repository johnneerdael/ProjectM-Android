package nl.neerdael.projectm.core;

import android.content.res.AssetManager;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.util.*;

/**
 * Mood facets over the bundled presets (preset-attributes/attributes.tsv, built by
 * tools/milk-analyzer/attribute_bundle.py). Options combine OR within a group and AND across
 * groups; an unselected group means "any". Mirrors tools/milk-analyzer/preset_facets.py; both run
 * the shared selection vectors. No Android types are used outside load().
 */
public final class PresetFacets {
    public static final String ASSET = "preset-attributes/attributes.tsv";
    private static final String MAGIC = "#projectm-tv-preset-attributes\t1";
    private static final int VALUE_COLUMNS = 8;

    public static final class Option {
        public final String id, label, groupId;
        Option(String id, String label, String groupId) { this.id = id; this.label = label; this.groupId = groupId; }
    }

    public static final class Group {
        public final String id, label;
        public final List<Option> options;
        Group(String id, String label, List<Option> options) { this.id = id; this.label = label; this.options = Collections.unmodifiableList(options); }
    }

    private final List<Group> groups;
    private final Map<String, Option> options = new LinkedHashMap<>();
    private final String[] names;
    private final Map<String, Integer> index = new HashMap<>();
    private final Map<String, long[]> members = new HashMap<>();
    private final int words;

    private PresetFacets(List<Group> groups, List<String> names, Map<String, Set<String>> rows) {
        this.groups = Collections.unmodifiableList(groups);
        for (Group g : groups) for (Option o : g.options) options.put(o.id, o);
        this.names = names.toArray(new String[0]);
        this.words = (this.names.length + 63) / 64;
        for (int i = 0; i < this.names.length; i++) index.put(this.names[i], i);
        for (String id : options.keySet()) members.put(id, new long[words]);
        for (int i = 0; i < this.names.length; i++)
            for (String id : rows.get(this.names[i])) members.get(id)[i >>> 6] |= 1L << (i & 63);
    }

    public static PresetFacets fromRows(List<Group> groups, Map<String, Set<String>> rows) {
        List<String> sorted = new ArrayList<>(rows.keySet());
        Collections.sort(sorted);
        Set<String> known = new HashSet<>();
        for (Group g : groups) for (Option o : g.options) if (!known.add(o.id)) throw new IllegalArgumentException("duplicate option " + o.id);
        for (Map.Entry<String, Set<String>> row : rows.entrySet())
            if (!known.containsAll(row.getValue())) throw new IllegalArgumentException("unknown option in " + row.getKey());
        return new PresetFacets(groups, sorted, rows);
    }

    public static PresetFacets parse(Reader reader) throws IOException {
        BufferedReader in = new BufferedReader(reader);
        String line = in.readLine();
        if (!MAGIC.equals(line)) throw new IllegalArgumentException("not a preset attribute table");
        List<Group> groups = new ArrayList<>();
        Map<String, List<Option>> groupOptions = new LinkedHashMap<>();
        Map<String, String> groupLabels = new LinkedHashMap<>();
        Map<String, Set<String>> rows = new LinkedHashMap<>();
        boolean columns = false;
        while ((line = in.readLine()) != null) {
            if (line.isEmpty()) continue;
            String[] f = line.split("\t", -1);
            if (!columns) {
                switch (f[0]) {
                    case "#definition": break;
                    case "#group":
                        if (f.length != 3 || groupLabels.containsKey(f[1])) throw new IllegalArgumentException("bad group line");
                        groupLabels.put(f[1], f[2]); groupOptions.put(f[1], new ArrayList<>()); break;
                    case "#option":
                        if (f.length != 4 || !groupOptions.containsKey(f[1])) throw new IllegalArgumentException("bad option line");
                        groupOptions.get(f[1]).add(new Option(f[2], f[3], f[1])); break;
                    case "#columns":
                        if (f.length != 3 + VALUE_COLUMNS || !"name".equals(f[1]) || !"options".equals(f[2])) throw new IllegalArgumentException("bad columns");
                        columns = true; break;
                    default: throw new IllegalArgumentException("unexpected header line");
                }
                continue;
            }
            if (f.length != 2 + VALUE_COLUMNS || f[0].isEmpty() || rows.containsKey(f[0])) throw new IllegalArgumentException("bad row");
            Set<String> ids = new LinkedHashSet<>();
            if (!f[1].isEmpty()) ids.addAll(Arrays.asList(f[1].split(",")));
            rows.put(f[0], ids);
        }
        if (!columns || groupLabels.isEmpty()) throw new IllegalArgumentException("incomplete attribute table");
        for (Map.Entry<String, String> g : groupLabels.entrySet()) groups.add(new Group(g.getKey(), g.getValue(), groupOptions.get(g.getKey())));
        return fromRows(groups, rows);
    }

    /** The bundled table, or null when it is missing or malformed (older official archives). */
    public static PresetFacets load(AssetManager assets) {
        try (Reader reader = new InputStreamReader(assets.open(ASSET), StandardCharsets.UTF_8)) {
            return parse(reader);
        } catch (IOException | IllegalArgumentException missingOrMalformed) {
            return null;
        }
    }

    public List<Group> groups() { return groups; }
    public int presetCount() { return names.length; }
    public boolean contains(String presetName) { return index.containsKey(presetName); }

    public Selection select(Collection<String> optionIds, Collection<String> excludedNames) {
        return new Selection(optionIds, excludedNames);
    }

    public final class Selection {
        private final List<String> selected = new ArrayList<>();
        private final List<String> ignored = new ArrayList<>();
        private final long[] excluded = new long[words];
        private final long[] pool;

        Selection(Collection<String> optionIds, Collection<String> excludedNames) {
            for (String id : new LinkedHashSet<>(optionIds)) (options.containsKey(id) ? selected : ignored).add(id);
            for (String name : excludedNames) {
                Integer i = index.get(name);
                if (i != null) excluded[i >>> 6] |= 1L << (i & 63);
            }
            pool = poolFor(selected);
        }

        private long[] poolFor(List<String> chosen) {
            long[] result = new long[words];
            for (int w = 0; w < words; w++) result[w] = ~excluded[w];
            if (names.length % 64 != 0) result[words - 1] &= (1L << (names.length % 64)) - 1;
            Map<String, long[]> byGroup = new LinkedHashMap<>();
            for (String id : chosen) {
                long[] union = byGroup.get(options.get(id).groupId);
                if (union == null) byGroup.put(options.get(id).groupId, union = new long[words]);
                long[] bits = members.get(id);
                for (int w = 0; w < words; w++) union[w] |= bits[w];
            }
            for (long[] union : byGroup.values()) for (int w = 0; w < words; w++) result[w] &= union[w];
            return result;
        }

        private int cardinality(long[] bits) { int n = 0; for (long w : bits) n += Long.bitCount(w); return n; }

        public List<String> selected() { return Collections.unmodifiableList(selected); }
        public List<String> ignored() { return Collections.unmodifiableList(ignored); }
        public int poolSize() { return cardinality(pool); }

        public int countIfToggled(String optionId) {
            if (!options.containsKey(optionId)) return 0;
            List<String> toggled = new ArrayList<>(selected);
            if (!toggled.remove(optionId)) toggled.add(optionId);
            return cardinality(poolFor(toggled));
        }

        public boolean isDimmed(String optionId) {
            return options.containsKey(optionId) && !selected.contains(optionId) && countIfToggled(optionId) == 0;
        }

        public String[] presetNames() {
            String[] out = new String[poolSize()];
            int n = 0;
            for (int i = 0; i < names.length; i++) if ((pool[i >>> 6] & (1L << (i & 63))) != 0) out[n++] = names[i];
            return out;
        }
    }
}
