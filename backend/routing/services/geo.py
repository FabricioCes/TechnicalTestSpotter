"""Geometry helpers: distances along a polyline and point sampling."""

from __future__ import annotations

import math

EARTH_RADIUS_MILES = 3958.8
METERS_PER_MILE = 1609.344


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def cumulative_miles(points: list[tuple[float, float]]) -> list[float]:
    """Cumulative distance in miles at every vertex of a [(lat, lon), ...] line."""
    distances = [0.0]
    for (lat1, lon1), (lat2, lon2) in zip(points, points[1:]):
        distances.append(distances[-1] + haversine_miles(lat1, lon1, lat2, lon2))
    return distances


def sample_along(
    points: list[tuple[float, float]], cumulative: list[float], target_miles: float
) -> tuple[float, float]:
    """Linearly interpolated (lat, lon) at `target_miles` along the line."""
    if target_miles <= 0:
        return points[0]
    if target_miles >= cumulative[-1]:
        return points[-1]
    # Find the segment that contains target_miles.
    lo, hi = 0, len(cumulative) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if cumulative[mid] <= target_miles:
            lo = mid
        else:
            hi = mid
    seg_len = cumulative[hi] - cumulative[lo]
    t = 0.0 if seg_len == 0 else (target_miles - cumulative[lo]) / seg_len
    (lat1, lon1), (lat2, lon2) = points[lo], points[hi]
    return lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t


def checkpoint_miles(total_miles: float, interval_miles: float) -> list[float]:
    """Mile markers every `interval_miles`, always including the origin and destination."""
    if interval_miles <= 0:
        raise ValueError("interval_miles must be positive")
    marks = []
    mile = 0.0
    while mile < total_miles:
        marks.append(round(mile, 3))
        mile += interval_miles
    marks.append(round(total_miles, 3))
    return marks


def offset_point(
    lat1: float, lon1: float, lat2: float, lon2: float, fraction: float, offset_miles: float
) -> tuple[float, float]:
    """A point at `fraction` of the straight line A->B, pushed `offset_miles` sideways.

    Used to build extra via-points when the routing API returns fewer than
    three alternatives.
    """
    mid_lat = lat1 + (lat2 - lat1) * fraction
    mid_lon = lon1 + (lon2 - lon1) * fraction
    # Perpendicular direction in a local flat approximation.
    dlat = lat2 - lat1
    dlon = (lon2 - lon1) * math.cos(math.radians(mid_lat))
    length = math.hypot(dlat, dlon) or 1.0
    perp_lat, perp_lon = -dlon / length, dlat / length  # 90 degrees to the line
    # Convert miles to degrees (approx. 69 miles per degree of latitude).
    deg = offset_miles / 69.0
    return mid_lat + perp_lat * deg, mid_lon + perp_lon * deg / max(math.cos(math.radians(mid_lat)), 0.2)
