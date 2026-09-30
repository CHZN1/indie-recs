#!/usr/bin/env python3
"""Rebuild the SVD model from the latest ratings table."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db
from app.training import train_svd


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        ok = train_svd(db)
        print("Model retrained." if ok else "No ratings found; model not written.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
