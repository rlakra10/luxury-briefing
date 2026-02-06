import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from html import unescape
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

from events_sources import EVENT_SOURCES


@dataclass
class EventItem:
    id: str
    title: str
    house: str
    start_date: str  # ISO yyyy-mm-dd (best-effort)
    end_date: str  # ISO yyyy-mm-dd (best-effort)
    location: str
    url: str


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome Safari"
)

DATE_RE = re.compile(r"\b(?:\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2})\b")
TAG_RE = re.compile(r"<[^>]+>")


KNOWN_CITIES = [
    "New York",
    "London",
    "Paris",
    "Hong Kong",
    "Geneva",
    "Milan",
    "Los Angeles",
    "Dubai",
    "Singapore",
    "Zurich",
    "Monaco",
    "Amsterdam",
    "Berlin",
]


def _stable_id(house: str, title: str, url: str) -> str:
    raw = f"{house}|{title}|{url}".encode("utf-8")
    h = hashlib.sha1(raw).hexdigest()[:12]
    return f"evt_{h}"


def _to_iso(d: Optional[date]) -> str:
    return d.isoformat() if d else ""


def _parse_date_any(s: str) -> Optional[date]:
    try:
        dt = dtparser.parse(s, fuzzy=True, dayfirst=False)
        return dt.date()
    except Exception:
        return None


def _extract_location(raw: str) -> str:
    s = " ".join(raw.split()).strip()
    for city in KNOWN_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", s):
            return city
    return ""


def _strip_html(s: str) -> str:
    s = unescape(s or "")
    s = TAG_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _polish_title(raw: str) -> str:
    s = _strip_html(raw)

    # Remove common labels (robust)
    s = re.sub(r"(?i)\btype:\s*", " ", s)
    s = re.sub(r"(?i)\bcategory:\s*", " ", s)
    s = re.sub(r"(?i)\bupcoming auction\b", " ", s)
    s = re.sub(r"(?i)\bupcoming\b", " ", s)

    # Remove generic leading words
    s = re.sub(r"(?i)^\s*(auction|sale|exhibition)\b[:\-]?\s*", "", s)

    # Remove time fragments (e.g., 10:00 AM EST)
    s = re.sub(r"\b\d{1,2}:\d{2}\s*(AM|PM)\s*[A-Z]{2,5}\b", " ", s)

    # Remove date fragments (we show start_date separately)
    s = re.sub(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b", " ", s)

    # Remove separators
    s = s.replace("|", " ")

    # Clean spaces
    s = re.sub(r"\s+", " ", s).strip()

    return s[:140] if len(s) > 140 else s


def _extract_jsonld_events(html: str, house: str, base_url: str) -> list[EventItem]:
    soup = BeautifulSoup(html, "lxml")
    items: list[EventItem] = []

    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for sc in scripts:
        txt = (sc.string or "").strip()
        if not txt:
            continue

        try:
            data = json.loads(txt)
        except Exception:
            continue

        candidates: list[Any] = []
        if (
            isinstance(data, dict)
            and "@graph" in data
            and isinstance(data["@graph"], list)
        ):
            candidates = data["@graph"]
        elif isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            candidates = [data]

        for obj in candidates:
            if not isinstance(obj, dict):
                continue

            typ = obj.get("@type") or obj.get("type")
            if isinstance(typ, list):
                typ = typ[0] if typ else None

            if str(typ).lower() not in {"event", "saleevent"}:
                continue

            raw_title = str(obj.get("name") or obj.get("headline") or "").strip()
            if not raw_title:
                continue

            url = str(obj.get("url") or base_url).strip()

            # location from JSON-LD if present
            loc = ""
            location_obj = obj.get("location")
            if isinstance(location_obj, dict):
                loc = str(
                    location_obj.get("name") or location_obj.get("address") or ""
                ).strip()
            elif isinstance(location_obj, str):
                loc = location_obj.strip()

            if not loc:
                loc = _extract_location(raw_title)

            title_clean = _polish_title(raw_title)
            if loc:
                title_clean = re.sub(rf"\b{re.escape(loc)}\b", "", title_clean).strip()
                title_clean = re.sub(r"\s+", " ", title_clean).strip()

            sd = _parse_date_any(str(obj.get("startDate") or ""))
            ed = _parse_date_any(str(obj.get("endDate") or "")) or sd

            items.append(
                EventItem(
                    id=_stable_id(house, title_clean, url),
                    title=title_clean,
                    house=house,
                    start_date=_to_iso(sd),
                    end_date=_to_iso(ed),
                    location=loc[:120],
                    url=url,
                )
            )

    return items


def _extract_fallback_events(html: str, house: str, base_url: str) -> list[EventItem]:
    soup = BeautifulSoup(html, "lxml")
    items: list[EventItem] = []
    seen: set[tuple[str, str]] = set()

    links = soup.find_all("a", href=True)
    for a in links:
        href = a.get("href", "").strip()
        text = " ".join(a.get_text(" ", strip=True).split())
        if not text or len(text) < 8:
            continue

        if not any(
            k in href.lower()
            for k in ["calendar", "sale", "auction", "event", "exhibition"]
        ):
            continue

        url = href
        if url.startswith("/"):
            m = re.match(r"^(https?://[^/]+)", base_url)
            url = (m.group(1) + url) if m else href

        key = (text, url)
        if key in seen:
            continue
        seen.add(key)

        parent_text = ""
        if a.parent:
            parent_text = " ".join(a.parent.get_text(" ", strip=True).split())
        blob = (parent_text + " " + text).strip()

        m = DATE_RE.search(blob)
        sd = _parse_date_any(m.group(0)) if m else None

        loc = _extract_location(text)
        title_clean = _polish_title(text)

        if loc:
            title_clean = re.sub(rf"\b{re.escape(loc)}\b", "", title_clean).strip()
            title_clean = re.sub(r"\s+", " ", title_clean).strip()

        items.append(
            EventItem(
                id=_stable_id(house, title_clean, url),
                title=title_clean,
                house=house,
                start_date=_to_iso(sd),
                end_date=_to_iso(sd),
                location=loc[:120],
                url=url,
            )
        )

        if len(items) >= 60:
            break

    return items


def fetch_events(days: int = 90) -> dict[str, Any]:
    all_items: list[EventItem] = []
    errors: list[str] = []

    for src in EVENT_SOURCES:
        house = src["house"]
        url = src["url"]

        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
            if r.status_code != 200:
                errors.append(f"{house}: HTTP {r.status_code}")
                continue
            html = r.text
        except Exception as e:
            errors.append(f"{house}: request error: {e}")
            continue

        items = _extract_jsonld_events(html, house, url)
        if not items:
            items = _extract_fallback_events(html, house, url)

        all_items.extend(items)

    uniq: dict[str, EventItem] = {it.id: it for it in all_items}
    out = list(uniq.values())

    def sort_key(it: EventItem):
        return (it.start_date or "9999-12-31", it.house, it.title)

    out.sort(key=sort_key)

    return {
        "ok": True,
        "count": len(out),
        "events": [
            {
                "id": it.id,
                "title": it.title,
                "house": it.house,
                "start_date": it.start_date,
                "end_date": it.end_date,
                "location": it.location,
                "url": it.url,
            }
            for it in out
        ],
        "errors": errors,
    }
