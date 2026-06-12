"""HTTP surface for the roadTrip planner.

Run locally with::

    uvicorn backend.app.main:app --reload

The iOS app POSTs a free-form idea to ``/plan`` and gets back a full itinerary
with coordinates and a cost breakdown. ``/health`` is a cheap liveness probe.
"""

from __future__ import annotations

from fastapi import FastAPI

from .llm_planner import plan_trip
from .schemas import PlanRequest, PlanResponse

app = FastAPI(
    title="roadTrip planner API",
    version="0.1.0",
    summary="Turn a one-line idea into a costed road-trip itinerary.",
)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/plan", response_model=PlanResponse, tags=["planner"])
async def create_plan(req: PlanRequest) -> PlanResponse:
    """Build a complete, costed plan from a user's initial idea."""

    return await plan_trip(req)
