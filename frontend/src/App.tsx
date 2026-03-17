import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

type Signal = {
  id: string;
  title: string;
  theme: string;
  rarity: string;
  confidence: number;
  date: string;
  summary: string;
  source: string;
  url: string;
};

type EventItem = {
  id: string;
  title: string;
  house: string;
  start_date: string;
  end_date: string;
  location: string;
  url: string;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const DRAWER_CLOSE_MS = 220;

function buildSignalsUrl(theme: string, q: string, sort: string) {
  const url = new URL(`${API_BASE}/signals`);
  if (theme && theme !== "All") url.searchParams.set("theme", theme);
  if (q.trim()) url.searchParams.set("q", q.trim());
  if (sort && sort !== "date") url.searchParams.set("sort", sort);
  return url.toString();
}

function rarityTone(rarity: string): "rare" | "uncommon" | "common" {
  const x = rarity.toLowerCase();
  if (x === "rare") return "rare";
  if (x === "uncommon") return "uncommon";
  return "common";
}

function extractKeywords(text: string, limit = 2) {
  const stop = new Set([
    "the", "and", "for", "with", "from", "that", "this", "into", "their", "will",
    "have", "has", "about", "after", "before", "through", "brand", "luxury",
    "daily", "news", "new", "its", "over", "than", "more", "less", "just",
  ]);

  const counts = new Map<string, number>();
  text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .filter((word) => word.length > 3 && !stop.has(word))
    .forEach((word) => counts.set(word, (counts.get(word) ?? 0) + 1));

  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([word]) => word);
}

function buildDrawerHighlights(signal: Signal) {
  const terms = extractKeywords(`${signal.title} ${signal.summary}`);
  const lead = terms.length
    ? `${terms.join(" / ")} are the dominant signals in this piece.`
    : "This signal captures a concentrated movement worth monitoring.";

  const impactByTheme: Record<string, string> = {
    Marketing: "Likely impact: brand visibility, campaign direction, and audience attention.",
    Finance: "Likely impact: capital flow, pricing confidence, and market positioning.",
    Design: "Likely impact: aesthetic direction, product storytelling, and desirability.",
  };

  const rarityLine =
    signal.rarity === "Rare"
      ? "This reads as a high-priority outlier rather than routine coverage."
      : signal.rarity === "Uncommon"
        ? "This sits above baseline noise and is worth brief monitoring."
        : "This is a baseline market signal, useful mainly in aggregate.";

  return [
    lead,
    impactByTheme[signal.theme] ?? "Likely impact: reputation, demand, and client attention.",
    `Confidence context: ${Math.round(signal.confidence * 100)}% confidence from current signal scoring.`,
    rarityLine,
  ];
}

