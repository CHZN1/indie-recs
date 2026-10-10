"""Owner-scoped review storage; no automatic preference inference."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Movie, Rating, Review, User
from app.security import principal, own_profile

router=APIRouter()

class ReviewInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    text: str=Field(min_length=1,max_length=20000)


def target(db,user_id,tmdb_id,require_rating=False):
    user=db.scalar(select(User).where(User.user_id==user_id))
    movie=db.scalar(select(Movie).where(Movie.tmdb_id==tmdb_id))
    if not user or not movie:raise HTTPException(404,'Profile or movie not found')
    rating=db.scalar(select(Rating.id).where(Rating.user_pk==user.id,Rating.movie_id==movie.id))
    if require_rating and rating is None:raise HTTPException(409,'Rate this movie before attaching a review')
    return user,movie


@router.put('/users/{user_id}/reviews/{tmdb_id}')
def save_review(user_id: str,tmdb_id: int,body: ReviewInput,actor=Depends(principal),db: Session=Depends(get_db)):
    own_profile(actor,user_id)
    if not body.text.strip():raise HTTPException(400,'Review text cannot be blank')
    user,movie=target(db,user_id,tmdb_id,require_rating=True)
    row=db.scalar(select(Review).where(Review.user_pk==user.id,Review.movie_id==movie.id))
    if row is None:row=Review(user_pk=user.id,movie_id=movie.id);db.add(row)
    row.text=body.text.strip();row.updated_at=datetime.utcnow();db.commit()
    return {'tmdb_id':tmdb_id,'stored':True,'used_for_ranking':False}


@router.get('/users/{user_id}/reviews/{tmdb_id}')
def get_review(user_id: str,tmdb_id: int,actor=Depends(principal),db: Session=Depends(get_db)):
    own_profile(actor,user_id);user,movie=target(db,user_id,tmdb_id)
    row=db.scalar(select(Review).where(Review.user_pk==user.id,Review.movie_id==movie.id))
    if not row:raise HTTPException(404,'Review not found')
    return {'tmdb_id':tmdb_id,'text':row.text,'used_for_ranking':False}


@router.delete('/users/{user_id}/reviews/{tmdb_id}')
def delete_review(user_id: str,tmdb_id: int,actor=Depends(principal),db: Session=Depends(get_db)):
    own_profile(actor,user_id);user,movie=target(db,user_id,tmdb_id)
    row=db.scalar(select(Review).where(Review.user_pk==user.id,Review.movie_id==movie.id))
    if row:db.delete(row);db.commit()
    return {'tmdb_id':tmdb_id,'deleted':True}
