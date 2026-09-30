#!/usr/bin/env python3
"""Refresh indie flags using TMDB metadata, reusing cached responses when available."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Movie
from app.tmdb import get_movie_bundle


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        movies = db.scalars(select(Movie)).all()
        updated = 0
        for movie in movies:
            bundle = get_movie_bundle(db, movie.tmdb_id)
            details = bundle["details"]
            companies = [c["name"] for c in details.get("production_companies") or []]
            movie.is_indie = bool(bundle["is_indie"])
            movie.popularity = float(details.get("popularity") or movie.popularity or 0)
            movie.overview = details.get("overview") or movie.overview
            movie.poster_path = details.get("poster_path") or movie.poster_path
            movie.production_companies = "; ".join(companies) if companies else movie.production_companies
            updated += 1
        db.commit()
        print(f"Updated {updated} movies.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
