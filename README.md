# Weather-Aware Truck Routing

A React + Django app that helps a truck driver choose the safest of three routes based on weather risk, load weight and travel time.

- **Backend:** Django 5.2 (`backend/`), exposes `POST /api/plan/`.
- **Frontend:** React 19 + Vite + Leaflet (`frontend/`), shows routes, checkpoints, risk levels, ETAs and a 0–48 h weather heatmap.
- **External services (all free, no API keys):** OpenStreetMap Nominatim (geocoding), OSRM demo server (driving routes with alternatives), Open-Meteo (hourly forecasts).
- **Deployment:** Docker Compose on a VPS. Nginx serves the React build and proxies `/api` to Gunicorn/Django.

## Run locally (without Docker)

Requirements: Python 3.12+ and Node 22+.

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py test routing   # 15 unit tests
python manage.py runserver 127.0.0.1:8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173, proxies /api to Django
```

Open http://localhost:5173, enter an origin, destination, departure time and load weight, then click **Plan routes**.

## Run with Docker

```bash
cp .env.example .env            # then edit the values
docker compose up --build -d    # then open the app through the frontend service on port 80 (see Dokploy section for hosted use)
```

Nginx (frontend container) serves the app and forwards `/api/` to the `backend` container. The browser only talks to one origin, so CORS is not needed in this setup.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | dev key | Required in production. Use a long random string. |
| `DJANGO_DEBUG` | `1` | Set to `0` in production. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames/IPs the site is served on (for example your domain and the VPS IP). |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Only needed when the frontend is served from another origin. |
| `NOMINATIM_URL`, `OSRM_URL`, `OPEN_METEO_URL` | public services | Override to use self-hosted or paid instances. |
| `VITE_BACKEND_URL` | `http://127.0.0.1:8000` | Dev proxy target (frontend, `npm run dev`). |
| `VITE_API_URL` | `/api` | API base used when building the frontend. |

## API

`POST /api/plan/`

```json
{
  "origin": "Denver, Colorado",
  "destination": "Salt Lake City, Utah",
  "departure": "2026-12-01T08:00:00Z",
  "load_lb": 35000,
  "interval_miles": 10
}
```

- `departure` is ISO 8601. Naive values are treated as UTC; the frontend converts the local time to UTC before sending.
- `interval_miles` must be `10`, `25` or `50`. Default in the UI: `10`.

The response contains the origin and destination, the three ranked routes (each with geometry, mile totals per risk level, average risk and checkpoints), and the recommendation with its reason. Each checkpoint has its ETA, wind/rain/snow values, risk level, and `hourly_levels` (risk for hours 0–48 after departure, used by the heatmap slider).

Errors return JSON `{"error": "..."}` with status 400 (bad input) or 502 (a third-party API failed).

## How the risk is calculated

Implemented in `backend/routing/services/risk.py`.

1. **Each condition is classified** with the thresholds from the spec (wind in mph, rain and snow in inches per hour):

   | Condition | Low | Moderate | High | Severe | No Travel |
   | --- | --- | --- | --- | --- | --- |
   | Wind | < 25 | 25–34 | 35–44 | 45–54 | ≥ 55 |
   | Rain | < 0.10 | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | > 1.00 |
   | Snow | < 0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | > 3.0 |

2. **Load rules** apply to wind:
   - ≥ 55 mph is No Travel for any load.
   - 45–54 mph with more than 30,000 lb is No Travel.
   - 35–44 mph with more than 40,000 lb is Severe.
3. **Checkpoint risk = the worst of the three conditions** (wind, rain, snow). Example: wind Low, rain High, snow Moderate gives a checkpoint risk of High.

Boundaries are lower-inclusive (25 mph is Moderate), except the No Travel rain and snow limits, which are strictly greater than the stated value (1.00 in/h rain is Severe, not No Travel), following the spec's `>1.00` and `>3.0`.

## Units and data sources

- Open-Meteo is queried with `wind_speed_unit=mph`, so wind arrives in mph.
- Open-Meteo returns rain in mm/h and snowfall in cm/h. The backend converts them: rain ÷ 25.4 and snowfall ÷ 2.54, giving in/h.
- Forecast times are requested in GMT, so all hours are UTC.
- The routing API, Nominatim and Open-Meteo are all free and keyless. Open-Meteo was chosen because it gives hourly wind, rain and snow for many points in a single request, in units that match the spec.

