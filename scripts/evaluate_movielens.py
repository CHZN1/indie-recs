#!/usr/bin/env python3
"""MovieLens ratings + tags research proxy, separate from live or synthetic data."""
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


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.resolve().is_relative_to(Path(__file__).resolve().parent.parent):
        parser.error('Keep research datasets and results outside the public repository.')
    with zipfile.ZipFile(args.zip) as archive:
        def read(name):return pd.read_csv(archive.open('ml-latest-small/'+name+'.csv'))
        links,ratings,tags=read('links'),read('ratings'),read('tags')
    with SessionLocal() as db:
        movies,documents=catalog(db,creative_credits=True)
        features=feature_catalog(db,movies)
    mapping={m.tmdb_id:m.id for m in movies}
    links['item_id']=links.tmdbId.map(mapping)
    links=links.dropna(subset=['item_id'])
    ratings=ratings.merge(links[['movieId','item_id']],on='movieId')
    ratings['user_id']=ratings.userId.map(lambda u:f'ml-{u}')
    ratings['item_id']=ratings.item_id.astype(int)
    ratings['rating']=ratings.rating*2
    frame=ratings[['user_id','item_id','rating']]
    tags=tags.merge(links[['movieId','item_id']],on='movieId')
    # All tags on a held-out movie disappear together with that user's rating.
    tags=tags.sort_values('timestamp').groupby(['userId','item_id']).tag.agg(lambda x:'; '.join(dict.fromkeys(x))).reset_index()
    joined=tags.merge(ratings[['userId','item_id','rating']],on=['userId','item_id'])
    counts=joined.groupby('userId').item_id.nunique()
    eligible=counts[counts>=5].index.tolist()
    if not eligible:raise ValueError('No user has five mapped tagged-and-rated films.')
    rng=np.random.default_rng(42)
    reports=[]
    for user in sorted(eligible):
        rows=joined[joined.userId==user]
        examples=[ReviewExample(int(r.item_id),float(r.rating),r.tag) for r in rows.itertuples()]
        positives=rows[rows.rating>=8].item_id.to_numpy()
        if not len(positives):continue
        targets=set(int(i) for i in rng.choice(positives,size=min(5,len(positives)),replace=False))
        report=evaluate(frame,movies,documents,examples,f'ml-{user}',max_features=None,features=features,target_ids=targets)
        report['limits'][1]='All rating rows in this experiment come from MovieLens, without fictional sample users or private Letterboxd ratings.'
        report['limits'][4]='Public creative credit names and a small curated style map do not provide complete score-style or lighting coverage.'
        reports.append(report)
        print(f'Evaluated user {len(reports)}/{len(eligible)}; {len(targets)} held-out liked films',flush=True)
    methods=reports[0]['aggregate'].keys()
    aggregate={name:{metric:round(float(np.mean([r['aggregate'][name][metric] for r in reports])),5)
                     for metric in ('rank','hit_at_10','mrr','ndcg_at_10')} for name in methods}
    allfolds=[f for r in reports for f in r['folds']]
    report={'source':'MovieLens latest-small (September 2018), GroupLens',
            'source_sha256':hashlib.sha256(args.zip.read_bytes()).hexdigest(),
            'source_url':'https://grouplens.org/datasets/movielens/latest/',
            'citation':'F. Maxwell Harper and Joseph A. Konstan. 2015. The MovieLens Datasets: History and Context. DOI:10.1145/2827872',
            'mapped_movies':len(links),'mapped_ratings':len(frame),
            'tagged_rated_users':joined.userId.nunique(),'evaluated_users':len(reports),
            'held_out_liked_films':len(allfolds),'seed':42,
            'aggregation':'Mean of each user’s fold means; users have equal weight. Up to five randomly selected liked targets per user (rating >=8/10). All remaining rated tags form the profile.',
            'aggregate':aggregate,'user_reports':reports,
            'feature_signal_folds':sum(bool(f['feature_evidence'].get('preferences')) for f in allfolds),
            'limits':['Tags are short descriptions, not reviews or explicit sentiment.',
                      'Only users with at least five mapped tagged-and-rated movies are evaluated; small biased subset.',
                      'Public metadata may reflect later updates; retrospective, not temporal evaluation.',
                      'Unrated candidates are unknown preferences, not confirmed dislikes.',
                      'Development dataset snapshot, not a standard benchmark; research-only permission does not grant commercial use.']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ('mapped_movies','mapped_ratings','evaluated_users','held_out_liked_films','aggregate','feature_signal_folds')},indent=2))


if __name__=='__main__':main()
