"""Stateless, explicitly confirmed preferences; raw review text never reranks here."""
from __future__ import annotations
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import ROOT_DIR
from app.models import Movie, TmdbCache
from app.recommend import recommend_for_user
from app.review_features import normalize
from app.discovery import eligible_ids

MAX_ADJUSTMENT = .2


class ConfirmedChoice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    feature: str = Field(min_length=1,max_length=200)
    direction: Literal['prefer','avoid']


class PreferenceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    choices: list[ConfirmedChoice] = Field(default_factory=list,max_length=8)


def cached_features(db: Session):
    """Read public cached credits and curated traits; never fetch or infer traits."""
    definitions=json.loads((ROOT_DIR/'research'/'curated_features.json').read_text())
    movies=db.scalars(select(Movie).order_by(Movie.id)).all()
    credits={row.cache_key:json.loads(row.payload) for row in db.scalars(select(TmdbCache).where(TmdbCache.cache_key.like('creative:%')))}
    features={}
    for movie in movies:
        traits=set(definitions['movies'].get(str(movie.tmdb_id),{}).get('features',[]))
        cached=credits.get(f'creative:{movie.tmdb_id}',{})
        for role,label in [('composers','composer'),('directors','director'),('cinematographers','cinematographer')]:
            traits.update(f'{label}:{normalize(name)}' for name in cached.get(role,[]))
        features[movie.id]=traits
    return movies,features


def preference_options(db: Session):
    movies,features=cached_features(db)
    by_id={m.id:m for m in movies}
    discovery=eligible_ids(db,movies,'all')
    strict=eligible_ids(db,movies,'indie')
    all_features=sorted({f for traits in features.values() for f in traits})
    return {'options':[{'feature':f,'label':f.replace(':',': ',1),
                        'catalog_matches':sum(f in traits for traits in features.values()),
                        'indie_matches':sum(f in traits and i in strict for i,traits in features.items()),
                        'discovery_matches':sum(f in traits and i in discovery for i,traits in features.items())}
                       for f in all_features],
            'max_adjustment_points':MAX_ADJUSTMENT,
            'source':'Cached TMDB creative credits and a small source-backed curated trait map.',
            'limitations':'Missing traits mean unknown. Counts include watched films; available candidates may be fewer.'}


def apply_choices(base: dict[int,float], features: dict[int,set[str]], choices: list[ConfirmedChoice]):
    """Average matched signed choices; multiple choices never exceed the cap."""
    adjustments={}
    explanations={}
    for item in base:
        matches=[c for c in choices if c.feature in features.get(item,set())]
        delta=MAX_ADJUSTMENT*sum(1 if c.direction=='prefer' else -1 for c in matches)/len(choices) if choices else 0
        adjustments[item]=max(0,min(10,base[item]+delta))-base[item]
        explanations[item]=[{'feature':c.feature,'direction':c.direction,
                             'source':'explicit_user_choice'} for c in matches]
    return adjustments,explanations


def recommend_confirmed(db: Session, user_id: str, request: PreferenceRequest, scope: str='indie'):
    movies,features=cached_features(db)
    allowed={f for values in features.values() for f in values}
    selected=[c.feature for c in request.choices]
    if len(selected)!=len(set(selected)):
        raise ValueError('Choose each preference only once.')
    if any(f not in allowed for f in selected):
        raise ValueError('Preference is not available in the catalog. Refresh the preference options.')
    # Score the entire eligible catalog before taking ten; reranking only the
    # old top ten would hide newly eligible matches just below the cutoff.
    response=recommend_for_user(db,user_id,limit=max(10,len(movies)),scope=scope)
    result=response.model_dump()
    active=bool(request.choices) and response.strategy=='cf'
    base={r.movie_id:r.predicted_rating for r in response.recommendations if r.predicted_rating is not None}
    adjustments,explanations=apply_choices(base,features,request.choices if active else [])
    rows=result['recommendations']
    if active:
        for row in rows:
            item=row['movie_id']
            row['ranking_score']=round(base[item]+adjustments[item],3)
            row['preference_adjustment']=round(adjustments[item],3)
            row['preference_matches']=explanations[item]
        rows.sort(key=lambda row:row['ranking_score'],reverse=True)
    result['recommendations']=rows[:10]
    result['preference_mode']='confirmed' if active else 'ratings_only'
    result['max_adjustment_points']=MAX_ADJUSTMENT if active else 0
    result['choices']=[c.model_dump() for c in request.choices]
    result['note']=('Confirmed preferences adjust ranking scores, not predicted ratings. No review text is interpreted or saved.' if active
                    else 'Ratings-only ordering. Confirmed adjustments require a trained personalized profile.')
    return result
