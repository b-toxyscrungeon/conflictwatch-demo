import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, IS_STATIC, SnapshotMeta, Stats } from "../api";
import { VisitorCount } from "./VisitorCount";

const SOURCE_LABELS: Record<string, string> = {
  ofac_sdn: "OFAC SDN list",
  adsb_opensky: "OpenSky Network (ADS-B)",
  ais_aisstream: "AISStream (AIS)",
};

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });

// Shared header + nav across the Graph / Map / Wiki views.
export function TopBar({ active }: { active: "graph" | "map" | "wiki" }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [query, setQuery] = useState("");
  const [meta, setMeta] = useState<SnapshotMeta | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.stats().then(setStats).catch(() => setStats(null));
    api.meta().then(setMeta).catch(() => setMeta(null));
  }, []);

  async function runSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    const results = await api.entities({ q: query.trim(), limit: 1 });
    if (results.length) navigate(`/graph?center=${results[0].id}`);
  }

  return (
    <div className="topbar">
      <Link to="/" className="brand" style={{ textDecoration: "none" }}>
        POINE<span>MAP</span> · Cuba
      </Link>
      <div className="tabs">
        <Link to="/graph" className={`tab ${active === "graph" ? "active" : ""}`}>
          Graph
        </Link>
        <Link to="/map" className={`tab ${active === "map" ? "active" : ""}`}>
          Map
        </Link>
        <Link to="/wiki" className={`tab ${active === "wiki" ? "active" : ""}`}>
          Wiki
        </Link>
      </div>
      <form onSubmit={runSearch} style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
        <input
          className="search"
          placeholder="Search entities (e.g. CUBAEXPORT)…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </form>
      {stats && (
        <div className="stats">
          {stats.entities.toLocaleString()} entities ·{" "}
          {stats.relationships.toLocaleString()} links
        </div>
      )}
      {meta?.as_of && (
        <div
          className="stats asof"
          title={Object.entries(meta.sources)
            .map(([src, ts]) => `${SOURCE_LABELS[src] ?? src}: ${fmtDate(ts)}`)
            .join("\n")}
        >
          Snapshot · data as of {fmtDate(meta.as_of)}
        </div>
      )}
      {IS_STATIC && <VisitorCount />}
    </div>
  );
}
