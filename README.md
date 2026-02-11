# Luxury Briefing — Full-Stack Demo (React + FastAPI + Postgres)

A luxury intelligence demo for young millionaires: a “signals” feed + curated “watch windows” (auctions/events) with a save-to-vault workflow and light/dark UI themes.

## What it does
- **Signals Feed:** browse short, high-signal briefings, with search/filter/sort
- **Watch Windows:** upcoming auctions/events surfaced as a timeline
- **Vault:** save/unsave items for later
- **Modes:** light/dark theme toggle with background switching

## Tech Stack
**Frontend**
- React + TypeScript (Vite)
- Fetch API
- CSS variables + theme switching (`data-theme`)

**Backend**
- FastAPI (Python)
- SQLAlchemy ORM
- RSS ingestion (`feedparser`) + dedupe/skip logic
- REST endpoints returning JSON

**Database**
- PostgreSQL

**Dev / DevOps**
- Docker + Docker Compose (db + api + web)
- Git (branching, commits)

## Project structure
- `frontend/` — React app (UI, tabs, themes)
- `backend/` — FastAPI app (API, ingestion, DB models)
- `docker-compose.yml` — compose stack for local run

## Run locally (Docker)
> Make sure Docker Desktop is running.

```bash
docker compose up --build
