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
HUE_FAMILIES=('red','orange','yellow','green','cyan','blue','purple','pink')
# Options where a direct classifier beats the value rule at equal precision (Vivid and Fast do not).
FACET_CLASSIFIER_OPTIONS=('dark','bright','monochrome','pastel','warm','cool','still','chill','intense','balanced','drifting','normal')
# The middle buckets are what the regression rule leaves over (regression towards the mean): balanced 53% precision
# at 85% recall, drifting 59% at 90% (out of fold, base rates 45% and 49%). Their classifiers are thresholded at a
# precision floor instead (balanced 37% and drifting 56% recall at 70%), level with the weakest extreme options.
FACET_PRECISION_FLOOR={'balanced':.7,'drifting':.7,'normal':.7,'pastel':.7}
TARGETS={'mean_luminance':None,'mean_abs_frame_difference':'log1p10','mean_flow_screen_widths_per_s':'log1p10',
         'global_brightness_jumps_per_10s':'log1p','mean_saturation':None,'warm_cool':None,'coloured_share':None,
         **{'hue_share_'+h:None for h in HUE_FAMILIES},'hue_top_share':None}
MISSING=-1e9


PALETTE_MIN_COLOURED=.2
PALETTE_POWERS=(1.,1.5,2.,2.5,3.,4.)


def choose_palette_sharpening(concentration,predicted,truth,powers=PALETTE_POWERS):
    """Sharpening power per quartile bin of the predicted top-colour share (out-of-fold inputs): the power whose
    renormalised predicted palette overlaps the ruler palette most (overlap = sum of per-family minima)."""
    import numpy as np
    concentration=np.asarray(concentration,float)
    P=np.clip(np.asarray(predicted,float),1e-4,None);P=P/P.sum(1,keepdims=True)
    T=np.clip(np.asarray(truth,float),0,None);T=T/np.maximum(T.sum(1,keepdims=True),1e-12)
    edges=[float(v) for v in np.quantile(concentration,[.25,.5,.75])]
    bins=np.searchsorted(edges,concentration,side='right');chosen=[]
    for b in range(len(edges)+1):
        m=bins==b
        def overlap(k):
            Q=P[m]**k;Q=Q/Q.sum(1,keepdims=True);return float(np.minimum(Q,T[m]).sum(1).mean())
        chosen.append(float(max(powers,key=overlap)) if m.any() else 1.)
    return {'edges':edges,'powers':chosen,'policy':'quartiles of out-of-fold predicted top-colour share; power maximising palette overlap'}


def _transform(value,kind):
    import math
    if kind=='log1p10':return math.log1p(10*value)
    if kind=='log1p':return math.log1p(value)
    return value


