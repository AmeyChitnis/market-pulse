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
import currencyDescriptions from './data/currencyDescriptions.json'

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

// Each currency (chaos/exalted/divine) is itself a tracked item with its
// own icon - rather than hardcoding separate icon URLs, look the
// currency up by name in the already-loaded items list and reuse its
// image_url. Falls back to no icon if that currency isn't in the list
// for some reason (e.g. it hasn't been collected yet).
function findCurrencyItem(items, currencyCode) {
  const label = currencyLabel(currencyCode)
  return items.find((i) => i.name === label)
}

// Format a number compactly for the rate display (e.g. 5012 -> "5.0k"),
// matching the style of poe.ninja's own UI for large values. Small
// values are shown with more decimal precision instead, since "0.0"
// would lose all the information for cheap currencies.
function formatRateValue(value) {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`
  return value.toFixed(2)
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

function ItemHoverCard({ item }) {
  console.log('ITEMHOVERCARD IS RENDERING', item.name)
  return (
    <div className="item-hover-card" style={{ background: 'red', width: '300px', height: '300px', position: 'fixed', top: '50px', left: '50px' }}>
      {item.image_url && (
        <img src={item.image_url} alt={item.name} className="item-hover-icon" />
      )}
      <div className="item-hover-name">{item.name}</div>
    </div>
  )
}

function ItemPicker({ items, selectedItem, onSelect }) {
  const [open, setOpen] = useState(false)
  const [hoveredItem, setHoveredItem] = useState(null)
  const [hoverPosition, setHoverPosition] = useState({ top: 0, left: 0 })

  const selected = items.find((i) => i.name === selectedItem)

  const handleMouseEnter = (item, event) => {
    const rect = event.currentTarget.getBoundingClientRect()
    setHoverPosition({ top: rect.top, left: rect.right + 8 })
    setHoveredItem(item)
  }

  return (
    <div className="item-picker">
      <button
        type="button"
        className="item-picker-trigger"
        onClick={() => setOpen((wasOpen) => !wasOpen)}
      >
        {selected ? selected.name : 'Select an asset'}
        <span className="item-picker-arrow">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="item-picker-menu">
          {items.map((item) => (
            <div
              key={item.id}
              className="item-picker-option"
              onMouseEnter={(e) => handleMouseEnter(item, e)}
              onMouseLeave={() => setHoveredItem(null)}
              onClick={() => {
                onSelect(item.name)
                setOpen(false)
                setHoveredItem(null)
              }}
            >
              <span className="item-picker-option-name">{item.name}</span>
              <span className="item-picker-option-prices">
                {item.latest_value_in_chaos?.toFixed(2) ?? 'N/A'}c /{' '}
                {item.latest_value_in_exalted?.toFixed(2) ?? 'N/A'}ex /{' '}
                {item.latest_value_in_divine?.toFixed(4) ?? 'N/A'}div
              </span>
            </div>
          ))}
        </div>
      )}

      {hoveredItem && (
        <div
          className="item-hover-card"
          style={{ top: hoverPosition.top, left: hoverPosition.left }}
        >
          {hoveredItem.image_url && (
            <img src={hoveredItem.image_url} alt={hoveredItem.name} className="item-hover-icon" />
          )}
          <div className="item-hover-name">{hoveredItem.name}</div>
          {currencyDescriptions[hoveredItem.name] && (
            <div className="item-hover-description">
              <div className="item-hover-descr-text">
                {currencyDescriptions[hoveredItem.name].descrText}
              </div>
              {currencyDescriptions[hoveredItem.name].explicitMods?.map((mod, i) => (
                <div key={i} className="item-hover-mod">
                  {mod}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
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
        <label>Asset: </label>
        <ItemPicker
          items={items}
          selectedItem={selectedItem}
          onSelect={setSelectedItem}
        />

        {(() => {
          const selected = items.find((i) => i.name === selectedItem)
          const currencyItem = findCurrencyItem(items, selectedCurrency)
          const rateValue = selected?.[`latest_value_in_${selectedCurrency}`]

          if (!selected || rateValue == null) return null

          return (
            <div className="rate-display">
              <span className="rate-value">1</span>
              {selected.image_url && (
                <img src={selected.image_url} alt={selected.name} className="rate-icon" />
              )}
              <span className="rate-arrow">⇄</span>
              <span className="rate-value">{formatRateValue(rateValue)}</span>
              {currencyItem?.image_url && (
                <img
                  src={currencyItem.image_url}
                  alt={currencyLabel(selectedCurrency)}
                  className="rate-icon"
                />
              )}
            </div>
          )
        })()}
      </div>

      <div className="currency-picker">
        {CURRENCIES.map((c) => {
          const currencyItem = findCurrencyItem(items, c.code)
          return (
            <button
              key={c.code}
              className={c.code === selectedCurrency ? 'currency-btn active' : 'currency-btn'}
              onClick={() => setSelectedCurrency(c.code)}
            >
              {currencyItem?.image_url && (
                <img src={currencyItem.image_url} alt={c.label} className="currency-btn-icon" />
              )}
              {c.label}
            </button>
          )
        })}
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