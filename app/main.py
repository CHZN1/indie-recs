from __future__ import annotations

from typing import Literal

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.config import ROOT_DIR, get_settings
from app.security import principal, own_profile, require_admin
from app.reviews import router as review_router
from app.jobs import enqueue
from app.models import TrainingJob
from app.importer import import_letterboxd_csv
from app.models import Movie, Rating, User
from app.recommend import recommend_for_user
from app.schemas import RecommendResponse, UploadResponse
from app.preferences import PreferenceRequest
from app.training import train_svd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
# httpx INFO request logs can include the TMDB api_key query parameter.
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)


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


app.include_router(review_router)


@app.get("/demo", include_in_schema=False)
def demo() -> FileResponse:
    if get_settings().auth_required:raise HTTPException(404, "Demo disabled in authenticated mode")
    return FileResponse(ROOT_DIR / "demo" / "index.html")


@app.get("/demo/sample", include_in_schema=False)
def demo_sample() -> FileResponse:
    if get_settings().auth_required:raise HTTPException(404, "Demo disabled in authenticated mode")
    return FileResponse(
        ROOT_DIR / "sample_data" / "letterboxd_ratings.csv",
        media_type="text/csv",
        filename="letterboxd_ratings.csv",
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/stats")
def stats(actor=Depends(principal), db: Session = Depends(get_db)) -> dict[str, int]:
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
    actor=Depends(principal),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")
    raw = await file.read(get_settings().max_upload_bytes+1)
    if len(raw)>get_settings().max_upload_bytes:raise HTTPException(413,'CSV exceeds upload size limit')
    if actor is not None and not actor.is_admin:
        from app.importer import parse_letterboxd_csv
        try:
            frame=parse_letterboxd_csv(raw)
            names=set(frame['Username'].dropna().astype(str).str.strip())- {''}
        except Exception:
            raise HTTPException(400,'Invalid ratings CSV') from None
        if names != {actor.user_id}:raise HTTPException(403,'CSV must contain only the credential owner profile')
    try:
        result = import_letterboxd_csv(db, raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Import failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Import failed; check the CSV and metadata service") from None

    job_id = None
    if get_settings().background_training:
        job_id = enqueue(db, actor.user_pk if actor else None)
        retrained = False
    else:
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
        training_job_id=job_id,
        warnings=result.warnings[:50],
    )


@app.get("/recommend/{user_id}", response_model=RecommendResponse)
def recommend(user_id: str, scope: Literal["indie", "all"] = "indie", db: Session = Depends(get_db), actor=Depends(principal)) -> RecommendResponse:
    own_profile(actor,user_id)
    return recommend_for_user(db, user_id, limit=10, scope=scope)


@app.get("/movies/{tmdb_id}/watch-providers")
def watch_providers(tmdb_id: int, region: str = Query("US", pattern="^[A-Z]{2}$"),
                    db: Session = Depends(get_db), actor=Depends(principal)) -> dict:
    from app.tmdb import get_watch_providers, TmdbError
    if tmdb_id < 1:
        raise HTTPException(status_code=400, detail="Movie ID must be positive.")
    if db.scalar(select(Movie.id).where(Movie.tmdb_id == tmdb_id)) is None:
        raise HTTPException(status_code=404, detail="Movie is not in the local catalog.")
    try:
        return get_watch_providers(db, tmdb_id, region)
    except TmdbError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


@app.get("/preferences/options")
def confirmed_preference_options(db: Session = Depends(get_db), actor=Depends(principal)) -> dict:
    from app.preferences import preference_options
    return preference_options(db)


@app.post("/recommend/{user_id}/preferences")
def confirmed_preferences(user_id: str, request: PreferenceRequest,
                          scope: Literal["indie", "all"] = "indie",
                          db: Session = Depends(get_db), actor=Depends(principal)) -> dict:
    own_profile(actor,user_id)
    from app.preferences import recommend_confirmed
    try:
        return recommend_confirmed(db, user_id, request, scope)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.post('/training/jobs')
def request_training(actor=Depends(principal),db: Session=Depends(get_db)):
    require_admin(actor)
    return {'job_id':enqueue(db,actor.user_pk if actor else None),'status':'queued'}


@app.get('/training/jobs/{job_id}')
def training_status(job_id: int,actor=Depends(principal),db: Session=Depends(get_db)):
    job=db.get(TrainingJob,job_id)
    if job is None:raise HTTPException(404,'Training job not found')
    if actor is not None and not actor.is_admin and job.owner_pk!=actor.user_pk:raise HTTPException(403,'Job belongs to another profile')
    return {'job_id':job.id,'status':job.status,'error':job.error}
