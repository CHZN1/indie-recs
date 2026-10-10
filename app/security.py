"""Provisioned bearer credentials for backend integrations; no public sign-up."""
from dataclasses import dataclass
import hashlib
import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models import ApiCredential, User

bearer = HTTPBearer(auto_error=False)

@dataclass(frozen=True)
class Principal:
    user_pk: int
    user_id: str
    is_admin: bool


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_credential(db, user, *, admin=False):
    token=secrets.token_urlsafe(32)
    row=ApiCredential(user_pk=user.id,token_hash=token_hash(token),is_admin=admin)
    db.add(row);db.flush()
    return row,token


def principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),db: Session = Depends(get_db)):
    if not get_settings().auth_required:return None
    if credentials is None or credentials.scheme.lower()!='bearer':
        raise HTTPException(401,'Bearer credential required',headers={'WWW-Authenticate':'Bearer'})
    row=db.scalar(select(ApiCredential).where(ApiCredential.token_hash==token_hash(credentials.credentials),ApiCredential.revoked.is_(False)))
    user=db.get(User,row.user_pk) if row else None
    if not row or not user:raise HTTPException(401,'Invalid or revoked credential',headers={'WWW-Authenticate':'Bearer'})
    return Principal(user.id,user.user_id,row.is_admin)


def own_profile(actor,user_id):
    if actor is not None and not actor.is_admin and actor.user_id!=user_id:
        raise HTTPException(403,'This credential cannot access that profile')


def require_admin(actor):
    if actor is not None and not actor.is_admin:raise HTTPException(403,'Administrator credential required')
