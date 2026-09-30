from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.importer import import_letterboxd_csv
from app.models import Movie, Rating, User
from app.recommend import recommend_for_user
from app.schemas import RecommendResponse, UploadResponse
from app.training import train_svd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Indie Recs",
    description="Collaborative filtering trained on all Letterboxd ratings; recommendations filtered to indie films.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict[str, int]:
    return {
        "users": int(db.scalar(select(func.count(User.id))) or 0),
        "movies": int(db.scalar(select(func.count(Movie.id))) or 0),
        "indie_movies": int(db.scalar(select(func.count(Movie.id)).where(Movie.is_indie.is_(True))) or 0),
        "ratings": int(db.scalar(select(func.count(Rating.id))) or 0),
    }


@app.post("/upload", response_model=UploadResponse)
async def upload_letterboxd_csv(
    file: UploadFile = File(..., description="Letterboxd export CSV"),
    db: Session = Depends(get_db),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")
    raw = await file.read()
    try:
        result = import_letterboxd_csv(db, raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Import failed")
        raise HTTPException(status_code=502, detail=f"Import failed: {exc}") from exc

    retrained = train_svd(db)
    return UploadResponse(
        user_ids=sorted(result.user_ids),
        imported_ratings=result.imported_ratings,
        skipped_unrated=result.skipped_unrated,
        skipped_unmatched=result.skipped_unmatched,
        movies_created=result.movies_created,
        unique_titles_resolved=result.unique_titles_resolved,
        elapsed_seconds=result.elapsed_seconds,
        model_retrained=retrained,
        warnings=result.warnings[:50],
    )


@app.get("/recommend/{user_id}", response_model=RecommendResponse)
def recommend(user_id: str, db: Session = Depends(get_db)) -> RecommendResponse:
    return recommend_for_user(db, user_id, limit=10)
