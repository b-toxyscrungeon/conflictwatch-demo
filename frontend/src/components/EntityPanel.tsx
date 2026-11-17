import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, colorFor, EntityDetail } from "../api";

export function EntityPanel({
  entityId,
  onSelect,
  onClose,
}: {
  entityId: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const [entity, setEntity] = useState<EntityDetail | null>(null);

  useEffect(() => {
    setEntity(null);
    api.entity(entityId).then(setEntity).catch(() => setEntity(null));
  }, [entityId]);

  if (!entity) return null;

  const props = entity.properties as Record<string, unknown>;
  const scalarProps = Object.entries(props).filter(
    ([, v]) => typeof v === "string" || typeof v === "number"
  );

  return (
    <div className="panel">
      <span className="close" onClick={onClose}>
        ✕
      </span>
      <span className="type" style={{ background: colorFor(entity.type) }}>
        {entity.type}
      </span>
      <h2>{entity.name}</h2>

      <Link className="open-page" to={`/e/${entity.id}`} target="_blank" rel="noreferrer">
        Open as page ↗
      </Link>

      {entity.aliases.length > 0 && (
        <div style={{ color: "var(--muted)", fontSize: 12.5, marginBottom: 6 }}>
          a.k.a. {entity.aliases.slice(0, 6).join(", ")}
          {entity.aliases.length > 6 ? "…" : ""}
        </div>
      )}

      {scalarProps.length > 0 && (
        <div className="kv">
          {scalarProps.map(([k, v]) => (
            <div key={k} style={{ display: "contents" }}>
              <div className="k">{k}</div>
              <div>{String(v)}</div>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 10, color: "var(--muted)", fontSize: 12 }}>
        {entity.relationships.length} connection
        {entity.relationships.length === 1 ? "" : "s"} · source {entity.source}
      </div>

      {entity.relationships.map((r) => (
        <div key={r.id} className="rel">
          <div className="rel-head" onClick={() => onSelect(r.other.id)}>
            <span className="dot" style={{ background: colorFor(r.other.type) }} />
            <div style={{ flex: 1 }}>
              <div className="verb">
                {r.direction === "out" ? r.type : `${r.type} (from)`}
              </div>
              {r.other.name}
            </div>
          </div>
          {r.description && <p className="rel-why">{r.description}</p>}
          <div className="rel-meta">
            <span className="conn-src">{r.source}</span>
            {r.confidence && <span className="conn-src">{r.confidence}</span>}
            {r.source_url && (
              <a href={r.source_url} target="_blank" rel="noreferrer">
                source ↗
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
