import { useEffect, useMemo, useState } from "react";
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

function buildSignalsUrl(theme: string, q: string, sort: string) {
  const url = new URL(`${API_BASE}/signals`);
  if (theme && theme !== "All") url.searchParams.set("theme", theme);
  if (q.trim()) url.searchParams.set("q", q.trim());
  if (sort && sort !== "date") url.searchParams.set("sort", sort);
  return url.toString();
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
  const [refreshing, setRefreshing] = useState(false);

  const [events, setEvents] = useState<EventItem[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventsError, setEventsError] = useState<string | null>(null);

  async function loadEvents() {
    setEventsLoading(true);
    setEventsError(null);

    try {
      const res = await fetch(`${API_BASE}/events?days=90`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setEvents(Array.isArray(data?.events) ? data.events : []);
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



  // Load themes ONCE
  useEffect(() => {
    fetch(`${API_BASE}/themes`)
      .then((r) => r.json())
      .then((data) => setThemes(Array.isArray(data) ? data : ["All"]))
      .catch(() => setThemes(["All"]));
  }, []);

  // Load saved list ONCE (for button state)
  useEffect(() => {
    fetch(`${API_BASE}/saved`)
      .then((r) => r.json())
      .then((data: Signal[]) => {
        const ids = new Set((Array.isArray(data) ? data : []).map((s) => s.id));
        setSavedIds(ids);
      })
      .catch(() => setSavedIds(new Set()));
  }, []);

  // Live typing debounce -> q
  useEffect(() => {
    const t = setTimeout(() => setQ(qInput), 250);
    return () => clearTimeout(t);
  }, [qInput]);

  // Fetch signals for current view
  useEffect(() => {
    setLoading(true);
    setError(null);

    const url =
      view === "vault"
        ? `${API_BASE}/saved`
        : buildSignalsUrl(theme, q, sort);

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

      // If in Vault and you unsave, remove card immediately
      if (view === "vault" && isSaved) {
        setSignals((prev) => prev.filter((s) => s.id !== id));
        if (selected?.id === id) setSelected(null);
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
      // After ingest, reload the current view
      const url =
        view === "vault"
          ? `${API_BASE}/saved`
          : buildSignalsUrl(theme, q, sort);

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

  function filterEventsByTab(all: EventItem[], tab: MainTab) {
    const lower = (x: string) => (x || "").toLowerCase();
    const blob = (e: EventItem) => `${e.title} ${e.house} ${e.location} ${e.url}`.toLowerCase();

    const isAuctiony = (e: EventItem) =>
      ["auction", "sale", "buy/auction", "lots"].some((k) => blob(e).includes(k));

    const isShowy = (e: EventItem) =>
      ["exhibition", "preview", "show", "fair", "opening"].some((k) => blob(e).includes(k));

    const byDate = (a: EventItem, b: EventItem) =>
      (a.start_date || "9999-12-31").localeCompare(b.start_date || "9999-12-31");

    if (tab === "radar") {
      // Wealth Radar: show auction/sale-heavy events
      return all.filter(isAuctiony).sort(byDate);
    }

    if (tab === "moves") {
      // Hidden Moves: exhibition/preview/fair/show
      // (will be smaller until we add more "show" sources)
      return all.filter(isShowy).sort(byDate);
    }

    // Concierge Edge: shortlist of next 10 upcoming (across all)
    return [...all].sort(byDate).slice(0, 10);
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

    // edge: shortlist of next 10 upcoming across ALL
    return [...events].sort(byDate).slice(0, 10);
  }, [events, tab]);





  return (
    <div className="page">
      <header className="header">
        <div>
          <h1 className="title">Private Concierge Briefing</h1>
          <p className="subtitle">Database-backed feed</p>
        </div>

        <div className="right">
          <div className="pill">Postgres + API</div>

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
            <button className="btn" type="button" onClick={refreshFeed} disabled={refreshing}>
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>

          </div>

          <div className="pill">{resultsLabel}</div>
          <div className="tabs">
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
      </header>



      {view === "briefing" && (
        <>
          <section className="controls">
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

            <label className="control grow">
              <span className="controlLabel">Search</span>
              <input
                className="input"
                type="text"
                placeholder="Search signals…"
                value={qInput}
                onChange={(e) => setQInput(e.target.value)}
              />
            </label>

            <button className="btn" onClick={() => setQ(qInput)} type="button">
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
          {signals.map((s, idx) => {
            const isSaved = savedIds.has(s.id);
            const busy = savingId === s.id;

            return (
              <article
                className={`card ${idx === 0 ? "featured" : ""}`}
                key={s.id}
                onClick={() => setSelected(s)}
                role="button"
                tabIndex={0}
              >
                <div className="cardTop">
                  <div className="meta">
                    <span>{s.theme}</span>
                    <span className="dot">•</span>
                    <span>{s.rarity}</span>
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


      {selected && (
        <div className="drawerOverlay" onClick={() => setSelected(null)}>
          <aside className="drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawerHeader">
              <div>
                <div className="drawerMeta">
                  {selected.theme} • {selected.rarity} • {selected.date}
                </div>
                <h2 className="drawerTitle">{selected.title}</h2>
              </div>
              <button
                className="drawerClose"
                onClick={() => setSelected(null)}
                type="button"
              >
                ✕
              </button>
            </div>

            <p className="drawerSummary">{selected.summary}</p>

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
                    }\nConfidence: ${Math.round(
                      selected.confidence * 100
                    )}%\nSource: ${selected.source}\n${selected.url ? `URL: ${selected.url}` : ""
                    }`;
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
