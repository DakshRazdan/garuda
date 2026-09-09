"""
Database engine/session setup.
Owned by: Ledger & Reconciliation Lead.

Defaults to a local SQLite file so you can build and test without
setting up Postgres first. Switch DATABASE_URL to a Postgres URL later
(e.g. via an env var) — nothing else in this package needs to change.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base

# Absolute path, anchored to this file's own location — NOT the caller's
# current working directory. A relative "./gi_ledger.db" would silently
# create a different SQLite file depending on whether you ran this from
# backend/ledger/, backend/api/, or the repo root, which is exactly the
# kind of bug that looks like "my data disappeared" during a demo.
_DEFAULT_SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gi_ledger.db")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE_PATH}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """Create all tables. Call once at startup / from seed_data.py."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Yield a session — usable as a context manager or FastAPI dependency."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
