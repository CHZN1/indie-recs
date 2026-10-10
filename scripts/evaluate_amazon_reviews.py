#!/usr/bin/env python3
"""Time-separated ASIN benchmark. No TMDB joins or live model writes."""
import argparse, gzip, hashlib, json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
from surprise import Dataset, Reader, SVD
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app.review_text import clean_review

def blend_scores(cf, text, weight):
    left=(pd.Series(cf).rank(method="average")-1)/(len(cf)-1) if len(cf)>1 else pd.Series({i:.5 for i in cf})
    if not any(abs(v)>1e-12 for v in text.values()):return left.to_dict()
    right=(pd.Series(text).rank(method="average")-1)/(len(text)-1) if len(text)>1 else pd.Series({i:.5 for i in text})
    return ((1-weight)*left+weight*right).to_dict()

WEIGHTS=(0,.05,.1,.2)

def split_rows(rows):
    times=sorted(r['unixReviewTime'] for r in rows)
    c1,c2=times[int(len(times)*.6)],times[int(len(times)*.8)]
    return ([r for r in rows if r['unixReviewTime']<c1],
            [r for r in rows if c1<=r['unixReviewTime']<c2],
            [r for r in rows if r['unixReviewTime']>=c2],c1,c2)

def metrics(order,positive,k=10):
    hits=[int(i in positive) for i in order[:k]]
    dcg=sum(h/np.log2(j+2) for j,h in enumerate(hits))
    ideal=sum(1/np.log2(j+2) for j in range(min(k,len(positive))))
    return [dcg/ideal,sum(hits)/len(positive),float(any(hits))]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reviews',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    if a.output.resolve().is_relative_to(Path(__file__).resolve().parent.parent):ap.error('Keep individual research output outside repository')
    raw=[json.loads(l) for l in gzip.open(a.reviews,'rt')]
    unique={};duplicates=0
    for r in sorted(raw,key=lambda x:x['unixReviewTime']):
        key=(r['reviewerID'],r['asin'])
        if key in unique:duplicates+=1;continue
        unique[key]=r
    train,val,test,c1,c2=split_rows(list(unique.values()))
    histories=defaultdict(list);docs=defaultdict(list)
    for r in train:
        histories[r['reviewerID']].append(r);docs[r['asin']].append(clean_review(r.get('reviewText',''))[:5000])
    items=sorted(docs);positions={i:j for j,i in enumerate(items)}
    vectorizer=TfidfVectorizer(ngram_range=(1,2),min_df=3,max_features=20000,sublinear_tf=True)
    matrix=normalize(vectorizer.fit_transform([' '.join(docs[i]) for i in items]))
    frame=pd.DataFrame([(r['reviewerID'],r['asin'],r['overall']) for r in train],columns=['user','item','rating'])
    svd=SVD(random_state=42,n_factors=100,n_epochs=30)
    svd.fit(Dataset.load_from_df(frame,Reader(rating_scale=(1,5))).build_full_trainset())
    # Item documents and user profiles contain training text only. No held-out text is transformed.
    def evaluate(rows,max_users):
        positives=defaultdict(set)
        for r in rows:
            if r['overall']>=4 and r['asin'] in positions:positives[r['reviewerID']].add(r['asin'])
        users=[u for u in positives if u in histories]
        users.sort(key=lambda u:hashlib.sha256(('42'+u).encode()).hexdigest());users=users[:max_users]
        output={str(w):[] for w in WEIGHTS};counts=[];cold=sum(r['asin'] not in positions for r in rows)
        for u in users:
            seen={r['asin'] for r in histories[u]};positive=positives[u]-seen
            if not positive:continue
            candidates=[i for i in items if i not in seen]
            cf={i:svd.predict(u,i).est for i in candidates}
            encoded=vectorizer.transform([clean_review(r.get('reviewText',''))[:5000] for r in histories[u]])
            weights=np.array([(r['overall']-3)/2 for r in histories[u]])
            profile=normalize(np.asarray(encoded.T@weights).reshape(1,-1)).ravel()
            scores=np.asarray(matrix@profile).ravel();text={i:float(scores[positions[i]]) for i in candidates}
            for w in WEIGHTS:
                blended=blend_scores(cf,text,w)
                order=sorted(candidates,key=lambda i:(-blended[i],hashlib.sha256(('42'+i).encode()).hexdigest()))
                output[str(w)].append(metrics(order,positive))
            counts.append(len(histories[u]))
        return output,{'users_evaluated':len(counts),'cold_item_interactions_excluded':cold,'history_counts':{'1':sum(c==1 for c in counts),'2_to_5':sum(2<=c<=5 for c in counts),'6_plus':sum(c>=6 for c in counts)}}
    validation,vs=evaluate(val,500)
    selected=max(WEIGHTS,key=lambda w:np.mean(np.array(validation[str(w)])[:,0]))
    final,ts=evaluate(test,1000)
    def aggregate(d):return {w:dict(zip(['ndcg_at_10','recall_at_10','hit_at_10'],np.mean(v,axis=0).tolist())) for w,v in d.items()}
    diff=np.array(final[str(selected)])[:,0]-np.array(final['0'])[:,0]
    rng=np.random.default_rng(42);boot=[float(rng.choice(diff,len(diff),replace=True).mean()) for _ in range(1000)]
    result={'source_sha256':hashlib.sha256(a.reviews.read_bytes()).hexdigest(),'seed':42,'split':'Global chronological 60/20/20 boundaries; identical training-only histories for validation and test; no refit on validation','cutoffs_unix':[c1,c2],'rows':{'raw':len(raw),'duplicate_user_products_removed':duplicates,'train':len(train),'validation':len(val),'test':len(test)},'catalog_products':len(items),'validation':aggregate(validation),'validation_population':vs,'selected_weight':selected,'test':aggregate(final),'test_population':ts,'selected_minus_ratings_ndcg':float(diff.mean()),'paired_bootstrap_95_interval':np.quantile(boot,[.025,.975]).tolist(),'limits':['Mixed Amazon video products; no reliable movie titles or indie classification.','Product ratings include playback/purchase sentiment.','Only warm products and users with at least one training interaction and an unseen positive qualify.','Unobserved products are unknown preferences, not confirmed negatives.','TF-IDF overlaps cannot establish aspect sentiment or causal preference.','User samples fixed by hash: at most 500 validation and 1000 test users.','Prior overall-sentiment experiments used some of these reviews; this is a new ranking protocol, not untouched project-wide data.','Test results are diagnostic after reporting; future tuning requires a new final holdout.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
