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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.vedic import compute_birth_chart
from app.numerology import compute_numerology_profile
from app.tarot import draw_three_card_spread
from app.vastu import compute_vastu_profile
from app import interpretation

app = FastAPI(title="Nakshatra Calculation API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class ReadingResponse(BaseModel):
    calculated_data: dict
    interpretation: str | None
    interpretation_error: str | None = None


# ---------- endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/readings/vedic", response_model=ReadingResponse)
async def vedic_reading(input: BirthInput):
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

    system, user = interpretation.build_vedic_prompt(input.name, chart, input.language)
    try:
        text = await call_claude(system, user)
        return ReadingResponse(calculated_data=calculated_data, interpretation=text)
    except HTTPException as e:
        return ReadingResponse(calculated_data=calculated_data, interpretation=None, interpretation_error=e.detail)


@app.post("/readings/numerology", response_model=ReadingResponse)
async def numerology_reading(input: BirthInput):
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

    system, user = interpretation.build_numerology_prompt(input.name, profile, input.language)
    try:
        text = await call_claude(system, user)
        return ReadingResponse(calculated_data=calculated_data, interpretation=text)
    except HTTPException as e:
        return ReadingResponse(calculated_data=calculated_data, interpretation=None, interpretation_error=e.detail)


class TarotInput(BaseModel):
    name: str
    language: str = "en"


@app.post("/readings/tarot", response_model=ReadingResponse)
async def tarot_reading(input: TarotInput):
    cards = draw_three_card_spread()

    calculated_data = {
        "cards": [
            {"position": c.position, "name": c.name, "reversed": c.reversed, "keywords": c.keywords}
            for c in cards
        ]
    }

    system, user = interpretation.build_tarot_prompt(input.name, cards, input.language)
    try:
        text = await call_claude(system, user)
        return ReadingResponse(calculated_data=calculated_data, interpretation=text)
    except HTTPException as e:
        return ReadingResponse(calculated_data=calculated_data, interpretation=None, interpretation_error=e.detail)


@app.post("/readings/vastu", response_model=ReadingResponse)
async def vastu_reading(input: VastuInput):
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

    system, user = interpretation.build_vastu_prompt(input.name, vastu_profile, input.language)
    try:
        text = await call_claude(system, user)
        return ReadingResponse(calculated_data=calculated_data, interpretation=text)
    except HTTPException as e:
        return ReadingResponse(calculated_data=calculated_data, interpretation=None, interpretation_error=e.detail)
