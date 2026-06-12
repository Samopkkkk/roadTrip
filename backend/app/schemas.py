"""Pydantic schemas shared across the planner, geocoder, and HTTP API.

These are the single source of truth for the request/response contract the iOS
app talks to. Keep them backwards compatible: the app may send extra fields we
don't know about yet (we ignore them) but it relies on the response shape.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class StopKind(str, Enum):
    """What a stop *is*, so the client can pick an icon and we can price it."""

    attraction = "attraction"
    scenic = "scenic"
    activity = "activity"
    food = "food"
    lodging = "lodging"
    fuel = "fuel"
    rest = "rest"


class Pace(str, Enum):
    """How hard the itinerary pushes per day."""

    relaxed = "relaxed"
    balanced = "balanced"
    packed = "packed"


class Coordinate(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)


class PlanStop(BaseModel):
    day: int = Field(..., ge=1)
    order: int = Field(default=0, ge=0)
    name: str
    kind: StopKind = StopKind.attraction
    coord: Coordinate
    arrival_local: str | None = None
    duration_minutes: int = Field(default=0, ge=0)
    notes: str | None = None


class CostBreakdown(BaseModel):
    """Itemised estimate. All values are USD unless noted."""

    fuel_usd: float = 0.0
    lodging_usd: float = 0.0
    food_usd: float = 0.0
    activities_usd: float = 0.0
    total_usd: float = 0.0
    per_person_usd: float = 0.0
    assumptions: list[str] = Field(default_factory=list)


class RouteLeg(BaseModel):
    """One drivable hop between two consecutive stops."""

    from_name: str | None = None
    to_name: str | None = None
    distance_meters: float = 0.0
    duration_seconds: float = 0.0


class PlanRequest(BaseModel):
    """A user's initial idea. Every field is optional except that *something*
    must be provided — a free-form idea, a destination, an attraction, or a
    direction to wander."""

    idea: str = Field(default="", description="Free-form trip idea, e.g. 'weekend near Yosemite'.")
    origin: str | None = Field(default=None, description="Where the trip starts.")
    destination: str | None = Field(default=None, description="Explicit destination, if known.")
    anchor_attraction: str | None = Field(
        default=None, description="A single must-see that anchors the trip."
    )
    direction: str | None = Field(
        default=None, description="A compass-ish hint ('north', 'pacific coast') for open-ended trips."
    )
    days: int = Field(default=3, ge=1, le=60)
    party_size: int = Field(default=2, ge=1, le=20)
    pace: Pace = Pace.balanced

    @model_validator(mode="after")
    def _require_some_seed(self) -> "PlanRequest":
        if not any(
            (
                self.idea.strip(),
                (self.origin or "").strip(),
                (self.destination or "").strip(),
                (self.anchor_attraction or "").strip(),
                (self.direction or "").strip(),
            )
        ):
            raise ValueError(
                "Provide at least one of: idea, destination, anchor_attraction, or direction."
            )
        return self


class PlanResponse(BaseModel):
    title: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    start_name: str
    start_coord: Coordinate
    end_name: str
    end_coord: Coordinate
    distance_meters: float
    expected_travel_time_seconds: float
    stops: list[PlanStop] = Field(default_factory=list)
    legs: list[RouteLeg] = Field(default_factory=list)
    costs: CostBreakdown
    source: str = "heuristic"
    origin_assumed: bool = Field(
        default=False,
        description="True when no start was given and one was assumed; the app "
        "should supply the traveler's location and re-plan.",
    )
    warnings: list[str] = Field(default_factory=list)
