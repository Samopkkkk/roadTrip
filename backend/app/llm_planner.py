"""LLM-backed planner — turns an idea into real, named POIs via Claude.

Architecture (matches the contract in ``planner.py``):

- Claude proposes the *itinerary* — named, real-world stops with coordinates,
  timing, and notes. This is the "richer stop list" the heuristic planner can't
  produce.
- We stay the source of truth for **distance and cost math**: the LLM's stops
  are fed through the same deterministic ``haversine``/``estimate_costs`` used by
  the heuristic planner, so dollars never come from a hallucination.
- Anything that fails — no API key, network error, refusal, malformed output —
  falls back to the heuristic planner, with a warning, so the endpoint always
  returns a usable plan.

The Claude call is isolated in ``_generate_itinerary`` and the response assembly
in ``_assemble_response`` so both can be tested without network access.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from .costs import estimate_costs
from .geocode import geocode
from .planner import _extract_endpoints_from_idea, plan_trip as heuristic_plan_trip
from .routing import plan_route
from .schemas import (
    Coordinate,
    PlanRequest,
    PlanResponse,
    PlanStop,
    StopKind,
)

_MODEL = "claude-opus-4-8"
_MAX_TOKENS = 8000
_TIMEOUT_SECONDS = 60.0


# --- Schema Claude fills (kept lenient; we validate/clamp in assembly) -------
class _LLMStop(BaseModel):
    day: int = Field(description="1-based day of the trip this stop belongs to.")
    name: str = Field(description="Specific, real place name (not 'Day 2 stop').")
    kind: str = Field(
        description="One of: attraction, scenic, activity, food, lodging, fuel, rest."
    )
    lat: float
    lng: float
    arrival_local: str | None = Field(
        default=None, description="Local arrival time as HH:MM, e.g. '14:30'."
    )
    duration_minutes: int = Field(default=60)
    notes: str | None = Field(default=None, description="One short, useful sentence.")


class _LLMItinerary(BaseModel):
    title: str
    summary: str
    tags: list[str]
    start_name: str
    start_lat: float
    start_lng: float
    end_name: str
    end_lat: float
    end_lng: float
    stops: list[_LLMStop]


_SYSTEM_PROMPT = """You are an expert road-trip planner. Given a traveler's initial idea, \
produce a complete, *doable* itinerary of real, named places.

Rules:
- Use specific, real points of interest with accurate latitude/longitude — actual \
parks, overlooks, landmarks, towns, and eateries. Never use placeholders like \
"Day 2 highlight".
- Respect the requested number of days and pace: relaxed = 1-2 stops/day, balanced \
= 2-3, packed = 3-4. Keep daily driving realistic (a few hours, not coast-to-coast).
- For multi-day trips, add one stop with kind "lodging" at the end of each day \
except the final day, placed in a real town where the traveler would sleep.
- Honor whatever the traveler gave you: an explicit destination, a single must-see \
attraction to build around, a compass direction to wander, or a free-form idea \
(parse origin/destination out of it yourself).
- Order stops in travel sequence. Give each a local arrival time (HH:MM), a sensible \
duration, and one short, genuinely useful note.
- Set start_name/end_name and their coordinates to the trip's true endpoints.
- Do NOT estimate costs or distances — those are computed downstream. Focus on great \
stops."""


def _llm_enabled() -> bool:
    """LLM path is on when a key is present and not explicitly disabled."""

    if os.getenv("ROADTRIP_DISABLE_LLM", "").strip().lower() in ("1", "true", "yes"):
        return False
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


def _build_user_prompt(req: PlanRequest) -> str:
    lines = ["Plan a trip from these inputs:"]
    if req.idea.strip():
        lines.append(f"- Idea: {req.idea.strip()}")
    if req.origin:
        lines.append(f"- Origin: {req.origin}")
    if req.destination:
        lines.append(f"- Destination: {req.destination}")
    if req.anchor_attraction:
        lines.append(f"- Must-see attraction: {req.anchor_attraction}")
    if req.direction:
        lines.append(f"- Direction to wander: {req.direction}")
    lines.append(f"- Days: {req.days}")
    lines.append(f"- Party size: {req.party_size}")
    lines.append(f"- Pace: {req.pace.value}")
    return "\n".join(lines)


async def _generate_itinerary(req: PlanRequest) -> _LLMItinerary | None:
    """Ask Claude for an itinerary. Returns None on refusal/empty output.

    Raises on transport/SDK errors so the caller can fall back.
    """

    from anthropic import AsyncAnthropic  # lazy: heuristic-only installs don't need it

    async with AsyncAnthropic() as client:
        response = await client.with_options(timeout=_TIMEOUT_SECONDS).messages.parse(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            thinking={"type": "adaptive"},
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(req)}],
            output_format=_LLMItinerary,
        )

    if response.stop_reason == "refusal":
        return None
    itinerary = response.parsed_output
    if itinerary is None or not itinerary.stops:
        return None
    return itinerary


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _coerce_kind(raw: str) -> StopKind:
    try:
        return StopKind(raw.strip().lower())
    except (ValueError, AttributeError):
        return StopKind.attraction


async def _resolve_endpoint(name: str, lat: float, lng: float) -> tuple[str, Coordinate]:
    """Prefer our gazetteer's coordinates for known places (deterministic);
    otherwise trust the model's coordinates."""

    geo = await geocode(name)
    if geo is not None:
        return geo.name, geo.coord
    return name, Coordinate(lat=_clamp(lat, -90.0, 90.0), lng=_clamp(lng, -180.0, 180.0))