### Why OSRM for routing

The routing API has to return alternative routes. OSRM's public server returns up to three alternatives with a single free request and no key. Mapbox and OpenRouteService would also work but need an API key. If OSRM returns fewer than three routes, the backend adds detour routes through side via-points, so the user always sees three options.

## How routes, checkpoints and the recommendation work

- **Checkpoints:** points are placed along each route's geometry every `interval_miles` (default 10), always including the origin and destination.
- **ETA:** the routing API's total duration is spread evenly over the distance, so each checkpoint's ETA is proportional to its distance along the route.
- **Weather at a checkpoint:** the forecast hour matching its ETA.
- **Mile totals:** each checkpoint is responsible for the stretch of road that ends at it. Those miles are summed per risk level.
- **Ranking (best first):**
  1. Fewest No Travel miles (added by me: driving in No Travel is never acceptable, so this comes before the spec's list)
  2. Fewest Severe miles
  3. Fewest High miles
  4. Lowest distance-weighted average risk (Low 0 … No Travel 4)
  5. Shortest travel time

## Assumptions and decisions

- **"Sample weather every 10 / 25 / 50 miles":** the spec is ambiguous. The implemented reading is a single sampling interval chosen by the user, with **10 miles as the default**. The UI offers 25 and 50 as alternatives.
- **Combining conditions:** the checkpoint's risk is its worst single condition (see above).
- **Heatmap slider:** shows the forecast for the selected route's checkpoints at *departure + N hours* (0–48 h), so the driver can see how the corridor's weather evolves. Markers and route totals use each checkpoint's ETA.
- **Time zone:** all times are UTC internally. The UI labels times in UTC.
- **Car routing, not truck routing:** OSRM's profile is for cars. Results may include roads unsuitable for heavy trucks. A commercial truck routing API (for example HERE Truck or PC*MILER) would fix this.

## Limitations

- The public OSRM and Nominatim servers are free community services with usage limits. Use self-hosted or paid instances for production traffic.
- Road conditions, closures and elevation are not modeled. Only the forecast at each checkpoint is used.
- No database: plans are computed per request and not stored.

## Project layout

```
docker-compose.yml     Backend + Nginx frontend
.env.example           Production environment template
backend/
  Dockerfile           Python image running Gunicorn
  config/              Django settings and root URLs
  routing/
    services/
      risk.py            Risk thresholds and classification (pure logic)
      recommendation.py  Route summaries, ranking and explanation
      geo.py             Distances, interpolation, detour points
      providers.py       Nominatim, OSRM and Open-Meteo clients
      planner.py         Orchestrates a full plan
    views.py, urls.py
    tests/               Unit tests for risk, ranking and geometry
frontend/
  Dockerfile           Multi-stage build: Vite build, then Nginx
  nginx.conf           Serves the app and proxies /api to the backend
  src/
    App.jsx              State and layout
    components/          TripForm, RouteList, MapView, HeatmapSlider, CheckpointTable
    api.js               Calls POST /api/plan/
    risk.js              Risk level names and colors
docs/
  LOOM_WALKTHROUGH.md  Script for the 5–10 minute video
```

## Deploying with Dokploy

1. In Dokploy, create a project and add a **Docker Compose** service. Use the Git source (the repository must be on GitHub, GitLab or similar) and the compose file `docker-compose.yml` at the repository root.
2. In the service's **Environment** tab set:
   - `DJANGO_SECRET_KEY`: a long random string
   - `DJANGO_ALLOWED_HOSTS`: your domain, e.g. `trucks.example.com`
   - `CORS_ALLOWED_ORIGINS`: leave empty
3. In the **Domains** tab add your domain, select service `frontend` and port `80`, and enable HTTPS (Let's Encrypt).
4. Deploy. Dokploy builds both images. The frontend container serves the app and proxies `/api` to the backend, so only one domain is needed.

Local check before deploying: `docker compose up --build` uses the variables from a local `.env` (see `.env.example`), but the app will then not be reachable on a host port because the compose file no longer publishes one; use Dokploy or add a `ports` entry temporarily.
