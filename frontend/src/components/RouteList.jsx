import { riskColor, ROUTE_COLORS } from '../risk'

function formatDuration(seconds) {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.round((seconds % 3600) / 60)
  return { hours, minutes }
}

// Splits the route into clear / high / severe / no-travel miles for the risk bar.
function riskSegments(route) {
  const high = route.high_miles ?? 0
  const severe = route.severe_miles ?? 0
  const blocked = route.no_travel_miles ?? 0
  const clear = Math.max(0, route.distance_miles - high - severe - blocked)
  return [
    { label: 'Low / moderate', miles: clear, color: riskColor('Low') },
    { label: 'High', miles: high, color: riskColor('High') },
    { label: 'Severe', miles: severe, color: riskColor('Severe') },
    { label: 'No Travel', miles: blocked, color: riskColor('No Travel') },
  ].filter((segment) => segment.miles > 0)
}

export default function RouteList({ routes, selectedId, onSelect }) {
  return (
    <ul className="route-list">
      {routes.map((route, index) => {
        const { hours, minutes } = formatDuration(route.duration_s)
        const segments = riskSegments(route)
        const summary = segments.map((s) => `${s.label} ${s.miles} mi`).join(', ')
        return (
          <li key={route.route_id}>
            <button
              type="button"
              className={`route-card ${route.route_id === selectedId ? 'selected' : ''}`}
              style={{ '--route-color': ROUTE_COLORS[index % ROUTE_COLORS.length] }}
              onClick={() => onSelect(route.route_id)}
              aria-pressed={route.route_id === selectedId}
            >
              <div className="route-title">
                <span className="route-swatch" aria-hidden="true" />
                <span className="route-name">{route.name}</span>
                {route.recommended && <span className="badge">Recommended</span>}
              </div>
              <div className="route-stats">
                <div>
                  <strong>{route.distance_miles}</strong>
                  <span>mi</span>
                </div>
                <div>
                  <strong>{hours}</strong>
                  <span>h</span> <strong>{minutes}</strong>
                  <span>m</span>
                </div>
              </div>
              <div className="risk-bar" role="img" aria-label={`Risk along the route: ${summary}`}>
                {segments.map((segment) => (
                  <i key={segment.label} style={{ flexGrow: segment.miles, background: segment.color }} />
                ))}
              </div>
              <div className="route-risk">
                {route.high_miles > 0 && (
                  <span style={{ '--c': riskColor('High') }}>
                    <i /> High {route.high_miles} mi
                  </span>
                )}
                {route.severe_miles > 0 && (
                  <span style={{ '--c': riskColor('Severe') }}>
                    <i /> Severe {route.severe_miles} mi
                  </span>
                )}
                {route.no_travel_miles > 0 && (
                  <span style={{ '--c': riskColor('No Travel') }}>
                    <i /> No Travel {route.no_travel_miles} mi
                  </span>
                )}
                {!route.high_miles && !route.severe_miles && !route.no_travel_miles && (
                  <span style={{ '--c': riskColor('Low') }}>
                    <i /> No high-risk miles
                  </span>
                )}
              </div>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
