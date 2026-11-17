import { lazy, Suspense, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, LinkRef, Stats } from "./api";
import { EntityPanel } from "./components/EntityPanel";
import { LinkPanel } from "./components/LinkPanel";
import { TopBar } from "./components/TopBar";

// Heavy view libs (react-force-graph, maplibre) load only when their view renders.
const GraphView = lazy(() =>
  import("./components/GraphView").then((m) => ({ default: m.GraphView }))
);
const MapView = lazy(() =>
  import("./components/MapView").then((m) => ({ default: m.MapView }))
);

export function Explorer({ view }: { view: "graph" | "map" }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [linkRef, setLinkRef] = useState<LinkRef | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [params, setParams] = useSearchParams();

  const center = params.get("center");

  // stats drives the graph's type-filter chips
  useEffect(() => {
    api.stats().then(setStats).catch(() => setStats(null));
  }, []);

  // Open the panel for whatever the graph is centered on (from a click or search).
  useEffect(() => {
    if (center) setSelected(center);
  }, [center]);

  // Selecting opens the side panel; on the graph it also re-centers via the URL.
  // Node and link selection are mutually exclusive — one panel at a time.
  function select(id: string) {
    setLinkRef(null);
    setSelected(id);
    if (view === "graph") setParams({ center: id });
  }

  function selectLink(ref: LinkRef) {
    setSelected(null);
    setLinkRef(ref);
  }

  return (
    <div className="app">
      <TopBar active={view} />
      <div className="body">
        <Suspense fallback={<div className="route-loading">Loading view…</div>}>
          {view === "graph" ? (
            <GraphView
              center={center}
              onSelect={select}
              onLinkSelect={selectLink}
              byType={stats?.by_type ?? []}
            />
          ) : (
            <MapView onSelect={select} />
          )}
        </Suspense>
        {linkRef ? (
          <LinkPanel
            linkRef={linkRef}
            onSelect={select}
            onClose={() => setLinkRef(null)}
          />
        ) : (
          selected && (
            <EntityPanel
              entityId={selected}
              onSelect={select}
              onClose={() => setSelected(null)}
            />
          )
        )}
      </div>
    </div>
  );
}
