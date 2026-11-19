import { useState } from 'react'

function defaultDepartureLocal() {
  // One hour from now, formatted for <input type="datetime-local">.
  const date = new Date(Date.now() + 60 * 60 * 1000)
  const offset = date.getTimezoneOffset() * 60000
  return new Date(date - offset).toISOString().slice(0, 16)
}

export default function TripForm({ onSubmit, loading }) {
  const [form, setForm] = useState({
    origin: '',
    destination: '',
    departureLocal: defaultDepartureLocal(),
    loadLb: 35000,
    intervalMiles: 10,
  })

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  const handleSubmit = (event) => {
    event.preventDefault()
    onSubmit(form)
  }

  return (
    <form className="trip-form" onSubmit={handleSubmit}>
      <label>
        Origin
        <input required value={form.origin} onChange={update('origin')} placeholder="Denver, CO" />
      </label>
      <label>
        Destination
        <input required value={form.destination} onChange={update('destination')} placeholder="Salt Lake City, UT" />
      </label>
      <label>
        Departure
        <input required type="datetime-local" value={form.departureLocal} onChange={update('departureLocal')} />
      </label>
      <label>
        Load weight (lb)
        <input required type="number" min="1" max="200000" step="any" value={form.loadLb} onChange={update('loadLb')} />
      </label>
      <label>
        Checkpoint every (miles)
        <select value={form.intervalMiles} onChange={update('intervalMiles')}>
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
