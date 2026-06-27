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
- **`app/database.py`, `app/models.py`, `app/auth.py`, `app/routes_auth.py`**
  — persistence layer. Email + password auth with bcrypt hashing and
  signed JWT session tokens; saved birth profiles (self + up to 4 family
  members); reading history that's automatically populated whenever a
  signed-in user generates any reading. Anonymous requests work exactly
  as before — nothing is persisted for them. Defaults to a local SQLite
  file (`nakshatra.db`) with zero setup; set `DATABASE_URL` to a Postgres
  connection string (e.g. from Supabase) for production and nothing else
  changes, since the code only uses SQLAlchemy's database-agnostic ORM
  layer.
- **`app/panchang.py`** — the five-limb daily Panchang (Tithi, Vaar,
  Nakshatra, Yoga, Karana) plus Rahu Kaal, calculated from real Sun/Moon
  longitudes. Cross-checked two ways during development: the computed
  Lahiri ayanamsha for a reference date matched DrikPanchang's published
  value to within 0.007° (~24 arcseconds — well within normal
  cross-implementation variance), and the computed Tithi/Yoga for a
  reference date matched the transition independently reported by a
  published Panchang for the previous day. The Rahu Kaal weekday-segment
  table is cross-checked against multiple independent sources. Supports
  personalization: pass a saved `profile_id` (requires sign-in) to use
  that profile's birth location instead of entering it each time.
- **`app/muhurta.py`** — auspicious timing search/validation for 6
  activities (marriage, housewarming, business launch, travel,
  education, naming ceremony), with classical rule sets (favorable
  nakshatras, tithis, weekdays, and karana exclusions) compiled from
  multiple cross-checked sources per activity. Scores real Panchang
  data — AI is never involved in scoring. AI's only role here is
  mapping the user's free-text activity description (e.g. "I want to
  open a shop") onto the closest matching rule-set key; a keyword
  heuristic fallback keeps this working even without an Anthropic API
  key configured. Supports both single-date validation and ranked
  date-range search (tested up to a full year, completes in well under
  a second).
- **`app/remedy.py`** — gemstone, mantra, and charity remedies for the
  full Navagraha (9 planets), with fixed classical lookup tables
  cross-checked against multiple independent sources for each planet's
  gemstone/metal/finger/day, beej mantra, and charity item. Which
  planets actually get flagged is determined by reading the already-
  calculated chart (debilitation sign, dusthana house placement) —
  never guessed. Rahu and Ketu are always included per Navagraha
  tradition, but their astronomically-constant "always retrograde"
  status is deliberately not reported as if it were a meaningful,
  chart-specific signal (an early version of this code did report it
  that way, caught and fixed during testing).
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

Auth and profile endpoints (no Anthropic key needed for these):

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/auth/signup` | email, password | returns a bearer token |
| POST | `/auth/login` | email, password | returns a bearer token |
| GET | `/auth/me` | — (Bearer token) | current user info |
| GET | `/profiles` | — (Bearer token) | list saved birth profiles |
| POST | `/profiles` | label, name, birth_date, birth_time, place_name, latitude, longitude, timezone, is_primary | max 5 per user |
| DELETE | `/profiles/{id}` | — (Bearer token) | |
| GET | `/readings/history` | — (Bearer token), optional `?reading_type=` filter | most recent first |
| DELETE | `/readings/history/{id}` | — (Bearer token) | |
| POST | `/readings/panchang` | name, date (optional, defaults today), latitude/longitude/timezone OR profile_id, language | profile_id requires sign-in |
| POST | `/readings/muhurta` | activity (free text), latitude, longitude, timezone, language, plus either `date` (single-date mode) or `search_start_date` + `search_num_days` (search mode) | activity is mapped to one of 6 supported types automatically |
| POST | `/readings/remedy` | name, birth_date, birth_time, latitude, longitude, timezone, language | gemstone/mantra/charity for flagged planets |

Every reading endpoint above (`/readings/vedic`, `/numerology`, `/tarot`,
`/vastu`, `/matching`) also now accepts an optional `Authorization: Bearer`
header. If present and valid, the generated reading is automatically
saved to that user's history. If absent, the endpoint behaves exactly
as it did before — fully anonymous, nothing persisted.

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

109 tests, all passing, covering: sign/nakshatra/pada boundary math,
the Rahu/Ketu 180° relationship, dasha timeline continuity, house range
validity, numerology hand-verified values, master number handling, tarot
deck integrity and draw randomness, Vastu zone boundary coverage across
all 360 degrees, the full Ashtakoot matching engine (all 27 nakshatras
classified correctly, Tara koota symmetry, Bhakoot dosha boundaries,
Mangal Dosha detection), the full auth/persistence layer (signup, login,
wrong-password rejection, profile CRUD with per-user isolation, profile
count limits, and reading history saving — run against an isolated
in-memory database, never touching the real one), the Panchang engine
(tithi/yoga/karana boundary correctness across the full 30/27/60 slot
cycles, Rahu Kaal table accuracy, sunrise-before-sunset and
daylight-fraction sanity checks), the Muhurta engine (rule completeness
for all 6 activities, single-date Rikta-tithi flagging, date-range
search sorting and exclusion logic, and full-year search performance),
and the remedy engine (lookup table completeness for all 9 planets,
correct Rahu/Ketu always-included-but-not-falsely-retrograde handling,
debilitation-first sort order, and chart-to-chart variation).

## What's NOT built yet

- No payments — that's the next phase per the master plan
- No rate limiting on the free tier
- No email verification or password reset flow (would need an email
  provider like Resend/Brevo, already flagged in the master plan's
  founder-responsibility list)
- City lookup on the frontend uses a fixed list of ~15 cities rather
  than live geocoding for the Vedic/numerology/matching forms (the
  Vastu reading does use live geocoding via Nominatim)
