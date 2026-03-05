import hashlib
import re
from datetime import date, datetime
from html import unescape
from typing import Any
from sqlalchemy.exc import IntegrityError


import feedparser
from sqlalchemy.orm import Session

from models import Signal
from feeds import FEEDS


_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"\b[\w'-]+\b")

HIGH_SIGNAL_TERMS = {
    "exclusive",
    "record",
    "first",
    "first-ever",
    "breakthrough",
    "acquisition",
    "merger",
    "investment",
    "funding",
    "flagship",
    "launch",
    "debut",
    "expansion",
    "partnership",
    "collaboration",
    "limited",
    "limited-edition",
    "private sale",
    "auction",
}

NOISE_TERMS = {
    "roundup",
    "gallery",
    "lookbook",
    "best of",
    "gift guide",
    "week in review",
    "weekly recap",
}

SOURCE_TRUST = {
    "luxury daily": 0.82,
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


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


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _source_trust_score(source_name: str) -> float:
    lower = (source_name or "").lower()
    for k, v in SOURCE_TRUST.items():
        if k in lower:
            return v
    return 0.7


def _recency_score(iso_date: str) -> float:
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except Exception:
        return 0.55

    days_old = (date.today() - d).days
    if days_old <= 2:
        return 0.9
    if days_old <= 7:
        return 0.82
    if days_old <= 21:
        return 0.72
    if days_old <= 45:
        return 0.62
    if days_old <= 90:
        return 0.54
    return 0.46


def _term_hits(text: str, terms: set[str]) -> int:
    lower = text.lower()
    return sum(1 for t in terms if t in lower)


def _truncate_words(text: str, max_words: int = 18) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip() + "..."


def _token_set(text: str) -> set[str]:
    return {
        w.lower()
        for w in _WORD_RE.findall(text)
        if len(w) > 2 and w.lower() not in STOPWORDS
    }


def _overlap_ratio(a: str, b: str) -> float:
    sa = _token_set(a)
    sb = _token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, min(len(sa), len(sb)))


def _extract_keywords(text: str, limit: int = 2) -> list[str]:
    out: list[str] = []
    for w in _WORD_RE.findall((text or "").lower()):
        if len(w) < 4 or w in STOPWORDS:
            continue
        if w not in out:
            out.append(w)
        if len(out) >= limit:
            break
    return out


def _small_ai_blurb(title: str, raw_summary: str, theme: str) -> str:
    t = (title or "").strip()
    s = (raw_summary or "").strip()
    if not s:
        s = "No summary available."

    # Remove duplicate title prefix patterns often seen in RSS snippets.
    s_lower = s.lower()
    t_lower = t.lower()
    if s_lower.startswith(t_lower):
        s = s[len(t):].lstrip(" :-–—|")

    # Prefer a short sentence that isn't too similar to title.
    candidates = [x.strip() for x in re.split(r"[.!?;]\s+", s) if x.strip()]
    for c in candidates:
        if len(c.split()) < 6:
            continue
        if _overlap_ratio(c, t) < 0.65:
            return _truncate_words(c, 18)

    # Fallback: synthesize a compact selling point.
    kws = _extract_keywords(f"{t} {s}", limit=2)
    topic = " / ".join(kws) if kws else "this move"
    if theme == "Finance":
        line = f"Why it matters: {topic} may signal capital flow shifts and premium demand."
    elif theme == "Design":
        line = f"Why it matters: {topic} hints at where luxury taste and product direction are heading."
    else:
        line = f"Why it matters: {topic} can shape brand momentum and high-value client attention."
    return _truncate_words(line, 18)


def _specificity_score(title: str) -> float:
    words = _WORD_RE.findall(title)
    n = len(words)
    has_number = bool(re.search(r"\b\d+(?:\.\d+)?\b", title))
    has_colon = ":" in title

    # Better scores for concrete but concise titles.
    score = 0.55
    if 6 <= n <= 16:
        score += 0.2
    elif n >= 4:
        score += 0.1
    if has_number:
        score += 0.08
    if has_colon:
        score += 0.05
    return _clamp(score, 0.35, 0.95)


