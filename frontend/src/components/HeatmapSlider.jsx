export default function HeatmapSlider({ hours, value, onChange, departure, enabled, onToggle }) {
  const moment = new Date(new Date(departure).getTime() + value * 3600 * 1000)
  return (
    <div className="heat-controls">
      <label className="toggle">
        <input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} />
        Weather heatmap
      </label>
      <label className="slider">
        <span>
          Forecast +{value} h <small>({moment.toISOString().replace('T', ' ').slice(0, 16)} UTC)</small>
        </span>
        <input
          type="range"
          min="0"
          max={hours}
          step="1"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          disabled={!enabled}
        />
      </label>
    </div>
  )
}
