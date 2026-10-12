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
        self.assertEqual(S.style_facts(summary(['image_driven_advection'])), [])
        self.assertEqual(S.style_facts(summary(['radial_feedback_transform'])), [])
        self.assertEqual(S.style_facts(summary(['cartesian_mirror_fold'])), [])
        self.assertEqual(S.style_facts(summary(['point_cloud_primitive'])), ['particles'])
        self.assertEqual(S.style_facts(summary(['complex_quadratic_recurrence'])), ['fractal'])

    def test_structure_scores_use_spec_thresholds(self):
        self.assertEqual(S.style_facts(summary(symmetry=.55)), ['kaleidoscope'])
        self.assertEqual(S.style_facts(summary(symmetry=.549)), [])
        self.assertEqual(S.style_facts(summary(organic=.6, geometric=.6, fractal=.6)), ['geometric', 'fractal'])
        self.assertEqual(S.style_facts(summary(['image_driven_advection'], organic=.6)), ['liquid'])
        self.assertEqual(S.style_facts(summary(['gradient_driven_advection'], organic=.59)), [])

    def test_unknown_scores_do_not_match(self):
        self.assertEqual(S.style_facts(summary(symmetry=None)), [])
