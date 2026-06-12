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
  schemas.py     # Pydantic request/response contract (source of truth for shape)
  geocode.py     # place name -> coordinates (offline gazetteer + optional Nominatim)
  routing.py     # road distance + drive time + per-leg breakdown (estimate or OSRM)
  costs.py       # transparent, itemised cost model (priced off road distance)
  planner.py     # heuristic planner: anchors -> stops -> costs (deterministic fallback)
  llm_planner.py # Claude-backed planner (real, named POIs) + heuristic fallback
  main.py        # FastAPI HTTP surface
```

Two planners, one contract:

- **LLM planner** (`llm_planner.py`) — when `ANTHROPIC_API_KEY` is set, Claude
  proposes a richer itinerary of real, named points of interest with coordinates.
  The model only picks the *stops*; distance and cost are still computed by the
  deterministic math in `costs.py`, so dollars never come from a hallucination.
- **Heuristic planner** (`planner.py`) — the offline, deterministic fallback. No
  API key, no surprise network calls, instant on first launch. Used automatically
  whenever the LLM path is unavailable (no key, network error, or bad output).

`POST /plan` goes through the LLM planner's dispatcher, which falls back to the
heuristic (and notes it in `warnings`) on any failure — the endpoint always
returns a usable, costed plan. Set `ROADTRIP_DISABLE_LLM=1` to force the
heuristic even when a key is present. The `source` field on the response says
which planner produced it (`"llm"` or `"heuristic"`).

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
  `expected_travel_time_seconds`, `stops[]`, a per-hop `legs[]` breakdown
  (from/to names + distance + duration), an itemised `costs` breakdown
  (fuel / lodging / food / activities + per-person, with the assumptions used),
  and `origin_assumed` (see below).

### No starting point?

If the traveler gives only a destination, attraction, or idea (no origin), the
plan is built **around the destination** rather than from the geographic centre
of the map — so a "see Yosemite" request returns *Explore Yosemite* with no
bogus cross-country drive, not a 1,800 km estimate from nowhere. The response
sets `origin_assumed: true`; the app should supply the traveler's real location
and re-plan to add the drive there. (A bare `direction` with no origin still
uses a placeholder location, also flagged.)

## Test

```bash
pip install -r backend/requirements.txt
pytest                # runs from repo root; see pytest.ini
```

## Distance & drive time

`routing.py` turns the ordered stops into road distance, drive time, and a
per-leg breakdown. By default it uses a deterministic estimate (great-circle ×
a road-winding factor at an average speed) — instant and offline. Cost is then
priced off that road distance in one place, so the factor isn't baked into the
cost model.

## Optional: live services

Both live integrations are opt-in and degrade gracefully — failures fall back to
the offline path, so the endpoint always returns a usable plan.

```bash
export ROADTRIP_USE_NOMINATIM=1            # geocode unknown places via OpenStreetMap
export ROADTRIP_USE_OSRM=1                 # real road routing via the public OSRM server
export ROADTRIP_OSRM_URL=http://host:5000  # ...or point at your own OSRM instance
```
