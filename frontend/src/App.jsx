import { useMemo, useState } from 'react'
import TripForm from './components/TripForm'
import RouteList from './components/RouteList'
import CheckpointTable from './components/CheckpointTable'
import HeatmapSlider from './components/HeatmapSlider'
import MapView from './components/MapView'
import { planTrip } from './api'
import './App.css'

const HEAT_HOURS = 48

export default function App() {
  const [plan, setPlan] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [heatEnabled, setHeatEnabled] = useState(true)
  const [heatHour, setHeatHour] = useState(0)

  const selectedRoute = useMemo(
    () => plan?.routes.find((r) => r.route_id === selectedId) ?? null,
    [plan, selectedId],
  )
  const recommended = plan?.routes.find((r) => r.recommended)
  const widestInterval = plan ? Math.max(...plan.routes.map((r) => r.checkpoint_interval_miles)) : 0

  const handleSubmit = async (form) => {
    setLoading(true)
    setError('')
    try {
      const result = await planTrip(form)
      setPlan(result)
      setSelectedId(result.recommendation.route_id)
      setHeatHour(0)
    } catch (err) {
      setPlan(null)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <div className="layout">
        <aside className="panel">
          <div className="brand">
            <div className="brand-mark" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="5" cy="18" r="2" />
                <circle cx="19" cy="6" r="2" />
                <path d="M7 18h6a3 3 0 0 0 0-6h-2a3 3 0 0 1 0-6h6" />
              </svg>
            </div>
            <div>
              <h1>Weather-aware routing</h1>
              <p>Compare routes by weather risk, load and travel time.</p>
            </div>
          </div>

          <TripForm onSubmit={handleSubmit} loading={loading} />
          {error && <p className="error">{error}</p>}

          {plan && (
            <>
              <section className="recommendation">
                <h2>Recommendation</h2>
                <p>
                  <strong>{recommended?.name}</strong>: {plan.recommendation.reason}
                </p>
                <small>
                  Checkpoints every {Math.max(plan.checkpoint_interval_miles, widestInterval)} mi · Load{' '}
                  {plan.load_lb.toLocaleString()} lb
                </small>
                {widestInterval > plan.checkpoint_interval_miles && (
                  <small className="note">
                    Long trip: checkpoints are spaced wider than requested to stay within the weather service limits.
                  </small>
                )}
              </section>

              <RouteList routes={plan.routes} selectedId={selectedRoute?.route_id} onSelect={setSelectedId} />

              {selectedRoute && <CheckpointTable route={selectedRoute} />}
            </>
          )}
        </aside>

        <main className="map-area">
          {plan ? (
            <>
              <HeatmapSlider
                hours={HEAT_HOURS}
                value={heatHour}
                onChange={setHeatHour}
                departure={plan.departure}
                enabled={heatEnabled}
                onToggle={setHeatEnabled}
              />
              <MapView
                routes={plan.routes}
                selectedId={selectedRoute?.route_id}
                onSelect={setSelectedId}
                heatEnabled={heatEnabled}
                heatHour={heatHour}
              />
            </>
          ) : (
            <div className="placeholder">
              <strong>Plan a trip to see the risk along each route</strong>
              <span>Add an origin, a destination and a departure time. You get three routes ranked by weather risk.</span>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