async def _assemble_response(req: PlanRequest, itin: _LLMItinerary) -> PlanResponse:
    """Turn a model itinerary into a PlanResponse with our own distance/cost math."""

    start_name, start_coord = await _resolve_endpoint(
        itin.start_name, itin.start_lat, itin.start_lng
    )
    end_name, end_coord = await _resolve_endpoint(
        itin.end_name, itin.end_lat, itin.end_lng
    )

    stops: list[PlanStop] = []
    order_by_day: dict[int, int] = {}
    for raw in itin.stops:
        day = max(1, min(req.days, raw.day))
        order = order_by_day.get(day, 0)
        order_by_day[day] = order + 1
        stops.append(
            PlanStop(
                day=day,
                order=order,
                name=raw.name,
                kind=_coerce_kind(raw.kind),
                coord=Coordinate(
                    lat=_clamp(raw.lat, -90.0, 90.0),
                    lng=_clamp(raw.lng, -180.0, 180.0),
                ),
                arrival_local=raw.arrival_local,
                duration_minutes=max(0, raw.duration_minutes),
                notes=raw.notes,
            )
        )

    # Route through start -> each stop -> end (real roads via OSRM when enabled).
    endpoints = [
        (start_name, start_coord),
        *((s.name, s.coord) for s in stops),
        (end_name, end_coord),
    ]
    route, legs = await plan_route(endpoints, round_trip=req.round_trip)

    costs = estimate_costs(
        distance_meters=route.distance_meters,
        days=req.days,
        party_size=req.party_size,
        stops=stops,
        round_trip=req.round_trip,
    )

    summary = itin.summary.strip() or (
        f"A {req.days}-day trip from {start_name} to {end_name} with {len(stops)} stops."
    )

    # True when the traveler never pinned a start (neither a field nor in the idea).
    parsed_origin, _ = _extract_endpoints_from_idea(req.idea)
    origin_assumed = req.origin is None and parsed_origin is None

    return PlanResponse(
        title=itin.title.strip() or f"{start_name} → {end_name}",
        summary=summary,
        tags=itin.tags,
        start_name=start_name,
        start_coord=start_coord,
        end_name=end_name,
        end_coord=end_coord,
        distance_meters=round(route.distance_meters, 1),
        expected_travel_time_seconds=round(route.duration_seconds, 0),
        stops=stops,
        legs=legs,
        costs=costs,
        source="llm",
        origin_assumed=origin_assumed,
        warnings=[],
    )


async def plan_trip(req: PlanRequest) -> PlanResponse:
    """Plan a trip, preferring the LLM planner and falling back to the heuristic.

    This is the entry point the API uses. The heuristic ``planner.plan_trip``
    remains available directly for offline/deterministic use.
    """

    if _llm_enabled():
        try:
            itinerary = await _generate_itinerary(req)
            if itinerary is not None:
                return await _assemble_response(req, itinerary)
            reason = "LLM planner returned no usable itinerary; used heuristic instead."
        except Exception as exc:  # noqa: BLE001 - any LLM failure must degrade gracefully
            reason = f"LLM planner unavailable ({type(exc).__name__}); used heuristic instead."

        fallback = await heuristic_plan_trip(req)
        fallback.warnings = [*fallback.warnings, reason]
        return fallback

    return await heuristic_plan_trip(req)
