import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, colorFor, DirectoryOut } from "../api";
import { TopBar } from "../components/TopBar";

const TYPE_LABELS: Record<string, string> = {
  program: "Sanctions programs",
  location: "Countries & places",
  organization: "Organizations",
  person: "People",
  vessel: "Vessels",
  aircraft: "Aircraft",
  commodity: "Commodities",
};

export function WikiHome() {
  const [dir, setDir] = useState<DirectoryOut | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.directory(8).then(setDir).catch(() => setError(true));
  }, []);

  return (
    <div className="app">
      <TopBar active="wiki" />
      <div className="wikihome">
        <div className="wikihome-inner">
          <h1>Browse the dossier</h1>
          <p className="lead">
            Pick a category and open any entity's page — its properties, its
            connections, and the sources behind them. Each list is ranked by how
            connected the entity is, so the hubs surface first.
          </p>

          {error && <div className="route-loading">Couldn't load the directory.</div>}
          {!dir && !error && <div className="route-loading">Loading…</div>}

          {dir?.groups.map((g) => (
            <section className="cat" key={g.type}>
              <h2>
                <span className="dot" style={{ background: colorFor(g.type) }} />
                {TYPE_LABELS[g.type] ?? g.type}
                <span className="cat-total">{g.total.toLocaleString()}</span>
              </h2>
              <div className="card-grid">
                {g.items.map((it) => (
                  <Link
                    className="ecard"
                    to={`/e/${it.id}`}
                    key={it.id}
                    style={{ borderLeftColor: colorFor(g.type) }}
                  >
                    <div className="ecard-name">{it.name}</div>
                    <div className="ecard-deg">
                      {it.degree.toLocaleString()} connection{it.degree === 1 ? "" : "s"}
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
