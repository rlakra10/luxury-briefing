import json
import os

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, case, inspect, text
from ingest import ingest_rss
from events_scrape import fetch_events
from curated_windows import curated_watch_windows
from db import Base, engine
import models  # registers tables


from db import get_db
from models import Signal, SavedSignal


app = FastAPI(title="Luxury Briefing API")

origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/themes")
def themes(db: Session = Depends(get_db)):
    rows = db.query(Signal.theme).distinct().order_by(Signal.theme).all()
    return ["All"] + [r[0] for r in rows]


@app.on_event("startup")
def _startup():
    Base.metadata.create_all(bind=engine)
    _ensure_signal_columns()


def _ensure_signal_columns():
    cols = {col["name"] for col in inspect(engine).get_columns("signals")}
    statements: list[str] = []

    if "briefing_summary" not in cols:
        statements.append("ALTER TABLE signals ADD COLUMN briefing_summary TEXT NOT NULL DEFAULT ''")
    if "key_points_json" not in cols:
        statements.append("ALTER TABLE signals ADD COLUMN key_points_json TEXT NOT NULL DEFAULT '[]'")
    if "entities_json" not in cols:
        statements.append("ALTER TABLE signals ADD COLUMN entities_json TEXT NOT NULL DEFAULT '[]'")
    if "freshness_status" not in cols:
        statements.append("ALTER TABLE signals ADD COLUMN freshness_status VARCHAR NOT NULL DEFAULT 'fresh'")
    if "freshness_age_days" not in cols:
        statements.append("ALTER TABLE signals ADD COLUMN freshness_age_days INTEGER NOT NULL DEFAULT 0")

    if not statements:
        return

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def _json_list(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in data if str(item).strip()]


def _serialize_signal(r: Signal) -> dict[str, object]:
    return {
        "id": r.id,
        "title": r.title,
        "theme": r.theme,
        "rarity": r.rarity,
        "confidence": r.confidence,
        "date": r.date,
        "summary": r.summary,
        "briefing_summary": r.briefing_summary or r.summary,
        "key_points": _json_list(r.key_points_json),
        "entities": _json_list(r.entities_json),
        "source": r.source,
        "freshness_status": r.freshness_status,
        "freshness_age_days": r.freshness_age_days,
        "url": r.url,
    }


@app.get("/signals")
def signals(
    theme: str | None = None,
    q: str | None = None,
    sort: str | None = None,  # <-- NEW
    db: Session = Depends(get_db),
):
    query = db.query(Signal)

    if theme and theme != "All":
        query = query.filter(Signal.theme == theme)

    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Signal.title.ilike(like),
                Signal.summary.ilike(like),
                Signal.briefing_summary.ilike(like),
                Signal.entities_json.ilike(like),
            )
        )

    # Sorting
    if sort == "confidence":
        query = query.order_by(Signal.confidence.desc())
    elif sort == "rarity":
        # Rare -> Uncommon -> Common -> everything else
        rarity_rank = case(
            (Signal.rarity == "Rare", 1),
            (Signal.rarity == "Uncommon", 2),
            (Signal.rarity == "Common", 3),
            else_=9,
        )
        query = query.order_by(rarity_rank.asc(), Signal.date.desc())
    else:
        # default newest (ISO date strings sort correctly)
        query = query.order_by(Signal.date.desc())

    rows = query.all()

    return [_serialize_signal(r) for r in rows]


@app.get("/saved")
def list_saved(db: Session = Depends(get_db)):
    rows = (
        db.query(Signal)
        .join(SavedSignal, SavedSignal.signal_id == Signal.id)
        .order_by(SavedSignal.saved_at.desc())
        .all()
    )
    return [_serialize_signal(r) for r in rows]


@app.post("/save/{signal_id}")
def save_signal(signal_id: str, db: Session = Depends(get_db)):
    s = db.get(Signal, signal_id)
    if not s:
        return {"ok": False, "error": "signal_not_found"}

    existing = db.get(SavedSignal, signal_id)
    if existing:
        return {"ok": True, "saved": True}

    db.add(SavedSignal(signal_id=signal_id))
    db.commit()
    return {"ok": True, "saved": True}


@app.delete("/save/{signal_id}")
def unsave_signal(signal_id: str, db: Session = Depends(get_db)):
    existing = db.get(SavedSignal, signal_id)
    if not existing:
        return {"ok": True, "saved": False}

    db.delete(existing)
    db.commit()
    return {"ok": True, "saved": False}


@app.post("/ingest")
def ingest(db: Session = Depends(get_db)):
    return ingest_rss(db)


@app.get("/events")
def events(days: int = 90):
    return fetch_events(days=days)


@app.get("/events/curated")
def events_curated():
    return {
        "ok": True,
        "count": len(curated_watch_windows()),
        "events": curated_watch_windows(),
    }
