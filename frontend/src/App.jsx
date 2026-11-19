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
      <header>
        <h1>Weather-Aware Truck Routing</h1>
        <p>Compare three routes by weather risk, load rules and travel time.</p>
      </header>

      <div className="layout">
        <aside className="panel">
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
                  Checkpoints every {plan.checkpoint_interval_miles} mi · Load {plan.load_lb.toLocaleString()} lb
                </small>
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
            <div className="placeholder">Enter a trip to see routes on the map.</div>
          )}
        </main>
      </div>
    </div>
  )
}
