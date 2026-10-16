import json
import unittest
from pathlib import Path

import preset_facets as F

HERE = Path(__file__).parent
VECTORS = json.loads((HERE / 'fixtures' / 'facet-selection-vectors-v1.json').read_text())


class DefinitionTest(unittest.TestCase):
    def test_groups_and_ids_are_unique_and_versioned(self):
        d = F.load_definition()
        self.assertEqual(d['version'], 1)
        ids = F.option_ids(d)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([g['id'] for g in d['groups']], ['energy', 'brightness', 'colour', 'palette', 'main_colour',
                                                     'movement', 'style', 'comfort'])
        self.assertEqual(F.group_of(d)['no_strobe'], 'comfort')


class MembershipTest(unittest.TestCase):
    def setUp(self):
        self.d = F.load_definition()

    def values(self, **kw):
        base = dict(luminance=.2, saturation=.4, coloured_share=.5, warm_cool=0., flow=.1, frame_difference=.02, jumps=0., activity=.5)
        base.update(kw)
        return base

    def test_thresholds_follow_the_spec_boundaries(self):
        m = F.memberships(self.values(activity=.30), set(), self.d)
        self.assertIn('chill', m); self.assertIn('normal', m); self.assertNotIn('intense', m)
        m = F.memberships(self.values(activity=.72), set(), self.d)
        self.assertIn('normal', m); self.assertIn('intense', m)
        self.assertIn('balanced', F.memberships(self.values(luminance=.12), set(), self.d))
        self.assertIn('dark', F.memberships(self.values(luminance=.1199), set(), self.d))
        self.assertIn('bright', F.memberships(self.values(luminance=.4001), set(), self.d))
        self.assertIn('no_strobe', F.memberships(self.values(jumps=.99), set(), self.d))
        self.assertNotIn('no_strobe', F.memberships(self.values(jumps=1.), set(), self.d))

    def test_pastel_excludes_monochrome_and_colour_options_are_independent(self):
        m = F.memberships(self.values(luminance=.5, saturation=.1, coloured_share=.05), set(), self.d)
        self.assertIn('monochrome', m); self.assertNotIn('pastel', m)
        m = F.memberships(self.values(luminance=.5, saturation=.1, coloured_share=.3), set(), self.d)
        self.assertIn('pastel', m)
        m = F.memberships(self.values(saturation=.6, warm_cool=.3), set(), self.d)
        self.assertIn('vivid', m); self.assertIn('warm', m)

    def test_style_options_come_from_style_facts_only(self):
        self.assertIn('tunnel', F.memberships(self.values(), {'tunnel'}, self.d))
        self.assertNotIn('tunnel', F.memberships(self.values(), set(), self.d))

    def test_missing_metric_never_matches(self):
        values = self.values(); del values['coloured_share']
        m = F.memberships(values, set(), self.d)
        self.assertNotIn('monochrome', m); self.assertNotIn('pastel', m)


class SelectionVectorTest(unittest.TestCase):
    def test_colour_groups_follow_the_preset_colour_tags(self):
        # Palette and Main colour come from static analysis: a preset carries tags 'palette:<family>' (every family with
        # at least 10% of its static palette) and 'main:<family>' (only when one colour clearly dominates).
        d = F.load_definition()
        ids = F.option_ids(d)
        self.assertEqual(len(ids), len(set(ids)))
        groups = [g['id'] for g in d['groups']]
        self.assertIn('palette', groups); self.assertIn('main_colour', groups)
        members = F.memberships({}, set(), d, colours={'palette:red', 'palette:blue', 'main:red'})
        self.assertIn('red', members); self.assertIn('blue', members); self.assertIn('main_red', members)
        self.assertNotIn('green', members); self.assertNotIn('main_blue', members)
        self.assertFalse({'red', 'blue', 'main_red'} & set(F.memberships({}, set(), d)))

    def test_shared_vectors(self):
        d = F.load_definition()
        for case in VECTORS['cases']:
            with self.subTest(selected=case['selected']):
                result = F.select(VECTORS['rows'], case['selected'], d, case['excluded'])
                self.assertEqual(result['pool'], case['pool'])
                self.assertEqual(result['count'], len(case['pool']))
                for option, count in case['option_counts'].items():
                    self.assertEqual(result['option_counts'][option], count, option)
                if 'ignored' in case:
                    self.assertEqual(result['ignored'], case['ignored'])
                    self.assertTrue(set(case['dimmed']) <= set(result['dimmed']))
                else:
                    self.assertEqual(set(result['dimmed']), set(case['dimmed']))

    def test_selected_option_is_never_dimmed(self):
        d = F.load_definition()
        # fractal (style) AND vivid (colour) match no row; both stay clearable.
        result = F.select(VECTORS['rows'], ['fractal', 'vivid'], d)
        self.assertEqual(result['count'], 0)
        self.assertNotIn('fractal', result['dimmed']); self.assertNotIn('vivid', result['dimmed'])


if __name__ == '__main__':
    unittest.main()
