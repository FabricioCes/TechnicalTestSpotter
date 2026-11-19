# Loom walkthrough script (5–10 minutes)

## 1. Demo (about 2 min)
- Open the app. Enter origin **Denver, Colorado**, destination **Salt Lake City, Utah**, departure time, and load **35,000 lb**.
- Click **Plan routes**. Point out the three routes on the map, the recommended badge, and the recommendation reason.
- Click a checkpoint marker to show its ETA, wind, rain, snow and risk level.

## 2. Risk logic (about 2 min)
- Show `backend/routing/services/risk.py`.
- Explain the thresholds for wind, rain and snow.
- Explain the load rules: 45–54 mph with more than 30,000 lb is No Travel; 35–44 mph with more than 40,000 lb is Severe.
- Explain that each checkpoint takes the **worst** of its three conditions.

## 3. Assumptions to mention
- **Sampling:** the spec says "every 10 / 25 / 50 miles". I read it as a single interval chosen by the user, with **10 miles** as the default.
- **Units:** Open-Meteo returns wind in mph (requested directly), rain in mm and snow in cm. The backend converts these to inches per hour.
- **Routing:** OSRM provides the alternatives (no key needed). If it returns fewer than three, the backend builds detours through side via-points.
- **Car routing:** OSRM uses a car profile, not a truck profile. A production system would use a truck routing API.

## 4. Recommendation logic (about 1 min)
- Ranking order: fewest No Travel miles, fewest Severe miles, fewest High miles, lowest average risk, shortest time.
- No Travel is placed first as a safety rule I added. Mention it.

## 5. Heatmap (about 1 min)
- Turn on the heatmap and move the 0–48 h slider.
- Explain that it shows the forecast for each checkpoint at *departure + N hours*.

## 6. Code structure (about 2 min)
- Backend: `routing/views.py` (API), `services/planner.py` (pipeline), `services/providers.py` (external APIs), tests in `routing/tests/`.
- Frontend: `App.jsx` (state), `components/MapView.jsx` (map, polylines, heat layer), `components/TripForm.jsx`.
- Deployment: `docker-compose.yml`, Nginx proxies `/api` to Gunicorn.

## 7. What I would improve next (about 1 min)
- Truck-specific routing API and road restrictions.
- Caching of forecasts and geocoding results.
- Automated frontend tests and HTTPS on the VPS.
