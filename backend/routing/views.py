import json
from datetime import datetime, timezone

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .services.planner import DEFAULT_INTERVAL_MILES, plan_trip
from .services.providers import Place, ProviderError, suggest_addresses

ALLOWED_INTERVALS = {10, 25, 50}


@require_GET
def health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


MIN_SUGGEST_CHARS = 3


@require_GET
def address_suggestions(request: HttpRequest) -> JsonResponse:
    query = request.GET.get("q", "").strip()
    if len(query) < MIN_SUGGEST_CHARS:
        return JsonResponse({"suggestions": []})
    if len(query) > 120:
        return JsonResponse({"error": "q is too long."}, status=400)
    try:
        places = suggest_addresses(query)
    except ProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    return JsonResponse(
        {"suggestions": [{"label": p.label, "lat": p.lat, "lon": p.lon} for p in places]}
    )


def _parse_location(value):
    """Free text is geocoded later. A suggestion object carries exact coordinates."""
    if isinstance(value, dict):
        try:
            lat, lon = float(value["lat"]), float(value["lon"])
        except (KeyError, TypeError, ValueError):
            return None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return Place(label=str(value.get("label", "")), lat=lat, lon=lon)
    text = str(value or "").strip()
    return text or None


def _parse_departure(value: str) -> datetime:
    # Accepts ISO 8601, e.g. 2026-11-20T08:30:00Z or with an offset.
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


@csrf_exempt  # stateless JSON API with no session or cookie auth
@require_POST
def plan(request: HttpRequest) -> JsonResponse:
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be JSON."}, status=400)

    origin = _parse_location(body.get("origin"))
    destination = _parse_location(body.get("destination"))
    if origin is None or destination is None:
        return JsonResponse(
            {"error": "origin and destination are required (text or a suggestion with lat/lon)."},
            status=400,
        )

    try:
        departure = _parse_departure(str(body.get("departure", "")))
    except ValueError:
        return JsonResponse({"error": "departure must be an ISO 8601 date-time."}, status=400)

    try:
        load_lb = float(body.get("load_lb"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "load_lb must be a number (pounds)."}, status=400)
    if not 0 < load_lb <= 200_000:
        return JsonResponse({"error": "load_lb must be between 0 and 200000."}, status=400)

    interval = body.get("interval_miles", DEFAULT_INTERVAL_MILES)
    if interval not in ALLOWED_INTERVALS:
        return JsonResponse({"error": "interval_miles must be 10, 25 or 50."}, status=400)

    try:
        result = plan_trip(origin, destination, departure, load_lb, interval_miles=interval)
    except ProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    return JsonResponse(result)
