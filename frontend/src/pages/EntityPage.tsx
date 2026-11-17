import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, colorFor, EntityDetail, RelationshipOut } from "../api";

// Human heading for a group of connections, given the link type + direction.
const CONN_HEADINGS: Record<string, string> = {
  "sanctioned_under:out": "Sanctioned under",
  "sanctioned_under:in": "Entities sanctioned under this",
  "flagged_in:out": "Flag state",
  "flagged_in:in": "Vessels flagged here",
  "owns:out": "Owns",
  "owns:in": "Owned by",
  "registered_in:out": "Registered in",
  "registered_in:in": "Aircraft registered here",
  "alias_of:out": "Alias of",
  "alias_of:in": "Aliases",
};

function headingFor(type: string, direction: string): string {
  return (
    CONN_HEADINGS[`${type}:${direction}`] ??
    `${type.replace(/_/g, " ")} (${direction === "out" ? "outgoing" : "incoming"})`
  );
}

function formatValue(v: unknown): string {
  if (Array.isArray(v)) return v.map((x) => (typeof x === "object" ? JSON.stringify(x) : String(x))).join(", ");
  if (v && typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function EntityPage() {
  const { id } = useParams();
  const [entity, setEntity] = useState<EntityDetail | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!id) return;
    setEntity(null);
    setError(false);
    api.entity(id).then(setEntity).catch(() => setError(true));
    window.scrollTo(0, 0);
  }, [id]);

  if (error) return <div className="route-loading">Entity not found.</div>;
  if (!entity) return <div className="route-loading">Loading…</div>;

  const props = Object.entries(entity.properties as Record<string, unknown>).filter(
    ([, v]) => v !== null && v !== "" && !(Array.isArray(v) && v.length === 0)
  );

  // group connections by (type, direction), preserving encounter order
  const groups = new Map<string, RelationshipOut[]>();
  for (const r of entity.relationships) {
    const key = `${r.type}:${r.direction}`;
    (groups.get(key) ?? groups.set(key, []).get(key)!).push(r);
  }

  return (
    <div className="wiki">
      <div className="wiki-nav">
        <Link to="/graph">← Explorer</Link>
        <Link to={`/graph?center=${entity.id}`}>View in graph →</Link>
      </div>

      <span className="type" style={{ background: colorFor(entity.type) }}>
        {entity.type}
      </span>
      <h1 className="wiki-title">{entity.name}</h1>
      {entity.aliases.length > 0 && (
        <p className="wiki-aka">
          <strong>Also known as:</strong> {entity.aliases.join(", ")}
        </p>
      )}

      {props.length > 0 && (
        <section className="wiki-section">
          <h2>Details</h2>
          <table className="infobox">
            <tbody>
              {props.map(([k, v]) => (
                <tr key={k}>
                  <th>{k.replace(/_/g, " ")}</th>
                  <td>{formatValue(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="wiki-section">
        <h2>Connections ({entity.relationships.length})</h2>
        {groups.size === 0 && <p className="wiki-aka">No connections recorded.</p>}
        {[...groups.entries()].map(([key, rels]) => {
          const [type, direction] = key.split(":");
          return (
            <div className="conn-group" key={key}>
              <h3>
                {headingFor(type, direction)} <span className="cnt">({rels.length})</span>
              </h3>
              {rels.map((r) => (
                <div className="conn-row" key={r.id}>
                  <div className="conn-head">
                    <span className="dot" style={{ background: colorFor(r.other.type) }} />
                    <Link to={`/e/${r.other.id}`}>{r.other.name}</Link>
                    <span className="conn-src">
                      {r.source}
                      {r.confidence ? ` · ${r.confidence} confidence` : ""}
                    </span>
                  </div>
                  {r.description && <p className="conn-why">{r.description}</p>}
                  {r.source_url && (
                    <a className="conn-cite" href={r.source_url} target="_blank" rel="noreferrer">
                      source ↗
                    </a>
                  )}
                </div>
              ))}
            </div>
          );
        })}
      </section>

      <section className="wiki-section">
        <h2>Provenance</h2>
        <p className="wiki-aka">
          Sourced from <strong>{entity.source}</strong> (ref <code>{entity.source_ref}</code>).
          Each connection above cites the source that asserts it.
        </p>
      </section>
    </div>
  );
}
