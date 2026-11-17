import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { api, colorFor, GraphData, LinkRef } from "../api";

export function GraphView({
  center,
  onSelect,
  onLinkSelect,
  byType,
}: {
  center: string | null;
  onSelect: (id: string) => void;
  onLinkSelect: (ref: LinkRef) => void;
  byType: { type: string; count: number }[];
}) {
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  // null = not yet initialized (types unknown); once known we seed it to "all on"
  const [active, setActive] = useState<Set<string> | null>(null);
  const fgRef = useRef<any>(null);

  const allTypes = useMemo(() => byType.map((t) => t.type), [byType]);

  useEffect(() => {
    if (active === null && allTypes.length) setActive(new Set(allTypes));
  }, [allTypes, active]);

  useEffect(() => {
    // Empty selection -> empty canvas, no request.
    if (active !== null && active.size === 0) {
      setData({ nodes: [], links: [] });
      return;
    }
    // "All on" (or types not yet known) sends no filter, keeping the default
    // seed/ego graph nicely connected. A strict subset sends the type filter.
    const full = active === null || (allTypes.length > 0 && active.size === allTypes.length);
    const params: { center?: string; depth?: number; limit?: number; types?: string } = {
      limit: 600,
    };
    if (center) {
      params.center = center;
      params.depth = 2;
    }
    if (!full && active) params.types = [...active].join(",");
    api.graph(params).then(setData).catch(() => setData({ nodes: [], links: [] }));
  }, [center, active, allTypes]);

  // ForceGraph mutates node objects; clone so React state stays clean.
  const graphData = useMemo(
    () => ({
      nodes: data.nodes.map((n) => ({ ...n })),
      links: data.links.map((l) => ({ ...l })),
    }),
    [data]
  );

  const isOn = (t: string) => active?.has(t) ?? true;
  const toggle = (t: string) =>
    setActive((prev) => {
      const next = new Set(prev ?? allTypes);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });

  return (
    <div className="view">
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        backgroundColor="#0b0f17"
        nodeRelSize={5}
        nodeColor={(n: any) => colorFor(n.type)}
        nodeLabel={(n: any) => `${n.name} (${n.type})`}
        linkColor={() => "rgba(148,163,184,0.25)"}
        linkLabel={(l: any) => l.type.replace(/_/g, " ")}
        linkHoverPrecision={6}
        onNodeClick={(n: any) => onSelect(n.id)}
        onLinkClick={(l: any) =>
          onLinkSelect({
            // after layout, source/target are node objects
            source_id: typeof l.source === "object" ? l.source.id : l.source,
            target_id: typeof l.target === "object" ? l.target.id : l.target,
            type: l.type,
          })
        }
        cooldownTicks={120}
        nodeCanvasObjectMode={() => "after"}
        nodeCanvasObject={(node: any, ctx, globalScale) => {
          if (globalScale < 1.4) return; // only label when zoomed in
          const label = node.name as string;
          ctx.font = `${11 / globalScale}px sans-serif`;
          ctx.fillStyle = "#cbd5e1";
          ctx.textAlign = "left";
          ctx.textBaseline = "middle";
          ctx.fillText(label, node.x + 7 / globalScale, node.y);
        }}
      />

      <div className="filterbar">
        <button className="fbtn" onClick={() => setActive(new Set(allTypes))}>
          All
        </button>
        <button className="fbtn" onClick={() => setActive(new Set())}>
          None
        </button>
        {byType.map(({ type, count }) => (
          <button
            key={type}
            className={`chip ${isOn(type) ? "" : "off"}`}
            onClick={() => toggle(type)}
            style={isOn(type) ? { borderColor: colorFor(type) } : undefined}
          >
            <span className="dot" style={{ background: colorFor(type) }} />
            {type}
            <span className="cnt">{count.toLocaleString()}</span>
          </button>
        ))}
      </div>

      <div className="hint">
        Toggle types above to filter. Click a node to inspect it and pull in its
        connections — or click an <strong>edge</strong> to see why that link exists
        and which sources assert it.
      </div>
    </div>
  );
}
