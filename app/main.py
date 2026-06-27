"""
Nakshatra calculation + interpretation API.

Every endpoint follows the same two-stage pipeline from the master plan:
  1. Calculate (vedic.py / numerology.py / tarot.py / vastu.py) — real
     data, never touched by AI.
  2. Interpret (interpretation.py + Anthropic API) — AI explains the
     already-calculated data, never recalculates it.

Run with: uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations
import os
from datetime import date

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.vedic import compute_birth_chart
from app.numerology import compute_numerology_profile
from app.tarot import draw_three_card_spread
from app.vastu import compute_vastu_profile
from app.matching import compute_kundli_match
from app.panchang import compute_panchang
from app.muhurta import validate_single_date, search_date_range, ACTIVITY_RULES
from app.remedy import compute_remedy_profile
from app import interpretation
from app.database import get_db, init_db
from app.models import User, SavedReading, BirthProfile
from app.auth import get_current_user_optional
from app.routes_auth import router as auth_router
import json
from sqlalchemy.orm import Session

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Nakshatra Calculation API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


def _save_reading_if_signed_in(
    db: Session,
    user: User | None,
    reading_type: str,
    calculated_data: dict,
    interpretation_text: str | None,
    language: str,
):
    """History is opt-in by virtue of being signed in — anonymous
    requests work exactly as before and nothing is persisted for them."""
    if user is None:
        return
    record = SavedReading(
        owner_id=user.id,
        reading_type=reading_type,
        calculated_data=json.dumps(calculated_data),
        interpretation=interpretation_text,
        language=language,
    )
    db.add(record)
    db.commit()


async def call_claude(system: str, user: str) -> str:
    """Thin wrapper around the Anthropic API. Requires ANTHROPIC_API_KEY
    to be set in the environment — this is the one credential the
    founder provides per the master plan's responsibility split."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not set. Interpretation is unavailable until it is configured.",
        )
    try:
        import anthropic
    except ImportError:
        raise HTTPException(status_code=500, detail="anthropic package not installed on the server.")

    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


