const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

async function readJson(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.error ?? `Request failed with HTTP ${response.status}`)
  }
  return data
}

// Suggestions already fetched in this session, so retyping or backspacing is instant.
const suggestionCache = new Map()

export async function suggestAddresses(query, { signal } = {}) {
  const key = query.trim().toLowerCase()
  if (suggestionCache.has(key)) return suggestionCache.get(key)

  const params = new URLSearchParams({ q: query })
  const response = await fetch(`${API_BASE}/addresses/suggest/?${params}`, { signal })
  const data = await readJson(response)
  suggestionCache.set(key, data.suggestions)
  return data.suggestions
}

// `origin` / `destination` are either free text or a suggestion {label, lat, lon}.
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
  return readJson(response)
}
