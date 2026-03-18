# Luxury Briefing

Luxury Briefing is a full-stack luxury-intelligence demo: a feed of scored market signals, a personal vault, and curated watch windows for auctions and events.

## What It Does

- Signals feed with search, theme filter, and sort by newest, confidence, or rarity
- Drawer-based article briefing with:
  - short card summary
  - richer briefing summary
  - key takeaways
  - extracted entities
  - freshness diagnostics
- Vault workflow for saving and unsaving signals
- Watch Windows timeline for upcoming events
- Light and dark UI themes

## Stack

### Frontend

- React
- TypeScript
- Vite
- CSS-only theming and glass UI treatment

### Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- RSS ingestion via `feedparser`

### Local Dev

- Docker Compose for database / full-stack container runs
- Python `venv` for local backend execution

## Project Structure

- `frontend/` — React app
- `backend/` — FastAPI app, models, ingest, event scraping
- `docker-compose.yml` — local container stack

## Prerequisites

- Node.js 18+
- Python 3.11+
- Docker Desktop or a local PostgreSQL instance
- `npm` available in the shell

## Run Locally

### Option A: Local Backend + Docker Postgres

From the repository root:

1. Start Postgres:

```bash
docker compose up -d db
```

2. Start backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If a virtual environment already exists, activate that instead of creating a new one.

3. In a second terminal, start frontend:

```bash
cd frontend
npm install
npm run dev
```

4. Open the local URL printed by Vite in the terminal.

This is usually:

```text
http://127.0.0.1:5173
```

but it may differ if that port is already in use.

### Option B: Full Docker

From the repository root:

```bash
docker compose up --build
```

Then open the frontend URL exposed by the compose stack on your machine.

## Enrichment Workflow

The backend enriches each signal during ingest with:

- confidence score
- rarity classification
- short card summary
- richer briefing summary
- key takeaways
- extracted entities
- freshness status

If you change ingest logic or add new signal fields, restart the backend and re-run ingest:

```bash
curl -sS -X POST "http://127.0.0.1:8000/ingest"
```

If the API is running on a different host or port, use that base URL instead.

## API Endpoints

- `GET /health`
- `GET /themes`
- `GET /signals`
- `GET /saved`
- `POST /save/{signal_id}`
- `DELETE /save/{signal_id}`
- `POST /ingest`
- `GET /events`
- `GET /events/curated`

## Notes

- Freshness is derived from article date:
  - `Fresh`: 0-3 days
  - `Recent`: 4-14 days
  - `Aging`: 15-30 days
  - `Stale`: 31+ days
- Existing databases are updated on backend startup with the required signal columns.
- If you run the backend locally, make sure the frontend points at the correct API base URL via `VITE_API_BASE` when needed.
