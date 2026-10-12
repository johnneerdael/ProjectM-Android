"""Fit source-calibrated display models from corpus summaries and engine-ruler labels (offline).

Inputs: a corpus_understanding output directory (per-preset summaries) and a
directory of ruler result JSON files. Writes the JSON tree model used by
``calibrated_display`` and a report with out-of-fold rank correlations; the
out-of-fold predictions (every preset predicted by a model that never saw it)
are written for corpus records. Optional dependencies: numpy, scipy,
scikit-learn (requirements-calibration.txt). Excluded presets (for example an
emulator-observed held-out set) are never used for fitting and are scored
separately.
"""
import argparse
import base64
import gzip
import json
import os
from pathlib import Path

POLICY='source-display-calibration-fit-v1'
TARGETS={'mean_luminance':None,'mean_abs_frame_difference':'log1p10','mean_flow_screen_widths_per_s':'log1p10',
         'global_brightness_jumps_per_10s':'log1p','mean_saturation':None,'warm_cool':None}
MISSING=-1e9


def _transform(value,kind):
    import math
    if kind=='log1p10':return math.log1p(10*value)
    if kind=='log1p':return math.log1p(value)
    return value


def main(argv=None):
    import numpy as np
    from scipy.stats import spearmanr
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.model_selection import KFold
    from static_descriptor import descriptor
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('corpus',type=Path,help='corpus_understanding output directory')
    parser.add_argument('ruler',type=Path,nargs='+',help='ruler results directories')
    parser.add_argument('--exclude',type=Path,action='append',default=[],help='JSON object/list of preset names never fitted')
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--oof',type=Path,required=True)
    parser.add_argument('--min-share',type=float,default=.01)
    args=parser.parse_args(argv)
    labels={}
    for directory in args.ruler:
        for name in os.listdir(directory):
            row=json.loads((directory/name).read_text())
            if row.get('status')=='measured':labels[row['preset']]=row
    excluded=set()
    for path in args.exclude:
        data=json.loads(path.read_text());excluded|=set(data if isinstance(data,list) else data)
    names=[];rows=[]
    for name in sorted(os.listdir(args.corpus/'results')):
        record=json.loads((args.corpus/'results'/name).read_text())
        if record.get('status')!='computed' or not record.get('summary_gzip_base64'):continue
        rows.append(descriptor(json.loads(gzip.decompress(base64.b64decode(record['summary_gzip_base64'])))));names.append(record['name'])
    counts={}
    for row in rows:
        for key in row:counts[key]=counts.get(key,0)+1
    columns=sorted(k for k,c in counts.items() if c>=len(rows)*args.min_share)
    index={k:i for i,k in enumerate(columns)}
    X=np.full((len(rows),len(columns)),MISSING,np.float64)
    for i,row in enumerate(rows):
        for key,value in row.items():
            j=index.get(key)
            if j is not None and np.isfinite(value):X[i,j]=max(-1e30,min(1e30,value))
    position={n:i for i,n in enumerate(names)}
    model={'policy':'source-calibrated-display-v1','columns':columns,'targets':{},'label_source':
           'engine ruler: pinned patched projectM-TV source34 rendered offline (macOS GLES, SwiftShader), checkpoint audio','fit_policy':POLICY}
    report={'policy':POLICY,'presets_with_summaries':len(names),'labelled':0,'excluded':len(excluded),'targets':{}}
    oof_all={}
    for target,transform in TARGETS.items():
        keys=[n for n in names if n in labels and labels[n].get(target) is not None]
        fit=[k for k in keys if k not in excluded];held=[k for k in keys if k in excluded]
        y=np.array([_transform(labels[k][target],transform) for k in fit]);Xf=X[[position[k] for k in fit]]
        oof=np.zeros(len(fit))
        def regressor():
            return HistGradientBoostingRegressor(max_iter=250,learning_rate=.06,max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=1.,random_state=7)
        for train,test in KFold(5,shuffle=True,random_state=11).split(Xf):
            oof[test]=regressor().fit(Xf[train],y[train]).predict(Xf[test])
        final=regressor().fit(Xf,y)
        residual=y-oof
        trees=[]
        for predictors in final._predictors:
            nodes=predictors[0].nodes
            trees.append([[float(n['value']),int(n['feature_idx']),float(n['num_threshold']),int(n['left']),int(n['right']),int(n['is_leaf'])] for n in nodes])
        spec={'transform':transform,'baseline':float(np.ravel(final._baseline_prediction)[0]),'trees':trees,
              'oof_spearman':round(float(spearmanr(oof,y).statistic),3),
              'residual_p10':float(np.percentile(residual,10)),'residual_p90':float(np.percentile(residual,90)),'n':len(fit)}
        model['targets'][target]=spec
        held_rho=None
        if len(held)>5:
            yh=np.array([_transform(labels[k][target],transform) for k in held])
            held_rho=round(float(spearmanr(final.predict(X[[position[k] for k in held]]),yh).statistic),3)
        report['targets'][target]={'n':len(fit),'oof_spearman':spec['oof_spearman'],'excluded_n':len(held),'excluded_spearman':held_rho}
        for k,value in zip(fit,oof):oof_all.setdefault(k,{})[target]=float(value)
        for k in held:oof_all.setdefault(k,{})[target]=float(final.predict(X[[position[k]]])[0])
        unlabelled=[n for n in names if n not in labels]
        if unlabelled:
            for k,value in zip(unlabelled,final.predict(X[[position[k] for k in unlabelled]])):oof_all.setdefault(k,{})[target]=float(value)
        print(target,report['targets'][target],flush=True)
    report['labelled']=len([n for n in names if n in labels])
    args.model.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(args.model,'wt') as handle:json.dump(model,handle,separators=(',',':'))
    args.report.write_text(json.dumps(report,indent=1)+'\n')
    args.oof.write_text(json.dumps({'policy':POLICY,'transforms':TARGETS,'predictions':oof_all})+'\n')


if __name__=='__main__':
    main()
