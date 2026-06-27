"""
Database models.

Three tables:
  - users: auth identity (email + hashed password)
  - birth_profiles: saved birth data, one per person (self or family
    member — supports the Elite tier's "up to 4 family profiles" feature
    from the master plan)
  - saved_readings: a history record each time a reading is generated,
    so the daily horoscope / Panchang / any future feature can look up
    "this user's profile" instead of asking for birth data every time
"""

from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    preferred_language: Mapped[str] = mapped_column(String(8), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    profiles: Mapped[list["BirthProfile"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    readings: Mapped[list["SavedReading"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class BirthProfile(Base):
    """A saved birth profile — the user's own, or a family member's.
    Every reading type (Vedic, numerology, Panchang, matching) reads
    from this instead of asking for birth data on every visit."""

    __tablename__ = "birth_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    label: Mapped[str] = mapped_column(String(100))  # e.g. "Myself", "Mother"
    name: Mapped[str] = mapped_column(String(255))
    birth_date: Mapped[str] = mapped_column(String(10))   # "YYYY-MM-DD"
    birth_time: Mapped[str] = mapped_column(String(5))     # "HH:MM"
    place_name: Mapped[str] = mapped_column(String(255))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(64))

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    owner: Mapped["User"] = relationship(back_populates="profiles")


class SavedReading(Base):
    """A history record of a generated reading, so users can revisit
    past readings instead of regenerating them."""

    __tablename__ = "saved_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("birth_profiles.id"), nullable=True)

    reading_type: Mapped[str] = mapped_column(String(32))  # "vedic" | "numerology" | "tarot" | "vastu" | "matching" | "panchang"
    calculated_data: Mapped[str] = mapped_column(Text)       # JSON-serialized
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    owner: Mapped["User"] = relationship(back_populates="readings")
