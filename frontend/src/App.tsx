import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

// Each route is its own chunk. The explorer pulls in the heavy graph/map libs;
// the entity page does not — so opening entity pages in tabs stays lightweight.
const Explorer = lazy(() =>
  import("./Explorer").then((m) => ({ default: m.Explorer }))
);
const EntityPage = lazy(() =>
  import("./pages/EntityPage").then((m) => ({ default: m.EntityPage }))
);
const WikiHome = lazy(() =>
  import("./pages/WikiHome").then((m) => ({ default: m.WikiHome }))
);

export function App() {
  return (
    <Suspense fallback={<div className="route-loading">Loading…</div>}>
      <Routes>
        <Route path="/" element={<Navigate to="/graph" replace />} />
        <Route path="/graph" element={<Explorer view="graph" />} />
        <Route path="/map" element={<Explorer view="map" />} />
        <Route path="/wiki" element={<WikiHome />} />
        <Route path="/e/:id" element={<EntityPage />} />
        <Route path="*" element={<Navigate to="/graph" replace />} />
      </Routes>
    </Suspense>
  );
}
