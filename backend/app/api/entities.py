from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Entity, Relationship
from app.schemas import (
    EntityDetail,
    EntitySummary,
    RelationshipOut,
    StatsOut,
    TypeCount,
)

router = APIRouter(prefix="/api", tags=["entities"])


@router.get("/stats", response_model=StatsOut)
def stats(session: Session = Depends(get_session)) -> StatsOut:
    by_type = session.execute(
        select(Entity.type, func.count()).group_by(Entity.type).order_by(func.count().desc())
    ).all()
    return StatsOut(
        entities=session.scalar(select(func.count()).select_from(Entity)) or 0,
        relationships=session.scalar(select(func.count()).select_from(Relationship)) or 0,
        by_type=[TypeCount(type=t, count=c) for t, c in by_type],
    )


@router.get("/entities", response_model=list[EntitySummary])
def list_entities(
    q: str | None = Query(None, description="Case-insensitive name/alias search"),
    type: str | None = Query(None),
    limit: int = Query(100, le=1000),
    session: Session = Depends(get_session),
) -> list[EntitySummary]:
    stmt = select(Entity)
    if type:
        stmt = stmt.where(Entity.type == type)
    if q:
        stmt = stmt.where(or_(Entity.name.ilike(f"%{q}%")))
    stmt = stmt.order_by(Entity.name).limit(limit)
    return [EntitySummary(id=e.id, type=e.type, name=e.name) for e in session.scalars(stmt)]


@router.get("/entities/{entity_id}", response_model=EntityDetail)
def get_entity(
    entity_id: uuid.UUID, session: Session = Depends(get_session)
) -> EntityDetail:
    ent = session.get(Entity, entity_id)
    if ent is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    def _rel_out(r: Relationship, other: Entity, direction: str) -> RelationshipOut:
        return RelationshipOut(
            id=r.id,
            type=r.type,
            source_id=r.source_id,
            target_id=r.target_id,
            other=EntitySummary(id=other.id, type=other.type, name=other.name),
            direction=direction,
            description=r.description,
            source=r.source,
            source_url=r.source_url,
            confidence=r.confidence,
        )

    rels: list[RelationshipOut] = []
    outgoing = session.scalars(
        select(Relationship).where(Relationship.source_id == entity_id)
    )
    for r in outgoing:
        rels.append(_rel_out(r, session.get(Entity, r.target_id), "out"))
    incoming = session.scalars(
        select(Relationship).where(Relationship.target_id == entity_id)
    )
    for r in incoming:
        rels.append(_rel_out(r, session.get(Entity, r.source_id), "in"))

    return EntityDetail(
        id=ent.id,
        type=ent.type,
        name=ent.name,
        properties=ent.properties or {},
        aliases=[a.name for a in ent.aliases],
        source=ent.source,
        source_ref=ent.source_ref,
        relationships=rels,
    )
