from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.indie import classify_indie
from app.models import TmdbCache

logger = logging.getLogger(__name__)
_MIN_REQUEST_INTERVAL = 0.03
_last_request_at = 0.0
_MISSING = object()
_memory: dict[str, Any] = {}
_http: httpx.Client | None = None


class TmdbError(RuntimeError):
    pass


def _http_client() -> httpx.Client:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.Client(timeout=20.0)
    return _http


def _throttle() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_at = time.monotonic()


def _cache_get(db: Session, key: str) -> Any:
    if key in _memory:
        return _memory[key]
    row = db.get(TmdbCache, key)
    if row is None:
        return _MISSING
    ttl = timedelta(days=get_settings().tmdb_cache_ttl_days)
    if datetime.utcnow() - row.created_at > ttl:
        db.delete(row)
        return _MISSING
    payload = json.loads(row.payload)
    _memory[key] = payload
    return payload


def _cache_set(db: Session, key: str, payload: Any) -> None:
    _memory[key] = payload
    existing = db.get(TmdbCache, key)
    encoded = json.dumps(payload)
    if existing:
        existing.payload = encoded
        existing.created_at = datetime.utcnow()
    else:
        db.add(TmdbCache(cache_key=key, payload=encoded))


def _get(path: str, params: dict[str, Any]) -> Any:
    settings = get_settings()
    if not settings.tmdb_api_key or settings.tmdb_api_key == "your_tmdb_api_key_here":
        raise TmdbError("TMDB_API_KEY is not set. Copy .env.example to .env and add your key.")
    query = {"api_key": settings.tmdb_api_key, **params}
    _throttle()
    url = f"{settings.tmdb_base_url}{path}"
    try:
        response = _http_client().get(url, params=query)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise TmdbError(f"TMDB returned HTTP {exc.response.status_code}.") from None
    except httpx.RequestError:
        raise TmdbError("Could not reach TMDB. Check your connection and try again.") from None
    return response.json()


def pick_search_result(results: list[dict[str, Any]], title: str, year: int | None) -> dict[str, Any] | None:
    if not results:
        return None
    title_n = title.strip().lower()

    def score(row: dict[str, Any]) -> tuple:
        pop = row.get("popularity") or 0
        votes = row.get("vote_count") or 0
        rtitle = (row.get("title") or "").strip().lower()
        exact = 1 if rtitle == title_n else 0
        release = row.get("release_date") or ""
        ry = int(release[:4]) if len(release) >= 4 and release[:4].isdigit() else None
        year_score = 0
        if year and ry:
            diff = abs(ry - year)
            if diff == 0:
                year_score = 4
            elif diff == 1:
                year_score = 2
            elif diff <= 2:
                year_score = 1
        elif not year:
            year_score = 1
        return (exact, year_score, pop, votes)

    return max(results, key=score)


def _search_raw(title: str, year: int | None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"query": title, "include_adult": False}
    if year:
        params["year"] = year
    data = _get("/search/movie", params)
    return list(data.get("results") or [])


def search_movie(db: Session, title: str, year: int | None) -> dict[str, Any] | None:
    cache_key = f"search:{title.strip().lower()}:{year or ''}"
    cached = _cache_get(db, cache_key)
    if cached is not _MISSING:
        return cached

    results = _search_raw(title, year)
    best = pick_search_result(results, title, year)
    if year:
        release = (best or {}).get("release_date") or ""
        ry = int(release[:4]) if len(release) >= 4 and release[:4].isdigit() else None
        if best is None or ry is None or abs(ry - year) > 2:
            broader = pick_search_result(_search_raw(title, None), title, year)
            if broader is not None:
                best = broader

    _cache_set(db, cache_key, best)
    return best


def get_movie_bundle(db: Session, tmdb_id: int) -> dict[str, Any]:
    cache_key = f"movie:{tmdb_id}"
    cached = _cache_get(db, cache_key)
    if cached is not _MISSING:
        details = cached["details"]
        cached["is_indie"] = classify_indie(
            production_companies=[c["name"] for c in details.get("production_companies") or []],
            genres=[g["name"] for g in details.get("genres") or []],
            keywords=cached["keywords"],
        )
        return cached

    details = _get(f"/movie/{tmdb_id}", {"append_to_response": "keywords"})
    keyword_block = details.get("keywords") or {}
    keywords = [k["name"] for k in keyword_block.get("keywords") or keyword_block.get("results") or []]
    companies = [c["name"] for c in details.get("production_companies") or []]
    genres = [g["name"] for g in details.get("genres") or []]
    bundle = {
        "details": details,
        "keywords": keywords,
        "is_indie": classify_indie(
            production_companies=companies,
            genres=genres,
            keywords=keywords,
        ),
    }
    _cache_set(db, cache_key, bundle)
    return bundle
