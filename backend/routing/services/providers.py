"""Clients for the third-party APIs used by the app.

- Nominatim (OpenStreetMap) for geocoding
- OSRM public demo server for driving routes with alternatives
- Open-Meteo for hourly forecasts (no API key required)

All three are free and keyless, which keeps the project runnable without
secrets. For production, swap in a paid provider (e.g. Mapbox, HERE, or a
truck-specific routing API) behind these same functions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import requests
from django.conf import settings

from .geo import haversine_miles, offset_point

logger = logging.getLogger(__name__)

TIMEOUT_S = 15


class ProviderError(Exception):
    """Raised when an external API fails or returns unusable data."""


@dataclass
class Place:
    label: str
    lat: float
    lon: float


@dataclass
class RouteCandidate:
    name: str
    distance_miles: float
    duration_s: float
    geometry: list[tuple[float, float]]  # (lat, lon)


def _get_json(url: str, params: dict) -> dict | list:
    headers = {"User-Agent": settings.HTTP_USER_AGENT}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT_S)
    except requests.RequestException as exc:
        raise ProviderError(f"Request to {url} failed: {exc}") from exc
    if response.status_code != 200:
        raise ProviderError(f"{url} returned HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderError(f"{url} returned invalid JSON") from exc


@lru_cache(maxsize=256)
def geocode(query: str) -> Place:
    """Resolve a free-text address to coordinates using Nominatim."""
    data = _get_json(
        f"{settings.NOMINATIM_URL}/search",
        {"q": query, "format": "json", "limit": 1},
    )
    if not data:
        raise ProviderError(f"Could not find a location for '{query}'")
    hit = data[0]
    return Place(label=hit["display_name"], lat=float(hit["lat"]), lon=float(hit["lon"]))


def _osrm_url(points: list[tuple[float, float]]) -> str:
    coords = ";".join(f"{lon},{lat}" for lat, lon in points)
    return f"{settings.OSRM_URL}/route/v1/driving/{coords}"


def _parse_osrm_routes(data: dict) -> list[RouteCandidate]:
    if data.get("code") != "Ok":
        raise ProviderError(f"Routing failed: {data.get('message', data.get('code'))}")
    candidates = []
    for index, route in enumerate(data.get("routes", []), start=1):
        coords = route["geometry"]["coordinates"]  # [lon, lat]
        candidates.append(
            RouteCandidate(
                name=f"Route {index}",
                distance_miles=route["distance"] / 1609.344,
                duration_s=float(route["duration"]),
                geometry=[(lat, lon) for lon, lat in coords],
            )
        )
    return candidates


def _route_key(candidate: RouteCandidate) -> tuple[int, int]:
    return round(candidate.distance_miles), round(candidate.duration_s / 60)


def get_route_options(
    origin: Place, destination: Place, wanted: int = 3
) -> list[RouteCandidate]:
    """Up to `wanted` distinct driving routes between two places.

    First asks OSRM for alternatives. If it returns fewer than requested, it
    adds detours through side via-points so the user still gets three options.
    """
    start = (origin.lat, origin.lon)
    end = (destination.lat, destination.lon)
    data = _get_json(
        _osrm_url([start, end]),
        {"alternatives": "true", "geometries": "geojson", "overview": "full", "steps": "false"},
    )
    routes = _parse_osrm_routes(data)

    straight = haversine_miles(*start, *end)
    if len(routes) < wanted and straight > 0:
        for fraction, offset in [(0.5, 0.25), (0.5, -0.25), (0.35, 0.2), (0.65, -0.2)]:
            if len(routes) >= wanted:
                break
            via = offset_point(*start, *end, fraction, offset * straight)
            try:
                detour = _parse_osrm_routes(
                    _get_json(
                        _osrm_url([start, via, end]),
                        {"geometries": "geojson", "overview": "full", "steps": "false"},
                    )
                )
            except ProviderError as exc:
                logger.info("Detour via %s failed: %s", via, exc)
                continue
            for candidate in detour:
                if all(_route_key(candidate) != _route_key(r) for r in routes):
                    routes.append(candidate)
                    break

    if not routes:
        raise ProviderError("No driving routes were found between these locations")
    for index, route in enumerate(routes[:wanted], start=1):
        route.name = f"Route {index}"
    return routes[:wanted]


@dataclass
class HourlyWeather:
    """Hourly values in the units the risk rules use."""

    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float


def _to_float(value) -> float:
    return float(value) if value is not None else 0.0


def get_hourly_weather(
    points: list[tuple[float, float]], start: datetime, end: datetime
) -> list[dict[datetime, HourlyWeather]]:
    """Hourly forecasts for many points in one request.

    Returns one dict per input point, mapping the hour (UTC, floored) to the
    weather during that hour. Open-Meteo accepts comma-separated coordinates,
    so all checkpoints of a route are fetched together.
    """
    if not points:
        return []
    results: list[dict[datetime, HourlyWeather]] = []
    chunk_size = 100
    for offset in range(0, len(points), chunk_size):
        chunk = points[offset : offset + chunk_size]
        params = {
            "latitude": ",".join(f"{lat:.4f}" for lat, _ in chunk),
            "longitude": ",".join(f"{lon:.4f}" for _, lon in chunk),
            "hourly": "wind_speed_10m,rain,snowfall",
            "wind_speed_unit": "mph",  # rain/snowfall use metric units, converted below
            "timezone": "GMT",
            "start_date": start.date().isoformat(),
            "end_date": end.date().isoformat(),
        }
        data = _get_json(f"{settings.OPEN_METEO_URL}/forecast", params)
        if isinstance(data, dict):  # a single location comes back as an object
            data = [data]
        for location in data:
            hourly = location["hourly"]
            by_hour: dict[datetime, HourlyWeather] = {}
            for i, stamp in enumerate(hourly["time"]):
                hour = datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
                by_hour[hour] = HourlyWeather(
                    wind_mph=_to_float(hourly["wind_speed_10m"][i]),
                    rain_in_hr=_to_float(hourly["rain"][i]) / 25.4,  # mm -> in
                    snow_in_hr=_to_float(hourly["snowfall"][i]) / 2.54,  # cm -> in
                )
            results.append(by_hour)
    return results


def floor_hour(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def forecast_window(departure: datetime, duration_s: float, extra_hours: int = 48) -> tuple[datetime, datetime]:
    """Time range the forecast must cover: departure through arrival plus the heatmap horizon."""
    start = floor_hour(departure)
    end = start + timedelta(seconds=duration_s) + timedelta(hours=extra_hours)
    return start, end
