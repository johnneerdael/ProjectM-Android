import unittest
import facet_style_facts as S


def summary(mechanisms=(), **structure):
    return {'facts': {'construction': [{'path': '/analysis/families/%d' % i, 'value': {'mechanism': m, 'stage': 'composite'}}
                                       for i, m in enumerate(mechanisms)]},
            'approximate_mood_features': {'structure.' + k: {'value': v} for k, v in structure.items()}}


class StyleFactsTest(unittest.TestCase):
    def test_mechanisms_map_to_styles(self):
        self.assertEqual(S.style_facts(summary(['angular_mirror_fold'])), ['kaleidoscope'])
        self.assertEqual(S.style_facts(summary(['polar_radial_sampling'])), ['tunnel'])
        self.assertEqual(S.style_facts(summary(['image_driven_advection'])), ['liquid'])
        self.assertEqual(S.style_facts(summary(['point_cloud_primitive'])), ['particles'])
        self.assertEqual(S.style_facts(summary(['complex_quadratic_recurrence'])), ['fractal'])

    def test_structure_scores_use_spec_thresholds(self):
        self.assertEqual(S.style_facts(summary(symmetry=.55)), ['kaleidoscope'])
        self.assertEqual(S.style_facts(summary(symmetry=.549)), [])
        self.assertEqual(S.style_facts(summary(organic=.6, geometric=.6, fractal=.6)), ['liquid', 'geometric', 'fractal'])

    def test_unknown_scores_do_not_match(self):
        self.assertEqual(S.style_facts(summary(symmetry=None)), [])
