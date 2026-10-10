#!/usr/bin/env python3
"""Local leave-one-film-out review experiment. Never changes the live model."""
from __future__ import annotations
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from sqlalchemy import select
from surprise import Dataset, Reader, SVD

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.database import SessionLocal
from app.models import Movie, TmdbCache
from app.review_features import FeatureCatalog, normalize
from app.review_text import ReviewExample, ReviewTextModel, blend_scores, ranking_metrics
from app.training import ratings_frame


def catalog(db, creative_credits=False):
    movies = db.scalars(select(Movie).order_by(Movie.id)).all()
    documents = {}
    for movie in movies:
        cached = db.get(TmdbCache, f'movie:{movie.tmdb_id}')
        bundle = json.loads(cached.payload) if cached else {}
        genres = [g['name'] for g in bundle.get('details', {}).get('genres', [])]
        parts = [movie.overview or '', *genres, *bundle.get('keywords', [])]
        if creative_credits:
            creative = db.get(TmdbCache, f'creative:{movie.tmdb_id}')
            if creative is None:
                raise ValueError('Creative credits are incomplete. Run scripts/enrich_creative_credits.py first.')
            credits = json.loads(creative.payload)
            labels = {'composers':'original music composer',
                      'cinematographers':'director of photography',
                      'directors':'director', 'editors':'editor'}
            parts.extend(f'{labels[role]} {name}' for role in labels for name in credits.get(role, []))
        documents[movie.id] = ' '.join(parts)
    return movies, documents



def feature_catalog(db, movies):
    definitions=json.loads((Path(__file__).resolve().parent.parent/'research'/'curated_features.json').read_text())
    features={}
    for movie in movies:
        row=db.get(TmdbCache,f'creative:{movie.tmdb_id}')
        credits=json.loads(row.payload) if row else {}
        values=set(definitions['movies'].get(str(movie.tmdb_id),{}).get('features',[]))
        roles={'composers':'composer','directors':'director','cinematographers':'cinematographer'}
        for role,label in roles.items():
            values.update(f'{label}:{normalize(name)}' for name in credits.get(role,[]))
        features[movie.id]=frozenset(values)
    return FeatureCatalog(features,definitions['reference_styles'])

def read_examples(db, path: Path, user: str, movies: list[Movie], frame):
    ratings = {int(r.item_id):float(r.rating) for r in frame[frame.user_id == user].itertuples()}
    resolved, warnings = {}, []
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not {'Name', 'Year', 'Review'} <= set(reader.fieldnames or []):
            raise ValueError('Expected native Letterboxd reviews.csv with Name, Year, Review.')
        for row in reader:
            if not row['Review'].strip():
                continue
            title, year = row['Name'].strip(), int(row['Year'])
            # Original export year may differ from TMDB's release year. Prefer the
            # importer's cached resolution; otherwise accept only one exact match.
            cached = db.get(TmdbCache, f'search:{title.lower()}:{year}')
            hit = json.loads(cached.payload) if cached else None
            matches = [m for m in movies if hit and m.tmdb_id == hit.get('id')]
            if not matches:
                matches = [m for m in movies if m.title.casefold() == title.casefold() and m.year == year]
            if len(matches) != 1 or matches[0].id not in ratings:
                warnings.append(f'Unmatched or unrated review: {title} ({year})')
                continue
            item = matches[0].id
            if item in resolved:
                raise ValueError(f'Multiple reviews resolve to movie {item}; choose one before evaluation.')
            resolved[item] = ReviewExample(item, ratings[item], row['Review'])
    return list(resolved.values()), warnings