def _summary_quality_score(summary: str) -> float:
    s = (summary or "").strip().lower()
    if not s or s == "no summary available.":
        return 0.42

    words = _WORD_RE.findall(s)
    n = len(words)
    if n >= 70:
        return 0.86
    if n >= 40:
        return 0.77
    if n >= 20:
        return 0.68
    if n >= 8:
        return 0.58
    return 0.5


def _signal_strength_score(title: str, summary: str) -> float:
    text = f"{title} {summary}".lower()
    pos_hits = _term_hits(text, HIGH_SIGNAL_TERMS)
    neg_hits = _term_hits(text, NOISE_TERMS)

    # Each positive hit nudges confidence up; noisy patterns reduce it.
    raw = 0.58 + (0.07 * min(pos_hits, 4)) - (0.06 * min(neg_hits, 3))
    return _clamp(raw, 0.35, 0.92)


def _compute_confidence(title: str, summary: str, source_name: str, iso_date: str) -> float:
    source = _source_trust_score(source_name)
    recency = _recency_score(iso_date)
    specificity = _specificity_score(title)
    summary_quality = _summary_quality_score(summary)
    signal_strength = _signal_strength_score(title, summary)

    # Weighted blend tuned to produce clearer separation across items.
    blended = (
        (0.18 * source)
        + (0.24 * recency)
        + (0.2 * specificity)
        + (0.26 * signal_strength)
        + (0.12 * summary_quality)
    )

    # Stable per-item micro-adjustment avoids visible score bunching.
    # Range: roughly [-0.08, +0.08], deterministic for a given title/source.
    salt = hashlib.sha1(f"{title}|{source_name}".encode("utf-8")).hexdigest()[:4]
    jitter = ((int(salt, 16) / 0xFFFF) - 0.5) * 0.16

    # Expand around center so cards don't cluster tightly around one value.
    expanded = 0.62 + ((blended - 0.62) * 1.25)
    return round(_clamp(expanded + jitter, 0.32, 0.95), 2)


def _classify_rarity(confidence: float, title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    rare_markers = {
        "record",
        "first",
        "first-ever",
        "exclusive",
        "breakthrough",
        "limited-edition",
        "private sale",
    }
    rare_hits = _term_hits(text, rare_markers)

    if confidence >= 0.8 or rare_hits >= 2:
        return "Rare"
    if confidence >= 0.65 or rare_hits >= 1:
        return "Uncommon"
    return "Common"


def ingest_rss(db: Session, per_feed_limit: int = 12) -> dict[str, Any]:
    inserted = 0
    updated = 0
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
            raw_summary = _clean_text(summary_raw)[:600]
            summary = _small_ai_blurb(title, raw_summary, theme)

            iso_date = _to_iso_date(entry)

            # Create a stable ID so we can avoid duplicates
            signal_id = _make_id(link, title)

            confidence = _compute_confidence(title, raw_summary, source_name, iso_date)
            rarity = _classify_rarity(confidence, title, raw_summary)

            # Skip if already exists (by id) OR if same URL already inserted
            existing_by_id = db.get(Signal, signal_id)
            if existing_by_id is not None:
                existing_by_id.title = title
                existing_by_id.theme = theme
                existing_by_id.rarity = rarity
                existing_by_id.confidence = confidence
                existing_by_id.date = iso_date
                existing_by_id.summary = summary or "No summary available."
                existing_by_id.source = source_name
                existing_by_id.url = link or ""
                updated += 1
                continue

            if link:
                existing_by_url = db.query(Signal).filter(Signal.url == link).first()
                if existing_by_url is not None:
                    existing_by_url.title = title
                    existing_by_url.theme = theme
                    existing_by_url.rarity = rarity
                    existing_by_url.confidence = confidence
                    existing_by_url.date = iso_date
                    existing_by_url.summary = summary or "No summary available."
                    existing_by_url.source = source_name
                    existing_by_url.url = link
                    updated += 1
                    continue

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
    return {
        "ok": True,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }
