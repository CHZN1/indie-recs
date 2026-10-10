#!/usr/bin/env python3
"""Validation-only weight selection followed by previously unevaluated sparse users."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app.database import SessionLocal
from app.review_text import ReviewExample
from scripts.evaluate_reviews import catalog, evaluate, feature_catalog

# Already explored users belong to development/validation, never the fresh test.
DEVELOPMENT_USERS = (62,424,474)
VALIDATION_USERS = (477,537,567)
PREVIOUSLY_EVALUATED = frozenset(DEVELOPMENT_USERS + VALIDATION_USERS)
WEIGHTS = (.25,.5,.75)


def select_method(reports):
    """Select by user-averaged validation NDCG@10; ties favor ratings alone."""
    methods=['ratings_svd',*[f'hybrid_{w:g}' for w in WEIGHTS]]
    means={method:float(np.mean([r['aggregate'][method]['ndcg_at_10'] for r in reports])) for method in methods}
    return max(methods,key=lambda method:means[method]),means


def summarize(reports, methods):
    return {method:{metric:float(np.mean([r['aggregate'][method][metric] for r in reports]))
                    for metric in ('rank','hit_at_10','mrr','ndcg_at_10')} for method in methods}


def paired_interval(reports, selected):
    differences=np.array([r['aggregate'][selected]['ndcg_at_10']-r['aggregate']['ratings_svd']['ndcg_at_10'] for r in reports])
    rng=np.random.default_rng(901)
    samples=rng.choice(differences,size=(10000,len(differences)),replace=True).mean(axis=1)
    return {'metric':'user-averaged NDCG@10 difference (selected minus ratings)',
            'mean':float(differences.mean()),'bootstrap_95_percent_interval':np.quantile(samples,[.025,.975]).tolist(),
            'user_differences':differences.tolist(),'resampling_unit':'user','bootstrap_samples':10000,
            'warning':'Small convenience sample; descriptive interval, not population evidence.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parent.parent
    if args.output.resolve().is_relative_to(root):parser.error('Keep research data and reports outside the repository.')
    with zipfile.ZipFile(args.zip) as z:
        def read(name):return pd.read_csv(z.open('ml-latest-small/'+name+'.csv'))
        links,ratings,tags=read('links'),read('ratings'),read('tags')
    with SessionLocal() as db:
        movies,documents=catalog(db,creative_credits=True);features=feature_catalog(db,movies)
    links['item_id']=links.tmdbId.map({m.tmdb_id:m.id for m in movies})
    links=links.dropna(subset=['item_id'])
    ratings=ratings.merge(links[['movieId','item_id']],on='movieId')
    ratings['item_id']=ratings.item_id.astype(int);ratings['rating']*=2
    ratings['user_id']=ratings.userId.map(lambda u:f'ml-{u}')
    frame=ratings[['user_id','item_id','rating']]
    tags=tags.merge(links[['movieId','item_id']],on='movieId').sort_values('timestamp')
    tags=tags.groupby(['userId','item_id']).tag.agg(lambda x:'; '.join(dict.fromkeys(x))).reset_index()
    joined=tags.merge(ratings[['userId','item_id','rating']],on=['userId','item_id'])
    counts=joined.groupby('userId').item_id.nunique()
    test_users=[int(u) for u in counts[counts>=2].index if int(u) not in PREVIOUSLY_EVALUATED]
    def run(users,weights):
        reports=[]
        for u in users:
            rows=joined[joined.userId==u]
            examples=[ReviewExample(int(r.item_id),float(r.rating),r.tag) for r in rows.itertuples()]
            positives=rows[rows.rating>=8].item_id.to_numpy()
            if len(positives)==0:continue
            rng=np.random.default_rng(42+u)
            targets=set(int(i) for i in rng.choice(positives,size=min(5,len(positives)),replace=False))
            report=evaluate(frame,movies,documents,examples,f'ml-{u}',text_weights=weights,
                            max_features=None,features=features,target_ids=targets)
            # Only retain evaluation outputs, not descriptive refits or generic pilot caveats.
            reports.append({'user_id':u,'aggregate':report['aggregate'],'folds':report['folds'],
                            'available_tags':len(examples)})
            print(f'Evaluated {u}: {len(report["folds"])} targets',flush=True)
        if not reports:raise ValueError('No eligible users with positive targets.')
        return reports
    validation=run(VALIDATION_USERS,WEIGHTS)
    selected,selection_scores=select_method(validation)
    # Freeze choice before evaluating any test targets; do not sweep weights on test.
    print(f'Frozen validation choice: {selected}',flush=True)
    weights=() if selected=='ratings_svd' else (float(selected.split('_')[1]),)
    test=run(test_users,weights)
    methods=list(dict.fromkeys(['ratings_svd',selected,'adaptive_features']))
    comparison=summarize(test,methods);interval=paired_interval(test,selected)
    signal=sum(bool(f['feature_evidence'].get('preferences')) for r in test for f in r['folds'])
    report={'protocol_version':1,'source':'MovieLens latest-small, September 2018',
            'dataset_sha256':hashlib.sha256(args.zip.read_bytes()).hexdigest(),
            'frozen_extractor_sha256':hashlib.sha256((root/'app/review_features.py').read_bytes()).hexdigest(),
            'development_users':list(DEVELOPMENT_USERS),'validation_users':list(VALIDATION_USERS),'test_users':[r['user_id'] for r in test],
            'selection_metric':'validation user-averaged NDCG@10; ties favor ratings',
            'validation_selection_scores':selection_scores,'selected_method':selected,
            'test_targets':sum(len(r['folds']) for r in test),'test_aggregate':comparison,
            'paired_comparison':interval,'feature_signal_folds':signal,
            'deployment_decision':'Keep review modeling offline: sample is too small and explicit aspect signal is absent or insufficient.',
            'validation_reports':validation,'test_reports':test,
            'limitations':['Validation users were previously explored; this is a fresh sparse-user test, not a wholly untouched dataset.',
                           'Test users have two mapped tagged-and-rated films, unlike the larger validation histories.',
                           'Tags are not full reviews; implicit and aspect sentiment quality cannot be established.',
                           'Leave-one-film-out removes target rating and tags; other users’ ratings remain training data.',
                           'Candidate metadata is retrospective; this is not a temporal evaluation.',
                           'Unrated candidates have unknown relevance; liked-target ranks are a proxy.',
                           'Research dataset and private exports are not stored or published in the repository.']}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ['selected_method','test_targets','test_aggregate','paired_comparison','feature_signal_folds','deployment_decision']},indent=2))


if __name__=='__main__':main()
