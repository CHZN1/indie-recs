from __future__ import annotations

import logging
import time
from io import BytesIO
from typing import BinaryIO

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Movie, Rating, User
from app.tmdb import get_movie_bundle, search_movie

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ("Username", "Movie Name", "Year", "Rating10")


class ImportResult:
    def __init__(self) -> None:
        self.user_ids: set[str] = set()
        self.imported_ratings = 0
        self.skipped_unrated = 0
        self.skipped_unmatched = 0
        self.movies_created = 0
        self.unique_titles_resolved = 0
        self.elapsed_seconds = 0.0
        self.warnings: list[str] = []


def _year_value(raw) -> int | None:
    if pd.isna(raw):
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _rating_value(raw) -> float | None:
    if pd.isna(raw) or raw == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < 0 or value > 10:
        return None
    return value


def parse_letterboxd_csv(source: BinaryIO | bytes | str) -> pd.DataFrame:
    if isinstance(source, bytes):
        source = BytesIO(source)
    df = pd.read_csv(source)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            "Letterboxd CSV is missing required columns: "
            + ", ".join(missing)
            + ". Expected Username, Movie Name, Year, Rating10."
        )
    return df


def _get_or_create_user(db: Session, username: str, cache: dict[str, User]) -> User:
    user = cache.get(username)
    if user is not None:
        return user
    user = db.scalar(select(User).where(User.user_id == username))
    if user is None:
        user = User(user_id=username)
        db.add(user)
        db.flush()
    cache[username] = user
    return user


def _get_or_create_movie(
    db: Session, tmdb_hit: dict, bundle: dict, cache: dict[int, Movie]
) -> tuple[Movie, bool]:
    tmdb_id = int(tmdb_hit["id"])
    movie = cache.get(tmdb_id)
    if movie is None:
        movie = db.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))
    details = bundle["details"]
    companies = [c["name"] for c in details.get("production_companies") or []]
    release = details.get("release_date") or tmdb_hit.get("release_date") or ""
    year = int(release[:4]) if len(release) >= 4 and release[:4].isdigit() else None
    created = False
    if movie is None:
        movie = Movie(
            title=details.get("title") or tmdb_hit.get("title") or "Unknown",
            year=year,
            tmdb_id=tmdb_id,
            is_indie=bool(bundle["is_indie"]),
            popularity=float(details.get("popularity") or tmdb_hit.get("popularity") or 0),
            vote_average=details.get("vote_average"),
            overview=details.get("overview"),
            poster_path=details.get("poster_path"),
            production_companies="; ".join(companies) if companies else None,
        )
        db.add(movie)
        db.flush()
        created = True
    else:
        movie.is_indie = bool(bundle["is_indie"])
        movie.popularity = float(details.get("popularity") or movie.popularity or 0)
        movie.production_companies = "; ".join(companies) if companies else movie.production_companies
    cache[tmdb_id] = movie
    return movie, created


def import_letterboxd_csv(db: Session, source: BinaryIO | bytes | str) -> ImportResult:
    started = time.perf_counter()
    df = parse_letterboxd_csv(source)
    result = ImportResult()
    users: dict[str, User] = {}
    movies: dict[int, Movie] = {}
    title_hits: dict[tuple[str, int | None], dict | None] = {}

    unique_keys: list[tuple[str, int | None]] = []
    seen: set[tuple[str, int | None]] = set()
    for _, row in df.iterrows():
        title = str(row["Movie Name"]).strip() if not pd.isna(row["Movie Name"]) else ""
        if not title or _rating_value(row["Rating10"]) is None:
            continue
        key = (title, _year_value(row["Year"]))
        if key not in seen:
            seen.add(key)
            unique_keys.append(key)

    for i, (title, year) in enumerate(unique_keys, start=1):
        try:
            hit = search_movie(db, title, year)
        except Exception as exc:  # noqa: BLE001
            warning = f"TMDB search failed for '{title}' ({year}): {exc}"
            logger.warning(warning)
            result.warnings.append(warning)
            title_hits[(title, year)] = None
            continue
        title_hits[(title, year)] = hit
        if hit is None:
            warning = f"No TMDB match for '{title}' ({year}); related ratings skipped."
            logger.warning(warning)
            result.warnings.append(warning)
        if i % 25 == 0 or i == len(unique_keys):
            logger.info("Resolved %s/%s unique titles", i, len(unique_keys))

    result.unique_titles_resolved = sum(1 for hit in title_hits.values() if hit is not None)

    rating_pairs: dict[tuple[int, int], Rating] = {}
    existing_ratings = db.scalars(select(Rating)).all()
    for rating in existing_ratings:
        rating_pairs[(rating.user_pk, rating.movie_id)] = rating

    for idx, row in df.iterrows():
        username = str(row["Username"]).strip() if not pd.isna(row["Username"]) else ""
        title = str(row["Movie Name"]).strip() if not pd.isna(row["Movie Name"]) else ""
        year = _year_value(row["Year"])
        rating_value = _rating_value(row["Rating10"])

        if not username or not title:
            result.warnings.append(f"Row {idx}: missing Username or Movie Name; skipped.")
            continue
        if rating_value is None:
            result.skipped_unrated += 1
            continue

        hit = title_hits.get((title, year))
        if hit is None:
            result.skipped_unmatched += 1
            continue

        bundle = get_movie_bundle(db, int(hit["id"]))
        user = _get_or_create_user(db, username, users)
        movie, created = _get_or_create_movie(db, hit, bundle, movies)
        if created:
            result.movies_created += 1

        pair_key = (user.id, movie.id)
        existing = rating_pairs.get(pair_key)
        if existing:
            existing.rating = rating_value
        else:
            created_rating = Rating(user_pk=user.id, movie_id=movie.id, rating=rating_value)
            db.add(created_rating)
            db.flush()
            rating_pairs[pair_key] = created_rating
        result.imported_ratings += 1
        result.user_ids.add(username)

    db.commit()
    result.elapsed_seconds = round(time.perf_counter() - started, 2)
    logger.info(
        "Imported %s ratings for %s users in %ss (%s unique titles matched)",
        result.imported_ratings,
        len(result.user_ids),
        result.elapsed_seconds,
        result.unique_titles_resolved,
    )
    return result
