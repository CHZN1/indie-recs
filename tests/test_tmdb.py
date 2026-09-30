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
