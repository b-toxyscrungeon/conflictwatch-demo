// Typed client for the ConflictWatch API. Calls are same-origin (Vite proxies /api).

export interface EntitySummary {
  id: string;
  type: string;
  name: string;
}

export interface RelationshipOut {
  id: string;
  type: string;
  source_id: string;
  target_id: string;
  other: EntitySummary;
  direction: "in" | "out";
  description: string | null;
  source: string;
  source_url: string | null;
  confidence: string | null;
}

export interface EntityDetail extends EntitySummary {
  properties: Record<string, unknown>;
  aliases: string[];
  source: string;
  source_ref: string;
  relationships: RelationshipOut[];
}

export interface GraphNode {
  id: string;
  type: string;
  name: string;
}

export interface GraphLink {
  source: string;
  target: string;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface Stats {
  entities: number;
  relationships: number;
  by_type: { type: string; count: number }[];
}

export interface LinkAssertion {
  source: string;
  description: string | null;
  source_url: string | null;
  confidence: string | null;
  retrieved_at: string | null;
  properties: Record<string, unknown>;
}

/** A directed link plus every source that asserts it (corroboration). */
export interface LinkOut {
  source_entity: EntitySummary;
  target_entity: EntitySummary;
  type: string;
  assertions: LinkAssertion[];
}

export interface LinkRef {
  source_id: string;
  target_id: string;
  type: string;
}

export interface DirectoryItem {
  id: string;
  type: string;
  name: string;
  degree: number;
}

export interface DirectoryGroup {
  type: string;
  total: number;
  items: DirectoryItem[];
}

export interface DirectoryOut {
  groups: DirectoryGroup[];
}

export interface FeatureCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    geometry: { type: string; coordinates: number[] };
    properties: { id: string; type: string; name: string; last_seen: string | null };
  }[];
}

/** Snapshot provenance — only present in the static (VITE_STATIC=1) build. */
export interface SnapshotMeta {
  as_of: string | null;
  sources: Record<string, string>;
  exported_at: string;
}

type GraphParams = { center?: string; depth?: number; limit?: number; types?: string };
type EntityParams = { q?: string; type?: string; limit?: number };

/** True for the GitHub Pages demo build, which reads exported JSON instead of the API. */
export const IS_STATIC = import.meta.env.VITE_STATIC === "1";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

const liveApi = {
  stats: () => get<Stats>("/api/stats"),
  entities: (params: { q?: string; type?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.type) qs.set("type", params.type);
    if (params.limit) qs.set("limit", String(params.limit));
    return get<EntitySummary[]>(`/api/entities?${qs}`);
  },
  entity: (id: string) => get<EntityDetail>(`/api/entities/${id}`),
  graph: (
    params: { center?: string; depth?: number; limit?: number; types?: string } = {}
  ) => {
    const qs = new URLSearchParams();
    if (params.center) qs.set("center", params.center);
    if (params.depth) qs.set("depth", String(params.depth));
    if (params.limit) qs.set("limit", String(params.limit));
    if (params.types) qs.set("types", params.types);
    return get<GraphData>(`/api/graph?${qs}`);
  },
  map: (type?: string) =>
    get<FeatureCollection>(`/api/map${type ? `?type=${type}` : ""}`),
  directory: (perType = 8) =>
    get<DirectoryOut>(`/api/directory?per_type=${perType}`),
  link: (ref: LinkRef) => {
    const qs = new URLSearchParams({
      source_id: ref.source_id,
      target_id: ref.target_id,
      type: ref.type,
    });
    return get<LinkOut>(`/api/link?${qs}`);
  },
  meta: async (): Promise<SnapshotMeta | null> => null,
};

// ---------------------------------------------------------------------------
// Static mode: reads files written by backend/app/scripts/export_static.py and
// reproduces the server's search / filter / ego-network logic in the browser.
// ---------------------------------------------------------------------------

const DATA = `${import.meta.env.BASE_URL}data`;
const cache = new Map<string, Promise<unknown>>();

/** Fetch a data file once; later callers share the same promise. */
function file<T>(name: string): Promise<T> {
  let p = cache.get(name);
  if (!p) {
    p = get<T>(`${DATA}/${name}`);
    p.catch(() => cache.delete(name)); // allow a retry after a network blip
    cache.set(name, p);
  }
  return p as Promise<T>;
}

const shard = (id: string) => id.slice(0, 2).toLowerCase();

interface GraphIndex {
  entities: EntitySummary[];
  byId: Map<string, EntitySummary>;
  links: GraphLink[];
  adjacency: Map<string, string[]>;
}

let graphIndex: Promise<GraphIndex> | null = null;

