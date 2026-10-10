"""Positive discovery evidence with explicit mainstream/franchise exclusions."""
import json
from sqlalchemy import select
from app.indie import _normalize
from app.models import TmdbCache

EXPANDED_COMPANIES = (
    'filmnation entertainment', 'participant', 'participant media', 'american zoetrope',
    'hanway films', 'the match factory', 'pastel', 'animal kingdom',
    'borderline films', 'protagonist pictures', 'see saw films',
    'element pictures', 'rt features', 'cinemaundici', 'arte france cinema',
    'arte france', 'arte', 'haut et court', 'why not productions',
)
MAJOR_COMPANIES=('warner bros', 'walt disney', 'paramount pictures', 'universal pictures',
                 'columbia pictures','20th century','twentieth century','sony pictures entertainment')


def matching(values, phrases):
    return [value for value in values if any(' '+_normalize(p)+' ' in ' '+_normalize(value)+' ' for p in phrases)]


def decision(movie, bundle):
    d=(bundle or {}).get('details',{})
    companies=[r['name'] for r in d.get('production_companies',[])]
    normalized=[_normalize(c) for c in companies]
    superhero=any('marvel' in c or c in ('dc films','dc entertainment','dc studios') for c in normalized)
    keywords=[_normalize(k) for k in (bundle or {}).get('keywords',[])]
    universe=any(k in ('marvel cinematic universe','dc extended universe','dceu','mcu') for k in keywords)
    major=bool(matching(companies,MAJOR_COMPANIES))
    if superhero or universe:
        return {'eligible':False,'reason':'superhero_studio_or_universe'}
    if (d.get('budget') or 0)>=40_000_000:
        return {'eligible':False,'reason':'large_budget_exclusion'}
    if d.get('belongs_to_collection') and major:
        return {'eligible':False,'reason':'major_studio_franchise'}
    if movie.is_indie:
        return {'eligible':True,'reason':'indie_tag'}
    evidence=matching(companies,EXPANDED_COMPANIES)
    if evidence and not major:
        return {'eligible':True,'reason':'independent_production_evidence','companies':evidence}
    return {'eligible':False,'reason':'insufficient_discovery_evidence'}


def eligible_ids(db,movies,scope):
    cached={int(r.cache_key.split(':')[1]):json.loads(r.payload) for r in db.scalars(
        select(TmdbCache).where(TmdbCache.cache_key.like('movie:%')))}
    ids=set()
    for movie in movies:
        result=decision(movie,cached.get(movie.tmdb_id))
        if result['eligible'] and (scope!='indie' or movie.is_indie):ids.add(movie.id)
    return ids
