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

function App() {
  // items: the full list from GET /items, used to populate the dropdown.
  const [items, setItems] = useState([])
  // selectedItem: which currency the user has picked (just the name).
  const [selectedItem, setSelectedItem] = useState('')
  // history: the price history points for whichever item is selected.
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Runs once when the component first mounts (empty dependency array
  // means "only run on first render, not on every re-render").
  useEffect(() => {
    fetch(`${API_BASE_URL}/items`)
      .then((response) => {
        if (!response.ok) throw new Error(`Request failed: ${response.status}`)
        return response.json()
      })
      .then((data) => {
        setItems(data)
        // Default to the first item alphabetically so the chart isn't
        // empty on first load.
        if (data.length > 0) {
          setSelectedItem(data[0].name)
        }
      })
      .catch((err) => setError(err.message))
  }, [])

  // Runs whenever `selectedItem` changes - including the first time it
  // gets set above, once the items list has loaded.
  useEffect(() => {
    if (!selectedItem) return

    setLoading(true)
    setError(null)

    fetch(`${API_BASE_URL}/items/${encodeURIComponent(selectedItem)}/history`)
      .then((response) => {
        if (!response.ok) throw new Error(`Request failed: ${response.status}`)
        return response.json()
      })
      .then((data) => {
        // Reshape into what Recharts wants: a flat array of objects.
        // Also format the timestamp into something readable on the
        // x-axis instead of a full ISO string.
        const points = data.points.map((point) => ({
          time: new Date(point.collected_at).toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          }),
          primary_value: point.primary_value,
        }))
        setHistory(points)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedItem])

  return (
    <div className="app">
      <h1>Market Pulse</h1>
      <p className="subtitle">Live price tracking for tradeable virtual assets</p>

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
              {item.name} ({item.latest_primary_value?.toFixed(4) ?? 'N/A'}{' '}
              {item.primary_currency ?? ''})
            </option>
          ))}
        </select>
      </div>

      {loading && <p>Loading history...</p>}

      {!loading && history.length > 0 && (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="primary_value"
                stroke="#8884d8"
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {!loading && history.length === 0 && selectedItem && (
        <p>No history yet for {selectedItem}.</p>
      )}
    </div>
  )
}

export default App