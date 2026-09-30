from __future__ import annotations

import logging
from pathlib import Path

import joblib
import pandas as pd
from surprise import SVD, Dataset, Reader, accuracy
from surprise.model_selection import train_test_split
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Rating, User

logger = logging.getLogger(__name__)


def ratings_frame(db: Session) -> pd.DataFrame:
    rows = db.execute(
        select(User.user_id, Rating.movie_id, Rating.rating).join(User, Rating.user_pk == User.id)
    ).all()
    return pd.DataFrame(rows, columns=["user_id", "item_id", "rating"])


def train_svd(db: Session, model_path: str | None = None) -> bool:
    df = ratings_frame(db)
    if df.empty or df["user_id"].nunique() < 1:
        logger.warning("No ratings available; skipping SVD training.")
        return False

    reader = Reader(rating_scale=(0, 10))
    data = Dataset.load_from_df(df[["user_id", "item_id", "rating"]], reader)
    trainset = data.build_full_trainset()
    n_factors = 50 if len(df) < 500 else 100
    n_epochs = 20 if len(df) < 500 else 30
    algo = SVD(n_factors=n_factors, n_epochs=n_epochs, random_state=42, verbose=False)
    algo.fit(trainset)

    payload = {
        "algo": algo,
        "user_ids": set(df["user_id"].astype(str).unique()),
        "item_ids": set(df["item_id"].astype(int).unique()),
    }
    path = Path(model_path or get_settings().model_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, path)
    logger.info("Saved SVD model to %s (%s ratings)", path, len(df))
    return True


def load_model(model_path: str | None = None) -> dict | None:
    path = Path(model_path or get_settings().model_path)
    if not path.exists():
        return None
    return joblib.load(path)


def evaluate_holdout(db: Session, test_size: float = 0.2) -> dict | None:
    df = ratings_frame(db)
    if len(df) < 80 or df["user_id"].nunique() < 5:
        logger.warning("Not enough ratings for a holdout evaluation.")
        return None
    reader = Reader(rating_scale=(0, 10))
    data = Dataset.load_from_df(df[["user_id", "item_id", "rating"]], reader)
    trainset, testset = train_test_split(data, test_size=test_size, random_state=42)
    algo = SVD(n_factors=100, n_epochs=30, random_state=42, verbose=False)
    algo.fit(trainset)
    predictions = algo.test(testset)
    return {
        "rmse": round(float(accuracy.rmse(predictions, verbose=False)), 4),
        "mae": round(float(accuracy.mae(predictions, verbose=False)), 4),
        "n_train": trainset.n_ratings,
        "n_test": len(testset),
        "n_users": df["user_id"].nunique(),
        "n_items": df["item_id"].nunique(),
    }
