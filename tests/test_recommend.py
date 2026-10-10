from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base
from app.models import Movie, Rating, User, TmdbCache
from app.training import train_svd, load_model
from app import recommend


def test_one_rating_personalizes_and_excludes_watched(tmp_path, monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(user_id='one-rating')
        watched = Movie(title='Watched', tmdb_id=1, is_indie=True)
        candidate = Movie(title='Unseen', tmdb_id=2, is_indie=True)
        db.add_all([user, watched, candidate]); db.flush()
        db.add(Rating(user_pk=user.id, movie_id=watched.id, rating=9)); db.commit()
        path = str(tmp_path / 'model.joblib')
        assert train_svd(db, path)
        monkeypatch.setattr(recommend, 'load_model', lambda: load_model(path))
        result = recommend.recommend_for_user(db, 'one-rating')
        assert result.strategy == 'cf'
        assert [r.tmdb_id for r in result.recommendations] == [2]
        assert recommend.recommend_for_user(db, 'new-user').strategy == 'cold_start'


def test_catalog_scope_preserves_exclusion_in_cf_and_fallback(monkeypatch):
    class Algo:
        def predict(self, user, movie):
            from types import SimpleNamespace
            return SimpleNamespace(est=9)
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine) as db:
        user=User(user_id='viewer')
        watched=Movie(title='Watched',tmdb_id=11,is_indie=False)
        indie=Movie(title='Tagged',tmdb_id=12,is_indie=True)
        broad=Movie(title='Untagged',tmdb_id=13,is_indie=False)
        db.add_all([user,watched,indie,broad]);db.flush()
        db.add(TmdbCache(cache_key='movie:13',payload='{"details":{"production_companies":[{"name":"FilmNation Entertainment"}]},"keywords":[]}'))
        db.add(Rating(user_pk=user.id,movie_id=watched.id,rating=8));db.commit()
        monkeypatch.setattr(recommend,'load_model',lambda:{'algo':Algo(),'user_ids':{'viewer'}})
        assert [r.tmdb_id for r in recommend.recommend_for_user(db,'viewer').recommendations]==[12]
        assert {r.tmdb_id for r in recommend.recommend_for_user(db,'viewer',scope='all').recommendations}=={12,13}
        monkeypatch.setattr(recommend,'load_model',lambda:None)
        assert {r.tmdb_id for r in recommend.recommend_for_user(db,'viewer',scope='all').recommendations}=={12,13}
