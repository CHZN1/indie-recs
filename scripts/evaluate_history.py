"""Compare history sizes with fixed held-out ratings and unchanged other users."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from surprise import Dataset, Reader, SVD
from app.database import SessionLocal
from app.training import ratings_frame


def evaluate(df, users=12):
    budgets = [1, 5, 10, 25, 50]
    errors = {k: [] for k in budgets}
    baseline = []
    eligible = sorted(u for u, rows in df.groupby('user_id') if len(rows) >= 60)[:users]
    for user in eligible:
        rows = df[df.user_id == user].sample(frac=1, random_state=42)
        holdout = rows.iloc[:10]
        history = rows.iloc[10:]
        others = df[df.user_id != user]
        means = others.groupby('item_id').rating.mean()
        for row in holdout.itertuples():
            baseline.append(float(means.get(row.item_id, others.rating.mean())) - row.rating)
        for count in budgets:
            import pandas as pd
            train = pd.concat([others, history.iloc[:count]])
            dataset = Dataset.load_from_df(train[['user_id', 'item_id', 'rating']], Reader(rating_scale=(0, 10)))
            algo = SVD(n_factors=100, n_epochs=30, random_state=42).fit(dataset.build_full_trainset())
            errors[count].extend(algo.predict(user, row.item_id).est - row.rating for row in holdout.itertuples())
    if not eligible:
        raise ValueError('Need users with at least 60 ratings for the 50-rating comparison.')
    def metrics(values):
        return {'rmse': round(float(np.sqrt(np.mean(np.square(values)))),4),
                'mae': round(float(np.mean(np.abs(values))),4), 'test_ratings': len(values)}
    return {'users_tested':len(eligible),'seed':42,'held_out_per_user':10,
            'method':'Other users unchanged; fixed holdout; nested histories; 0–10 scale. Synthetic data is a pipeline check, not evidence of real-world quality.',
            'history_sizes':{str(k):metrics(v) for k,v in errors.items()},'item_mean_baseline':metrics(baseline)}

if __name__ == '__main__':
    with SessionLocal() as db:
        print(json.dumps(evaluate(ratings_frame(db)), indent=2))
