#!/usr/bin/env python3
"""Stronger baselines and review ablations on previously unreported ranking users."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
from surprise import Dataset, Reader, SVD
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app.review_text import clean_review
from scripts.evaluate_amazon_reviews import split_rows, metrics

WEIGHTS=(0,.05,.1,.2)
SEEDS=(42,7,2026)

def ranked(values):
    if len(values)<2:return np.full(len(values),.5)
    return (pd.Series(values).rank(method='average').to_numpy()-1)/(len(values)-1)

def aggregate(values):
    return dict(zip(('ndcg_at_10','recall_at_10','hit_at_10'),np.mean(values,axis=0).tolist()))

def paired(left,right):
    diff=np.asarray(left)[:,0]-np.asarray(right)[:,0]
    rng=np.random.default_rng(42)
    bootstrap=[rng.choice(diff,len(diff),replace=True).mean() for _ in range(2000)]
    return {'ndcg_difference':float(diff.mean()),'bootstrap_95_interval':np.quantile(bootstrap,[.025,.975]).tolist()}

def user_hash(u):return hashlib.sha256(('42'+u).encode()).hexdigest()

def populations(rows,histories,positions,excluded=(),limit=500):
    positives=defaultdict(set)
    for r in rows:
        if r['overall']>=4 and r['asin'] in positions:positives[r['reviewerID']].add(r['asin'])
    users=sorted((u for u in positives if u in histories),key=user_hash)
    chosen=[]
    for u in users:
        if u in excluded:continue
        seen={r['asin'] for r in histories[u]}
        if positives[u]-seen:chosen.append((u,positives[u]-seen))
        if len(chosen)==limit:break
    return chosen

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reviews',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--movie-manifest',type=Path);ap.add_argument('--scope',choices=('indie','all','catalog'),default='indie');a=ap.parse_args()
    if a.output.resolve().is_relative_to(Path(__file__).resolve().parent.parent):ap.error('Research output must be outside repository')
    raw=[json.loads(l) for l in gzip.open(a.reviews,'rt')];unique={}
    for r in sorted(raw,key=lambda r:r['unixReviewTime']):unique.setdefault((r['reviewerID'],r['asin']),r)
    train,val,test,c1,c2=split_rows(list(unique.values()))
    histories=defaultdict(list);docs=defaultdict(list)
    for r in train:
        histories[r['reviewerID']].append(r);docs[r['asin']].append(clean_review(r.get('reviewText',''))[:5000])
    items=sorted(docs);positions={i:j for j,i in enumerate(items)}
    manifest=json.loads(a.movie_manifest.read_text()) if a.movie_manifest else None
    candidate_positions=positions
    if manifest:
        allowed={str(m['tmdb_id']) for m in manifest['catalog'] if a.scope=='catalog' or (m['discovery']['eligible'] and (a.scope=='all' or m['is_indie']))}
        candidate_positions={i:j for i,j in positions.items() if i in allowed}
    users=sorted(histories);userpos={u:j for j,u in enumerate(users)}
    # Exclude the earlier benchmark's test users and all validation-evaluated users.
    old_test=set() if manifest else {u for u,_ in populations(test,histories,positions,limit=1000)}
    validation=populations(val,histories,candidate_positions,limit=500)
    final=populations(test,histories,candidate_positions,excluded=old_test|{u for u,_ in validation},limit=1000)
    if not final:raise ValueError('No previously unreported ranking users remain')
    vectorizer=TfidfVectorizer(ngram_range=(1,2),min_df=3,max_features=20000,sublinear_tf=True)
    item_text=normalize(vectorizer.fit_transform([' '.join(docs[i]) for i in items]))
    profile_vectors={};metadata_vectors={}
    for u,_ in validation+final:
        history=histories[u];weights=np.array([(r['overall']-3)/2 for r in history])
        encoded=vectorizer.transform([clean_review(r.get('reviewText',''))[:5000] for r in history])
        profile_vectors[u]=normalize(np.asarray(encoded.T@weights).reshape(1,-1)).ravel()
        metadata_vectors[u]=normalize(np.asarray(item_text[[positions[r['asin']] for r in history]].T@weights).reshape(1,-1)).ravel()
    # Ratings-only implicit item-item cosine baseline; no review words.
    positive=csr_matrix(([1. for r in train if r['overall']>=4],([userpos[r['reviewerID']] for r in train if r['overall']>=4],[positions[r['asin']] for r in train if r['overall']>=4])),shape=(len(users),len(items)))
    columns=normalize(positive.T);similarity=(columns@columns.T).toarray();np.fill_diagonal(similarity,0)
    popularity=np.asarray(positive.sum(axis=0)).ravel()
    frame=pd.DataFrame([(r['reviewerID'],r['asin'],r['overall']) for r in train],columns=['user','item','rating'])
    data=Dataset.load_from_df(frame,Reader(rating_scale=(1,5))).build_full_trainset()
    models={}
    for seed in SEEDS:
        for factors,reg in [(100,.02),(20,.1)]:
            name=f'svd_{factors}_reg{reg}_seed{seed}'
            models[name]=SVD(n_factors=factors,reg_all=reg,n_epochs=30,random_state=seed).fit(data)
    ties=np.array([user_hash(i) for i in items]);rng=np.random.default_rng(42);permutation=rng.permutation(len(items))
    def evaluate(population):
        output=defaultdict(list);counts=[]
        for u,positives in population:
            history=histories[u];seen={r['asin'] for r in history};indices=np.array([j for j,i in enumerate(items) if i not in seen and i in candidate_positions]);candidate_items=[items[j] for j in indices]
            text=np.asarray(item_text@profile_vectors[u]).ravel()
            controls={'review':text,'history_item_text':np.asarray(item_text@metadata_vectors[u]).ravel(),'shuffled_review':text[permutation]}
            bases={'popularity':popularity[indices],'item_cosine':np.asarray(positive[userpos[u]]@similarity).ravel()[indices]}
            bases.update({name:np.array([m.predict(u,i).est for i in candidate_items]) for name,m in models.items()})
            for base_name,values in bases.items():
                bp=ranked(values)
                def score(name,values):
                    order=np.lexsort((ties[indices],-values));output[name].append(metrics([candidate_items[j] for j in order],positives))
                score(base_name,bp)
                for source,signal in controls.items():
                    tp=ranked(signal[indices]) if np.any(np.abs(signal[indices])>1e-12) else bp
                    for w in WEIGHTS[1:]:score(f'{base_name}|{source}|{w}',(1-w)*bp+w*tp)
            counts.append(len(history))
        return output,counts
    print('Training complete; evaluating validation and reserved ranking users',flush=True)
    v,vc=evaluate(validation)
    base_names=['popularity','item_cosine',*models]
    best_rating=max(base_names,key=lambda n:aggregate(v[n])['ndcg_at_10'])
    review_names=base_names+[n for n in v if '|review|' in n]
    best_hybrid=max(review_names,key=lambda n:aggregate(v[n])['ndcg_at_10'])
    # Controls use the selected model's same base and coefficient, never optimized on test.
    base,_,weight=best_hybrid.partition('|review|')
    selected=[best_rating,best_hybrid]
    if weight:selected += [f'{base}|history_item_text|{weight}',f'{base}|shuffled_review|{weight}']
    t,tc=evaluate(final)
    bucket_indices={'one_rating':[j for j,c in enumerate(tc) if c==1],'two_to_five':[j for j,c in enumerate(tc) if 2<=c<=5],'six_plus':[j for j,c in enumerate(tc) if c>=6]}
    buckets={b:{'users':len(ix),'results':{n:aggregate(np.asarray(t[n])[ix]) for n in selected}} for b,ix in bucket_indices.items() if ix}
    result={'source_sha256':hashlib.sha256(a.reviews.read_bytes()).hexdigest(),'movie_manifest_sha256':hashlib.sha256(a.movie_manifest.read_bytes()).hexdigest() if manifest else None,'candidate_scope':a.scope if manifest else 'all_amazon_products','eligible_training_candidates':len(candidate_positions),'training_rows':len(train),'catalog_products':len(items),'cutoffs_unix':[c1,c2],'validation_users':len(validation),'reserved_test_users':len(final),'previous_test_users_excluded':len(old_test),'validation_users_excluded_from_test':len(validation),'selection_metric':'validation NDCG@10; all candidates; no final-test tuning','selected_ratings_baseline':best_rating,'selected_hybrid':best_hybrid,'validation':{n:aggregate(v[n]) for n in v},'test':{n:aggregate(t[n]) for n in selected},'rating_baselines_test':{n:aggregate(t[n]) for n in base_names},'seed_sensitivity_fixed_20_percent':{n:paired(t[n+'|review|0.2'],t[n]) for n in models},'hybrid_vs_best_ratings':paired(t[best_hybrid],t[best_rating]),'buckets':buckets,'controls':{n:paired(t[best_hybrid],t[n]) for n in selected[2:]},'limits':['Movie mode uses a new source and excludes validation users from test; Amazon mode additionally excludes earlier ranking test users.','Movie mode joins exact cached IMDb links and year checks, but indie labels remain metadata heuristics; Amazon mode mixes video products without movie identities.','All item documents and user histories use training reviews only; no held-out review text used.','History-item-text control uses other users earlier reviews, so is not a ratings-only baseline.','Shuffled control permutes candidate text associations, preserving the score distribution.','Bootstrap intervals cover user sampling, not product clustering or multiple comparisons.','Observational future positive ratings; unobserved products are not verified dislikes.','No claim of globally optimal model or validated aspect sentiment.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('validation','seed_sensitivity_fixed_20_percent')},indent=2))
if __name__=='__main__':main()
