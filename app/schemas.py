from pydantic import BaseModel, Field


class RecommendationItem(BaseModel):
    movie_id: int
    tmdb_id: int
    title: str
    year: int | None = None
    predicted_rating: float | None = None
    popularity: float | None = None
    is_indie: bool = True
    overview: str | None = None
    poster_path: str | None = None


class RecommendResponse(BaseModel):
    user_id: str
    strategy: str = Field(description="cf for collaborative filtering, cold_start for popular indie fallback")
    recommendations: list[RecommendationItem]


class UploadResponse(BaseModel):
    user_ids: list[str]
    imported_ratings: int
    skipped_unrated: int
    skipped_unmatched: int
    movies_created: int
    unique_titles_resolved: int = 0
    elapsed_seconds: float = 0.0
    model_retrained: bool
    warnings: list[str] = []
