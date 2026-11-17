"""Export a static snapshot of the API for the GitHub Pages demo build.

Writes every answer the frontend needs as JSON under ``frontend/public/data/``
so a ``VITE_STATIC=1`` build can run with no backend:

    meta.json              snapshot date + last successful run per source
    stats.json             /api/stats
    directory.json         /api/directory?per_type=50 (client slices to what it asks for)
    map.json               /api/map (full FeatureCollection; client filters by type)
    entities.json          every EntitySummary — the in-browser search/graph index
    graph.json             every relationship as {source, target, type}
    entities/<xx>.json     /api/entities/{id}, sharded by the id's first two hex chars
    links/<xx>.json        /api/link, keyed "source_id|target_id|type", sharded by source_id

Entity and link details are sharded (256 files each) rather than one file per
id: ~19k entities + ~24k links as individual files would bloat the repo and the
Pages deploy for no benefit.

Only data that the public API already serves is exported — no settings, keys or
``.env`` values are read or written.

Usage (from backend/, venv active):

    python -m app.scripts.export_static [--out ../frontend/public/data]
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from app.api.directory import directory as directory_route
from app.api.entities import stats as stats_route
from app.api.map import map_features as map_route
from app.db import SessionLocal
from app.models import Entity, EntityAlias, IngestRun, Relationship
from app.schemas import (
    EntityDetail,
    EntitySummary,
    LinkAssertion,
    LinkOut,
    RelationshipOut,
)

DEFAULT_OUT = Path(__file__).resolve().parents[3] / "frontend" / "public" / "data"


def _shard(uuid_str: str) -> str:
    return uuid_str[:2]


def _dump(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # compact separators: these files are fetched by browsers
    path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False, default=str))


def _model(m) -> dict:
    return m.model_dump(mode="json")


def export(out: Path) -> dict[str, int]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    with SessionLocal() as session:
        # --- endpoints reused verbatim from the API --------------------------------
        _dump(out / "stats.json", _model(stats_route(session=session)))
        _dump(out / "directory.json", _model(directory_route(per_type=50, session=session)))
        _dump(out / "map.json", map_route(type=None, limit=20000, session=session))

        # --- snapshot metadata ----------------------------------------------------
        runs = session.execute(
            select(IngestRun.source, func.max(IngestRun.finished_at))
            .where(IngestRun.status == "success")
            .group_by(IngestRun.source)
        ).all()
        sources = {src: ts.isoformat() for src, ts in runs if ts}
        as_of = max((ts for _, ts in runs if ts), default=None)
        _dump(
            out / "meta.json",
            {
                "as_of": as_of.isoformat() if as_of else None,
                "sources": sources,
                "exported_at": datetime.now(UTC).isoformat(),
            },
        )

        # --- bulk load the graph once ---------------------------------------------
        entities = {e.id: e for e in session.scalars(select(Entity).order_by(Entity.name))}
        summaries = {
            eid: EntitySummary(id=e.id, type=e.type, name=e.name) for eid, e in entities.items()
        }
        aliases: dict = defaultdict(list)
        for eid, name in session.execute(select(EntityAlias.entity_id, EntityAlias.name)):
            aliases[eid].append(name)
        rels = list(session.scalars(select(Relationship).order_by(Relationship.created_at)))

    # entities.json: [id, type, name] tuples (ordered by name) — compact search index
    _dump(out / "entities.json", [[str(s.id), s.type, s.name] for s in summaries.values()])
    # graph.json: [source, target, type] tuples, in the server's default seed order
    _dump(out / "graph.json", [[str(r.source_id), str(r.target_id), r.type] for r in rels])

    # --- /api/entities/{id} ----------------------------------------------------------
    outgoing: dict = defaultdict(list)
    incoming: dict = defaultdict(list)
    for r in rels:
        outgoing[r.source_id].append(r)
        incoming[r.target_id].append(r)

    def rel_out(r: Relationship, other_id, direction: str) -> RelationshipOut:
        return RelationshipOut(
            id=r.id,
            type=r.type,
            source_id=r.source_id,
            target_id=r.target_id,
            other=summaries[other_id],
            direction=direction,
            description=r.description,
            source=r.source,
            source_url=r.source_url,
            confidence=r.confidence,
        )

    entity_shards: dict[str, dict] = defaultdict(dict)
    for eid, e in entities.items():
        detail = EntityDetail(
            id=e.id,
            type=e.type,
            name=e.name,
            properties=e.properties or {},
            aliases=aliases.get(eid, []),
            source=e.source,
            source_ref=e.source_ref,
            relationships=[rel_out(r, r.target_id, "out") for r in outgoing[eid]]
            + [rel_out(r, r.source_id, "in") for r in incoming[eid]],
        )
        entity_shards[_shard(str(eid))][str(eid)] = _model(detail)
    for shard, items in entity_shards.items():
        _dump(out / "entities" / f"{shard}.json", items)

    # --- /api/link -------------------------------------------------------------------
    grouped: dict = defaultdict(list)
    for r in rels:
        grouped[(r.source_id, r.target_id, r.type)].append(r)
    link_shards: dict[str, dict] = defaultdict(dict)
    for (sid, tid, rtype), rows in grouped.items():
        link = LinkOut(
            source_entity=summaries[sid],
            target_entity=summaries[tid],
            type=rtype,
            assertions=[
                LinkAssertion(
                    source=r.source,
                    description=r.description,
                    source_url=r.source_url,
                    confidence=r.confidence,
                    retrieved_at=r.retrieved_at,
                    properties=r.properties or {},
                )
                for r in rows
            ],
        )
        link_shards[_shard(str(sid))][f"{sid}|{tid}|{rtype}"] = _model(link)
    for shard, items in link_shards.items():
        _dump(out / "links" / f"{shard}.json", items)

    return {"entities": len(entities), "relationships": len(rels), "links": len(grouped)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    counts = export(args.out)
    size = sum(p.stat().st_size for p in args.out.rglob("*.json"))
    print(f"exported {counts} -> {args.out} ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