function loadGraphIndex(): Promise<GraphIndex> {
  graphIndex ??= Promise.all([
    file<[string, string, string][]>("entities.json"),
    file<[string, string, string][]>("graph.json"),
  ])
    .then(([ents, rels]) => {
      const entities = ents.map(([id, type, name]) => ({ id, type, name }));
      const byId = new Map(entities.map((e) => [e.id, e]));
      const links = rels.map(([source, target, type]) => ({ source, target, type }));
      const adjacency = new Map<string, string[]>();
      const add = (a: string, b: string) => {
        const list = adjacency.get(a);
        if (list) list.push(b);
        else adjacency.set(a, [b]);
      };
      for (const l of links) {
        add(l.source, l.target);
        add(l.target, l.source);
      }
      return { entities, byId, links, adjacency };
    })
    .catch((err) => {
      graphIndex = null;
      throw err;
    });
  return graphIndex;
}

function linksAmong(links: GraphLink[], ids: Set<string>): GraphLink[] {
  return links.filter((l) => ids.has(l.source) && ids.has(l.target));
}

const staticApi: typeof liveApi = {
  stats: () => file<Stats>("stats.json"),

  // mirrors GET /api/entities: case-insensitive name match, ordered by name, limit 100
  entities: async ({ q, type, limit = 100 }: EntityParams = {}) => {
    const { entities } = await loadGraphIndex();
    const needle = q?.toLowerCase();
    const out: EntitySummary[] = [];
    for (const e of entities) {
      if (type && e.type !== type) continue;
      if (needle && !e.name.toLowerCase().includes(needle)) continue;
      out.push(e);
      if (out.length >= limit) break;
    }
    return out;
  },

  entity: async (id: string) => {
    const items = await file<Record<string, EntityDetail>>(`entities/${shard(id)}.json`);
    const hit = items[id];
    if (!hit) throw new Error("404 Entity not found");
    return hit;
  },

  // mirrors GET /api/graph: ego network (BFS, both directions), type browse, or default seed
  graph: async ({ center, depth = 1, limit = 300, types }: GraphParams = {}) => {
    const { entities, byId, links, adjacency } = await loadGraphIndex();
    const typeSet = types ? new Set(types.split(",").map((t) => t.trim()).filter(Boolean)) : null;

    let nodes: EntitySummary[];
    let edges: GraphLink[];
    if (center) {
      if (!byId.has(center)) throw new Error("404 center entity not found");
      const seen = new Set([center]);
      let frontier = [center];
      for (let d = 0; d < depth && frontier.length; d++) {
        const next: string[] = [];
        for (const id of frontier)
          for (const n of adjacency.get(id) ?? [])
            if (!seen.has(n)) {
              seen.add(n);
              next.push(n);
            }
        frontier = next;
      }
      nodes = [...seen].map((id) => byId.get(id)!).filter((n) => !typeSet || typeSet.has(n.type));
      edges = linksAmong(links, new Set(nodes.map((n) => n.id)));
    } else if (typeSet) {
      nodes = entities.filter((e) => typeSet.has(e.type)).slice(0, limit);
      edges = linksAmong(links, new Set(nodes.map((n) => n.id)));
    } else {
      edges = links.slice(0, limit);
      const ids = new Set(edges.flatMap((l) => [l.source, l.target]));
      nodes = [...ids].map((id) => byId.get(id)!).filter(Boolean);
    }
    return {
      nodes: nodes.map(({ id, type, name }) => ({ id, type, name })),
      links: edges.map((l) => ({ ...l })),
    };
  },

  map: async (type?: string) => {
    const fc = await file<FeatureCollection>("map.json");
    return type ? { ...fc, features: fc.features.filter((f) => f.properties.type === type) } : fc;
  },

  directory: async (perType = 8) => {
    const dir = await file<DirectoryOut>("directory.json");
    return { groups: dir.groups.map((g) => ({ ...g, items: g.items.slice(0, perType) })) };
  },

  link: async (ref: LinkRef) => {
    const items = await file<Record<string, LinkOut>>(`links/${shard(ref.source_id)}.json`);
    const hit = items[`${ref.source_id}|${ref.target_id}|${ref.type}`];
    if (!hit) throw new Error("404 link not found");
    return hit;
  },

  meta: () => file<SnapshotMeta>("meta.json"),
};

export const api = IS_STATIC ? staticApi : liveApi;

// color per entity type — shared by graph + map so the two views read as one system
export const TYPE_COLORS: Record<string, string> = {
  person: "#4ea1ff",
  organization: "#ffb020",
  vessel: "#2dd4bf",
  aircraft: "#c084fc",
  location: "#f472b6",
  program: "#f43f5e",
  commodity: "#a3e635",
  unknown: "#94a3b8",
};

export const colorFor = (type: string) => TYPE_COLORS[type] ?? TYPE_COLORS.unknown;
