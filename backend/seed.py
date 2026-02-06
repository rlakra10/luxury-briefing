from sqlalchemy.orm import Session
from db import SessionLocal
from models import Signal

DEMO_SIGNALS = [
    {
        "id": "sig_001",
        "title": "Quiet luxury shifts toward tactile materials",
        "theme": "Design",
        "rarity": "Rare",
        "confidence": 0.78,
        "date": "2026-02-01",
        "summary": "A short signal showing the style of content we’ll serve.",
        "source": "Demo Briefing",
        "url": "https://example.com/quiet-luxury-materials"
    },
    {
        "id": "sig_002",
        "title": "Private markets: new infrastructure narratives",
        "theme": "Finance",
        "rarity": "Uncommon",
        "confidence": 0.72,
        "date": "2026-01-28",
        "summary": "Another demo signal for the feed UI.",
        "source": "Demo Briefing",
        "url": "https://example.com/private-markets-infrastructure"
    },
    {
    "id": "sig_003",
    "title": "Ultra-high confidence signal (older date)",
    "theme": "Finance",
    "rarity": "Common",
    "confidence": 0.95,
    "date": "2026-01-10",
    "summary": "Older, but very high confidence to test confidence sorting.",
    "source": "Demo Briefing",
    "url": "https://example.com/high-confidence",
},
{
    "id": "sig_004",
    "title": "Very rare signal (low confidence, mid date)",
    "theme": "Design",
    "rarity": "Rare",
    "confidence": 0.40,
    "date": "2026-01-20",
    "summary": "Rare but low confidence to test rarity sorting vs confidence sorting.",
    "source": "Demo Briefing",
    "url": "https://example.com/very-rare-low-confidence",
},

]

def upsert_signals(db: Session):
    for s in DEMO_SIGNALS:
        existing = db.get(Signal, s["id"])
        if existing:
            for k, v in s.items():
                setattr(existing, k, v)
        else:
            db.add(Signal(**s))
    db.commit()

def main():
    db = SessionLocal()
    try:
        upsert_signals(db)
        print("seeded")
    finally:
        db.close()

if __name__ == "__main__":
    main()
