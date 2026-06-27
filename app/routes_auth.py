"""
Auth and birth-profile management routes.

Kept in their own router (rather than crammed into main.py) since this
is a genuinely separate concern from the calculation engines — this
module only ever touches the database, never Swiss Ephemeris or Claude.
"""

from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import User, BirthProfile, SavedReading
from app.auth import hash_password, verify_password, create_access_token, get_current_user
import json

router = APIRouter()


# ---------- schemas ----------

class SignupInput(BaseModel):
    email: EmailStr
    password: str
    preferred_language: str = "en"


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    preferred_language: str


class BirthProfileInput(BaseModel):
    label: str
    name: str
    birth_date: str
    birth_time: str
    place_name: str
    latitude: float
    longitude: float
    timezone: str
    is_primary: bool = False


class BirthProfileResponse(BaseModel):
    id: int
    label: str
    name: str
    birth_date: str
    birth_time: str
    place_name: str
    latitude: float
    longitude: float
    timezone: str
    is_primary: bool


def _profile_to_response(p: BirthProfile) -> BirthProfileResponse:
    return BirthProfileResponse(
        id=p.id, label=p.label, name=p.name, birth_date=p.birth_date,
        birth_time=p.birth_time, place_name=p.place_name, latitude=p.latitude,
        longitude=p.longitude, timezone=p.timezone, is_primary=p.is_primary,
    )


# ---------- auth endpoints ----------

@router.post("/auth/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(input: SignupInput, db: Session = Depends(get_db)):
    user = User(
        email=input.email.lower(),
        hashed_password=hash_password(input.password),
        preferred_language=input.preferred_language,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    db.refresh(user)
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.post("/auth/login", response_model=TokenResponse)
def login(input: LoginInput, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == input.email.lower()).first()
    if not user or not verify_password(input.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/auth/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return UserResponse(id=user.id, email=user.email, preferred_language=user.preferred_language)


# ---------- birth profile endpoints (require sign-in) ----------

MAX_PROFILES_PER_USER = 5  # self + up to 4 family members, per the Elite tier plan


@router.get("/profiles", response_model=list[BirthProfileResponse])
def list_profiles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profiles = db.query(BirthProfile).filter(BirthProfile.owner_id == user.id).all()
    return [_profile_to_response(p) for p in profiles]


@router.post("/profiles", response_model=BirthProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    input: BirthProfileInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing_count = db.query(BirthProfile).filter(BirthProfile.owner_id == user.id).count()
    if existing_count >= MAX_PROFILES_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"You can save up to {MAX_PROFILES_PER_USER} profiles. Delete one before adding another.",
        )

    if input.is_primary:
        db.query(BirthProfile).filter(BirthProfile.owner_id == user.id).update({"is_primary": False})

    profile = BirthProfile(owner_id=user.id, **input.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _profile_to_response(profile)


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.get(BirthProfile, profile_id)
    if not profile or profile.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Profile not found.")
    db.delete(profile)
    db.commit()


# ---------- reading history (requires sign-in) ----------

class SavedReadingResponse(BaseModel):
    id: int
    reading_type: str
    calculated_data: dict
    interpretation: str | None
    language: str
    created_at: str


@router.get("/readings/history", response_model=list[SavedReadingResponse])
def list_reading_history(
    reading_type: str | None = None,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(SavedReading).filter(SavedReading.owner_id == user.id)
    if reading_type:
        query = query.filter(SavedReading.reading_type == reading_type)
    records = query.order_by(SavedReading.created_at.desc()).limit(min(limit, 100)).all()
    return [
        SavedReadingResponse(
            id=r.id,
            reading_type=r.reading_type,
            calculated_data=json.loads(r.calculated_data),
            interpretation=r.interpretation,
            language=r.language,
            created_at=r.created_at.isoformat(),
        )
        for r in records
    ]


@router.delete("/readings/history/{reading_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reading(
    reading_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.get(SavedReading, reading_id)
    if not record or record.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Reading not found.")
    db.delete(record)
    db.commit()
