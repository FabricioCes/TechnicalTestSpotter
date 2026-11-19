import { riskColor } from '../risk'

function formatDuration(seconds) {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.round((seconds % 3600) / 60)
  return `${hours}h ${minutes}m`
}

export default function RouteList({ routes, selectedId, onSelect }) {
  return (
    <ul className="route-list">
      {routes.map((route) => (
        <li key={route.route_id}>
          <button
            type="button"
            className={`route-card ${route.route_id === selectedId ? 'selected' : ''}`}
            onClick={() => onSelect(route.route_id)}
          >
            <div className="route-title">
              <span className="route-name">{route.name}</span>
              {route.recommended && <span className="badge">Recommended</span>}
            </div>
            <div className="route-stats">
              <span>{route.distance_miles} mi</span>
              <span>{formatDuration(route.duration_s)}</span>
            </div>
            <div className="route-risk">
              <span style={{ color: riskColor('Severe') }}>Severe {route.severe_miles} mi</span>
              <span style={{ color: riskColor('High') }}>High {route.high_miles} mi</span>
              {route.no_travel_miles > 0 && (
                <span style={{ color: riskColor('No Travel') }}>No Travel {route.no_travel_miles} mi</span>
              )}
            </div>
          </button>
        </li>
      ))}
    </ul>
  )
}
