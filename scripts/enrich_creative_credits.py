#!/usr/bin/env python3
"""Fetch public creative credits for the local catalog; never transmit reviews."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Movie
from app.tmdb import get_creative_credits, TmdbError


def main():
    counts = dict(composers=0, cinematographers=0, directors=0, editors=0)
    failures = []
    with SessionLocal() as db:
        movies = db.scalars(select(Movie).order_by(Movie.id)).all()
        for index, movie in enumerate(movies, 1):
            try:
                result = get_creative_credits(db, movie.tmdb_id)
                for role in counts:
                    counts[role] += bool(result[role])
            except TmdbError as exc:
                db.rollback()
                failures.append({'tmdb_id': movie.tmdb_id, 'error': str(exc)})
            if index % 25 == 0:
                print(f'Checked {index}/{len(movies)} movies', flush=True)
        print(json.dumps({'movies': len(movies), 'coverage': counts, 'failures': failures}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
