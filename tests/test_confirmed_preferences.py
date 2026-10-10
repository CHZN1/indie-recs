import json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base, get_db
from app.models import Movie, Rating, User, TmdbCache
from app.main import app
from app import recommend
from app.preferences import ConfirmedChoice, apply_choices


@pytest.fixture
def client(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=__import__('sqlalchemy').pool.StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user=User(user_id='viewer')
        watched=Movie(tmdb_id=1,title='Watched',is_indie=True)
        films=[Movie(tmdb_id=i,title=f'Film {i}',is_indie=i!=13) for i in range(2,14)]
        db.add_all([user,watched,*films]);db.flush()
        db.add(Rating(user_pk=user.id,movie_id=watched.id,rating=9))
        for tmdb in (1,12,13):db.add(TmdbCache(cache_key=f'creative:{tmdb}',payload=json.dumps({'composers':['Hans Zimmer']})))
        db.add(TmdbCache(cache_key='movie:13',payload=json.dumps({'details':{'production_companies':[{'name':'FilmNation Entertainment'}]},'keywords':[]})))
        db.commit()
        scores={m.id:8.1 for m in films};scores[films[-2].id]=8.0
        class Algo:
            def predict(self,u,i):return SimpleNamespace(est=scores[i])
        monkeypatch.setattr(recommend,'load_model',lambda:{'algo':Algo(),'user_ids':{'viewer'}})
        def dependency():yield db
        app.dependency_overrides[get_db]=dependency
        try:yield TestClient(app),db
        finally:app.dependency_overrides.clear()


def test_confirmed_match_can_enter_top_ten_without_changing_rating(client):
    c,db=client
    before=c.get('/recommend/viewer').json()
    assert 12 not in [r['tmdb_id'] for r in before['recommendations']]
    r=c.post('/recommend/viewer/preferences',json={'choices':[{'feature':'composer:hans zimmer','direction':'prefer'}]}).json()
    matched=next(row for row in r['recommendations'] if row['tmdb_id']==12)
    assert matched['predicted_rating']==8.0 and matched['ranking_score']==8.2
    assert matched['preference_matches'][0]['source']=='explicit_user_choice'
    assert 1 not in [row['tmdb_id'] for row in r['recommendations']]
    assert 13 not in [row['tmdb_id'] for row in r['recommendations']]
    assert c.get('/recommend/viewer').json()==before


def test_no_choices_matches_baseline_and_unknown_profile_keeps_fallback(client):
    c,_=client
    assert c.post('/recommend/viewer/preferences',json={'choices':[]}).json()['recommendations']==c.get('/recommend/viewer').json()['recommendations']
    r=c.post('/recommend/unknown/preferences?scope=all',json={'choices':[{'feature':'composer:hans zimmer','direction':'prefer'}]}).json()
    assert r['strategy']=='cold_start' and r['preference_mode']=='ratings_only'


def test_choices_validate_and_scope_all_includes_untagged(client):
    c,_=client
    choices=[{'feature':'composer:hans zimmer','direction':'prefer'}]
    assert c.post('/recommend/viewer/preferences',json={'choices':choices*2}).status_code==400
    assert c.post('/recommend/viewer/preferences',json={'choices':[{'feature':'invented','direction':'prefer'}]}).status_code==400
    assert c.post('/recommend/viewer/preferences',json={'choices':choices,'reviews':'secret'}).status_code==422
    assert c.post('/recommend/viewer/preferences?scope=no',json={'choices':choices}).status_code==422
    rows=c.post('/recommend/viewer/preferences?scope=all',json={'choices':choices}).json()['recommendations']
    assert 13 in [r['tmdb_id'] for r in rows]
    options=c.get('/preferences/options').json()['options']
    zimmer=next(r for r in options if r['feature']=='composer:hans zimmer')
    assert zimmer['catalog_matches']==3 and zimmer['indie_matches']==2


def test_cap_opposition_and_rating_boundaries():
    choices=[ConfirmedChoice(feature='composer:a',direction='prefer'),ConfirmedChoice(feature='visual:b',direction='avoid')]
    delta,_=apply_choices({1:9.99,2:.01,3:5},{1:{'composer:a'},2:{'visual:b'},3:{'composer:a','visual:b'}},choices)
    assert delta[1]==pytest.approx(.01) and delta[2]==pytest.approx(-.01) and delta[3]==0
