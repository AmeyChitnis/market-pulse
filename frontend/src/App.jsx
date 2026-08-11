import { useState, useEffect, useRef } from 'react'
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
const API_BASE_URL = ''

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

// Which game the user picked, remembered across reloads so the modal
// only interrupts on a genuinely first visit.
const GAME_STORAGE_KEY = 'marketpulse.game'

// The category the three reference currencies live in. Both games use
// this same category name for it.
const CURRENCY_CATEGORY = 'Currency'

function GameSelectModal({ games, onSelect }) {
  return (
    <div className="game-modal-backdrop">
      <div className="game-modal">
        <h2 className="game-modal-title">Choose a game</h2>
        <p className="game-modal-subtitle">
          Prices are tracked separately for each game. You can switch later.
        </p>
        <div className="game-modal-options">
          {games.map((g) => (
            <button
              key={g.game}
              className="game-modal-btn"
              onClick={() => onSelect(g.game)}
            >
              <span className="game-modal-btn-label">{g.label}</span>
              <span className="game-modal-btn-league">{g.league}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// Each currency (chaos/exalted/divine) is itself a tracked item with its
// own icon - rather than hardcoding separate icon URLs, look the
// currency up by name and reuse its image_url.
//
// NOTE: this deliberately searches a SEPARATE currencyItems list, not the
// main items list. Once the item list is filtered to a category, the
// reference currencies are no longer in it - so searching `items` would
// make the currency icons vanish the moment you selected Scarabs.
function findCurrencyItem(currencyItems, currencyCode) {
  const label = currencyLabel(currencyCode)
  return currencyItems.find((i) => i.name === label)
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

// Section tabs across the top, categories underneath. Mirrors how
// poe.ninja groups its own sidebar. Both rows are driven by
// GET /categories, which reads config.yaml - so re-grouping a category
// is a YAML edit, not a frontend change.
function CategoryNav({
  sections,
  selectedSection,
  selectedCategory,
  counts,
  onSelectSection,
  onSelectCategory,
}) {
  const activeSection = sections.find((s) => s.name === selectedSection)

  if (sections.length === 0) return null

  return (
    <div className="category-nav">
      <div className="category-sections">
        {sections.map((section) => (
          <button
            key={section.name}
            className={
              section.name === selectedSection
                ? 'section-btn active'
                : 'section-btn'
            }
            onClick={() => onSelectSection(section.name)}
          >
            {section.name}
          </button>
        ))}
      </div>

      <div className="category-list">
        {activeSection?.categories.map((category) => (
          <button
            key={category.type}
            className={
              category.type === selectedCategory
                ? 'category-btn active'
                : 'category-btn'
            }
            onClick={() => onSelectCategory(category.type)}
          >
            {category.label}
            {counts[category.type] != null && (
              <span className="category-count">{counts[category.type]}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

// Score how well an item name matches the typed query. Higher is better;
// -1 means no match at all.
//
// Plain substring matching covers more than it looks like it would,
// because the query can span a word boundary: "y mem" matches
// "A Dust(y Mem)ory" directly. The token pass below is only there for
// out-of-order queries like "memory dusty", which substring can't catch.
//
// Deliberately NOT a fuzzy/subsequence match: on 394 divination cards,
// subsequence matching returns almost everything for short queries and
// the ranking stops meaning anything.
function scoreMatch(name, query) {
  const q = query.toLowerCase().trim()
  if (!q) return 0

  const n = name.toLowerCase()

  if (n.startsWith(q)) return 3        // "a dus" -> A Dusty Memory
  if (n.includes(q)) return 2          // "y mem" -> A Dusty Memory

  const tokens = q.split(/\s+/)
  if (tokens.length > 1 && tokens.every((t) => n.includes(t))) return 1

  return -1
}

function ItemPicker({ items, selectedItem, onSelect }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [highlight, setHighlight] = useState(0)
  const [hoveredItem, setHoveredItem] = useState(null)
  const [hoverPosition, setHoverPosition] = useState({ top: 0, left: 0 })

  const containerRef = useRef(null)
  const inputRef = useRef(null)

  const selected = items.find((i) => i.name === selectedItem)

  // Rank matches, then fall back to alphabetical within the same score so
  // the ordering is stable and doesn't jump around as you type.
  const visibleItems = items
    .map((item) => ({ item, score: scoreMatch(item.name, query) }))
    .filter(({ score }) => score >= 0)
    .sort((a, b) => b.score - a.score || a.item.name.localeCompare(b.item.name))
    .map(({ item }) => item)

  // Close when clicking anywhere outside. Needed now that the menu holds a
  // text input - without it, clicking away leaves the menu covering the
  // chart with no obvious way to dismiss it.
  useEffect(() => {
    if (!open) return

    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false)
        setHoveredItem(null)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  // Focus the search box as soon as the menu opens, so you can start
  // typing without a second click.
  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  // A changing filter can leave the highlight past the end of the list.
  useEffect(() => {
    setHighlight(0)
  }, [query])

  const choose = (item) => {
    onSelect(item.name)
    setOpen(false)
    setQuery('')
    setHoveredItem(null)
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      setOpen(false)
      setQuery('')
      return
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setHighlight((h) => Math.min(h + 1, visibleItems.length - 1))
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlight((h) => Math.max(h - 1, 0))
      return
    }
    if (event.key === 'Enter' && visibleItems[highlight]) {
      event.preventDefault()
      choose(visibleItems[highlight])
    }
  }

  const handleMouseEnter = (item, event) => {
    const rect = event.currentTarget.getBoundingClientRect()
    setHoverPosition({ top: rect.top, left: rect.right + 8 })
    setHoveredItem(item)
  }

  return (
    <div className="item-picker" ref={containerRef}>
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
          <div className="item-picker-search">
            <input
              ref={inputRef}
              type="text"
              className="item-picker-search-input"
              placeholder="Search assets..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            {query && (
              <span className="item-picker-search-count">
                {visibleItems.length} of {items.length}
              </span>
            )}
          </div>

          <div className="item-picker-options">
            {visibleItems.map((item, index) => (
              <div
                key={item.id}
                className={
                  index === highlight
                    ? 'item-picker-option highlighted'
                    : 'item-picker-option'
                }
                onMouseEnter={(e) => {
                  setHighlight(index)
                  handleMouseEnter(item, e)
                }}
                onMouseLeave={() => setHoveredItem(null)}
                onClick={() => choose(item)}
              >
                <span className="item-picker-option-name">{item.name}</span>
                <span className="item-picker-option-prices">
                  {item.latest_value_in_chaos?.toFixed(2) ?? 'N/A'}c /{' '}
                  {item.latest_value_in_exalted?.toFixed(2) ?? 'N/A'}ex /{' '}
                  {item.latest_value_in_divine?.toFixed(4) ?? 'N/A'}div
                </span>
              </div>
            ))}

            {visibleItems.length === 0 && (
              <div className="item-picker-empty">
                No assets in this category match "{query}"
              </div>
            )}
          </div>
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
  // Read the stored choice synchronously on first render, so a returning
  // user never sees the modal flash before it loads.
  const [selectedGame, setSelectedGame] = useState(
    () => localStorage.getItem(GAME_STORAGE_KEY) || ''
  )
  const [games, setGames] = useState([])

  // Category navigation, all driven by GET /categories.
  const [sections, setSections] = useState([])
  const [selectedSection, setSelectedSection] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('')
  const [counts, setCounts] = useState({})

  // items: the list for the SELECTED CATEGORY only, used by the picker.
  const [items, setItems] = useState([])
  // currencyItems: the Currency category, kept separately and only for
  // icons. See findCurrencyItem for why this can't share `items`.
  const [currencyItems, setCurrencyItems] = useState([])

  const [selectedItem, setSelectedItem] = useState('')
  // selectedCurrency: which of chaos/exalted/divine the chart is shown
  // in. User-controlled via the picker buttons, so the chart always
  // stays in ONE currency for an item's whole history.
  const [selectedCurrency, setSelectedCurrency] = useState('exalted')
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Which games this backend actually collects. Read from the API rather
  // than hardcoded, so adding a source in config.yaml surfaces here.
  useEffect(() => {
    fetch(`${API_BASE_URL}/games`)
      .then((r) => {
        if (!r.ok) throw new Error(`Request failed: ${r.status}`)
        return r.json()
      })
      .then(setGames)
      .catch((err) => setError(err.message))
  }, [])

  // Category catalog for this game, plus a default selection. Sections
  // arrive in the order they appear in config.yaml, so the UI grouping
  // always matches the file you edit.
  useEffect(() => {
    if (!selectedGame) return

    fetch(`${API_BASE_URL}/categories`)
      .then((r) => {
        if (!r.ok) throw new Error(`Request failed: ${r.status}`)
        return r.json()
      })
      .then((data) => {
        const entry = data.find((d) => d.game === selectedGame)
        const gameSections = entry?.sections ?? []
        setSections(gameSections)

        const firstSection = gameSections[0]
        setSelectedSection(firstSection?.name ?? '')
        setSelectedCategory(firstSection?.categories[0]?.type ?? '')
      })
      .catch((err) => setError(err.message))
  }, [selectedGame])

  // Item counts per category, for the badges on the category buttons.
  // A missing key means zero collected so far, not an error.
  useEffect(() => {
    if (!selectedGame) return

    fetch(`${API_BASE_URL}/items/counts?game=${selectedGame}`)
      .then((r) => (r.ok ? r.json() : {}))
      .then(setCounts)
      .catch(() => setCounts({}))
  }, [selectedGame])

  // The reference currencies, fetched once per game and held apart from
  // the filtered item list purely so their icons stay available.
  useEffect(() => {
    if (!selectedGame) return

    fetch(`${API_BASE_URL}/items?game=${selectedGame}&category=${CURRENCY_CATEGORY}`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setCurrencyItems)
      .catch(() => setCurrencyItems([]))
  }, [selectedGame])

  // The item list for the picker. Refetches whenever the category
  // changes, and resets the selected item - otherwise you'd be charting
  // a Scarab while the picker reads "Oils".
  useEffect(() => {
    if (!selectedGame || !selectedCategory) return

    fetch(
      `${API_BASE_URL}/items?game=${selectedGame}&category=${encodeURIComponent(selectedCategory)}`
    )
      .then((response) => {
        if (!response.ok) throw new Error(`Request failed: ${response.status}`)
        return response.json()
      })
      .then((data) => {
        setItems(data)
        setSelectedItem(data.length > 0 ? data[0].name : '')
        setHistory([])
      })
      .catch((err) => setError(err.message))
  }, [selectedGame, selectedCategory])

  // Runs whenever selectedItem OR selectedCurrency changes - either one
  // changing means we need a fresh history fetch in the right currency.
  useEffect(() => {
    if (!selectedItem) return

    setLoading(true)
    setError(null)

    const url =
      `${API_BASE_URL}/items/${encodeURIComponent(selectedItem)}/history` +
      `?game=${selectedGame}&currency=${selectedCurrency}`

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
  }, [selectedItem, selectedCurrency, selectedGame])

  const handleSelectGame = (game) => {
    // Clear the old game's selection first: item names and categories are
    // per-game, so keeping them would fire requests that 404 or 400.
    setSelectedItem('')
    setHistory([])
    setItems([])
    setSections([])
    setSelectedSection('')
    setSelectedCategory('')
    setSelectedGame(game)
    localStorage.setItem(GAME_STORAGE_KEY, game)
  }

  // Picking a section jumps to its first category, so the item list is
  // never left showing a category from the section you just left.
  const handleSelectSection = (sectionName) => {
    setSelectedSection(sectionName)
    const section = sections.find((s) => s.name === sectionName)
    setSelectedCategory(section?.categories[0]?.type ?? '')
  }

  const activeGame = games.find((g) => g.game === selectedGame)

  if (!selectedGame) {
    return games.length > 0 ? (
      <GameSelectModal games={games} onSelect={handleSelectGame} />
    ) : (
      <div className="app">
        <p>{error ? `Error: ${error}` : 'Loading...'}</p>
      </div>
    )
  }

  return (
    <div className="app">
      <div className="game-bar">
        <span className="game-bar-current">
          {activeGame ? `${activeGame.label} — ${activeGame.league}` : selectedGame}
        </span>
        <button className="game-bar-switch" onClick={() => handleSelectGame('')}>
          Switch game
        </button>
      </div>

      <div className="app-header">
        <h1>Market Pulse</h1>
        <p className="subtitle">Live price tracking for tradeable virtual assets</p>
        <p className="project-blurb">
          A small full-stack project tracking Path of Exile's in-game item and
          currency prices over time, used here as a free, fast-moving real-world
          dataset for practicing data collection, time-series storage, and API
          design.
        </p>
      </div>

      {error && <p className="error">Error: {error}</p>}

      <CategoryNav
        sections={sections}
        selectedSection={selectedSection}
        selectedCategory={selectedCategory}
        counts={counts}
        onSelectSection={handleSelectSection}
        onSelectCategory={setSelectedCategory}
      />

      <div className="controls">
        <label>Asset: </label>
        <ItemPicker
          items={items}
          selectedItem={selectedItem}
          onSelect={setSelectedItem}
        />

        {(() => {
          const selected = items.find((i) => i.name === selectedItem)
          const currencyItem = findCurrencyItem(currencyItems, selectedCurrency)
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
          const currencyItem = findCurrencyItem(currencyItems, c.code)
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

      {!loading && items.length === 0 && selectedCategory && (
        <p>Nothing collected yet for {selectedCategory}.</p>
      )}
    </div>
  )
}

export default App
