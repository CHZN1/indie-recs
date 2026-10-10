#!/usr/bin/env python3
"""Audit discovery tags against cached metadata without network calls or writes."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Movie,TmdbCache
from app.indie import indie_evidence
from app.discovery import decision
from collections import Counter


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.resolve().is_relative_to(Path(__file__).resolve().parent.parent):
        parser.error('Keep local catalog reports outside the repository.')
    rows=[]
    with SessionLocal() as db:
        for movie in db.scalars(select(Movie).order_by(Movie.id)):
            cached=db.get(TmdbCache,f'movie:{movie.tmdb_id}')
            bundle=json.loads(cached.payload) if cached else None
            details=bundle.get('details',{}) if bundle else {}
            reasons=indie_evidence(production_companies=[c['name'] for c in details.get('production_companies',[])],
                                   genres=[g['name'] for g in details.get('genres',[])],
                                   keywords=bundle.get('keywords',[])) if bundle else None
            credit=db.get(TmdbCache,f'creative:{movie.tmdb_id}')
            credits=json.loads(credit.payload) if credit else {}
            rows.append({'tmdb_id':movie.tmdb_id,'title':movie.title,'year':movie.year,
                         'stored_tag':movie.is_indie,'evidence':reasons,
                         'recomputed_tag':bool(reasons) if reasons is not None else None,
                         'composers':credits.get('composers',[]),
                         'discovery':decision(movie,bundle),
                         'budget':details.get('budget') or None,
                         'budget_unknown':not bool(details.get('budget')),
                         'festival_only_evidence':bool(reasons) and all(r.startswith('festival keyword:') for r in reasons),
                         'production_companies':[c['name'] for c in details.get('production_companies',[])],
                         'cached_vote_count':details.get('vote_count'),
                         'identity_review_suggested':details.get('vote_count',0)<50})
    zimmer=[r for r in rows if 'Hans Zimmer' in r['composers']]
    summary={'catalog':len(rows),'tagged_indie':sum(r['stored_tag'] for r in rows),
             'missing_metadata':sum(r['evidence'] is None for r in rows),
             'stale_flags':sum(r['recomputed_tag'] is not None and r['stored_tag']!=r['recomputed_tag'] for r in rows),
             'identity_review_suggested':sum(r['identity_review_suggested'] for r in rows),
             'zimmer_films':len(zimmer),'zimmer_indie_eligible':sum(r['stored_tag'] and r['discovery']['eligible'] for r in zimmer),
             'strict_eligible':sum(r['stored_tag'] and r['discovery']['eligible'] for r in rows),
             'expanded_eligible':sum(r['discovery']['eligible'] for r in rows),
             'eligible_budget_unknown':sum(r['discovery']['eligible'] and r['budget_unknown'] for r in rows),
             'eligible_festival_only':sum(r['discovery']['eligible'] and r['festival_only_evidence'] for r in rows),
             'discovery_reasons':dict(Counter(r['discovery']['reason'] for r in rows))}
    report={'summary':summary,'limitations':['Company and festival matches are discovery signals, not verified financing or ownership classifications.',
                                            'Missing evidence means untagged, not non-independent. Cached metadata may be outdated. Low vote counts flag identity review, not a wrong-match verdict.'], 'movies':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
