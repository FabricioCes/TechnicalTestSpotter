import { riskColor } from '../risk'

export default function CheckpointTable({ route }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Mile</th>
            <th>ETA (UTC)</th>
            <th>Wind</th>
            <th>Rain</th>
            <th>Snow</th>
            <th>Risk</th>
          </tr>
        </thead>
        <tbody>
          {route.checkpoints.map((cp) => (
            <tr key={cp.index}>
              <td>{cp.mile}</td>
              <td>{new Date(cp.eta).toISOString().replace('T', ' ').slice(0, 16)}</td>
              <td>{cp.wind_mph} mph</td>
              <td>{cp.rain_in_hr} in/h</td>
              <td>{cp.snow_in_hr} in/h</td>
              <td>
                <span className="risk-pill" style={{ background: riskColor(cp.risk_level) }}>
                  {cp.risk_level}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
