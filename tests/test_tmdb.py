from types import SimpleNamespace

import httpx
import pytest

from app import tmdb


@pytest.mark.parametrize("failure", ["status", "connection"])
def test_tmdb_errors_do_not_expose_credentials(monkeypatch, failure):
    key = "test-key-must-not-appear-in-errors"
    settings = SimpleNamespace(tmdb_api_key=key, tmdb_base_url="https://api.themoviedb.org/3")
    monkeypatch.setattr(tmdb, "get_settings", lambda: settings)
    monkeypatch.setattr(tmdb, "_throttle", lambda: None)

    def respond(request):
        assert request.url.params["api_key"] == key
        if failure == "connection":
            raise httpx.ConnectError(f"Connection failed: {request.url}", request=request)
        return httpx.Response(401, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(tmdb, "_http_client", lambda: client)
        with pytest.raises(tmdb.TmdbError) as caught:
            tmdb._get("/search/movie", {"query": "Moonlight"})

    assert key not in str(caught.value)
    assert "api_key" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_cached_movie_is_reclassified_with_current_rules(monkeypatch):
    bundle = {
        "details": {"production_companies": [{"name": "A24"}], "genres": []},
        "keywords": [],
        "is_indie": False,
    }
    monkeypatch.setattr(tmdb, "_cache_get", lambda db, key: bundle)
    assert tmdb.get_movie_bundle(None, 1)["is_indie"] is True


def test_cached_unmatched_search_remains_unmatched(monkeypatch):
    monkeypatch.setattr(tmdb, "_cache_get", lambda db, key: None)
    assert tmdb.search_movie(None, "Unmatched title", 2024) is None


def test_providers_keep_regions_and_purchase_types_separate(monkeypatch):
    payload = {'results': {'US': {'link': 'https://www.themoviedb.org/movie/1/watch',
        'rent': [{'provider_name': 'Example rental', 'logo_path': '/logo.png'}]}}}
    monkeypatch.setattr(tmdb, '_cache_get', lambda db, key: payload)
    us = tmdb.get_watch_providers(None, 1, 'US')
    assert us['providers']['rent'][0]['name'] == 'Example rental'
    assert us['providers']['flatrate'] == []
    assert not any(tmdb.get_watch_providers(None, 1, 'GB')['providers'].values())


def test_provider_cache_expires_after_one_day(monkeypatch):
    import json
    from datetime import datetime, timedelta
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.database import Base
    from app.models import TmdbCache
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    monkeypatch.setattr(tmdb, 'get_settings', lambda: SimpleNamespace(tmdb_cache_ttl_days=30))
    with Session(engine) as db:
        db.add(TmdbCache(cache_key='providers:1',payload=json.dumps({'results': {}}),
                         created_at=datetime.utcnow()-timedelta(hours=25)))
        db.commit()
        assert tmdb._cache_get(db,'providers:1') is tmdb._MISSING


def test_creative_credits_use_exact_roles_and_deduplicate(monkeypatch):
    monkeypatch.setattr(tmdb, '_cache_get', lambda db, key: tmdb._MISSING)
    monkeypatch.setattr(tmdb, '_get', lambda path, params: {'crew': [
        {'job':'Original Music Composer','name':'Example Composer'},
        {'job':'Original Music Composer','name':'Example Composer'},
        {'job':'Music Supervisor','name':'Different Person'},
        {'job':'Director of Photography','name':'Example Photographer'},
        {'job':'Gaffer','name':'Lighting Technician'},
    ]})
    saved=[]
    monkeypatch.setattr(tmdb, '_cache_set', lambda db, key, value: saved.append((key,value)))
    db=SimpleNamespace(commit=lambda:None)
    result=tmdb.get_creative_credits(db,1)
    assert result['composers']==['Example Composer']
    assert result['cinematographers']==['Example Photographer']
    assert result['directors']==[]
    assert saved[0][0]=='creative:1'


def test_creative_credits_cache_avoids_network(monkeypatch):
    cached={'composers':[],'cinematographers':[],'directors':[],'editors':[]}
    monkeypatch.setattr(tmdb,'_cache_get',lambda db,key:cached)
    monkeypatch.setattr(tmdb,'_get',lambda *args:pytest.fail('Cached credits must not fetch again'))
    assert tmdb.get_creative_credits(None,1)==cached
