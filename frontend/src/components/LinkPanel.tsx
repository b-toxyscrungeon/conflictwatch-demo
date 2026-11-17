import { useEffect, useState } from "react";
import { api, colorFor, LinkOut, LinkRef } from "../api";

/** Detail for one graph edge: why it exists, and which sources assert it. */
export function LinkPanel({
  linkRef,
  onSelect,
  onClose,
}: {
  linkRef: LinkRef;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const [link, setLink] = useState<LinkOut | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLink(null);
    setError(false);
    api.link(linkRef).then(setLink).catch(() => setError(true));
  }, [linkRef.source_id, linkRef.target_id, linkRef.type]);

  if (error)
    return (
      <div className="panel">
        <span className="close" onClick={onClose}>
          ✕
        </span>
        <div style={{ color: "var(--muted)", fontSize: 13 }}>
          No details recorded for this link.
        </div>
      </div>
    );
  if (!link) return null;

  const { source_entity: src, target_entity: tgt } = link;

  return (
    <div className="panel">
      <span className="close" onClick={onClose}>
        ✕
      </span>
      <span className="type" style={{ background: "var(--muted)" }}>
        link
      </span>
      <h2 style={{ fontSize: 15 }}>{link.type.replace(/_/g, " ")}</h2>

      <div className="link-ends">
        <div className="link-end" onClick={() => onSelect(src.id)}>
          <span className="dot" style={{ background: colorFor(src.type) }} />
          {src.name}
        </div>
        <div className="link-arrow">↓ {link.type.replace(/_/g, " ")} ↓</div>
        <div className="link-end" onClick={() => onSelect(tgt.id)}>
          <span className="dot" style={{ background: colorFor(tgt.type) }} />
          {tgt.name}
        </div>
      </div>

      <div style={{ marginTop: 12, color: "var(--muted)", fontSize: 12 }}>
        {link.assertions.length} source
        {link.assertions.length === 1 ? "" : "s"} assert this link
      </div>

      {link.assertions.map((a, i) => (
        <div className="assertion" key={`${a.source}-${i}`}>
          <div className="assertion-head">
            <span className="conn-src">{a.source}</span>
            {a.confidence && <span className="conn-src">{a.confidence} confidence</span>}
          </div>
          {a.description && <p className="conn-why">{a.description}</p>}
          <div className="assertion-meta">
            {a.retrieved_at && (
              <span>retrieved {new Date(a.retrieved_at).toLocaleDateString()}</span>
            )}
            {a.source_url && (
              <a href={a.source_url} target="_blank" rel="noreferrer">
                source ↗
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
