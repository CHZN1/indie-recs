#!/usr/bin/env python3
"""Zip the project for GitHub/portfolio upload. Excludes secrets, venv, and local DB/model files."""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "dist"
OUT = OUT_DIR / "indie-recs-github.zip"

SKIP_DIR_NAMES = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", "dist"}
SKIP_FILE_NAMES = {".env", ".DS_Store"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".db", ".db-journal", ".joblib", ".zip", ".log"}


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIR_NAMES:
        return True
    if path.name in SKIP_FILE_NAMES:
        return True
    if path.suffix in SKIP_SUFFIXES:
        return True
    return False


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in ROOT.rglob("*"):
            if not path.is_file() or should_skip(path):
                continue
            archive.write(path, arcname=Path("indie-recs") / path.relative_to(ROOT))
            count += 1
    print(f"Wrote {OUT} ({count} files)")


if __name__ == "__main__":
    main()
