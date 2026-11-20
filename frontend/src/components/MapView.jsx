import { useEffect, useMemo, useRef } from 'react'
import { MapContainer, TileLayer, Polyline, CircleMarker, Popup, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { HeatLayer } from 'leaflet.heat'
import { riskColor, RISK_LEVELS, ROUTE_COLORS } from '../risk'

const HEAT_GRADIENT = { 0.2: '#2a9d8f', 0.4: '#e9c46a', 0.6: '#f4a261', 0.8: '#e76f51', 1: '#6d0e1a' }

function formatEta(iso) {
  return new Date(iso).toISOString().replace('T', ' ').slice(0, 16)
}

function FitToRoutes({ routes }) {
  const map = useMap()
  useEffect(() => {
    const points = routes.flatMap((route) => route.geometry)
    if (points.length) {
      map.fitBounds(L.latLngBounds(points), { padding: [30, 30] })
    }
  }, [map, routes])
  return null
}

// Draws the forecast for the selected hour as a heat layer over the checkpoints.
// The layer is created once and updated in place, so slider moves stay smooth.
function HeatOverlay({ points }) {
  const map = useMap()
  const layerRef = useRef(null)

  useEffect(() => {
    if (!points) {
      layerRef.current?.remove()
      layerRef.current = null
      return
    }
    if (!layerRef.current) {
      layerRef.current = new HeatLayer(points, {
        radius: 35,
        blur: 25,
        maxZoom: 11,
        max: 1,
        gradient: HEAT_GRADIENT,
      }).addTo(map)
    } else {
      layerRef.current.setLatLngs(points)
    }
  }, [map, points])

  useEffect(
    () => () => {
      layerRef.current?.remove()
      layerRef.current = null
    },
    [map],
  )
  return null
}

export default function MapView({ routes, selectedId, onSelect, heatEnabled, heatHour }) {
  const selected = routes.find((r) => r.route_id === selectedId) ?? routes[0]

  const heatPoints = useMemo(() => {
    if (!heatEnabled || !selected) return null
    return selected.checkpoints.map((cp) => {
      const level = cp.hourly_levels[heatHour]
      // Intensity grows with the risk score; hours without data contribute nothing.
      const intensity = level === null || level === undefined ? 0 : 0.2 + level * 0.2
      return [cp.lat, cp.lon, intensity]
    })
  }, [heatEnabled, selected, heatHour])

  const origin = selected?.geometry[0]
  const destination = selected?.geometry[selected.geometry.length - 1]

  return (
    <MapContainer center={[39.5, -98.35]} zoom={5} className="map">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        className="map-tiles"
      />
      <FitToRoutes routes={routes} />

      {routes.map((route, index) => {
        const isSelected = route.route_id === selected?.route_id
        return (
          <Polyline
            key={route.route_id}
            positions={route.geometry}
            pathOptions={{
              color: ROUTE_COLORS[index % ROUTE_COLORS.length],
              weight: isSelected ? 6 : 3,
              opacity: isSelected ? 0.95 : 0.45,
            }}
            eventHandlers={{ click: () => onSelect(route.route_id) }}
          />
        )
      })}

      {selected && (
        <>
          {selected.checkpoints.map((cp) => (
            <CircleMarker
              key={cp.index}
              center={[cp.lat, cp.lon]}
              radius={6}
              pathOptions={{ color: '#07090c', weight: 2, fillColor: riskColor(cp.risk_level), fillOpacity: 1 }}
            >
              <Popup>
                <strong>Mile {cp.mile}</strong>
                <br />
                ETA: {formatEta(cp.eta)} UTC
                <br />
                Wind {cp.wind_mph} mph · Rain {cp.rain_in_hr} in/h · Snow {cp.snow_in_hr} in/h
                <br />
                Risk: <strong>{cp.risk_level}</strong>
              </Popup>
            </CircleMarker>
          ))}
          {origin && (
            <CircleMarker center={origin} radius={9} pathOptions={{ color: '#fff', weight: 3, fillColor: '#07090c', fillOpacity: 1 }}>
              <Popup>Origin</Popup>
            </CircleMarker>
          )}
          {destination && (
            <CircleMarker center={destination} radius={9} pathOptions={{ color: '#fff', weight: 3, fillColor: '#fff', fillOpacity: 1 }}>
              <Popup>Destination</Popup>
            </CircleMarker>
          )}
        </>
      )}

      <HeatOverlay points={heatPoints} />

      <div className="legend leaflet-bottom leaflet-right">
        {RISK_LEVELS.map((level) => (
          <span key={level}>
            <i style={{ background: riskColor(level) }} /> {level}
          </span>
        ))}
      </div>
    </MapContainer>
  )
}
