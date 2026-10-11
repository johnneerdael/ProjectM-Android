"""The SDK-fact illustrator uses closed-form maps and abstains without facts."""
import numpy as np
import pytest

from prediction_illustration import _retained_radius,illustrate,_spread_sigma


@pytest.mark.parametrize('a,b',[(0.9995139837265015,.01),(1.0,.02),(1.01,0.0)])
def test_closed_form_matches_iterated_inverse_feature_map(a,b):
    radius=np.array([.05,.3,.6])
    iterated=radius.copy()
    for _ in range(25):iterated=a*iterated/(1-b*iterated)
    assert np.allclose(_retained_radius(radius,{'a':a,'b':b},25),iterated,rtol=1e-12)


def test_summary_without_supported_facts_draws_nothing_and_says_why():
    summary={'policy':'preset-understanding-v1','facts':{'context':[{'path':
        '/analysis/visual_description/static_behaviour/context','value':{'viewport':[64,36],'feedback_fps':30}}]}}
    image,used,limitations=illustrate(summary,time=1.0,fps=30.0,history_steps=4)
    assert image.shape==(36,64,3) and not image.any()
    assert used==[]
    assert limitations


def test_spread_reference_uses_uniform_offset_variance():
    spread={'per_step_variance_uniform_offset_reference_texels2':1/6}
    assert _spread_sigma(spread,6)==pytest.approx(1.0)
    assert _spread_sigma(None,6)==0.0


def test_faint_channels_follow_their_own_stored_level_orbit():
    from prediction_illustration import _level_table
    table=_level_table(float(np.float32(.98)),200)
    assert table[200][26]==25
    assert table[200][255]==25
    assert table[0][26]==26


def test_palette_display_keeps_exact_flat_field_colour():
    from prediction_illustration import _palette_display
    base='/analysis/visual_description/nonlinear_texture_colour_bounds'
    facts={base+'/stages/composite/scalar_palette':{'samples':[{'scalar':0.,'clamped_rgb':[1,1,0]},{'scalar':1.,'clamped_rgb':[.6,.4,0]},
            {'scalar':1.4,'clamped_rgb':[.2,0,0]}],'black_content_scalar':[0.,0.]},
           base+'/flat_field':{'state_rgb':[0,1,.5],'composite_rgb_at_state':[.54,.13,0]}}
    image=np.zeros((4,4,3),np.float32);image[:]=[0,1,.5]
    shown=_palette_display(image,facts,[])
    assert np.allclose(shown,[.54,.13,0])
