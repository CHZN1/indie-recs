#!/usr/bin/env python3
"""Fresh-import a large Letterboxd CSV, retrain, evaluate RMSE, and print recommendations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select

from app.config import get_settings
from app.database import Base, SessionLocal, engine, init_db
from app.importer import import_letterboxd_csv
from app.models import Movie, Rating, User
from app.recommend import recommend_for_user
from app.training import evaluate_holdout, train_svd


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    init_db()
    model_path = Path(get_settings().model_path)
    if model_path.exists():
        model_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="sample_data/letterboxd_large.csv")
    parser.add_argument("--fresh", action="store_true", help="Delete tables in the configured database and the saved model first")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}. Run python scripts/generate_large_export.py first.")

    init_db()
    if args.fresh:
        reset_db()

    db = SessionLocal()
    try:
        result = import_letterboxd_csv(db, str(csv_path))
        trained = train_svd(db)
        holdout = evaluate_holdout(db)
        stats = {
            "users": db.scalar(select(func.count(User.id))),
            "movies": db.scalar(select(func.count(Movie.id))),
            "indie_movies": db.scalar(select(func.count(Movie.id)).where(Movie.is_indie.is_(True))),
            "ratings": db.scalar(select(func.count(Rating.id))),
        }
        recs = {}
        for user_id in ("maya", "jordan", "sam", "riley"):
            payload = recommend_for_user(db, user_id, limit=10)
            recs[user_id] = {
                "strategy": payload.strategy,
                "titles": [item.title for item in payload.recommendations],
                "all_indie": all(item.is_indie for item in payload.recommendations),
                "count": len(payload.recommendations),
            }

        summary = {
            "import": {
                "imported_ratings": result.imported_ratings,
                "skipped_unrated": result.skipped_unrated,
                "skipped_unmatched": result.skipped_unmatched,
                "movies_created": result.movies_created,
                "unique_titles_resolved": result.unique_titles_resolved,
                "elapsed_seconds": result.elapsed_seconds,
                "warning_count": len(result.warnings),
                "warnings_head": result.warnings[:15],
            },
            "model_retrained": trained,
            "holdout": holdout,
            "stats": stats,
            "recommendations": recs,
        }
        print(json.dumps(summary, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
