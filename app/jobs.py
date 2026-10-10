"""Persistent training queue; run one worker per shared model directory."""
from datetime import datetime
import fcntl
from pathlib import Path
from sqlalchemy import select, update
from app.config import get_settings
from app.database import SessionLocal
from app.models import TrainingJob
from app.training import train_svd


def enqueue(db,owner_pk=None):
    job=TrainingJob(owner_pk=owner_pk,status='queued');db.add(job);db.commit();db.refresh(job);return job.id


def work_once():
    path=Path(get_settings().model_path);path.parent.mkdir(parents=True,exist_ok=True)
    with (path.parent/'training.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return False
        with SessionLocal() as db:
            job=db.scalar(select(TrainingJob).where(TrainingJob.status=='queued').order_by(TrainingJob.id).limit(1))
            if job is None:return False
            claimed=db.execute(update(TrainingJob).where(TrainingJob.id==job.id,TrainingJob.status=='queued').values(status='running')).rowcount;db.commit()
            if not claimed:return False
            try:
                trained=train_svd(db)
                job.status='succeeded' if trained else 'failed'
                job.error=None if trained else 'No ratings available'
            except Exception:
                db.rollback();job=db.get(TrainingJob,job.id);job.status='failed';job.error='Training failed; inspect worker environment'
            job.finished_at=datetime.utcnow();db.commit()
        return True
