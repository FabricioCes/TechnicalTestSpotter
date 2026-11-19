"""Builds a full trip plan: routes, checkpoints, ETAs, risk and recommendation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .geo import checkpoint_miles, cumulative_miles, sample_along
from .providers import (
    ProviderError,
    Place,
    RouteCandidate,
    floor_hour,
    forecast_window,
    geocode,
    get_hourly_weather,
    get_route_options,
)
from .recommendation import Checkpoint, RouteSummary, explain_choice, rank_routes, summarize
from .risk import classify_checkpoint

HEATMAP_HOURS = 48
DEFAULT_INTERVAL_MILES = 10


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_route(
    route_id: str,
    candidate: RouteCandidate,
    departure: datetime,
    load_lb: float,
    interval_miles: float,
) -> RouteSummary:
    points = candidate.geometry
    cumulative = cumulative_miles(points)
    total_miles = cumulative[-1]
    marks = checkpoint_miles(total_miles, interval_miles)
    coords = [sample_along(points, cumulative, mile) for mile in marks]

    # The routing API gives the total drive time. Assume it is spread evenly
    # over the distance, so each checkpoint's ETA is proportional to its mile.
    etas = [
        departure + timedelta(seconds=candidate.duration_s * (mile / total_miles if total_miles else 0))
        for mile in marks
    ]

    window_start, window_end = forecast_window(departure, candidate.duration_s, HEATMAP_HOURS)
    weather = get_hourly_weather(coords, window_start, window_end)

    heat_start = floor_hour(departure)
    checkpoints: list[Checkpoint] = []
    for index, (mile, (lat, lon), eta) in enumerate(zip(marks, coords, etas)):
        at_eta = weather[index].get(floor_hour(eta))
        if at_eta is None:
            raise ProviderError("Forecast is not available for the estimated arrival time")
        level = classify_checkpoint(at_eta.wind_mph, at_eta.rain_in_hr, at_eta.snow_in_hr, load_lb)

        hourly_levels: list[int | None] = []
        for hour_offset in range(HEATMAP_HOURS + 1):
            hour = heat_start + timedelta(hours=hour_offset)
            sample = weather[index].get(hour)
            hourly_levels.append(
                None
                if sample is None
                else int(classify_checkpoint(sample.wind_mph, sample.rain_in_hr, sample.snow_in_hr, load_lb))
            )

        previous_mile = marks[index - 1] if index else mile
        checkpoints.append(
            Checkpoint(
                index=index,
                mile=round(mile, 1),
                segment_miles=round(mile - previous_mile, 3),
                lat=lat,
                lon=lon,
                eta=eta,
                wind_mph=round(at_eta.wind_mph, 1),
                rain_in_hr=round(at_eta.rain_in_hr, 3),
                snow_in_hr=round(at_eta.snow_in_hr, 3),
                level=level,
                hourly_levels=hourly_levels,
            )
        )

    return summarize(
        route_id=route_id,
        name=candidate.name,
        distance_miles=total_miles,
        duration_s=candidate.duration_s,
        checkpoints=checkpoints,
        geometry=[[lat, lon] for lat, lon in points],
    )


def _checkpoint_json(cp: Checkpoint) -> dict:
    return {
        "index": cp.index,
        "mile": cp.mile,
        "lat": cp.lat,
        "lon": cp.lon,
        "eta": _iso(cp.eta),
        "wind_mph": cp.wind_mph,
        "rain_in_hr": cp.rain_in_hr,
        "snow_in_hr": cp.snow_in_hr,
        "risk_level": cp.level.label,
        "risk_score": int(cp.level),
        "hourly_levels": cp.hourly_levels,
    }


def _route_json(route: RouteSummary) -> dict:
    return {
        "route_id": route.route_id,
        "name": route.name,
        "rank": route.rank,
        "recommended": route.recommended,
        "distance_miles": route.distance_miles,
        "duration_s": round(route.duration_s),
        "severe_miles": route.severe_miles,
        "high_miles": route.high_miles,
        "no_travel_miles": route.no_travel_miles,
        "average_risk": route.average_risk,
        "geometry": route.geometry,
        "checkpoints": [_checkpoint_json(cp) for cp in route.checkpoints],
    }


def _place_json(place: Place) -> dict:
    return {"label": place.label, "lat": place.lat, "lon": place.lon}


def _resolve(location: str | Place) -> Place:
    """A Place chosen from autocomplete is used as-is; free text is geocoded."""
    return location if isinstance(location, Place) else geocode(location)


def plan_trip(
    origin_text: str | Place,
    destination_text: str | Place,
    departure: datetime,
    load_lb: float,
    interval_miles: float = DEFAULT_INTERVAL_MILES,
) -> dict:
    """Run the whole pipeline and return a JSON-serializable plan."""
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=timezone.utc)

    origin = _resolve(origin_text)
    destination = _resolve(destination_text)
    candidates = get_route_options(origin, destination, wanted=3)

    summaries = [
        _build_route(f"route-{i}", candidate, departure, load_lb, interval_miles)
        for i, candidate in enumerate(candidates, start=1)
    ]
    ranked = rank_routes(summaries)
    best = ranked[0]

    return {
        "origin": _place_json(origin),
        "destination": _place_json(destination),
        "departure": _iso(departure),
        "load_lb": load_lb,
        "checkpoint_interval_miles": interval_miles,
        "heatmap_hours": HEATMAP_HOURS,
        "recommendation": {
            "route_id": best.route_id,
            "reason": explain_choice(best, ranked[1:]),
        },
        "routes": [_route_json(route) for route in ranked],
    }
