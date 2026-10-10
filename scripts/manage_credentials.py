#!/usr/bin/env python3
"""Provision or revoke backend credentials. Plaintext goes only to a new 0600 file."""
import argparse, os, sys
from pathlib import Path
from sqlalchemy import select
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app.database import init_db,SessionLocal
from app.models import User,ApiCredential
from app.security import issue_credential

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    create=sub.add_parser('issue');create.add_argument('--user',required=True);create.add_argument('--admin',action='store_true');create.add_argument('--output',type=Path,required=True)
    revoke=sub.add_parser('revoke');revoke.add_argument('--credential-id',type=int,required=True);a=p.parse_args();init_db()
    with SessionLocal() as db:
        if a.command=='revoke':
            row=db.get(ApiCredential,a.credential_id)
            if not row:p.error('Credential not found')
            row.revoked=True;db.commit();print('Credential revoked')
        else:
            if not a.user.strip() or len(a.user)>255:p.error('User ID must contain 1–255 characters')
            a.user=a.user.strip()
            if a.output.resolve().is_relative_to(Path(__file__).resolve().parent.parent):p.error('Store credentials outside the public project')
            user=db.scalar(select(User).where(User.user_id==a.user))
            if user is None:user=User(user_id=a.user);db.add(user);db.flush()
            row,token=issue_credential(db,user,admin=a.admin)
            # Exclusive create avoids replacing credentials or following an existing symlink.
            fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            try:
                with os.fdopen(fd,'w') as f:f.write(token+'\n')
                db.commit()
            except BaseException:
                db.rollback();a.output.unlink(missing_ok=True);raise
            print(f'Issued credential {row.id}; plaintext saved to the requested private file')
