const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

export async function planTrip({ origin, destination, departureLocal, loadLb, intervalMiles }) {
  // The <input type="datetime-local"> value has no timezone. Convert it from the
  // user's local time to UTC so the backend and the forecast use the same clock.
  const departure = new Date(departureLocal).toISOString()

  const response = await fetch(`${API_BASE}/plan/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      origin,
      destination,
      departure,
      load_lb: Number(loadLb),
      interval_miles: Number(intervalMiles),
    }),
  })

  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.error ?? `Request failed with HTTP ${response.status}`)
  }
  return data
}
