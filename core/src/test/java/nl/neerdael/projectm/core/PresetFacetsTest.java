package nl.neerdael.projectm.core;

import static org.junit.Assert.*;

import java.io.IOException;
import java.io.StringReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.Test;

public class PresetFacetsTest {
    private static final String HEADER =
            "#projectm-tv-preset-attributes\t1\n#definition\tabc\n"
            + "#group\tenergy\tEnergy\n#option\tenergy\tchill\tChill\n#option\tenergy\tnormal\tNormal\n#option\tenergy\tintense\tIntense\n"
            + "#group\tbrightness\tBrightness\n#option\tbrightness\tdark\tDark\n#option\tbrightness\tbalanced\tBalanced\n#option\tbrightness\tbright\tBright\n"
            + "#group\tcolour\tColour\n#option\tcolour\tmonochrome\tMonochrome\n#option\tcolour\tpastel\tPastel\n#option\tcolour\tvivid\tVivid\n#option\tcolour\twarm\tWarm\n#option\tcolour\tcool\tCool\n"
            + "#group\tpalette\tPalette\n#option\tpalette\tred\tRed\n#option\tpalette\torange\tOrange\n#option\tpalette\tyellow\tYellow\n#option\tpalette\tgreen\tGreen\n#option\tpalette\tcyan\tCyan\n#option\tpalette\tblue\tBlue\n#option\tpalette\tpurple\tPurple\n#option\tpalette\tpink\tPink\n"
            + "#group\tmain_colour\tMain colour\n#option\tmain_colour\tmain_red\tRed\n#option\tmain_colour\tmain_orange\tOrange\n#option\tmain_colour\tmain_yellow\tYellow\n#option\tmain_colour\tmain_green\tGreen\n#option\tmain_colour\tmain_cyan\tCyan\n#option\tmain_colour\tmain_blue\tBlue\n#option\tmain_colour\tmain_purple\tPurple\n#option\tmain_colour\tmain_pink\tPink\n"
            + "#group\tmovement\tMovement\n#option\tmovement\tstill\tStill\n#option\tmovement\tdrifting\tDrifting\n#option\tmovement\tfast\tFast\n"
            + "#group\tstyle\tStyle\n#option\tstyle\tkaleidoscope\tKaleidoscope\n#option\tstyle\ttunnel\tTunnel\n#option\tstyle\tliquid\tLiquid\n#option\tstyle\tgeometric\tGeometric\n#option\tstyle\tparticles\tParticles\n#option\tstyle\tfractal\tFractal\n"
            + "#group\tcomfort\tComfort\n#option\tcomfort\tno_strobe\tNo strobe\n"
            + "#columns\tname\toptions\tluminance\tsaturation\tcoloured_share\twarm_cool\tflow\tframe_difference\tjumps\tactivity\n";

    /** Builds attributes.tsv text from the shared vector rows. */
    private static String vectorsAsTable(String vectors) {
        StringBuilder table = new StringBuilder(HEADER);
        Matcher row = Pattern.compile("\\{\"name\": \"([^\"]+)\", \"options\": \\[([^\\]]*)\\]\\}").matcher(vectors);
        List<String[]> rows = new ArrayList<>();
        while (row.find()) rows.add(new String[]{row.group(1), row.group(2).replace("\"", "").replace(" ", "")});
        rows.sort(Comparator.comparing(r -> r[0]));
        for (String[] r : rows) table.append(r[0]).append('\t').append(r[1]).append("\t0.1\t0.1\t0.1\t0\t0.1\t0.01\t0\t0.5\n");
        return table.toString();
    }

    private static String vectors() throws IOException {
        return new String(Files.readAllBytes(Paths.get("../tools/milk-analyzer/fixtures/facet-selection-vectors-v1.json")), StandardCharsets.UTF_8);
    }

    private static List<String> list(String json) {
        List<String> out = new ArrayList<>();
        Matcher item = Pattern.compile("\"([^\"]+)\"").matcher(json);
        while (item.find()) out.add(item.group(1));
        return out;
    }

    @Test public void sharedVectorsMatchPythonSemantics() throws IOException {
        String text = vectors();
        PresetFacets facets = PresetFacets.parse(new StringReader(vectorsAsTable(text)));
        assertEquals(8, facets.presetCount());
        Matcher c = Pattern.compile("\\{\"selected\": \\[([^\\]]*)\\], \"excluded\": \\[([^\\]]*)\\], \"pool\": \\[([^\\]]*)\\],(?:\\s*\"ignored\": \\[([^\\]]*)\\],)?\\s*\"option_counts\": \\{([^}]*)\\},\\s*\"dimmed\": \\[([^\\]]*)\\]\\}").matcher(text);
        int cases = 0;
        while (c.find()) {
            cases++;
            PresetFacets.Selection s = facets.select(list(c.group(1)), list(c.group(2)));
            assertEquals(list(c.group(3)), Arrays.asList(s.presetNames()));
            assertEquals(list(c.group(3)).size(), s.poolSize());
            Matcher count = Pattern.compile("\"([a-z_]+)\": (\\d+)").matcher(c.group(5));
            while (count.find()) assertEquals(count.group(1), Integer.parseInt(count.group(2)), s.countIfToggled(count.group(1)));
            for (String dimmed : list(c.group(6))) assertTrue(dimmed, s.isDimmed(dimmed));
            if (c.group(4) != null) assertEquals(list(c.group(4)), s.ignored());
        }
        assertEquals(9, cases);
    }

    @Test public void selectedOptionIsNeverDimmedAndUnknownIdsAreIgnored() throws IOException {
        PresetFacets facets = PresetFacets.parse(new StringReader(vectorsAsTable(vectors())));
        PresetFacets.Selection s = facets.select(Arrays.asList("fractal", "tunnel", "nonsense"), Collections.emptyList());
        assertFalse(s.isDimmed("fractal")); assertFalse(s.isDimmed("tunnel"));
        assertEquals(Collections.singletonList("nonsense"), s.ignored());
        assertEquals(0, s.countIfToggled("nonsense"));
    }

    @Test public void absentPresetNamesAreIgnoredForExclusion() throws IOException {
        PresetFacets facets = PresetFacets.parse(new StringReader(vectorsAsTable(vectors())));
        assertEquals(8, facets.select(Collections.emptyList(), Collections.singletonList("not-bundled.milk")).poolSize());
        assertFalse(facets.contains("not-bundled.milk"));
    }

    @Test public void unmeasuredRowsNeverJoinAPool() throws IOException {
        PresetFacets facets = PresetFacets.parse(new StringReader(HEADER + "m.milk\t\t-\t-\t-\t-\t-\t-\t-\t-\nz.milk\tchill\t0.1\t0.1\t0.1\t0\t0.1\t0.01\t0\t0.1\n"));
        assertEquals(2, facets.select(Collections.emptyList(), Collections.emptyList()).poolSize());
        assertArrayEquals(new String[]{"z.milk"}, facets.select(Collections.singletonList("chill"), Collections.emptyList()).presetNames());
    }

    @Test public void malformedInputIsRejected() {
        String[] bad = {"", "#projectm-tv-preset-attributes\t2\n", HEADER + "a.milk\tchill\n", HEADER + "a.milk\tspirals\t1\t1\t1\t1\t1\t1\t1\t1\n",
                        HEADER.replace("#columns", "#group\tenergy\tAgain\n#columns")};
        for (String text : bad) {
            try { PresetFacets.parse(new StringReader(text)); fail("accepted: " + text.length()); }
            catch (IllegalArgumentException | IOException expected) { /* rejected */ }
        }
    }
}