async def map_activity_text(free_text: str) -> str:
    """Maps free text to one of the known ACTIVITY_RULES keys using
    Claude. Falls back to a simple keyword heuristic if the API key
    isn't configured, so this endpoint stays usable without it."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _heuristic_activity_match(free_text)

    system, user_prompt = interpretation.build_activity_mapping_prompt(free_text)
    try:
        result = await call_claude(system, user_prompt)
        key = result.strip().lower()
        if key in ACTIVITY_RULES:
            return key
        return _heuristic_activity_match(free_text)
    except HTTPException:
        return _heuristic_activity_match(free_text)


def _heuristic_activity_match(free_text: str) -> str:
    """A simple keyword fallback so activity matching still works when
    the Anthropic API key isn't configured (e.g. local dev without a
    key set). Uses short stems so common inflections (married, marrying,
    moving, traveling) still match."""
    text = free_text.lower()
    keyword_map = {
        "marriage": ["marry", "marri", "wedding", "vivah", "wed "],
        "housewarming": ["hous", "home", "griha", "move in", "moving", "new home", "shift"],
        "business": ["busines", "shop", "office", "compan", "launch", "startup", "venture"],
        "travel": ["travel", "journey", "trip", "flight", "yatra", "voyage"],
        "education": ["school", "educat", "study", "studies", "course", "college", "vidya"],
        "naming": ["naming", "namkaran", "newborn name", "name the baby", "name my"],
    }
    for key, words in keyword_map.items():
        if any(w in text for w in words):
            return key
    return "none"


# ---------- request/response models ----------

class BirthInput(BaseModel):
    name: str
    birth_date: str          # "YYYY-MM-DD"
    birth_time: str          # "HH:MM"
    latitude: float
    longitude: float
    timezone: str             # IANA name, e.g. "Asia/Kolkata"
    language: str = "en"


class VastuInput(BaseModel):
    name: str
    place: str
    entrance_facing_degrees: float | None = None
    language: str = "en"


class PersonInput(BaseModel):
    name: str
    birth_date: str
    birth_time: str
    latitude: float
    longitude: float
    timezone: str


class MatchingInput(BaseModel):
    person_a: PersonInput
    person_b: PersonInput
    language: str = "en"


class PanchangInput(BaseModel):
    # either pass an explicit location, or a saved profile_id to use
    # that profile's saved birth location (requires being signed in)
    name: str | None = None
    date: str | None = None          # defaults to today if omitted
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None
    profile_id: int | None = None
    language: str = "en"


class MuhurtaInput(BaseModel):
    activity: str              # free text, e.g. "starting a new business"
    latitude: float
    longitude: float
    timezone: str
    language: str = "en"
    date: str | None = None                  # single-date validation mode
    search_start_date: str | None = None      # date-range search mode
    search_num_days: int | None = None


class RemedyInput(BaseModel):
    name: str
    birth_date: str
    birth_time: str
    latitude: float
    longitude: float
    timezone: str
    language: str = "en"


class ReadingResponse(BaseModel):
    calculated_data: dict
    interpretation: str | None
    interpretation_error: str | None = None


# ---------- endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/readings/vedic", response_model=ReadingResponse)
async def vedic_reading(
    input: BirthInput,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    chart = compute_birth_chart(
        input.birth_date, input.birth_time, input.latitude, input.longitude, input.timezone
    )

    calculated_data = {
        "ascendant_sign": chart.ascendant_sign,
        "ascendant_degree": chart.ascendant_degree,
        "moon_nakshatra": chart.moon_nakshatra,
        "moon_nakshatra_pada": chart.moon_nakshatra_pada,
        "current_dasha": chart.current_dasha,
        "planets": [
            {
                "name": p.name, "sign": p.sign, "sign_degree": p.sign_degree,
                "house": p.house, "nakshatra": p.nakshatra,
                "nakshatra_pada": p.nakshatra_pada, "retrograde": p.retrograde,
            }
            for p in chart.planets
        ],
        "dasha_timeline": [
            {"planet": d.planet, "start": d.start.isoformat(), "end": d.end.isoformat()}
            for d in chart.dasha_timeline[:5]
        ],
    }

    system, user_prompt = interpretation.build_vedic_prompt(input.name, chart, input.language)
    try:
        text = await call_claude(system, user_prompt)
        _save_reading_if_signed_in(db, user, "vedic", calculated_data, text, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=text)
    except HTTPException as e:
        _save_reading_if_signed_in(db, user, "vedic", calculated_data, None, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=None, interpretation_error=e.detail)


@app.post("/readings/numerology", response_model=ReadingResponse)
async def numerology_reading(
    input: BirthInput,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    y, m, d = (int(x) for x in input.birth_date.split("-"))
    birth_date = date(y, m, d)
    target_year = date.today().year

    profile = compute_numerology_profile(input.name, birth_date, target_year)

    calculated_data = {
        num.name: {"value": num.value, "is_master": num.is_master,
                    "steps": [{"input": s.input_value, "output": s.output_value} for s in num.steps]}
        for num in [profile.life_path, profile.expression, profile.soul_urge,
                    profile.personality, profile.personal_year]
    }

    system, user_prompt = interpretation.build_numerology_prompt(input.name, profile, input.language)
    try:
        text = await call_claude(system, user_prompt)
        _save_reading_if_signed_in(db, user, "numerology", calculated_data, text, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=text)
    except HTTPException as e:
        _save_reading_if_signed_in(db, user, "numerology", calculated_data, None, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=None, interpretation_error=e.detail)


class TarotInput(BaseModel):
    name: str
    language: str = "en"


@app.post("/readings/tarot", response_model=ReadingResponse)
async def tarot_reading(
    input: TarotInput,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    cards = draw_three_card_spread()

    calculated_data = {
        "cards": [
            {"position": c.position, "name": c.name, "reversed": c.reversed, "keywords": c.keywords}
            for c in cards
        ]
    }

    system, user_prompt = interpretation.build_tarot_prompt(input.name, cards, input.language)
    try:
        text = await call_claude(system, user_prompt)
        _save_reading_if_signed_in(db, user, "tarot", calculated_data, text, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=text)
    except HTTPException as e:
        _save_reading_if_signed_in(db, user, "tarot", calculated_data, None, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=None, interpretation_error=e.detail)


@app.post("/readings/vastu", response_model=ReadingResponse)
async def vastu_reading(
    input: VastuInput,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        vastu_profile = await compute_vastu_profile(input.place, input.entrance_facing_degrees)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Could not reach geocoding or magnetic declination services. Try again shortly.",
        )

    calculated_data = {
        "place": vastu_profile.place.place_name,
        "latitude": vastu_profile.place.latitude,
        "longitude": vastu_profile.place.longitude,
        "magnetic_declination": vastu_profile.magnetic_declination,
        "zones": vastu_profile.zones,
    }

    system, user_prompt = interpretation.build_vastu_prompt(input.name, vastu_profile, input.language)
    try:
        text = await call_claude(system, user_prompt)
        _save_reading_if_signed_in(db, user, "vastu", calculated_data, text, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=text)
    except HTTPException as e:
        _save_reading_if_signed_in(db, user, "vastu", calculated_data, None, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=None, interpretation_error=e.detail)


@app.post("/readings/matching", response_model=ReadingResponse)
async def matching_reading(
    input: MatchingInput,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    a, b = input.person_a, input.person_b
    match, chart_a, chart_b = compute_kundli_match(
        a.name, a.birth_date, a.birth_time, a.latitude, a.longitude, a.timezone,
        b.name, b.birth_date, b.birth_time, b.latitude, b.longitude, b.timezone,
    )

    calculated_data = {
        "person_a_name": match.person_a_name,
        "person_b_name": match.person_b_name,
        "total_score": match.total_score,
        "max_score": match.max_score,
        "verdict": match.verdict,
        "kootas": [
            {"name": k.name, "max_points": k.max_points, "score": k.score, "note": k.note}
            for k in match.kootas
        ],
        "nadi_dosha": match.nadi_dosha,
        "bhakoot_dosha": match.bhakoot_dosha,
        "mangal_dosha": {
            "person_a_dosha": match.mangal_dosha.person_a_dosha,
            "person_b_dosha": match.mangal_dosha.person_b_dosha,
            "person_a_mars_house": match.mangal_dosha.person_a_mars_house,
            "person_b_mars_house": match.mangal_dosha.person_b_mars_house,
            "cancelled": match.mangal_dosha.cancelled,
            "cancellation_reason": match.mangal_dosha.cancellation_reason,
        },
    }

    system, user_prompt = interpretation.build_matching_prompt(match, input.language)
    try:
        text = await call_claude(system, user_prompt)
        _save_reading_if_signed_in(db, user, "matching", calculated_data, text, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=text)
    except HTTPException as e:
        _save_reading_if_signed_in(db, user, "matching", calculated_data, None, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=None, interpretation_error=e.detail)


@app.post("/readings/panchang", response_model=ReadingResponse)
async def panchang_reading(
    input: PanchangInput,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    name = input.name or "you"
    target_date = input.date or date.today().isoformat()

    latitude, longitude, timezone = input.latitude, input.longitude, input.timezone

    if input.profile_id is not None:
        if user is None:
            raise HTTPException(status_code=401, detail="Sign in to use a saved profile.")
        profile = db.get(BirthProfile, input.profile_id)
        if not profile or profile.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Profile not found.")
        latitude, longitude, timezone = profile.latitude, profile.longitude, profile.timezone
        name = input.name or profile.name

    if latitude is None or longitude is None or timezone is None:
        raise HTTPException(
            status_code=400,
            detail="Provide a location (latitude, longitude, timezone) or a saved profile_id.",
        )

    panchang = compute_panchang(target_date, latitude, longitude, timezone)

    calculated_data = {
        "date": panchang.date,
        "weekday": panchang.weekday,
        "weekday_lord": panchang.weekday_lord,
        "paksha": panchang.paksha,
        "tithi_name": panchang.tithi_name,
        "tithi_number": panchang.tithi_number,
        "nakshatra": panchang.nakshatra,
        "nakshatra_pada": panchang.nakshatra_pada,
        "yoga_name": panchang.yoga_name,
        "yoga_is_favorable": panchang.yoga_is_favorable,
        "karana_name": panchang.karana_name,
        "sunrise": panchang.sunrise.isoformat(),
        "sunset": panchang.sunset.isoformat(),
        "rahu_kaal_start": panchang.rahu_kaal_start.isoformat(),
        "rahu_kaal_end": panchang.rahu_kaal_end.isoformat(),
    }

    system, user_prompt = interpretation.build_panchang_prompt(name, panchang, input.language)
    try:
        text = await call_claude(system, user_prompt)
        _save_reading_if_signed_in(db, user, "panchang", calculated_data, text, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=text)
    except HTTPException as e:
        _save_reading_if_signed_in(db, user, "panchang", calculated_data, None, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=None, interpretation_error=e.detail)


def _score_to_dict(score) -> dict:
    return {
        "date": score.date,
        "weekday": score.weekday,
        "score": score.score,
        "max_score": score.max_score,
        "verdict": score.verdict,
        "nakshatra_favorable": score.nakshatra_favorable,
        "tithi_favorable": score.tithi_favorable,
        "weekday_favorable": score.weekday_favorable,
        "karana_favorable": score.karana_favorable,
        "has_rikta_tithi": score.has_rikta_tithi,
        "tithi_name": score.panchang.tithi_name,
        "nakshatra": score.panchang.nakshatra,
        "karana_name": score.panchang.karana_name,
        "yoga_name": score.panchang.yoga_name,
        "rahu_kaal_start": score.panchang.rahu_kaal_start.isoformat(),
        "rahu_kaal_end": score.panchang.rahu_kaal_end.isoformat(),
    }


@app.post("/readings/muhurta", response_model=ReadingResponse)
async def muhurta_reading(
    input: MuhurtaInput,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    activity_key = await map_activity_text(input.activity)
    if activity_key == "none" or activity_key not in ACTIVITY_RULES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Couldn't match '{input.activity}' to a supported activity type. "
                f"Supported: {', '.join(r.label for r in ACTIVITY_RULES.values())}."
            ),
        )
    activity_label = ACTIVITY_RULES[activity_key].label

    is_search = input.search_start_date is not None

    if is_search:
        num_days = input.search_num_days or 90
        scores = search_date_range(
            activity_key, input.search_start_date, num_days,
            input.latitude, input.longitude, input.timezone, limit=10,
        )
        calculated_data = {
            "mode": "search",
            "matched_activity": activity_key,
            "matched_activity_label": activity_label,
            "candidates": [_score_to_dict(s) for s in scores],
        }
        if not scores:
            system, user_prompt = (
                "Be brief and direct.",
                f"No favorable dates for {activity_label} were found in the searched "
                f"range. State this plainly and suggest widening the search window.",
            )
        else:
            system, user_prompt = interpretation.build_muhurta_search_prompt(activity_label, scores, input.language)
    else:
        target_date = input.date or date.today().isoformat()
        score = validate_single_date(
            activity_key, target_date, input.latitude, input.longitude, input.timezone,
        )
        calculated_data = {
            "mode": "single",
            "matched_activity": activity_key,
            "matched_activity_label": activity_label,
            **_score_to_dict(score),
        }
        system, user_prompt = interpretation.build_muhurta_single_prompt(activity_label, score, input.language)

    try:
        text = await call_claude(system, user_prompt)
        _save_reading_if_signed_in(db, user, "muhurta", calculated_data, text, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=text)
    except HTTPException as e:
        _save_reading_if_signed_in(db, user, "muhurta", calculated_data, None, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=None, interpretation_error=e.detail)


@app.post("/readings/remedy", response_model=ReadingResponse)
async def remedy_reading(
    input: RemedyInput,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    chart = compute_birth_chart(
        input.birth_date, input.birth_time, input.latitude, input.longitude, input.timezone
    )
    profile = compute_remedy_profile(input.name, chart)

    calculated_data = {
        "strongest_planet": profile.strongest_planet,
        "concerns": [
            {
                "planet": c.planet,
                "reason": c.reason,
                "house": c.house,
                "sign": c.sign,
                "is_debilitated": c.is_debilitated,
                "is_in_dusthana": c.is_in_dusthana,
                "is_retrograde": c.is_retrograde,
                "gemstone": {
                    "english": c.gemstone.gemstone_english,
                    "sanskrit": c.gemstone.gemstone_sanskrit,
                    "metal": c.gemstone.metal,
                    "finger": c.gemstone.finger,
                    "weekday": c.gemstone.weekday,
                    "substitute": c.gemstone.substitute,
                },
                "mantra": {
                    "beej_mantra": c.mantra.beej_mantra,
                    "deity": c.mantra.deity,
                    "recitation_count": c.mantra.recitation_count,
                },
                "charity": {
                    "item": c.charity.item,
                    "weekday": c.charity.weekday,
                },
            }
            for c in profile.concerns
        ],
    }

    system, user_prompt = interpretation.build_remedy_prompt(profile, input.language)
    try:
        text = await call_claude(system, user_prompt)
        _save_reading_if_signed_in(db, user, "remedy", calculated_data, text, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=text)
    except HTTPException as e:
        _save_reading_if_signed_in(db, user, "remedy", calculated_data, None, input.language)
        return ReadingResponse(calculated_data=calculated_data, interpretation=None, interpretation_error=e.detail)
