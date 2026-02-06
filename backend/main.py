from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, case
from ingest import ingest_rss
from events_scrape import fetch_events

from db import get_db
from models import Signal, SavedSignal

app = FastAPI(title="Luxury Briefing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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

@app.get("/signals")
def signals(
    theme: str | None = None,
    q: str | None = None,
    sort: str | None = None,   # <-- NEW
    db: Session = Depends(get_db),
):
    query = db.query(Signal)

    if theme and theme != "All":
        query = query.filter(Signal.theme == theme)

    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(Signal.title.ilike(like), Signal.summary.ilike(like)))

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

    return [
        {
            "id": r.id,
            "title": r.title,
            "theme": r.theme,
            "rarity": r.rarity,
            "confidence": r.confidence,
            "date": r.date,
            "summary": r.summary,
            "source": r.source,
            "url": r.url,
        }
        for r in rows
    ]

@app.get("/saved")
def list_saved(db: Session = Depends(get_db)):
    rows = (
        db.query(Signal)
        .join(SavedSignal, SavedSignal.signal_id == Signal.id)
        .order_by(SavedSignal.saved_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "theme": r.theme,
            "rarity": r.rarity,
            "confidence": r.confidence,
            "date": r.date,
            "summary": r.summary,
            "source": r.source,
            "url": r.url,
        }
        for r in rows
    ]

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
