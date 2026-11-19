import { useState } from 'react'
import AddressInput from './AddressInput'

function defaultDepartureLocal() {
  // One hour from now, formatted for <input type="datetime-local">.
  const date = new Date(Date.now() + 60 * 60 * 1000)
  const offset = date.getTimezoneOffset() * 60000
  return new Date(date - offset).toISOString().slice(0, 16)
}

// Sends a suggestion's coordinates when one was picked, otherwise the typed text.
const toPayload = (field) => field.place ?? field.text.trim()

export default function TripForm({ onSubmit, loading }) {
  const [origin, setOrigin] = useState({ text: '', place: null })
  const [destination, setDestination] = useState({ text: '', place: null })
  const [departureLocal, setDepartureLocal] = useState(defaultDepartureLocal())
  const [loadLb, setLoadLb] = useState(35000)
  const [intervalMiles, setIntervalMiles] = useState(10)

  const handleSubmit = (event) => {
    event.preventDefault()
    onSubmit({
      origin: toPayload(origin),
      destination: toPayload(destination),
      departureLocal,
      loadLb,
      intervalMiles,
    })
  }

  return (
    <form className="trip-form" onSubmit={handleSubmit}>
      <AddressInput
        label="Origin"
        placeholder="9 Hi River Road, Barnstable, MA"
        value={origin}
        onChange={setOrigin}
        required
      />
      <AddressInput
        label="Destination"
        placeholder="Salt Lake City, UT"
        value={destination}
        onChange={setDestination}
        required
      />
      <label>
        Departure
        <input required type="datetime-local" value={departureLocal} onChange={(e) => setDepartureLocal(e.target.value)} />
      </label>
      <label>
        Load weight (lb)
        <input
          required
          type="number"
          min="1"
          max="200000"
          step="any"
          value={loadLb}
          onChange={(e) => setLoadLb(e.target.value)}
        />
      </label>
      <label>
        Checkpoint every (miles)
        <select value={intervalMiles} onChange={(e) => setIntervalMiles(e.target.value)}>
          <option value="10">10</option>
          <option value="25">25</option>
          <option value="50">50</option>
        </select>
      </label>
      <button type="submit" disabled={loading}>
        {loading ? 'Planning…' : 'Plan routes'}
      </button>
    </form>
  )
}
