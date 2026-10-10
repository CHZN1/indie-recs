from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Movie, Rating, User
from app.schemas import RecommendationItem, RecommendResponse
from app.training import load_model
from app.discovery import eligible_ids


def _movie_to_item(movie: Movie, predicted: float | None) -> RecommendationItem:
    return RecommendationItem(
        movie_id=movie.id,
        tmdb_id=movie.tmdb_id,
        title=movie.title,
        year=movie.year,
        predicted_rating=None if predicted is None else round(float(predicted), 3),
        popularity=movie.popularity,
        is_indie=movie.is_indie,
        overview=movie.overview,
        poster_path=movie.poster_path,
    )


def popular_indie(db: Session, exclude_ids: set[int], limit: int = 10, *, scope: str = "indie") -> list[RecommendationItem]:
    eligible = eligible_ids(db, db.scalars(select(Movie)).all(), scope)
    avg_rating = func.avg(Rating.rating).label("avg_rating")
    rating_count = func.count(Rating.id).label("rating_count")
    rows = (
        db.execute(
            select(Movie, avg_rating, rating_count)
            .outerjoin(Rating, Rating.movie_id == Movie.id)
            .where(Movie.id.in_(eligible))
            .group_by(Movie.id)
            .order_by(rating_count.desc(), avg_rating.desc(), Movie.popularity.desc())
        )
        .all()
    )
    items: list[RecommendationItem] = []
    for movie, avg, _count in rows:
        if movie.id in exclude_ids:
            continue
        items.append(_movie_to_item(movie, avg))
        if len(items) >= limit:
            break
    return items


def recommend_for_user(db: Session, user_id: str, limit: int = 10, *, scope: str = "indie") -> RecommendResponse:
    if scope not in ("indie", "all"):
        raise ValueError("scope must be indie or all")
    user = db.scalar(select(User).where(User.user_id == user_id))
    rated_ids: set[int] = set()
    if user:
        rated_ids = set(db.scalars(select(Rating.movie_id).where(Rating.user_pk == user.id)).all())

    model = load_model()
    indie_movies = db.scalars(select(Movie)).all()
    eligible = eligible_ids(db, indie_movies, scope)
    candidates = [m for m in indie_movies if m.id not in rated_ids and m.id in eligible]

    if (
        model is None
        or user is None
        or user_id not in model["user_ids"]
        or not candidates
    ):
        return RecommendResponse(
            user_id=user_id,
            strategy="cold_start",
            recommendations=popular_indie(db, rated_ids, limit, scope=scope),
        )

    algo = model["algo"]
    scored: list[tuple[Movie, float]] = []
    for movie in candidates:
        prediction = algo.predict(user_id, movie.id)
        scored.append((movie, float(prediction.est)))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    recs = [_movie_to_item(movie, est) for movie, est in scored[:limit]]
    return RecommendResponse(user_id=user_id, strategy="cf", recommendations=recs)