export default function App() {
  const [view, setView] = useState<"briefing" | "vault">("briefing");

  const [signals, setSignals] = useState<Signal[]>([]);
  const [themes, setThemes] = useState<string[]>(["All"]);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());

  const [theme, setTheme] = useState("All");
  const [sort, setSort] = useState<"date" | "confidence" | "rarity">("date");

  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");

  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [selected, setSelected] = useState<Signal | null>(null);
  const [isDrawerClosing, setIsDrawerClosing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const drawerCloseTimerRef = useRef<number | null>(null);

  const [events, setEvents] = useState<EventItem[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventsError, setEventsError] = useState<string | null>(null);

  const [uiTheme, setUiTheme] = useState<"dark" | "light">(() => {
    const saved = window.localStorage.getItem("luxury-briefing-theme");
    if (saved === "dark" || saved === "light") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  useEffect(() => {
    const root = document.documentElement;
    root.classList.add("theme-switching");
    root.dataset.theme = uiTheme;
    window.localStorage.setItem("luxury-briefing-theme", uiTheme);

    const t = window.setTimeout(() => root.classList.remove("theme-switching"), 520);
    return () => window.clearTimeout(t);
  }, [uiTheme]);

  useEffect(() => {
    return () => {
      if (drawerCloseTimerRef.current !== null) {
        window.clearTimeout(drawerCloseTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeDrawer();
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selected, isDrawerClosing]);

  function openDrawer(signal: Signal) {
    if (drawerCloseTimerRef.current !== null) {
      window.clearTimeout(drawerCloseTimerRef.current);
      drawerCloseTimerRef.current = null;
    }

    setIsDrawerClosing(false);
    setSelected(signal);
  }

  function closeDrawer() {
    if (!selected || isDrawerClosing) return;

    setIsDrawerClosing(true);
    drawerCloseTimerRef.current = window.setTimeout(() => {
      setSelected(null);
      setIsDrawerClosing(false);
      drawerCloseTimerRef.current = null;
    }, DRAWER_CLOSE_MS);
  }


  async function loadEvents() {
    setEventsLoading(true);
    setEventsError(null);

    try {
      const [r1, r2] = await Promise.all([
        fetch(`${API_BASE}/events?days=90`),
        fetch(`${API_BASE}/events/curated`),
      ]);

      if (!r1.ok) throw new Error(`HTTP ${r1.status} (events)`);
      if (!r2.ok) throw new Error(`HTTP ${r2.status} (curated)`);

      const d1 = await r1.json();
      const d2 = await r2.json();

      const a1: EventItem[] = Array.isArray(d1?.events) ? d1.events : [];
      const a2: EventItem[] = Array.isArray(d2?.events) ? d2.events : [];

      const map = new Map<string, EventItem>();
      [...a1, ...a2].forEach((e) => map.set(e.id, e));
      setEvents(Array.from(map.values()));
    } catch (e: unknown) {
      setEventsError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setEventsLoading(false);
    }
  }

  type MainTab = "moves" | "radar" | "edge";
  type SubView = "feed" | "events";

  const [tab, setTab] = useState<MainTab>("moves");
  const [subView, setSubView] = useState<SubView>("feed");

  useEffect(() => {
    if (subView === "events") loadEvents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subView]);

  useEffect(() => {
    fetch(`${API_BASE}/themes`)
      .then((r) => r.json())
      .then((data) => setThemes(Array.isArray(data) ? data : ["All"]))
      .catch(() => setThemes(["All"]));
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/saved`)
      .then((r) => r.json())
      .then((data: Signal[]) => {
        const ids = new Set((Array.isArray(data) ? data : []).map((s) => s.id));
        setSavedIds(ids);
      })
      .catch(() => setSavedIds(new Set()));
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setQ(qInput), 250);
    return () => clearTimeout(t);
  }, [qInput]);

  useEffect(() => {
    setLoading(true);
    setError(null);

    const url =
      view === "vault" ? `${API_BASE}/saved` : buildSignalsUrl(theme, q, sort);

    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => setSignals(Array.isArray(data) ? data : []))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Unknown error")
      )
      .finally(() => setLoading(false));
  }, [view, theme, q, sort]);

  const resultsLabel = useMemo(() => {
    if (loading) return "Loading…";
    if (error) return "Error";
    return `${signals.length} signal${signals.length === 1 ? "" : "s"}`;
  }, [loading, error, signals.length]);

  async function toggleSave(id: string) {
    setSavingId(id);
    setError(null);

    const isSaved = savedIds.has(id);

    try {
      const res = await fetch(`${API_BASE}/save/${id}`, {
        method: isSaved ? "DELETE" : "POST",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      setSavedIds((prev) => {
        const next = new Set(prev);
        if (isSaved) next.delete(id);
        else next.add(id);
        return next;
      });

      if (view === "vault" && isSaved) {
        setSignals((prev) => prev.filter((s) => s.id !== id));
        if (selected?.id === id) closeDrawer();
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSavingId(null);
    }
  }

  async function refreshFeed() {
    setRefreshing(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/ingest`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const url =
        view === "vault" ? `${API_BASE}/saved` : buildSignalsUrl(theme, q, sort);

      const r2 = await fetch(url);
      if (!r2.ok) throw new Error(`HTTP ${r2.status}`);
      const data = await r2.json();
      setSignals(Array.isArray(data) ? data : []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setRefreshing(false);
    }
  }

  const filteredEvents = useMemo(() => {
    const byDate = (a: EventItem, b: EventItem) =>
      (a.start_date || "9999-12-31").localeCompare(b.start_date || "9999-12-31");

    const blob = (e: EventItem) =>
      `${e.title} ${e.house} ${e.location} ${e.url}`.toLowerCase();

    const isAuctiony = (e: EventItem) =>
      ["auction", "sale", "buy/auction", "lots"].some((k) => blob(e).includes(k));

    const isShowy = (e: EventItem) =>
      ["exhibition", "private selling", "preview", "show", "fair", "opening"].some((k) =>
        blob(e).includes(k)
      );

    if (tab === "radar") return [...events].filter(isAuctiony).sort(byDate);
    if (tab === "moves") return [...events].filter(isShowy).sort(byDate);

    const auctions = [...events].filter(isAuctiony).sort(byDate).slice(0, 5);
    const moves = [...events].filter(isShowy).sort(byDate).slice(0, 5);

    const map = new Map<string, EventItem>();
    [...moves, ...auctions].forEach((e) => map.set(e.id, e));

    return Array.from(map.values()).sort(byDate).slice(0, 10);
  }, [events, tab]);

  const drawerHighlights = useMemo(
    () => (selected ? buildDrawerHighlights(selected) : []),
    [selected]
  );

  return (
    <div
      className={`page state-${view} tab-${tab} subview-${subView}${selected ? " drawer-open" : ""}`}
    >
      <div className="ambient" aria-hidden="true">
        <span className="ambientLayer ambientField" />
        <span className="ambientLayer ambientMesh" />
      </div>

      <header className="header">
        <div className="headerBrand">
          <h1 className="title">Private Concierge Briefing</h1>
          <p className="subtitle">Database-backed feed</p>
        </div>
      </header>

      <div className="contentShell">
        <main className="contentMain">
          {view === "briefing" && (
            <>
              <section className="topSearch">
                <label className="control grow">
                  <input
                    className="input"
                    type="text"
                    placeholder="Search signals…"
                    aria-label="Search signals"
                    value={qInput}
                    onChange={(e) => setQInput(e.target.value)}
                  />
                </label>

                <button className="btn topSearchBtn" onClick={() => setQ(qInput)} type="button">
                  Search
                </button>
              </section>

              <div className="statusLine">
                Showing <strong>{resultsLabel}</strong> • Sort: <strong>{sort}</strong>
                {theme !== "All" ? (
                  <>
                    {" "}
                    • Theme: <strong>{theme}</strong>
                  </>
                ) : null}
                {q.trim() ? (
                  <>
                    {" "}
                    • Query: <strong>{q.trim()}</strong>
                  </>
                ) : null}
              </div>
            </>
          )}

          {subView === "events" && (
            <div className="timeline">
              {eventsLoading && <div className="state">Loading watch windows…</div>}
              {eventsError && <div className="state error">Error: {eventsError}</div>}

              {!eventsLoading && !eventsError && filteredEvents.length === 0 && (
                <div className="state">No watch windows for this tab yet.</div>
              )}

              {!eventsLoading &&
                !eventsError &&
                filteredEvents.map((ev) => (
                  <div className="eventRow" key={ev.id}>
                    <div className="eventDate">{ev.start_date || "—"}</div>

                    <div className="eventBody">
                      <div className="eventTitle">{ev.title}</div>
                      <div className="eventMeta">
                        {ev.house}
                        {ev.location ? ` • ${ev.location}` : ""}
                      </div>
                    </div>

                    <a className="eventLink" href={ev.url} target="_blank" rel="noreferrer">
                      Open
                    </a>
                  </div>
                ))}
            </div>
          )}

          {error && <div className="state error">Error: {error}</div>}
          {loading && <div className="state">Loading…</div>}

          {subView === "feed" && !loading && !error && (
            <div className="grid">
              {signals.map((s) => {
                const isSaved = savedIds.has(s.id);
                const busy = savingId === s.id;
                const tone = rarityTone(s.rarity);

                return (
                  <article
                    className={`card rarity-card-${tone}`}
                    key={s.id}
                    onClick={() => openDrawer(s)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        openDrawer(s);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="cardTop">
                      <div className="meta">
                        <span>{s.theme}</span>
                        <span className="dot">•</span>
                        <span className={`rarity rarity-${rarityTone(s.rarity)}`}>
                          <span className="rarityDot" aria-hidden="true" />
                          {s.rarity}
                        </span>
                        <span className="dot">•</span>
                        <span>{s.date}</span>
                      </div>

                      <button
                        className={`saveBtn ${isSaved ? "saved" : ""}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSave(s.id);
                        }}
                        disabled={busy}
                        type="button"
                        title={isSaved ? "Remove from Vault" : "Save to Vault"}
                      >
                        {busy ? "…" : isSaved ? "Saved" : "Save"}
                      </button>
                    </div>

                    <h2 className="cardTitle">{s.title}</h2>
                    <p className="summary">{s.summary}</p>

                    <div className="footer">
                      <span className="source">{s.source}</span>
                      <span className="confidence">
                        Confidence: {(s.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </main>

        <aside className="sidebar">
          <div className="sidebarPanel">
            <div className="sidebarEyebrow">Controls</div>

            <div className="toolRow toolRowTop">
              <div className="pill">Postgres + API</div>
              <div className="pill">{resultsLabel}</div>
            </div>

            <div className="toolRow">
              <div className="tabs">
                <button
                  className={`tab ${view === "briefing" ? "active" : ""}`}
                  onClick={() => setView("briefing")}
                  type="button"
                >
                  Briefing
                </button>
                <button
                  className={`tab ${view === "vault" ? "active" : ""}`}
                  onClick={() => setView("vault")}
                  type="button"
                >
                  Vault ({savedIds.size})
                </button>
              </div>
            </div>

            <div className="toolRow toolRowModes">
              <button
                className={`tabBtn ${tab === "moves" ? "active" : ""}`}
                type="button"
                onClick={() => setTab("moves")}
              >
                Hidden Moves
              </button>
              <button
                className={`tabBtn ${tab === "radar" ? "active" : ""}`}
                type="button"
                onClick={() => setTab("radar")}
              >
                Wealth Radar
              </button>
              <button
                className={`tabBtn ${tab === "edge" ? "active" : ""}`}
                type="button"
                onClick={() => setTab("edge")}
              >
                Concierge Edge
              </button>
            </div>

            <div className="toolRow">
              <div className="tabs">
                <button
                  className={`tabBtn ${subView === "feed" ? "active" : ""}`}
                  type="button"
                  onClick={() => setSubView("feed")}
                >
                  Feed
                </button>
                <button
                  className={`tabBtn ${subView === "events" ? "active" : ""}`}
                  type="button"
                  onClick={() => setSubView("events")}
                >
                  Watch Windows
                </button>
              </div>
            </div>

            <div className="toolRow">
              <button
                className="btn"
                type="button"
                onClick={refreshFeed}
                disabled={refreshing}
              >
                {refreshing ? "Refreshing…" : "Refresh"}
              </button>
            </div>

            {view === "briefing" && (
              <section className="sidebarFilters">
                <label className="control">
                  <span className="controlLabel">Theme</span>
                  <select
                    className="select"
                    value={theme}
                    onChange={(e) => setTheme(e.target.value)}
                  >
                    {themes.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="control">
                  <span className="controlLabel">Sort</span>
                  <select
                    className="select"
                    value={sort}
                    onChange={(e) => setSort(e.target.value as any)}
                  >
                    <option value="date">Newest</option>
                    <option value="confidence">Confidence</option>
                    <option value="rarity">Rarity</option>
                  </select>
                </label>
              </section>
            )}
          </div>
        </aside>
      </div>

      <div className="themeDock">
        <div className={`themeSwitch ${uiTheme}`} role="group" aria-label="Theme toggle">
          <span className="themeBlob" aria-hidden="true" />
          <button
            className="tabBtn themeToggleBtn"
            type="button"
            onClick={() => setUiTheme("dark")}
            aria-label="Enable dark mode"
            title="Dark mode"
          >
            <svg
              className="themeIcon"
              viewBox="0 0 24 24"
              aria-hidden="true"
              focusable="false"
            >
              <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 1 0 9.8 9.8Z" />
            </svg>
          </button>
          <button
            className="tabBtn themeToggleBtn"
            type="button"
            onClick={() => setUiTheme("light")}
            aria-label="Enable light mode"
            title="Light mode"
          >
            <svg
              className="themeIcon"
              viewBox="0 0 24 24"
              aria-hidden="true"
              focusable="false"
            >
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v3M12 19v3M22 12h-3M5 12H2M19.07 4.93l-2.12 2.12M7.05 16.95l-2.12 2.12M19.07 19.07l-2.12-2.12M7.05 7.05 4.93 4.93" />
            </svg>
          </button>
        </div>
      </div>

      {selected && (
        <div
          className={`drawerOverlay ${isDrawerClosing ? "closing" : ""}`}
          onClick={closeDrawer}
        >
          <aside className="drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawerHeader">
              <div>
                <div className="drawerMeta">
                  {selected.theme} •{" "}
                  <span className={`rarity rarity-${rarityTone(selected.rarity)}`}>
                    <span className="rarityDot" aria-hidden="true" />
                    {selected.rarity}
                  </span>{" "}
                  • {selected.date}
                </div>
                <h2 className="drawerTitle">{selected.title}</h2>
              </div>
              <button className="drawerClose" onClick={closeDrawer} type="button">
                ✕
              </button>
            </div>

            <p className="drawerSummary">{selected.summary}</p>

            <section className="drawerBrief">
              <div className="drawerSectionLabel">Key Takeaways</div>
              <ul className="drawerPoints">
                {drawerHighlights.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            </section>

            <section className="drawerFacts">
              <div className="drawerFact">
                <span className="drawerFactLabel">Source</span>
                <span className="drawerFactValue">{selected.source}</span>
              </div>
              <div className="drawerFact">
                <span className="drawerFactLabel">Theme</span>
                <span className="drawerFactValue">{selected.theme}</span>
              </div>
              <div className="drawerFact">
                <span className="drawerFactLabel">Confidence</span>
                <span className="drawerFactValue">{Math.round(selected.confidence * 100)}%</span>
              </div>
            </section>

            <div className="drawerActions">
              <button
                className={`saveBtn ${savedIds.has(selected.id) ? "saved" : ""}`}
                onClick={() => toggleSave(selected.id)}
                type="button"
              >
                {savedIds.has(selected.id) ? "Saved" : "Save"}
              </button>

              <a
                className="linkBtn"
                href={selected.url || "#"}
                target="_blank"
                rel="noreferrer"
                onClick={(e) => {
                  if (!selected.url) e.preventDefault();
                }}
              >
                Open Source
              </a>

              <button
                className="linkBtn"
                type="button"
                onClick={() => {
                  const text = `${selected.title}\n\n${selected.summary}\n\nTheme: ${selected.theme
                    }\nConfidence: ${Math.round(selected.confidence * 100)}%\nSource: ${selected.source
                    }\n${selected.url ? `URL: ${selected.url}` : ""}`;
                  navigator.clipboard.writeText(text);
                }}
              >
                Copy Brief
              </button>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
