# Market Pulse

A time-series market analytics tool: it collects price snapshots for a set
of tradeable assets, stores them over time, and serves trend, volatility,
and "top movers" analytics through a REST API and a React dashboard.

The dataset used for this build is the in-game economy of *Path of Exile*
(via the public [poe.ninja](https://poe.ninja) API), but the system is
built the way you'd build a tracker for any market with frequent,
freely-available price updates — stocks, crypto, commodities, or
collectibles. Swapping the data source means writing a new collector;
the storage, API, and dashboard layers don't change.

## Why this dataset

Real historical price feeds (stocks, crypto) are usually paywalled or
rate-limited. Game economies publish live pricing data publicly and
change meaningfully day to day, which makes them a surprisingly good
free proxy for practicing real market-data engineering: ingestion,
time-series storage, trend/volatility computation, and dashboarding.

## Architecture

```
poe.ninja (external API)
        │  fetch (hourly)
        ▼
FastAPI collector ──► SQLite (price snapshots over time)
        ▲
        │  GET /items, /items/{id}/history, /items/{id}/volatility
        │
React dashboard (search, trend charts, top movers)
```

## Stack

- **Backend**: FastAPI, SQLite, SQLAlchemy, APScheduler (periodic collection)
- **Frontend**: React, Recharts
- **Data source**: poe.ninja public economy API

## Project structure

```
backend/
  app/
    main.py          # FastAPI app entrypoint
    database.py      # SQLAlchemy engine/session setup
    models/          # ORM models (Item, PriceSnapshot)
    routers/          # API route handlers
    services/         # Collector + analytics logic
  tests/
frontend/
  src/
    api/             # API client functions
    components/       # React components
docs/                 # Design notes, API documentation
```

## Status

Early scaffold — see `docs/` for design notes as the project develops.

## Getting started

Setup instructions will be added once the backend dependencies are in place.