def _descriptor_row(path):
    """(name, descriptor) for one corpus result file, or None when it has no summary."""
    from static_descriptor import descriptor
    record=json.loads(Path(path).read_text())
    if record.get('status')!='computed' or not record.get('summary_gzip_base64'):return None
    return record['name'],descriptor(json.loads(gzip.decompress(base64.b64decode(record['summary_gzip_base64']))))


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
    parser.add_argument('--workers',type=int,default=4,help='processes computing descriptors')
    parser.add_argument('--descriptor-cache',type=Path,help='pickle of descriptor rows: reused when present, written otherwise')
    parser.add_argument('--only',help='comma-separated targets/options to fit (regression targets, no_strobe, facet options)')
    parser.add_argument('--extra-columns',type=Path,help='pickle {preset: {column: value}} merged into cached descriptor rows '
                        '(e.g. recipe probe columns computed separately for a descriptor cache made before they existed)')
    parser.add_argument('--merge-into',type=Path,help='existing model whose other targets are kept (descriptor columns must match)')
    args=parser.parse_args(argv)
    labels={}
    for directory in args.ruler:
        for name in os.listdir(directory):
            row=json.loads((directory/name).read_text())
            if row.get('status')=='measured':
                # Hue shares become one target per family (share of coloured pixels; 0 when absent).
                shares=row.get('hue_shares') if isinstance(row.get('hue_shares'),dict) else {}
                row.update({'hue_share_'+h:float(shares.get(h,0.)) for h in HUE_FAMILIES} if shares or row.get('coloured_share') is not None else {})
                # Palette concentration: the top family's share of the hue histogram, for coloured presets only.
                total=sum(float(v) for v in shares.values()) if shares else 0.
                if total>0 and (row.get('coloured_share') or 0.)>PALETTE_MIN_COLOURED:row['hue_top_share']=max(float(v) for v in shares.values())/total
                labels[row['preset']]=row
    excluded=set()
    for path in args.exclude:
        data=json.loads(path.read_text());excluded|=set(data if isinstance(data,list) else data)
    from concurrent.futures import ProcessPoolExecutor
    paths=sorted(args.corpus/'results'/name for name in os.listdir(args.corpus/'results'))
    import pickle
    if args.descriptor_cache and args.descriptor_cache.exists():
        loaded=pickle.load(open(args.descriptor_cache,'rb'))
    else:
        with ProcessPoolExecutor(args.workers) as pool:
            loaded=[row for row in pool.map(_descriptor_row,paths,chunksize=32) if row is not None]
        if args.descriptor_cache:pickle.dump(loaded,open(args.descriptor_cache,'wb'))
    if args.extra_columns:
        extra=pickle.load(open(args.extra_columns,'rb'))
        loaded=[(name,{**row,**extra.get(name,{})}) for name,row in loaded]
    names=[name for name,_ in loaded];rows=[row for _,row in loaded]
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
    only=set(args.only.split(',')) if args.only else None
    if args.merge_into:
        with gzip.open(args.merge_into,'rt') as handle:base_model=json.load(handle)
        if base_model['columns']!=columns:raise SystemExit('merge-into model has different descriptor columns')
        model['targets'].update(base_model['targets'])
        oof_all.update({k:dict(v) for k,v in (json.load(open(args.oof)).get('predictions') or {}).items()} if args.oof.exists() else {})
    for target,transform in TARGETS.items():
        if only is not None and target not in only:continue
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
        if target=='hue_top_share':
            rows=[k for k in fit if all('hue_share_'+h in oof_all.get(k,{}) for h in HUE_FAMILIES)]
            if rows:
                position_fit={k:i for i,k in enumerate(fit)}
                P=np.array([[oof_all[k]['hue_share_'+h] for h in HUE_FAMILIES] for k in rows])
                T=np.array([[labels[k]['hue_share_'+h] for h in HUE_FAMILIES] for k in rows])
                spec['sharpening']=choose_palette_sharpening(oof[[position_fit[k] for k in rows]],P,T)
                report['targets'][target]['sharpening']=spec['sharpening']
        for k in held:oof_all.setdefault(k,{})[target]=float(final.predict(X[[position[k]]])[0])
        unlabelled=[n for n in names if n not in labels]
        if unlabelled:
            for k,value in zip(unlabelled,final.predict(X[[position[k] for k in unlabelled]])):oof_all.setdefault(k,{})[target]=float(value)
        print(target,report['targets'][target],flush=True)
    # No strobe classifier: calm (< 1 brightness jump per 10 s) vs flicker. Admitting a flickering preset is the
    # costly error, so flickering (>= 1) and strobing (>= 10) presets weigh 2x and 4x. Stored as trees with a
    # logistic link; the prediction is the probability of calm.
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import roc_auc_score
    target='no_strobe_probability';source='global_brightness_jumps_per_10s'
    fit_no_strobe=only is None or 'no_strobe' in only
    def classifier():
        return HistGradientBoostingClassifier(max_iter=300,learning_rate=.06,max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=1.,random_state=7)
    if fit_no_strobe:
        keys=[n for n in names if n in labels and labels[n].get(source) is not None]
        fit=[k for k in keys if k not in excluded];held=[k for k in keys if k in excluded]
        jumps=np.array([labels[k][source] for k in fit]);y=(jumps<1).astype(int);Xf=X[[position[k] for k in fit]]
        weight=np.where(jumps>=10,4.,np.where(jumps>=1,2.,1.))
        oof=np.zeros(len(fit))
        for train,test in StratifiedKFold(5,shuffle=True,random_state=11).split(Xf,y):
            oof[test]=classifier().fit(Xf[train],y[train],sample_weight=weight[train]).predict_proba(Xf[test])[:,1]
        final=classifier().fit(Xf,y,sample_weight=weight)
        trees=[[[float(n['value']),int(n['feature_idx']),float(n['num_threshold']),int(n['left']),int(n['right']),int(n['is_leaf'])] for n in predictors[0].nodes]
               for predictors in final._predictors]
        auc=round(float(roc_auc_score(y,oof)),3)
        order=np.argsort(-oof)
        admission={str(k):{'flicker_admitted':int((jumps[order[:k]]>=1).sum()),'strobing_admitted':int((jumps[order[:k]]>=10).sum()),
                           'probability_threshold':float(oof[order[k-1]])} for k in (500,836,1500,1848,3000) if k<=len(order)}
        model['targets'][target]={'transform':'logistic','baseline':float(np.ravel(final._baseline_prediction)[0]),'trees':trees,
                                  'oof_spearman':auc,'metric':'roc_auc','residual_p10':0.,'residual_p90':0.,'n':len(fit),'admission_table':admission}
        report['targets'][target]={'n':len(fit),'oof_roc_auc':auc,'admission_table':admission}
        for k,value in zip(fit,oof):oof_all.setdefault(k,{})[target]=float(value)
        print(target,report['targets'][target],flush=True)
    # Per-option facet classifiers: membership learnt directly admits more true members than the value rule at the
    # same precision (out of fold: dark recall 19% -> 33%, monochrome 9% -> 24%). Each threshold is set where the
    # classifier's OOF precision first reaches the value rule's OOF precision (highest recall at that precision).
    import preset_facets
    from calibrated_display import _inverse
    definition=preset_facets.load_definition()
    metric_fields={'luminance':'mean_luminance','saturation':'mean_saturation','warm_cool':'warm_cool','coloured_share':'coloured_share',
                   'flow':'mean_flow_screen_widths_per_s','frame_difference':'mean_abs_frame_difference','jumps':'global_brightness_jumps_per_10s'}
    from preset_recipe import facet_activity
    def members(values):
        metrics={m:values.get(f) for m,f in metric_fields.items()}
        metrics['activity']=facet_activity({m:metrics.get(m) for m in ('frame_difference','flow','jumps')})
        return set(preset_facets.memberships(metrics,[],definition))
    for option in FACET_CLASSIFIER_OPTIONS:
        if only is not None and option not in only:continue
        keys=[n for n in names if n in labels and n in oof_all and all(labels[n].get(f) is not None for f in metric_fields.values() if f!='warm_cool')]
        fit=[k for k in keys if k not in excluded]
        y=np.array([option in members(labels[k]) for k in fit]).astype(int)
        estimated=np.array([option in members({t:_inverse(v,TARGETS.get(t)) for t,v in oof_all[k].items() if t in TARGETS}) for k in fit])
        if y.sum()<50:continue
        rule_precision=float((estimated&(y==1)).sum()/max(estimated.sum(),1))
        target_precision=max(rule_precision,FACET_PRECISION_FLOOR.get(option,0.))
        Xf=X[[position[k] for k in fit]];oof=np.zeros(len(fit))
        for train,test in StratifiedKFold(5,shuffle=True,random_state=11).split(Xf,y):
            oof[test]=classifier().fit(Xf[train],y[train]).predict_proba(Xf[test])[:,1]
        order=np.argsort(-oof);tp=np.cumsum(y[order]);precision=tp/np.arange(1,len(y)+1)
        ok=np.where(precision>=target_precision)[0]
        threshold=float(oof[order[ok.max()]]) if len(ok) else 1.
        final=classifier().fit(Xf,y)
        trees=[[[float(n['value']),int(n['feature_idx']),float(n['num_threshold']),int(n['left']),int(n['right']),int(n['is_leaf'])] for n in predictors[0].nodes]
               for predictors in final._predictors]
        recall=float(tp[ok.max()]/y.sum()) if len(ok) else 0.
        name='facet_%s_probability'%option
        model['targets'][name]={'transform':'logistic','baseline':float(np.ravel(final._baseline_prediction)[0]),'trees':trees,'threshold':threshold,
                                'oof_spearman':round(float(roc_auc_score(y,oof)),3),'metric':'roc_auc','residual_p10':0.,'residual_p90':0.,'n':len(fit),
                                'rule_precision':round(rule_precision,3),'rule_recall':round(float((estimated&(y==1)).sum()/y.sum()),3),'classifier_recall_at_rule_precision':round(recall,3),
                                'target_precision':round(target_precision,3)}
        report['targets'][name]={k:model['targets'][name][k] for k in ('n','oof_spearman','threshold','rule_precision','rule_recall','classifier_recall_at_rule_precision','target_precision')}
        for k,value in zip(fit,oof):oof_all.setdefault(k,{})[name]=float(value)
        print(name,report['targets'][name],flush=True)
    report['labelled']=len([n for n in names if n in labels])
    args.model.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(args.model,'wt') as handle:json.dump(model,handle,separators=(',',':'))
    args.report.write_text(json.dumps(report,indent=1)+'\n')
    args.oof.write_text(json.dumps({'policy':POLICY,'transforms':TARGETS,'predictions':oof_all})+'\n')


if __name__=='__main__':
    main()
