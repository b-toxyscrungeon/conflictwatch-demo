import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { api, FeatureCollection, IS_STATIC, TYPE_COLORS } from "../api";

// Free OSM raster basemap — no API key required.
const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

// color-match graph node types
const COLOR_MATCH: any = ["match", ["get", "type"]];
for (const [type, color] of Object.entries(TYPE_COLORS)) {
  if (type !== "unknown") COLOR_MATCH.push(type, color);
}
COLOR_MATCH.push(TYPE_COLORS.unknown);

// Contacts fade as they age: full opacity when fresh, floor of 0.2 past ~24h.
const FADE_FLOOR = 0.2;
const FADE_HOURS = 24;
const SPATIAL_TYPES = ["aircraft", "vessel"];
const REFRESH_MS = 60_000;

// `now` is the snapshot date in the static demo, so its contacts fade relative to
// each other instead of all looking stale months later.
function withOpacity(fc: FeatureCollection, now = Date.now()): FeatureCollection {
  return {
    ...fc,
    features: fc.features.map((f) => {
      const seen = f.properties.last_seen ? Date.parse(f.properties.last_seen) : NaN;
      const ageH = Number.isNaN(seen) ? FADE_HOURS : (now - seen) / 3_600_000;
      const opacity = Math.max(FADE_FLOOR, 1 - (ageH / FADE_HOURS) * (1 - FADE_FLOOR));
      return { ...f, properties: { ...f.properties, opacity } };
    }),
  };
}

export function MapView({ onSelect }: { onSelect: (id: string) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [empty, setEmpty] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: [-79.5, 21.8], // Cuba
      zoom: 5.5,
    });
    mapRef.current = map;

    const refresh = async () => {
      const fc = await api
        .map()
        .catch(() => ({ type: "FeatureCollection", features: [] }) as FeatureCollection);
      setEmpty(!fc.features.length);
      const meta = await api.meta().catch(() => null);
      const asOf = meta?.as_of ? Date.parse(meta.as_of) : undefined;
      const data = withOpacity(fc, asOf) as any;
      const src = map.getSource("entities") as maplibregl.GeoJSONSource | undefined;
      if (src) src.setData(data);
      return data;
    };

    map.on("load", async () => {
      const data = await refresh();
      map.addSource("entities", { type: "geojson", data });
      map.addLayer({
        id: "entities",
        type: "circle",
        source: "entities",
        paint: {
          "circle-radius": 6,
          "circle-color": COLOR_MATCH,
          "circle-opacity": ["get", "opacity"],
          "circle-stroke-width": 1,
          "circle-stroke-color": "#0b0f17",
          "circle-stroke-opacity": ["get", "opacity"],
        },
      });
      map.on("click", "entities", (e) => {
        const id = e.features?.[0]?.properties?.id;
        if (id) onSelect(String(id));
      });
      map.on("mouseenter", "entities", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "entities", () => (map.getCanvas().style.cursor = ""));
    });

    // Reposition dots as new ingests land (a static snapshot never changes).
    const timer = IS_STATIC ? undefined : window.setInterval(refresh, REFRESH_MS);
    return () => {
      window.clearInterval(timer);
      map.remove();
    };
  }, [onSelect]);

  return (
    <div className="view">
      <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />
      <div className="legend">
        {SPATIAL_TYPES.map((t) => (
          <div className="item" key={t}>
            <span className="dot" style={{ background: TYPE_COLORS[t] }} />
            {t}
          </div>
        ))}
        <div className="item" style={{ opacity: 0.45 }}>
          <span className="dot" style={{ background: "#94a3b8" }} />
          faded = stale
        </div>
      </div>
      {empty && !IS_STATIC && (
        <div className="hint">
          No geospatial entities yet. Run an ADS-B/AIS ingest (or the scheduler) to
          populate the map with aircraft and vessels around Cuba.
        </div>
      )}
    </div>
  );
}
