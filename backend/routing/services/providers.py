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
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from urllib.parse import urlparse

import requests
from django.conf import settings

from .geo import haversine_miles, offset_point

logger = logging.getLogger(__name__)

TIMEOUT_S = 15
# Transient failures worth retrying: rate limiting and gateway errors.
RETRY_STATUSES = {429, 502, 503, 504}
MAX_ATTEMPTS = 3
MAX_BACKOFF_S = 4
# Forecasts change hourly, so a short cache avoids repeat calls without going stale.
WEATHER_CACHE_TTL_S = 30 * 60
WEATHER_CACHE_MAX_ENTRIES = 5000
# Search-as-you-type must fail fast: a slow suggestion is worse than none.
SUGGEST_TIMEOUT_S = 6
# Rough bounding box of the US (min lon, min lat, max lon, max lat), Alaska and Hawaii included.
US_BBOX = "-179.2,18.8,-66.9,71.5"


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


def _retry_delay(response: requests.Response, attempt: int) -> float:
    """Seconds to wait before retrying: Retry-After when numeric, else exponential backoff."""
    retry_after = response.headers.get("Retry-After", "")
    if retry_after.isdigit():
        return min(float(retry_after), MAX_BACKOFF_S)
    return min(2.0**attempt, MAX_BACKOFF_S)


def _rate_limit_reason(response: requests.Response) -> str:
    """Open-Meteo says which limit was hit (minutely, hourly, daily) in the JSON body."""
    try:
        body = response.json()
    except ValueError:
        return ""
    return str(body.get("reason", "")) if isinstance(body, dict) else ""


def _get_json(
    url: str, params: dict, timeout: float = TIMEOUT_S, attempts: int = 1
) -> dict | list:
    """GET a JSON document, retrying transient failures up to `attempts` times."""
    headers = {"User-Agent": settings.HTTP_USER_AGENT}
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            raise ProviderError(f"Request to {url} failed: {exc}") from exc
        if response.status_code == 200:
            break
        reason = _rate_limit_reason(response) if response.status_code == 429 else ""
        # Only a per-minute limit clears fast enough to be worth retrying.
        waits_out = response.status_code != 429 or not reason or "minutely" in reason.lower()
        if response.status_code in RETRY_STATUSES and waits_out and attempt < attempts:
            time.sleep(_retry_delay(response, attempt))
            continue
        if response.status_code == 429:
            host = urlparse(url).netloc
            detail = reason or "Try again in a few minutes."
            raise ProviderError(f"{host} is rate-limiting requests. {detail}")
        raise ProviderError(f"{url} returned HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderError(f"{url} returned invalid JSON") from exc


def _photon_label(props: dict) -> str:
    """'9 Hi River Road, Barnstable, MA 02648' style label from Photon properties."""
    street = " ".join(p for p in [props.get("housenumber"), props.get("street") or props.get("name")] if p)
    city = props.get("city") or props.get("town") or props.get("village") or props.get("county") or ""
    state = props.get("state_code") or props.get("state") or ""
    parts = [street, city, " ".join(p for p in [state, props.get("postcode")] if p)]
    return ", ".join(p for p in parts if p)


@lru_cache(maxsize=512)
def suggest_addresses(query: str, limit: int = 6) -> tuple[Place, ...]:
    """US address suggestions for a partial query (search-as-you-type).

    Photon returns results worldwide; only US hits are kept.
    """
    data = _get_json(
        f"{settings.PHOTON_URL}/",
        {"q": query, "limit": 10, "lang": "en", "bbox": US_BBOX},
        timeout=SUGGEST_TIMEOUT_S,
    )
    suggestions: list[Place] = []
    seen: set[str] = set()
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        if props.get("countrycode") != "US":
            continue
        label = _photon_label(props)
        lon, lat = feature["geometry"]["coordinates"]
        if not label or label in seen:
            continue
        seen.add(label)
        suggestions.append(Place(label=label, lat=float(lat), lon=float(lon)))
        if len(suggestions) == limit:
            break
    return tuple(suggestions)


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


# (lat, lon, start date, end date) -> (time stored, hourly weather)
_weather_cache: dict[tuple, tuple[float, dict[datetime, HourlyWeather]]] = {}


def _parse_hourly(location: dict) -> dict[datetime, HourlyWeather]:
    hourly = location["hourly"]
    by_hour: dict[datetime, HourlyWeather] = {}
    for i, stamp in enumerate(hourly["time"]):
        hour = datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
        by_hour[hour] = HourlyWeather(
            wind_mph=_to_float(hourly["wind_speed_10m"][i]),
            rain_in_hr=_to_float(hourly["rain"][i]) / 25.4,  # mm -> in
            snow_in_hr=_to_float(hourly["snowfall"][i]) / 2.54,  # cm -> in
        )
    return by_hour


def _cached_weather(key: tuple, now: float) -> dict[datetime, HourlyWeather] | None:
    entry = _weather_cache.get(key)
    if entry is None or now - entry[0] > WEATHER_CACHE_TTL_S:
        return None
    return entry[1]


def get_hourly_weather(
    points: list[tuple[float, float]], start: datetime, end: datetime
) -> list[dict[datetime, HourlyWeather]]:
    """Hourly forecasts for many points, fetched in as few requests as possible.

    Returns one dict per input point, mapping the hour (UTC, floored) to the
    weather during that hour. Open-Meteo accepts comma-separated coordinates.
    Coordinates are rounded to 2 decimals (about 1 km, finer than the forecast
    grid) so that nearby checkpoints and repeated trips share cached results,
    which keeps the app under Open-Meteo's free rate limit.
    """
    if not points:
        return []
    now = time.monotonic()
    dates = (start.date().isoformat(), end.date().isoformat())
    keys = [(round(lat, 2), round(lon, 2), *dates) for lat, lon in points]
    missing = [key for key in dict.fromkeys(keys) if _cached_weather(key, now) is None]

    chunk_size = 100
    for offset in range(0, len(missing), chunk_size):
        chunk = missing[offset : offset + chunk_size]
        params = {
            "latitude": ",".join(f"{key[0]:.2f}" for key in chunk),
            "longitude": ",".join(f"{key[1]:.2f}" for key in chunk),
            "hourly": "wind_speed_10m,rain,snowfall",
            "wind_speed_unit": "mph",  # rain/snowfall use metric units, converted in _parse_hourly
            "timezone": "GMT",
            "start_date": dates[0],
            "end_date": dates[1],
        }
        data = _get_json(f"{settings.OPEN_METEO_URL}/forecast", params, attempts=MAX_ATTEMPTS)
        if isinstance(data, dict):  # a single location comes back as an object
            data = [data]
        if len(data) != len(chunk):
            raise ProviderError("The weather service returned an unexpected response")
        if len(_weather_cache) + len(chunk) > WEATHER_CACHE_MAX_ENTRIES:
            _weather_cache.clear()
        for key, location in zip(chunk, data):
            _weather_cache[key] = (now, _parse_hourly(location))

    return [_weather_cache[key][1] for key in keys]


def floor_hour(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def forecast_window(departure: datetime, duration_s: float, extra_hours: int = 48) -> tuple[datetime, datetime]:
    """Time range the forecast must cover: departure through arrival plus the heatmap horizon."""
    start = floor_hour(departure)
    end = start + timedelta(seconds=duration_s) + timedelta(hours=extra_hours)
    return start, end
