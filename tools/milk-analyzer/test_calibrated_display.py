import math

from calibrated_display import predict


def test_tree_model_predicts_with_transform_and_interval():
    column = 'motion:/x#max'
    model = {'columns': [column], 'label_source': 'test ruler', 'targets': {
        'mean_flow_screen_widths_per_s': {'transform': 'log1p10', 'baseline': math.log1p(1.), 'oof_spearman': .7,
            'residual_p10': -.1, 'residual_p90': .1,
            # one stump: x <= 0.5 -> -0.2, else +0.2
            'trees': [[[0., 0, .5, 1, 2, 0], [-.2, 0, 0., 0, 0, 1], [.2, 0, 0., 0, 0, 1]]]}}}
    summary = {'facts': {'motion': [{'path': '/x', 'value': .8}]}}
    result = predict(summary, model)['mean_flow_screen_widths_per_s']
    assert math.isclose(result['value'], math.expm1(math.log1p(1.) + .2) / 10)
    assert result['interval'][0] < result['value'] < result['interval'][1]
    assert result['evidence'] == 'source-calibrated'
    missing = predict({'facts': {}}, model)['mean_flow_screen_widths_per_s']
    assert math.isclose(missing['value'], math.expm1(math.log1p(1.) - .2) / 10)  # missing sentinel goes left


def test_values_and_intervals_stay_inside_each_statistics_physical_range():
    # A luminance or saturation cannot leave [0, 1]; residual intervals added to a low value must not either.
    import calibrated_display as C
    model = {'columns': [], 'label_source': 'x', 'targets': {
        'mean_luminance': {'baseline': .05, 'trees': [], 'residual_p10': -.2, 'residual_p90': .2, 'oof_spearman': .6},
        'mean_saturation': {'baseline': .95, 'trees': [], 'residual_p10': -.1, 'residual_p90': .3, 'oof_spearman': .6},
        'warm_cool': {'baseline': -.9, 'trees': [], 'residual_p10': -.3, 'residual_p90': .3, 'oof_spearman': .6}}}
    out = C.predict({}, model)
    assert out['mean_luminance']['interval'] == [0., .25] and out['mean_luminance']['value'] == .05
    assert out['mean_saturation']['interval'][1] == 1. and abs(out['mean_saturation']['interval'][0] - .85) < 1e-12
    assert out['warm_cool']['interval'][0] == -1.


def test_logistic_targets_return_a_probability():
    # No strobe is a yes/no question: a calm-vs-flicker classifier stored as trees with a logistic link beats the
    # jumps regression at matched admissions (836 admitted: 8 vs 20 flickering presets).
    import math
    from calibrated_display import _inverse
    assert abs(_inverse(0., 'logistic') - .5) < 1e-12
    assert _inverse(4., 'logistic') > .98 and _inverse(-4., 'logistic') < .02
    assert 0. <= _inverse(1e9, 'logistic') <= 1. and 0. <= _inverse(-1e9, 'logistic') <= 1.


def test_predict_reads_recipe_probe_columns_from_a_supplied_render():
    # build_recipe passes its render so the probes are not rendered twice; the darkening warp splits luminance here.
    column = 'recipe:warp_detail/mean_luma'
    model = {'columns': [column], 'targets': {'mean_luminance': {'baseline': .4, 'oof_spearman': .7, 'residual_p10': 0., 'residual_p90': 0.,
             'trees': [[[0., 0, .1, 1, 2, 0], [-.2, 0, 0., 0, 0, 1], [.2, 0, 0., 0, 0, 1]]]}}}
    def render(luma):
        return {'layers': [], 'feedback': {'warp_detail_response': {'mean_luma': luma}}, 'composite': {}}
    assert math.isclose(predict({'facts': {}}, model, render=render(.02))['mean_luminance']['value'], .2)
    assert math.isclose(predict({'facts': {}}, model, render=render(.46))['mean_luminance']['value'], .6)
