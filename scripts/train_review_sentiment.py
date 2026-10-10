#!/usr/bin/env python3
"""Offline real-review sentiment benchmark; leaves live recommendations untouched."""
import argparse, gzip, hashlib, json, tarfile
from pathlib import Path
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, confusion_matrix
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.pipeline import make_pipeline


def model():
    return make_pipeline(TfidfVectorizer(ngram_range=(1,2), min_df=3, max_features=60000, sublinear_tf=True), LogisticRegression(C=1, max_iter=1000, random_state=42))


def measure(m,x,y):
    p=m.predict(x)
    return dict(n=len(y),accuracy=accuracy_score(y,p),balanced_accuracy=balanced_accuracy_score(y,p),macro_f1=f1_score(y,p,average='macro'),confusion_matrix=confusion_matrix(y,p).tolist())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cornell',type=Path,required=True);ap.add_argument('--amazon',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    cx=[];cy=[]
    with tarfile.open(a.cornell) as ar:
        for member in sorted(ar.getmembers(),key=lambda r:r.name):
            if member.isfile() and member.name.endswith('.txt') and ('/pos/' in member.name or '/neg/' in member.name):
                cx.append(ar.extractfile(member).read().decode('utf8',errors='replace'));cy.append(int('/pos/' in member.name))
    ax=[];ay=[];groups=[];seen=set();neutral=duplicates=0
    with gzip.open(a.amazon,'rt') as f:
        for line in f:
            r=json.loads(line);rating=float(r['overall']);t=r.get('reviewText','').strip();key=' '.join(t.lower().split())
            if rating==3:neutral+=1;continue
            if not t or key in seen:duplicates+=1;continue
            seen.add(key);ax.append(t);ay.append(int(rating>=4));groups.append(r['reviewerID'])
    train,test=train_test_split(np.arange(len(cx)),test_size=.2,stratify=cy,random_state=42)
    cm=model();cm.fit([cx[i] for i in train],[cy[i] for i in train]);cornell=measure(cm,[cx[i] for i in test],[cy[i] for i in test])
    at,ae=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42).split(ax,ay,groups))
    am=model();am.fit([ax[i] for i in at],[ay[i] for i in at]);amazon=measure(am,[ax[i] for i in ae],[ay[i] for i in ae])
    amazon['majority_accuracy']=max(np.mean(np.array(ay)[ae]),1-np.mean(np.array(ay)[ae]))
    amazon['train_users']=len({groups[i] for i in at});amazon['test_users']=len({groups[i] for i in ae})
    assert not {groups[i] for i in at}&{groups[i] for i in ae}
    result={'seed':42,'fixed_configuration':'TF-IDF unigrams/bigrams + logistic regression, C=1; no test tuning','cornell':cornell,'amazon':amazon,'amazon_to_cornell_test':measure(am,[cx[i] for i in test],[cy[i] for i in test]),'amazon_neutral_removed':neutral,'amazon_empty_or_duplicates_removed':duplicates,'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [a.cornell,a.amazon]},'limitations':['Overall review polarity only; no independent aspect labels.','Amazon includes TV and product feedback; not an indie-only corpus.','Cornell split is review-stratified, not verified reviewer/film disjoint.','Amazon split separates reviewers but may share products.','No ASIN to TMDB join or personalized recommendation evaluation.','These test sets become consumed after reporting; use a fresh final holdout for future tuning.']}
    joblib.dump(cm,a.output_dir/'cornell-sentiment.joblib');joblib.dump(am,a.output_dir/'amazon-sentiment.joblib')
    (a.output_dir/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
