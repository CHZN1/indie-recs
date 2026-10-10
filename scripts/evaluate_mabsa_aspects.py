#!/usr/bin/env python3
"""Human aspect labels on supplied approximate English translations; offline only."""
import argparse, hashlib, json, re
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, accuracy_score, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline

ASPECTS=('Direction','Acting','Songs','Screenplay','Story','Camera','Casting','BGM','Editing')
LABELS=('absent','negative','neutral','positive')

def labels(values):
    return np.array(['absent' if pd.isna(v) else {0.:'negative',.5:'neutral',1.:'positive'}[float(v)] for v in values])

def duplicate_groups(original,translated):
    parents=list(range(len(original)))
    def find(i):
        while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
        return i
    seen={}
    for i,(a,b) in enumerate(zip(original,translated)):
        for key in ('o:'+re.sub(r'\s+',' ',str(a).strip().casefold()),'t:'+re.sub(r'\s+',' ',str(b).strip().casefold())):
            if key in seen:parents[find(i)]=find(seen[key])
            else:seen[key]=i
    return np.array([find(i) for i in range(len(original))])

def measure(y,p):
    mentioned=y!='absent';pred_present=p!='absent'
    return {'n':len(y),'accuracy':accuracy_score(y,p),'macro_f1':f1_score(y,p,labels=LABELS,average='macro',zero_division=0),'presence_f1':f1_score(mentioned,pred_present,zero_division=0),'mentioned_count':int(mentioned.sum()),'mentioned_exact_polarity_accuracy':float(np.mean(p[mentioned]==y[mentioned])) if mentioned.any() else None,'negative_recall':float(np.mean(p[y=='negative']=='negative')) if np.any(y=='negative') else None,'class_counts':{l:int(np.sum(y==l)) for l in LABELS},'confusion_matrix_labels':LABELS,'confusion_matrix':confusion_matrix(y,p,labels=LABELS).tolist()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--csv',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args()
    if a.output_dir.resolve().is_relative_to(Path(__file__).resolve().parent.parent):ap.error('Keep data/models outside public repo')
    df=pd.read_csv(a.csv);x=df['English Translation (Approximate) '].astype(str).to_numpy();groups=duplicate_groups(df['Review'],x)
    trainval,test=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42).split(x,groups=groups))
    tr,va=next(GroupShuffleSplit(n_splits=1,test_size=.25,random_state=42).split(x[trainval],groups=groups[trainval]));train=trainval[tr];val=trainval[va]
    assert not set(groups[train])&set(groups[val]) and not set(groups[trainval])&set(groups[test])
    a.output_dir.mkdir(parents=True,exist_ok=True);results={};bundle={}
    for aspect in ASPECTS:
        y=labels(df[aspect]);candidates=[]
        for c in (.1,1,10):
            m=make_pipeline(TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=20000,sublinear_tf=True),LogisticRegression(C=c,class_weight='balanced',max_iter=1000,random_state=42))
            m.fit(x[train],y[train]);score=f1_score(y[val],m.predict(x[val]),labels=LABELS,average='macro',zero_division=0);candidates.append((score,c,m))
        score,c,m=max(candidates,key=lambda t:t[0]);baseline=DummyClassifier(strategy='most_frequent').fit(np.zeros((len(train),1)),y[train])
        results[aspect]={'selected_c':c,'validation_macro_f1':score,'test':measure(y[test],m.predict(x[test])),'majority_baseline':measure(y[test],baseline.predict(np.zeros((len(test),1))))};bundle[aspect]=m
    result={'source':'https://data.mendeley.com/datasets/f3ftpd7xpg/4','source_sha256':hashlib.sha256(a.csv.read_bytes()).hexdigest(),'seed':42,'rows':len(df),'duplicate_groups':len(set(groups)),'split_rows':{'train':len(train),'validation':len(val),'test':len(test)},'aspects':results,'limits':['Labels are human annotations of Malayalam originals; inputs are supplied approximate English translations.','Review duplicates in either language are grouped; reviewer and movie IDs are unavailable, so those overlaps cannot be excluded.','Absent is distinct from a labeled neutral opinion.','Only C selected on validation; held-out test used once for this report.','These broad aspects do not label named composers, Wes Anderson style, lighting preferences, or musical similarity.','This classifier does not modify the frozen language extractor or live recommendation model.']}
    joblib.dump(bundle,a.output_dir/'aspect-models.joblib');(a.output_dir/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps({'split_rows':result['split_rows'],'aspects':{k:{'macro_f1':v['test']['macro_f1'],'presence_f1':v['test']['presence_f1'],'polarity_accuracy':v['test']['mentioned_exact_polarity_accuracy']} for k,v in results.items()}},indent=2))
if __name__=='__main__':main()
