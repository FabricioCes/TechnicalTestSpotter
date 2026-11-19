"""Route summaries and best-route selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .risk import RiskLevel


@dataclass
class Checkpoint:
    index: int
    mile: float  # cumulative miles from origin
    segment_miles: float  # miles since the previous checkpoint (0 for origin)
    lat: float
    lon: float
    eta: datetime  # estimated arrival time of the truck at this point
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float
    level: RiskLevel
    # Risk level at each hour 0..48 after departure, for the heatmap slider.
    # None when the forecast is not available for that hour.
    hourly_levels: list[int | None] = field(default_factory=list)


@dataclass
class RouteSummary:
    route_id: str
    name: str
    distance_miles: float
    duration_s: float
    severe_miles: float
    high_miles: float
    no_travel_miles: float
    average_risk: float  # distance-weighted mean of the numeric risk score
    checkpoints: list[Checkpoint]
    geometry: list[list[float]]  # [lat, lon] pairs for the map
    rank: int = 0
    recommended: bool = False

    def sort_key(self) -> tuple:
        # Ordering from the spec, with No Travel miles placed first because
        # driving in a No Travel zone is never acceptable.
        return (
            round(self.no_travel_miles, 1),
            round(self.severe_miles, 1),
            round(self.high_miles, 1),
            round(self.average_risk, 3),
            round(self.duration_s, 0),
        )


def summarize(
    route_id: str,
    name: str,
    distance_miles: float,
    duration_s: float,
    checkpoints: list[Checkpoint],
    geometry: list[list[float]],
) -> RouteSummary:
    """Compute mile totals per risk level for a route.

    Each checkpoint covers the stretch of road that ends at it, so its
    `segment_miles` is attributed to its risk level.
    """
    severe = high = no_travel = 0.0
    weighted_score = 0.0
    total = 0.0
    for cp in checkpoints:
        miles = cp.segment_miles
        total += miles
        weighted_score += miles * int(cp.level)
        if cp.level == RiskLevel.SEVERE:
            severe += miles
        elif cp.level == RiskLevel.HIGH:
            high += miles
        elif cp.level == RiskLevel.NO_TRAVEL:
            no_travel += miles
    average = weighted_score / total if total else 0.0
    return RouteSummary(
        route_id=route_id,
        name=name,
        distance_miles=round(distance_miles, 1),
        duration_s=duration_s,
        severe_miles=round(severe, 1),
        high_miles=round(high, 1),
        no_travel_miles=round(no_travel, 1),
        average_risk=round(average, 3),
        checkpoints=checkpoints,
        geometry=geometry,
    )


def rank_routes(routes: list[RouteSummary]) -> list[RouteSummary]:
    """Sort routes best-first and flag the recommended one."""
    ordered = sorted(routes, key=lambda r: r.sort_key())
    for position, route in enumerate(ordered, start=1):
        route.rank = position
        route.recommended = position == 1
    return ordered


def explain_choice(best: RouteSummary, others: list[RouteSummary]) -> str:
    """Short human-readable reason for the recommendation."""
    if not others:
        return "Only one route was available."
    if best.no_travel_miles > 0:
        return (
            "Every route crosses No Travel conditions; this one has the least "
            "exposure, but it is not safe to drive without a change in timing."
        )
    worst_severe = max(r.severe_miles for r in others)
    if best.severe_miles < worst_severe:
        return (
            f"Fewest Severe miles ({best.severe_miles} mi vs up to "
            f"{worst_severe} mi on other routes)."
        )
    worst_high = max(r.high_miles for r in others)
    if best.high_miles < worst_high:
        return (
            f"Same Severe miles, but fewer High-risk miles "
            f"({best.high_miles} mi vs up to {worst_high} mi)."
        )
    if best.average_risk < max(r.average_risk for r in others):
        return "Same Severe and High exposure, but a lower average weather risk."
    return "Equal weather risk; this route has the shortest travel time."
