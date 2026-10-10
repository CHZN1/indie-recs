import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.database import Base
from app.models import Movie, Rating
from app import importer


def test_explicit_tmdb_id_bypasses_ambiguous_search(monkeypatch):
    monkeypatch.setattr(importer,'search_movie',lambda *a:pytest.fail('Explicit ID must bypass title search'))
    def bundle(db,tmdb_id):
        return {'details':{'title':'Same Title','release_date':'2016-01-01','production_companies':[]},'is_indie':True}
    monkeypatch.setattr(importer,'get_movie_bundle',bundle)
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine) as db:
        raw=b'Username,Movie Name,Year,Rating10,TMDB ID\na,Same Title,2015,9,10\na,Same Title,2015,7,11\n'
        result=importer.import_letterboxd_csv(db,raw)
        assert result.imported_ratings==2
        assert {m.tmdb_id for m in db.scalars(select(Movie))}=={10,11}
        assert len(db.scalars(select(Rating)).all())==2


@pytest.mark.parametrize('value',['-1','0','1.5','nonsense','inf'])
def test_invalid_explicit_id_rejected_before_search(monkeypatch,value):
    monkeypatch.setattr(importer,'search_movie',lambda *a:pytest.fail('Invalid IDs should fail before search'))
    with pytest.raises(ValueError,match='TMDB ID'):
        importer.import_letterboxd_csv(None,f'Username,Movie Name,Year,Rating10,TMDB ID\na,X,2020,9,{value}\n'.encode())


def test_review_column_upserts_without_blank_erasure_and_rejects_long_text(monkeypatch):
    from app.models import Review
    monkeypatch.setattr(importer,'get_movie_bundle',lambda *a:{'details':{'title':'Film','release_date':'2000-01-01','production_companies':[]},'is_indie':True})
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine) as db:
        header='Username,Movie Name,Year,Rating10,TMDB ID,Review\n'
        importer.import_letterboxd_csv(db,(header+'alice,Film,2000,8,12,Loved the music\nalice,Film,2000,9,12,Great score\n').encode())
        assert db.scalar(select(Review)).text=='Great score'
        importer.import_letterboxd_csv(db,(header+'alice,Film,2000,7,12,\n').encode())
        assert db.scalar(select(Review)).text=='Great score'
        with pytest.raises(ValueError,match='20000'):
            importer.import_letterboxd_csv(db,(header+'alice,Film,2000,8,12,'+'a'*20001+'\n').encode())
        assert db.scalar(select(Review)).text=='Great score'


@pytest.mark.parametrize('value',['nan','inf','-inf'])
def test_nonfinite_ratings_are_rejected(value):
    assert importer._rating_value(value) is None
