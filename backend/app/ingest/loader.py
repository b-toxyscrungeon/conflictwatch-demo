"""Loads an ``IngestBatch`` into the database, idempotently.

Entities are upserted on ``(source, source_ref)``; relationships on
``(source_id, target_id, type, source)``. Re-running the same connector updates
in place rather than duplicating, so ingests are safe to schedule.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.base import Connector
from app.models import Entity, EntityAlias, IngestRun, Relationship


def _point_ewkt(lonlat: tuple[float, float]) -> str:
    lon, lat = lonlat
    return f"SRID=4326;POINT({lon} {lat})"


def load(session: Session, connector: Connector) -> IngestRun:
    run = IngestRun(source=connector.source_name, status="running")
    session.add(run)
    session.flush()

    try:
        batch = connector.parse(connector.fetch())

        existing: dict[str, Entity] = {
            e.source_ref: e
            for e in session.scalars(
                select(Entity).where(Entity.source == connector.source_name)
            )
        }
        ref_to_id: dict[str, object] = {}
        created = updated = 0
        now = datetime.now(UTC)

        for raw in batch.entities:
            ent = existing.get(raw.source_ref)
            if ent is None:
                ent = Entity(source=connector.source_name, source_ref=raw.source_ref)
                session.add(ent)
                existing[raw.source_ref] = ent
                created += 1
            else:
                updated += 1
            ent.type = raw.type
            ent.name = raw.name
            ent.properties = raw.properties
            ent.last_seen = now
            ent.geom = _point_ewkt(raw.lonlat) if raw.lonlat else None
            ent.aliases = [
                EntityAlias(name=a, alias_type="aka") for a in dict.fromkeys(raw.aliases)
            ]
            session.flush()
            ref_to_id[raw.source_ref] = ent.id

        # existing relationships for this source, keyed for idempotent upsert
        existing_rels: dict[tuple, Relationship] = {
            (r.source_id, r.target_id, r.type): r
            for r in session.scalars(
                select(Relationship).where(Relationship.source == connector.source_name)
            )
        }
        rel_created = 0
        for rel in batch.relationships:
            sid = ref_to_id.get(rel.source_ref)
            tid = ref_to_id.get(rel.target_ref)
            if sid is None or tid is None:
                continue
            key = (sid, tid, rel.type)
            row = existing_rels.get(key)
            if row is None:
                row = Relationship(
                    source_id=sid, target_id=tid, type=rel.type, source=connector.source_name
                )
                session.add(row)
                existing_rels[key] = row
                rel_created += 1
            row.properties = rel.properties
            row.description = rel.description
            row.source_url = rel.source_url
            row.confidence = rel.confidence
            row.retrieved_at = now

        run.stats = {
            "entities_created": created,
            "entities_updated": updated,
            "relationships_created": rel_created,
            "entities_total": len(batch.entities),
        }
        run.status = "success"
        run.finished_at = datetime.now(UTC)
        session.commit()
    except Exception as exc:  # noqa: BLE001 — record failure then re-raise
        run.status = "error"
        run.error = str(exc)
        run.finished_at = datetime.now(UTC)
        session.commit()
        raise

    return run
