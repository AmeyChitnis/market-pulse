# Market Pulse
 
A time-series market analytics tool: it collects price snapshots for a
set of tradeable assets, stores them over time, and serves price history
through a REST API and a React dashboard.
 
The dataset used for this build is the in-game currency economy of
*Path of Exile 2* (via the public [poe.ninja](https://poe.ninja) API),
but the system is built the way you'd build a tracker for any market
with frequent, freely-available price updates — stocks, crypto,
commodities, or collectibles. Swapping the data source means writing a
new collector client; the storage, scheduling, API, and dashboard
layers don't change.
 
## Why this dataset
 
Real historical price feeds (stocks, crypto) are usually paywalled or
rate-limited. Game economies publish live pricing data publicly and
change meaningfully over short windows, which makes them a surprisingly
good free proxy for practicing real market-data engineering: API
integration, scheduled ingestion, time-series storage, and dashboarding.
 
## Architecture
 
```
poe.ninja (external API)
        │  fetch every 10 minutes (APScheduler)
        ▼
FastAPI collector ──► SQLite (price snapshots: chaos / exalted / divine)
        ▲
        │  GET /items, GET /items/{name}/history?currency=...&hours=...
        │
React dashboard (asset picker, currency picker, price chart)
```
 
## Stack
 
- **Backend**: FastAPI, SQLite, SQLAlchemy, APScheduler (periodic collection), httpx
- **Frontend**: React (Vite), Recharts
- **Data source**: poe.ninja's public PoE2 economy API
## Project structure
 
```
backend/
  app/
    main.py             # FastAPI app entrypoint, CORS, scheduler lifecycle
    config.py           # Settings (league, collection interval) from .env
    database.py         # SQLAlchemy engine/session setup
    schemas.py          # Pydantic response models
    models/              # ORM models (Item, PriceSnapshot)
    routers/              # API route handlers (health, collection, items)
    services/
      poe_ninja_client.py   # Fetches + parses poe.ninja's API
      collector.py           # Persists parsed data to the database
      scheduler.py            # Runs the collector on a timer
  ml/                    # Exploratory feature engineering / model training
                           # scripts (CatBoost), parked pending more history
  inspect_db.py          # Manual database inspection helper
frontend/
  src/
    App.jsx             # Main dashboard: asset + currency pickers, chart
    App.css             # Styling
```
 
## Status
 
Working end-to-end: live data collection every 10 minutes, a queryable
REST API, and a dashboard for browsing price history by currency. The
`ml/` folder holds a feature-engineering and CatBoost-training pipeline
that's functionally complete but intentionally paused until enough
collection history has accumulated to train on meaningfully — see that
folder's docstrings for specifics.
 
## Getting started
 
### Backend
 
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env         # then check POE_LEAGUE is still current
uvicorn app.main:app --reload
```
 
Visit `http://localhost:8000/docs` for interactive API docs.
 
### Frontend
 
```bash
cd frontend
npm install
npm run dev
```
 
Visit `http://localhost:5173`. The frontend expects the backend running
at `http://localhost:8000`.
 
### Notes
 
- PoE2's league name changes every few months (a new "league" launches
  with each content patch). Check the current one directly against
  poe.ninja's site if data collection starts failing — see the comments
  in `app/services/poe_ninja_client.py` for how to verify this against
  live network traffic rather than trusting search results, which have
  repeatedly been stale for this particular API.
- The scheduler only runs while `uvicorn` is running and the process
  hasn't been interrupted (machine sleep, `--reload` restarts, etc. all
  reset its timer). For continuous collection, keep the backend process
  running.