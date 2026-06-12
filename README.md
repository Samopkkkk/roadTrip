# roadTrip

Backend for the roadTrip app — turn a one-line idea into a complete, costed
road-trip (or normal-trip) itinerary in seconds.

The user gives only an **initial idea**; we return a doable plan with stops,
coordinates, drive time, and a transparent cost estimate. Three input styles all
work:

| You give…                  | Example                                   |
|----------------------------|-------------------------------------------|
| A **destination**          | `{"destination": "Grand Canyon"}`         |
| A **direction** to wander  | `{"origin": "Denver", "direction": "west"}` |
| A single **attraction**    | `{"anchor_attraction": "Yosemite"}`       |
| Or just free-form **idea** | `{"idea": "road trip from SF to Seattle"}` |

## Architecture

```
backend/app/
  schemas.py   # Pydantic request/response contract (source of truth for shape)
  geocode.py   # place name -> coordinates (offline gazetteer + optional Nominatim)
  costs.py     # haversine distance + transparent, itemised cost model
  planner.py   # heuristic planner: anchors -> stops -> costs (LLM-backed planner TBD)
  main.py      # FastAPI HTTP surface
```

The default planner is **deterministic and offline** — no API keys, no surprise
network calls, instant on first launch. A richer LLM-backed planner is on the
roadmap; this heuristic stays the source of truth for distance/cost math and the
response schema.

## Run it

```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload   # run from the repo root
```

Then:

```bash
curl -s localhost:8000/plan \
  -H 'content-type: application/json' \
  -d '{"idea": "weekend near Lake Tahoe", "days": 2, "party_size": 2}' | jq
```

### Endpoints

- `GET /health` — liveness probe.
- `POST /plan` — body is a `PlanRequest`; returns a `PlanResponse` with
  `title`, `summary`, `tags`, start/end coords, `distance_meters`,
  `expected_travel_time_seconds`, `stops[]`, and an itemised `costs` breakdown
  (fuel / lodging / food / activities + per-person, with the assumptions used).

## Test

```bash
pip install -r backend/requirements.txt
pytest                # runs from repo root; see pytest.ini
```

## Optional: live geocoding

By default geocoding uses a built-in gazetteer of common road-trip anchors. To
fall back to OpenStreetMap Nominatim for unknown places, set:

```bash
export ROADTRIP_USE_NOMINATIM=1
```

Failures degrade gracefully — the planner's own fallbacks take over.
