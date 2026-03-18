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
        "briefing_summary": "A demo briefing on tactile-material positioning and its effect on desirability.",
        "key_points_json": "[\"Primary focus: tactile materials.\", \"Watch for influence on product language and desirability.\", \"Scoring: 78% confidence and rare rarity.\", \"Published 45 days ago, so it is better as context than as a lead indicator.\"]",
        "entities_json": "[\"Quiet Luxury\", \"Tactile Materials\"]",
        "source": "Demo Briefing",
        "freshness_status": "stale",
        "freshness_age_days": 45,
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
        "briefing_summary": "A demo briefing on infrastructure narratives and what they imply for premium capital allocation.",
        "key_points_json": "[\"Primary focus: private markets, infrastructure.\", \"Watch for downstream movement in valuation, liquidity, and appetite for premium assets.\", \"Scoring: 72% confidence and uncommon rarity.\", \"Published 49 days ago, so it is better as context than as a lead indicator.\"]",
        "entities_json": "[\"Private Markets\", \"Infrastructure\"]",
        "source": "Demo Briefing",
        "freshness_status": "stale",
        "freshness_age_days": 49,
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
    "briefing_summary": "A demo briefing for confidence sorting behavior.",
    "key_points_json": "[\"Primary focus: confidence sorting.\", \"Watch for downstream movement in valuation, liquidity, and appetite for premium assets.\", \"Scoring: 95% confidence and common rarity.\", \"Published 66 days ago, which makes this a stale source signal.\"]",
    "entities_json": "[\"Confidence Sorting\"]",
    "source": "Demo Briefing",
    "freshness_status": "stale",
    "freshness_age_days": 66,
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
    "briefing_summary": "A demo briefing for rarity sorting behavior.",
    "key_points_json": "[\"Primary focus: rarity sorting.\", \"Watch for influence on product language, materials, and desirability cues.\", \"Scoring: 40% confidence and rare rarity.\", \"Published 56 days ago, which makes this a stale source signal.\"]",
    "entities_json": "[\"Rarity Sorting\"]",
    "source": "Demo Briefing",
    "freshness_status": "stale",
    "freshness_age_days": 56,
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
