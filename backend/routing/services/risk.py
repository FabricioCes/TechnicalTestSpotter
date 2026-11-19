"""Weather risk classification rules.

All units follow the assessment spec:
- wind in miles per hour (mph)
- rain in inches per hour (in/hr)
- snow in inches per hour (in/hr)
- load in pounds (lb)

Thresholds are lower-inclusive (e.g. 25 mph is Moderate, not Low), except the
"No Travel" rain and snow thresholds, which are strictly greater than the
limit (e.g. exactly 1.00 in/hr rain is Severe, not No Travel), because the
spec writes them as ">1.00" and ">3.0".
"""

from __future__ import annotations

from enum import IntEnum


class RiskLevel(IntEnum):
    """Ordered risk levels. The integer value doubles as a numeric score."""

    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return {
            RiskLevel.LOW: "Low",
            RiskLevel.MODERATE: "Moderate",
            RiskLevel.HIGH: "High",
            RiskLevel.SEVERE: "Severe",
            RiskLevel.NO_TRAVEL: "No Travel",
        }[self]


# Thresholds from the "Risk Rules" table. Each tuple is the lower bound of
# Moderate, High, Severe and the No Travel boundary.
WIND_MPH = {"moderate": 25, "high": 35, "severe": 45, "no_travel": 55}
RAIN_IN_HR = {"moderate": 0.10, "high": 0.25, "severe": 0.50, "no_travel": 1.00}
SNOW_IN_HR = {"moderate": 0.5, "high": 1.0, "severe": 2.0, "no_travel": 3.0}

# Load rules ("Load rules" section of the spec).
HEAVY_LOAD_LB = 30_000  # 45-54 mph + more than this -> No Travel
VERY_HEAVY_LOAD_LB = 40_000  # 35-44 mph + more than this -> Severe


def _classify_wind(mph: float) -> RiskLevel:
    if mph >= WIND_MPH["no_travel"]:
        return RiskLevel.NO_TRAVEL
    if mph >= WIND_MPH["severe"]:
        return RiskLevel.SEVERE
    if mph >= WIND_MPH["high"]:
        return RiskLevel.HIGH
    if mph >= WIND_MPH["moderate"]:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def _classify_rain(in_hr: float) -> RiskLevel:
    if in_hr > RAIN_IN_HR["no_travel"]:
        return RiskLevel.NO_TRAVEL
    if in_hr >= RAIN_IN_HR["severe"]:
        return RiskLevel.SEVERE
    if in_hr >= RAIN_IN_HR["high"]:
        return RiskLevel.HIGH
    if in_hr >= RAIN_IN_HR["moderate"]:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def _classify_snow(in_hr: float) -> RiskLevel:
    if in_hr > SNOW_IN_HR["no_travel"]:
        return RiskLevel.NO_TRAVEL
    if in_hr >= SNOW_IN_HR["severe"]:
        return RiskLevel.SEVERE
    if in_hr >= SNOW_IN_HR["high"]:
        return RiskLevel.HIGH
    if in_hr >= SNOW_IN_HR["moderate"]:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def _wind_with_load(mph: float, load_lb: float) -> RiskLevel:
    """Wind classification including the load-dependent rules."""
    level = _classify_wind(mph)
    if mph >= WIND_MPH["no_travel"]:
        return RiskLevel.NO_TRAVEL  # applies to any load
    if WIND_MPH["severe"] <= mph < WIND_MPH["no_travel"] and load_lb > HEAVY_LOAD_LB:
        return RiskLevel.NO_TRAVEL
    if WIND_MPH["high"] <= mph < WIND_MPH["severe"] and load_lb > VERY_HEAVY_LOAD_LB:
        return max(level, RiskLevel.SEVERE)
    return level


def classify_checkpoint(
    wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float
) -> RiskLevel:
    """Overall risk of a checkpoint: the worst of wind, rain and snow."""
    return max(
        _wind_with_load(wind_mph, load_lb),
        _classify_rain(rain_in_hr),
        _classify_snow(snow_in_hr),
    )
