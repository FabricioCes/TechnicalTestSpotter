// Risk levels mirror the backend's RiskLevel enum (score = array index).
export const RISK_LEVELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel']

export const RISK_COLORS = {
  Low: '#2a9d8f',
  Moderate: '#e9c46a',
  High: '#f4a261',
  Severe: '#e76f51',
  'No Travel': '#b0203a',
}

export function riskColor(levelName) {
  return RISK_COLORS[levelName] ?? '#888'
}

// One color per route, shared by the map lines and the route cards.
export const ROUTE_COLORS = ['#4f8cff', '#b388ff', '#ff7eb6']
