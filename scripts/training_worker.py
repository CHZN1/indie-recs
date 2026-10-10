#!/usr/bin/env python3
"""Drain queued training once, or keep polling with --poll-seconds."""
import argparse, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app.database import init_db
from app.jobs import work_once

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--poll-seconds',type=float,default=0);a=p.parse_args()
    if a.poll_seconds<0:p.error('Polling interval must be nonnegative')
    init_db()
    while True:
        worked=work_once()
        if worked:continue
        if not a.poll_seconds:break
        time.sleep(max(1,a.poll_seconds))
