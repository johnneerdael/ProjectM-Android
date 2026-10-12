"""Display activity and activity bands from display statistics (standard library).

Activity follows the Mood facets definition: the mean of the percentile ranks of
mean frame difference, optical-flow speed and global brightness jumps, placed
against a frozen reference corpus (the engine ruler over the bundled pack:
pinned patched engine, 480x270, 300 frames at 30 fps, checkpoint audio,
statistics over frames 60-299). The rank of the mean is itself converted to a
percentile with the corpus activity table, so 0.35 means "more active than 35%
of the reference pack". Bands overlap like the existing moods: Chill <= 0.35,
Normal 0.25-0.75, Intense >= 0.70.

Inputs are display statistics with an evidence label: source-calibrated
estimates (``calibrated_display``) with intervals, or engine-ruler measurements
when a caller is allowed to use them (the facet bundle). An interval maps to
the union of bands it touches; a band is certain only when the whole interval
lies inside it. The reference tables are calibration constants, not a claim
about any preset outside the reference conditions.
"""
import argparse
import bisect
import json
import os
from pathlib import Path

POLICY='display-activity-v1'
METRICS=('mean_abs_frame_difference','mean_flow_screen_widths_per_s','global_brightness_jumps_per_10s')
BANDS=(('Chill',0.,.35),('Normal',.25,.75),('Intense',.70,1.))
DEFAULT_TABLE=Path(__file__).with_name('fixtures')/'display-activity-reference-v1.json'
QUANTILES=1001
_CACHE={}


def load(path=None):
    path=Path(path or DEFAULT_TABLE)
    if str(path) not in _CACHE:
        _CACHE[str(path)]=json.loads(path.read_text()) if path.exists() else None
    return _CACHE[str(path)]


def _rank(sorted_values,value):
    """Mid-rank of value in a quantile table, in [0, 1]."""
    low=bisect.bisect_left(sorted_values,value);high=bisect.bisect_right(sorted_values,value)
    return ((low+high)/2)/len(sorted_values)


def activity(stats,table=None):
    """Activity percentile in [0, 1] for {metric: value}, or None when a metric is missing."""
    table=table or load()
    if table is None:return None
    values=[stats.get(name) for name in METRICS]
    if any(type(v) not in (int,float) for v in values):return None
    raw=sum(_rank(table['metrics'][name],float(value)) for name,value in zip(METRICS,values))/len(METRICS)
    return _rank(table['activity'],raw)


def bands(value):
    return [name for name,low,high in BANDS if low<=value<=high]


def classify(estimate,table=None):
    """Bands for a display estimate {metric: {'value', 'interval'?}} or {metric: value}.

    Returns {'activity','activity_interval','bands','possible_bands','certain'}; an interval
    combines the metrics' interval ends (all low, all high), which bounds the monotone activity.
    """
    table=table or load()
    if table is None:return None
    point={};low={};high={}
    for name in METRICS:
        entry=estimate.get(name)
        if isinstance(entry,dict):
            point[name]=entry.get('value');span=entry.get('interval') or [entry.get('value')]*2
        else:point[name]=entry;span=[entry,entry]
        low[name],high[name]=span
    value=activity(point,table)
    if value is None:return None
    a,b=activity(low,table),activity(high,table)
    interval=[min(a,b,value),max(a,b,value)]
    possible=[name for name,lo,hi in BANDS if interval[0]<=hi and interval[1]>=lo]
    certain=[name for name,lo,hi in BANDS if lo<=interval[0] and interval[1]<=hi]
    return {'policy':POLICY,'activity':round(value,4),'activity_interval':[round(v,4) for v in interval],
            'bands':bands(value),'possible_bands':possible,'certain_bands':certain}


def build(directories,output):
    """Freeze quantile tables from engine-ruler result directories."""
    rows=[]
    for directory in directories:
        for name in sorted(os.listdir(directory)):
            row=json.loads((Path(directory)/name).read_text())
            if row.get('status')=='measured' and all(type(row.get(m)) in (int,float) for m in METRICS):rows.append(row)
    if len(rows)<100:raise ValueError('too few measured presets for a reference table')
    def quantiles(values):
        values=sorted(values);n=len(values)
        return [values[min(n-1,round(i*(n-1)/(QUANTILES-1)))] for i in range(QUANTILES)]
    metrics={name:quantiles([float(r[name]) for r in rows]) for name in METRICS}
    raw=[sum(_rank(metrics[name],float(r[name])) for name in METRICS)/len(METRICS) for r in rows]
    table={'policy':POLICY,'presets':len(rows),'quantiles':QUANTILES,'metrics':metrics,'activity':quantiles(raw),
           'reference':rows[0].get('ruler'),'statistics_window':'frames 60-299 of 300 at 30 fps',
           'bands':[{'name':n,'low':lo,'high':hi} for n,lo,hi in BANDS]}
    Path(output).write_text(json.dumps(table,separators=(',',':'))+'\n')
    return table


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('ruler',type=Path,nargs='+',help='engine-ruler results directories')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    table=build(args.ruler,args.output)
    print(json.dumps({'presets':table['presets'],'output':str(args.output)}))


if __name__=='__main__':
    main()
