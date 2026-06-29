import { useState, useEffect } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import './App.css'

// Base URL of the FastAPI backend. Hardcoded for now since this is a
// local-only demo - if this app is ever deployed, this should move to
// an environment variable instead.
const API_BASE_URL = 'http://localhost:8000'

// The three currencies the backend can express prices in. Order here
// controls the order the picker buttons render in.
const CURRENCIES = [
  { code: 'chaos', label: 'Chaos Orb' },
  { code: 'exalted', label: 'Exalted Orb' },
  { code: 'divine', label: 'Divine Orb' },
]

function currencyLabel(code) {
  return CURRENCIES.find((c) => c.code === code)?.label ?? code
}

// Custom tooltip: "For 1 <Item>, pay <value> <Currency>" instead of
// Recharts' default "value: X" text.
function PriceTooltip({ active, payload, label, itemName, currencyCode }) {
  if (!active || !payload || payload.length === 0) return null

  const value = payload[0].value

  return (
    <div className="price-tooltip">
      <div className="price-tooltip-time">{label}</div>
      <div className="price-tooltip-price">
        For 1 {itemName}, pay {value.toFixed(4)} {currencyLabel(currencyCode)}
      </div>
    </div>
  )
}

function App() {
  // items: the full list from GET /items, used to populate the dropdown.
  const [items, setItems] = useState([])
  // selectedItem: which currency the user has picked (just the name).
  const [selectedItem, setSelectedItem] = useState('')
  // selectedCurrency: which of chaos/exalted/divine the chart is shown
  // in. User-controlled via the picker buttons, so the chart always
  // stays in ONE currency for an item's whole history - this is what
  // fixes the fake-looking spikes that happened when the backend used
  // to switch currencies on its own between collection runs.
  const [selectedCurrency, setSelectedCurrency] = useState('exalted')
  // history: the price history points for whichever item is selected.
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Runs once when the component first mounts.
  useEffect(() => {
    fetch(`${API_BASE_URL}/items`)
      .then((response) => {
        if (!response.ok) throw new Error(`Request failed: ${response.status}`)
        return response.json()
      })
      .then((data) => {
        setItems(data)
        if (data.length > 0) {
          setSelectedItem(data[0].name)
        }
      })
      .catch((err) => setError(err.message))
  }, [])

  // Runs whenever selectedItem OR selectedCurrency changes - either one
  // changing means we need a fresh history fetch in the right currency.
  useEffect(() => {
    if (!selectedItem) return

    setLoading(true)
    setError(null)

    const url = `${API_BASE_URL}/items/${encodeURIComponent(selectedItem)}/history?currency=${selectedCurrency}`

    fetch(url)
      .then((response) => {
        if (!response.ok) throw new Error(`Request failed: ${response.status}`)
        return response.json()
      })
      .then((data) => {
        const points = data.points.map((point) => ({
          time: new Date(point.collected_at).toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          }),
          value: point.value,
        }))
        setHistory(points)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedItem, selectedCurrency])

  return (
    <div className="app">
      <div className="app-header">
        <h1>Market Pulse</h1>
        <p className="subtitle">Live price tracking for tradeable virtual assets</p>
        <p className="project-blurb">
          A small full-stack project tracking Path of Exile 2's in-game currency
          exchange rates over time, used here as a free, fast-moving real-world
          dataset for practicing data collection, time-series storage, and API
          design.
        </p>
      </div>

      {error && <p className="error">Error: {error}</p>}

      <div className="controls">
        <label htmlFor="item-select">Asset: </label>
        <select
          id="item-select"
          value={selectedItem}
          onChange={(e) => setSelectedItem(e.target.value)}
        >
          {items.map((item) => (
            <option key={item.id} value={item.name}>
              {item.name} - {item.latest_value_in_chaos?.toFixed(2) ?? 'N/A'}c /{' '}
              {item.latest_value_in_exalted?.toFixed(2) ?? 'N/A'}ex /{' '}
              {item.latest_value_in_divine?.toFixed(4) ?? 'N/A'}div
            </option>
          ))}
        </select>
      </div>

      <div className="currency-picker">
        {CURRENCIES.map((c) => (
          <button
            key={c.code}
            className={c.code === selectedCurrency ? 'currency-btn active' : 'currency-btn'}
            onClick={() => setSelectedCurrency(c.code)}
          >
            {c.label}
          </button>
        ))}
      </div>

      {loading && <p>Loading history...</p>}

      {!loading && history.length > 0 && (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={history} margin={{ top: 10, right: 30, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2e3a" />
              <XAxis
                dataKey="time"
                stroke="#8b8f9c"
                tick={{ fill: '#8b8f9c', fontSize: 12 }}
                label={{ value: 'Time', position: 'insideBottom', offset: -10, fill: '#8b8f9c' }}
              />
              <YAxis
                stroke="#8b8f9c"
                tick={{ fill: '#8b8f9c', fontSize: 12 }}
                label={{
                  value: `Price (${currencyLabel(selectedCurrency)})`,
                  angle: -90,
                  position: 'insideLeft',
                  fill: '#8b8f9c',
                }}
              />
              <Tooltip
                content={
                  <PriceTooltip itemName={selectedItem} currencyCode={selectedCurrency} />
                }
              />
              <Line type="monotone" dataKey="value" stroke="#7c83fb" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {!loading && history.length === 0 && selectedItem && (
        <p>No history yet for {selectedItem} in this currency.</p>
      )}
    </div>
  )
}

export default App