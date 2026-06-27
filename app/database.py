"""
Database engine and session management.

Defaults to a local SQLite file so the whole backend runs with zero
external setup. In production, set DATABASE_URL to a Postgres connection
string (e.g. from Supabase) and nothing else in the codebase needs to
change — SQLAlchemy abstracts the dialect difference for everything
we do here (no raw SQL, no SQLite-specific features used).
"""

from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./nakshatra.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Safe to call repeatedly — no-op if tables
    already exist. Called once at app startup."""
    import app.models  # noqa: F401 — ensures models are registered on Base
    Base.metadata.create_all(bind=engine)