def evaluate(frame, movies, documents, examples, user, text_weights=(.25, .5, .75), max_features=20000, features=None, target_ids=None):
    if len(examples) < 2:
        raise ValueError('Need at least two matched rated reviews for leave-one-film-out evaluation.')
    model = ReviewTextModel(documents, max_features=max_features)
    target_rows = frame[frame.user_id == user]
    rated_ids = set(target_rows.item_id.astype(int))
    titles = {m.id:m.title for m in movies}
    indie_ids = {m.id for m in movies if m.is_indie}
    folds = []
    for held in examples:
        if target_ids is not None and held.item_id not in target_ids:
            continue
        training = frame[~((frame.user_id == user) & (frame.item_id == held.item_id))]
        available_reviews = [r for r in examples if r.item_id != held.item_id]
        # Metadata control has every remaining rated movie, even if not reviewed.
        metadata_profile = [ReviewExample(int(r.item_id), float(r.rating), '')
                            for r in training[training.user_id == user].itertuples()]
        data = Dataset.load_from_df(training[['user_id','item_id','rating']], Reader(rating_scale=(0,10)))
        algo = SVD(n_factors=50 if len(training)<500 else 100,
                   n_epochs=20 if len(training)<500 else 30, random_state=42).fit(data.build_full_trainset())
        candidates = [m.id for m in movies if m.id not in rated_ids or m.id == held.item_id]
        cf = {i:float(algo.predict(user,i).est) for i in candidates}
        review_all = model.scores(available_reviews)
        metadata_all = model.scores(metadata_profile, 'metadata')
        review = {i:review_all[i] for i in candidates}
        variants = {'ratings_svd':cf, 'rating_metadata':{i:metadata_all[i] for i in candidates},
                    'reviews_tfidf':review}
        for weight in text_weights:
            variants[f'hybrid_{weight:g}'] = blend_scores(cf,review,weight)
        feature_evidence = {}
        if features is not None:
            variants['adaptive_features'],feature_evidence=features.adjust(cf,available_reviews)
        fold = {'held_out':titles[held.item_id], 'item_id':held.item_id,
                'candidate_count':len(candidates), 'indie_eligible':held.item_id in indie_ids,
                'known_item_in_cf':bool((training.item_id == held.item_id).any()),
                'training_reviews':len(available_reviews), 'feature_evidence':feature_evidence,
                'review_signal':bool(np.linalg.norm(model.profile(available_reviews)) > 0),
                'metrics':{name:ranking_metrics(scores,held.item_id) for name,scores in variants.items()}}
        if held.item_id in indie_ids:
            fold['indie_metrics'] = {name:ranking_metrics({i:s for i,s in scores.items() if i in indie_ids}, held.item_id)
                                    for name,scores in variants.items()}
        folds.append(fold)
    def aggregate(selected, key):
        if not selected:
            return None
        return {name:{metric:round(float(np.mean([f[key][name][metric] for f in selected])),5)
                      for metric in ('rank','hit_at_10','mrr','ndcg_at_10')}
                for name in selected[0][key]}
    # Descriptive full-history examples are not evaluation labels.
    final_text = model.scores(examples)
    indie_candidates = [m.id for m in movies if m.id not in rated_ids and m.is_indie]
    # Refit using all ratings for the descriptive comparison only.
    algo.fit(Dataset.load_from_df(frame[['user_id','item_id','rating']],Reader(rating_scale=(0,10))).build_full_trainset())
    final_cf = {i:float(algo.predict(user,i).est) for i in indie_candidates}
    final_review = {i:final_text[i] for i in final_cf}
    comparison = {'ratings_svd':final_cf,'reviews_tfidf':final_review,
                  'hybrid_0.25':blend_scores(final_cf,final_review,.25)}
    if features is not None:
        comparison['adaptive_features'],full_evidence=features.adjust(final_cf,examples)
    top = {name:[{'title':titles[i], 'item_id':i, 'text_matches':model.explain(examples,i)}
                 for i in sorted(scores,key=lambda i:(-scores[i],i))[:10]] for name,scores in comparison.items()}
    indie_folds = [f for f in folds if f['indie_eligible']]
    known_folds = [f for f in folds if f['known_item_in_cf']]
    return {'method':'Leave one reviewed film out: remove its rating and review; fixed candidate catalog; other users unchanged; metadata-only TF-IDF vocabulary; expected metrics for ties.',
            'max_features':max_features,'vocabulary_size':len(model.vectorizer.vocabulary_),
            'seed':42,'users_tested':1,'reviews_tested':len(folds),'available_reviews':len(examples),'catalog_size':len(movies),
            'indie_folds':len(indie_folds),'cf_known_item_folds':len(known_folds),
            'aggregate':aggregate(folds,'metrics'),'indie_aggregate':aggregate(indie_folds,'indie_metrics'),
            'known_item_aggregate':aggregate(known_folds,'metrics'),'folds':folds,
            'review_coverage':[{'title':titles[r.item_id],**model.review_coverage(r.text)} for r in examples],
            'descriptive_indie_top10':top,
            'limits':[f'One user and {len(examples)} reviewed ratings cannot establish general quality.',
                      'Other users have synthetic ratings; this is a mixed-data pilot.',
                      'Unrated candidates are unknown preferences, not confirmed dislikes.',
                      'Hybrid weights are predetermined sensitivity checks, not tuned or validated.',
                      'Plot/genre/keyword metadata has limited soundtrack, lighting, and composer coverage.',
                      'Bag of words does not reliably understand negation, sentiment scope, or synonyms.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviews',type=Path,required=True)
    parser.add_argument('--user',required=True)
    parser.add_argument('--creative-credits',action='store_true',help='Include cached factual composer and cinematographer credits.')
    parser.add_argument('--output',type=Path,required=True,help='Private JSON output; kept outside the repository.')
    parser.add_argument('--adaptive-features',action='store_true',help='Add the experimental ratings-first feature adjustment.')
    parser.add_argument('--full-vocabulary',action='store_true',help='Remove the vocabulary cap for a fair expanded-metadata comparison.')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    if args.output.resolve().is_relative_to(root):
        parser.error('Keep personal experiment output outside the repository.')
    with SessionLocal() as db:
        movies,documents=catalog(db,args.creative_credits);frame=ratings_frame(db)
        examples,warnings=read_examples(db,args.reviews,args.user,movies,frame)
        report=evaluate(frame,movies,documents,examples,args.user,max_features=None if args.full_vocabulary else 20000,
                        features=feature_catalog(db,movies) if args.adaptive_features else None)
        report['warnings']=warnings
        report['metadata_variant']='creative_credits' if args.creative_credits else 'overview_genres_keywords'
        if args.creative_credits:
            report['limits'][4]='Factual creative credit names are available, but do not establish soundtrack style or lighting aesthetics.'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['reviews_tested','catalog_size','indie_folds','cf_known_item_folds','aggregate','limits']},indent=2))


if __name__=='__main__':
    main()
