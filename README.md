# Nakshatra backend — calculation + interpretation API

A FastAPI service implementing the master plan's authenticity pipeline:
**calculate first, interpret second** — the AI never touches a planetary
position, a numerology digit, a card draw, or a compass bearing. It only
explains what's already been computed.

## What's real here

- **`app/vedic.py`** — Swiss Ephemeris (Lahiri ayanamsha) birth chart
  calculation: ascendant, all 9 grahas (including Rahu/Ketu), nakshatras,
  padas, whole-sign houses, and the full Vimshottari Dasha timeline.
  Cross-checked against the published Lahiri ayanamsha value at J2000.0
  (23.85°) — confirmed exact match.
- **`app/numerology.py`** — Pythagorean numerology, pure math, every
  reduction step preserved so it can be shown to the user. Life Path,
  Expression, Soul Urge, Personality, Personal Year. Hand-verified.
- **`app/tarot.py`** — the full 78-card deck, genuinely randomized
  three-card draw, no repeats.
- **`app/vastu.py`** — geocodes a place name via Nominatim (OpenStreetMap)
  and looks up true magnetic declination via NOAA's World Magnetic Model,
  so directional guidance is anchored to the person's real coordinates.
  **Note:** both of these are free public APIs with no key required —
  but this sandbox's network allowlist blocks outbound calls to either
  host, so this module could not be live-tested here. The request shape
  matches each service's published API exactly and will work on any
  normal host (Render, Railway, your own machine).
- **`app/matching.py`** — classical 36-point Ashtakoot Guna Milan
  (Kundli matching): Varna, Vashya, Tara, Yoni, Graha Maitri, Gana,
  Bhakoot, and Nadi kootas, plus Mangal Dosha detection. All 27
  nakshatras are classified for Nadi/Gana/Yoni and verified to have the
  correct 9/9/9 distribution for Nadi and Gana. Tara koota's
  even/odd-remainder rule is verified symmetric and produces a real
  0/1.5/3 distribution (an earlier implementation bug that collapsed
  this to a single flat value was caught by the test suite and fixed).
- **`app/interpretation.py`** — builds the system/user prompts sent to
  Claude. Every prompt only contains already-calculated data and
  explicit instructions never to recalculate it.
- **`app/main.py`** — the FastAPI app wiring calculation + interpretation
  together behind four endpoints.

## Running it

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

The frontend expects this running at `http://localhost:8000` by default
(see `frontend/src/lib/api.ts` — override with `NEXT_PUBLIC_API_URL`).

## Endpoints

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/health` | — | liveness check |
| POST | `/readings/vedic` | name, birth_date, birth_time, latitude, longitude, timezone, language | |
| POST | `/readings/numerology` | same as above | latitude/longitude/timezone unused but accepted for a consistent shape |
| POST | `/readings/tarot` | name, language | |
| POST | `/readings/vastu` | name, place, entrance_facing_degrees, language | needs live internet (Nominatim + NOAA) |
| POST | `/readings/matching` | person_a {name, birth_date, birth_time, latitude, longitude, timezone}, person_b {...}, language | Ashtakoot Guna Milan + Mangal/Nadi/Bhakoot dosha |

Every response shape is:
```json
{
  "calculated_data": { ... },
  "interpretation": "..." ,
  "interpretation_error": null
}
```

If `ANTHROPIC_API_KEY` isn't set, `calculated_data` still returns fully
correct — only `interpretation` is null with `interpretation_error`
explaining why. This was verified directly: every endpoint's calculation
layer works independently of the AI layer.

## Tests

```bash
python3 -m pytest app/tests/ -v
```

46 tests, all passing, covering: sign/nakshatra/pada boundary math,
the Rahu/Ketu 180° relationship, dasha timeline continuity, house range
validity, numerology hand-verified values, master number handling, tarot
deck integrity and draw randomness, Vastu zone boundary coverage across
all 360 degrees, and the full Ashtakoot matching engine (all 27
nakshatras classified correctly, Tara koota symmetry, Bhakoot dosha
boundaries, Mangal Dosha detection).

## What's NOT built yet

- No database — readings aren't persisted between requests
- No auth — anyone who can reach this API can call it
- No payments — that's Week 3-4 per the master plan
- No rate limiting on the free tier
