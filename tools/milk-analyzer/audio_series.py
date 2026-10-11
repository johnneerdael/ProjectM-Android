"""Per-frame drawing-brightness series for audio-driven source expressions (standard library).

Audio responses are often nonlinear (thresholds, products of bands), so their
typical size and how often they jump cannot be read from band midpoints:
E[f(bands)] differs from f(E[bands]). This module evaluates the exported
closed-form channel graphs of untextured custom shapes and closed-form point
clouds over a declared band sequence (``fixtures/reference-band-sequence-*``,
native frame k at source time (k+1)/fps) and returns the nominal screen-mean
drawing contribution per frame:

- shapes: nominal area fraction times the fan-averaged alpha (centre a and
  perimeter a2 interpolate linearly, so the area mean is a/3 + 2*a2/3) times
  the luma of the fan-averaged colour, after native colour modulo 256/255.
  Textured shapes multiply an unknown previous-frame image: they use a
  declared nominal content luma (CONTENT_LUMA) and are flagged;
- point clouds: points per frame times the dot area (2x2 for thick waves) over
  the declared viewport, times the mean alpha*luma of the points.

Transitions count frame-to-frame changes of the summed series above a
declared threshold. The series is the fresh drawing of one frame: feedback
accumulation, overlap, clipping, textures and the composite are not included,
so it is a source estimate of audio-driven brightness change, not a measured
flash rate.
"""
import json
import math
from pathlib import Path

from time_expression import evaluate_inputs,input_names

POLICY='source-audio-drawing-series-v1'
BANDS=('bass','mid','treb','bass_att','mid_att','treb_att')
PERIOD=256/255
TRANSITION_THRESHOLD=.03
CONTENT_LUMA=.25
DEFAULT_SEQUENCE=Path(__file__).with_name('fixtures')/'reference-band-sequence-2026-10-12.json'


def _native(value):
    return min(1.,max(0.,math.fmod(math.fmod(value,PERIOD)+PERIOD,PERIOD)))


def _luma(rgb):
    return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]


def load_sequence(path=None):
    data=json.loads(Path(path or DEFAULT_SEQUENCE).read_text())
    frames=data.get('frames')
    if not isinstance(frames,list) or not frames or any(set(BANDS)-set(f) for f in frames):
        raise ValueError('declared band sequence needs six bands per frame')
    return {'frames':frames,'fps':float(data.get('fps',30)),'policy':data.get('policy'),'source':data.get('source')}


def _evaluable(program,allowed):
    names=input_names(program) if program else None
    return names is not None and names<=allowed


def _shape_series(facts,sequence):
    rows=[]
    allowed={'time',*BANDS}
    for path,material in facts.items():
        if not path.endswith('/material') or not isinstance(material,dict):continue
        role=(material.get('texture') or {}).get('role')
        if role not in ('untextured_vertex_gradient','previous_main'):continue
        element=path[:-len('/material')]
        geometry=facts.get(element+'/geometry') or {}
        area=geometry.get('summed_nominal_area_fraction_per_aspect_y')
        if type(area) not in (int,float):continue
        channels=material.get('channel_expressions') or {}
        programs={name:(channels.get(group) or {}).get(name) for group,names in (('centre','rgba'),('perimeter',('r2','g2','b2','a2')))
                  for name in names}
        if not all(_evaluable(p,allowed) for p in programs.values()):continue
        if not any(input_names(p)&set(BANDS) for p in programs.values()):continue
        rows.append((facts.get(element+'/id'),area,programs,role=='previous_main'))
    return rows


def _cloud_series(facts,viewport):
    rows=[]
    for path,value in facts.items():
        if '/colour/components/' not in path or not isinstance(value,dict):continue
        record=(value.get('source_palette') or {}).get('point_colour_distribution') or {}
        programs=record.get('programs')
        if record.get('status')!='closed_form_point_colours' or not programs:continue
        if not any(input_names(programs[name])&set(BANDS) for name in 'rgba' if programs.get(name)):continue
        flags=record.get('draw_flags') or {}
        dot=4 if flags.get('thick') else 1
        count=int(record.get('sample_count') or 0)
        if count<1:continue
        rows.append((value.get('component_id'),count*dot/float(viewport[0]*viewport[1]),programs,count))
    return rows


def audio_drawing_series(summary,sequence=None,*,points=32):
    """Return {'policy','series','mean','transitions_hz','delta_p95','components'} or None when nothing is audio-driven."""
    facts={row['path']:row['value'] for rows in summary.get('facts',{}).values() for row in rows}
    context=facts.get('/analysis/visual_description/static_behaviour/context') or {}
    viewport=context.get('viewport') or [480,270]
    aspect_y=min(1.,viewport[1]/viewport[0])
    sequence=sequence or load_sequence()
    shapes=_shape_series(facts,sequence);clouds=_cloud_series(facts,viewport)
    if not shapes and not clouds:return None
    fps=sequence['fps'];series=[];components={}
    for index,bands in enumerate(sequence['frames']):
        inputs={**{name:float(bands[name]) for name in BANDS},'time':(index+1)/fps}
        total=0.
        try:
            for identity,area,programs,textured in shapes:
                value={name:_native(evaluate_inputs(program,inputs)) for name,program in programs.items()}
                alpha=value['a']/3+2*value['a2']/3
                rgb=[value[c]/3+2*value[c+'2']/3 for c in 'rgb']
                contribution=area*aspect_y*alpha*_luma(rgb)*(CONTENT_LUMA if textured else 1.)
                components.setdefault(identity,[]).append(contribution);total+=contribution
            for identity,weight,programs,count in clouds:
                step=max(1,count//points);acc=0.;n=0
                for j in range(0,count,step):
                    values={**inputs,'sample':j/(count-1) if count>1 else 0.}
                    rgba=[_native(evaluate_inputs(programs[c],values)) for c in 'rgba']
                    acc+=rgba[3]*_luma(rgba[:3]);n+=1
                contribution=min(1.,weight)*acc/n
                components.setdefault(identity,[]).append(contribution);total+=contribution
        except ValueError:
            return None
        series.append(total)
    deltas=[abs(b-a) for a,b in zip(series,series[1:])]
    seconds=len(series)/fps
    ordered=sorted(deltas)
    return {'policy':POLICY,'series':series,'mean':sum(series)/len(series),
            'transitions_hz':sum(1 for d in deltas if d>TRANSITION_THRESHOLD)/seconds,
            'delta_p95':ordered[min(len(ordered)-1,int(.95*len(ordered)))] if ordered else 0.,
            'transition_threshold':TRANSITION_THRESHOLD,
            'textured_content_luma_assumed':CONTENT_LUMA if any(row[3] for row in shapes) else None,
            'components':{str(k):{'mean':sum(v)/len(v),'max':max(v)} for k,v in components.items()},
            'sequence_policy':sequence.get('policy'),'scope':'fresh drawing per frame; feedback, overlap, textures and composite excluded'}
