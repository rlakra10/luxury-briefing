import hashlib
import re
from datetime import datetime
from html import unescape
from typing import Any
from sqlalchemy.exc import IntegrityError


import feedparser
from sqlalchemy.orm import Session

from models import Signal
from feeds import FEEDS


_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(x: str | None) -> str:
    if not x:
        return ""
    x = unescape(x)
    x = _TAG_RE.sub("", x)  # strip HTML tags
    x = re.sub(r"\s+", " ", x).strip()
    return x


def _to_iso_date(entry: dict[str, Any]) -> str:
    # feedparser gives published_parsed/updated_parsed as time.struct_time
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if t:
        dt = datetime(t.tm_year, t.tm_mon, t.tm_mday)
        return dt.date().isoformat()
    # fallback: today
    return datetime.utcnow().date().isoformat()


def _make_id(link: str, title: str) -> str:
    base = (link or title).encode("utf-8")
    h = hashlib.sha1(base).hexdigest()[:12]
    return f"rss_{h}"


def ingest_rss(db: Session, per_feed_limit: int = 12) -> dict[str, Any]:
    inserted = 0
    skipped = 0
    errors: list[str] = []

    for feed in FEEDS:
        feed_url = feed["url"]
        theme = feed.get("theme", "General")
        source_name = feed.get("name", "RSS")

        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            errors.append(f"{source_name}: parse error: {e}")
            continue

        entries = parsed.entries[:per_feed_limit]

        for entry in entries:
            link = (entry.get("link") or "").strip()
            title = _clean_text(entry.get("title", ""))[:240]
            if not title:
                skipped += 1
                continue

            # Prefer summary/description
            summary_raw = entry.get("summary") or entry.get("description") or ""
            summary = _clean_text(summary_raw)[:600]

            iso_date = _to_iso_date(entry)

            # Create a stable ID so we can avoid duplicates
            signal_id = _make_id(link, title)

            # Skip if already exists (by id) OR if same URL already inserted
            if db.get(Signal, signal_id) is not None:
                skipped += 1
                continue

            if link:
                existing_by_url = db.query(Signal).filter(Signal.url == link).first()
                if existing_by_url is not None:
                    skipped += 1
                    continue

            # Simple heuristics for MVP
            confidence = 0.65
            rarity = "Common"
            if any(k in title.lower() for k in ["exclusive", "record", "first", "breakthrough"]):
                rarity = "Uncommon"
                confidence = 0.7

            s = Signal(
                id=signal_id,
                title=title,
                theme=theme,
                rarity=rarity,
                confidence=confidence,
                date=iso_date,
                summary=summary or "No summary available.",
                source=source_name,
                url=link or "",
            )

            # Use a SAVEPOINT so one duplicate doesn’t kill the whole ingest
            try:
                with db.begin_nested():   # SAVEPOINT
                    db.add(s)
                    db.flush()            # forces the INSERT now (so we catch duplicates here)
                inserted += 1
            except IntegrityError:
                skipped += 1


    db.commit()
    return {"ok": True, "inserted": inserted, "skipped": skipped, "errors": errors}
