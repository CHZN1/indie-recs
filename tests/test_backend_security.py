from types import SimpleNamespace
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app.models import User,Movie,Rating,Review,ApiCredential,TrainingJob
from app import security, main, jobs
from app.security import issue_credential
from app.config import Settings


@pytest.fixture
def secured(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);factory=sessionmaker(bind=engine,expire_on_commit=False)
    with factory() as db:
        alice=User(user_id='alice');bob=User(user_id='bob');movie=Movie(tmdb_id=12,title='Film',is_indie=True)
        db.add_all([alice,bob,movie]);db.flush();db.add(Rating(user_pk=alice.id,movie_id=movie.id,rating=8))
        row,token=issue_credential(db,alice);admin,admintoken=issue_credential(db,bob,admin=True);db.commit();credential_id=row.id
    def database():
        with factory() as db:yield db
    app.dependency_overrides[get_db]=database
    settings=SimpleNamespace(auth_required=True,background_training=True,max_upload_bytes=1000,model_path='unused')
    monkeypatch.setattr(security,'get_settings',lambda:settings);monkeypatch.setattr(main,'get_settings',lambda:settings)
    try:yield TestClient(app),factory,{'Authorization':'Bearer '+token},{'Authorization':'Bearer '+admintoken},credential_id
    finally:app.dependency_overrides.clear();engine.dispose()


def test_tokens_are_hashed_revocable_and_production_fails_closed(secured):
    client,factory,headers,admin,credential_id=secured
    assert client.get('/stats').status_code==401
    assert client.get('/stats',headers={'Authorization':'Bearer wrong'}).status_code==401
    assert client.get('/stats',headers=headers).status_code==200
    assert client.get('/demo').status_code==404
    with factory() as db:
        row=db.get(ApiCredential,credential_id);assert row.token_hash!=headers['Authorization'].split()[1];row.revoked=True;db.commit()
    assert client.get('/stats',headers=headers).status_code==401
    with pytest.raises(ValueError):Settings(_env_file=None,environment='production')
    assert Settings(_env_file=None,environment='production',auth_required=True,background_training=True).auth_required


def test_review_ownership_validation_and_delete(secured):
    client,factory,h,admin,_=secured
    assert client.put('/users/bob/reviews/12',headers=h,json={'text':'love it'}).status_code==403
    assert client.get('/recommend/bob',headers=h).status_code==403
    assert client.post('/recommend/bob/preferences',headers=h,json={'choices':[]}).status_code==403
    assert client.put('/users/alice/reviews/12',headers=h,json={'text':'   '}).status_code==400
    response=client.put('/users/alice/reviews/12',headers=h,json={'text':'Loved the score'})
    assert response.status_code==200 and not response.json()['used_for_ranking']
    assert client.get('/users/alice/reviews/12',headers=h).json()['text']=='Loved the score'
    assert client.get('/users/alice/reviews/12').status_code==401
    assert client.put('/users/alice/reviews/99',headers=h,json={'text':'Review'}).status_code==404
    assert client.put('/users/bob/reviews/12',headers=admin,json={'text':'Review'}).status_code==409
    assert client.delete('/users/alice/reviews/12',headers=h).status_code==200
    with factory() as db:assert db.scalar(select(Review)) is None


def test_upload_checks_ownership_before_import_and_queues_training(secured,monkeypatch):
    client,factory,h,admin,_=secured;calls=[]
    def importer(db,raw):
        calls.append(raw)
        return SimpleNamespace(user_ids={'alice'},imported_ratings=1,skipped_unrated=0,skipped_unmatched=0,movies_created=0,unique_titles_resolved=1,elapsed_seconds=0,warnings=[])
    monkeypatch.setattr(main,'import_letterboxd_csv',importer)
    monkeypatch.setattr(main,'train_svd',lambda db:pytest.fail('Training must run outside request'))
    bad='Username,Movie Name,Year,Rating10\nbob,Film,2000,8\n'
    assert client.post('/upload',headers=h,files={'file':('ratings.csv',bad)}).status_code==403 and not calls
    good=bad.replace('bob','alice')
    response=client.post('/upload',headers=h,files={'file':('ratings.csv',good)})
    assert response.status_code==200 and not response.json()['model_retrained']
    jid=response.json()['training_job_id'];assert client.get(f'/training/jobs/{jid}',headers=h).json()['status']=='queued'
    assert client.post('/training/jobs',headers=h).status_code==403
    assert client.post('/training/jobs',headers=admin).status_code==200
    assert client.post('/upload',headers=h,files={'file':('large.csv','x'*1001)}).status_code==413


def test_worker_reports_failure_without_exposing_exception(secured,monkeypatch,tmp_path):
    _,factory,_,_,_=secured
    monkeypatch.setattr(jobs,'SessionLocal',factory);monkeypatch.setattr(jobs,'get_settings',lambda:SimpleNamespace(model_path=str(tmp_path/'model.joblib')))
    with factory() as db:jid=jobs.enqueue(db)
    def fail(db):raise RuntimeError('secret credential must not appear')
    monkeypatch.setattr(jobs,'train_svd',fail)
    assert jobs.work_once()
    with factory() as db:
        row=db.get(TrainingJob,jid);assert row.status=='failed' and 'secret' not in row.error
    assert not jobs.work_once()


def test_worker_publishes_success_atomically(secured,monkeypatch,tmp_path):
    _,factory,_,_,_=secured
    from app.training import train_svd,load_model
    path=tmp_path/'model.joblib'
    monkeypatch.setattr(jobs,'SessionLocal',factory);monkeypatch.setattr(jobs,'get_settings',lambda:SimpleNamespace(model_path=str(path)))
    monkeypatch.setattr(jobs,'train_svd',lambda db:train_svd(db,str(path)))
    with factory() as db:jid=jobs.enqueue(db)
    assert jobs.work_once() and load_model(str(path))['user_ids']=={'alice'}
    assert not list(tmp_path.glob('*.tmp'))
    with factory() as db:assert db.get(TrainingJob,jid).status=='succeeded'
