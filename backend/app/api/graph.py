"""Node-link projection of the entity/relationship graph for the graph view."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Entity, Relationship
from app.schemas import GraphLink, GraphNode, GraphOut

router = APIRouter(prefix="/api", tags=["graph"])


def _links_among(session: Session, ids: set[uuid.UUID]) -> list[Relationship]:
    if not ids:
        return []
    return list(
        session.scalars(
            select(Relationship).where(
                Relationship.source_id.in_(ids), Relationship.target_id.in_(ids)
            )
        )
    )


def _ego_ids(session: Session, center: uuid.UUID, depth: int) -> set[uuid.UUID]:
    """BFS outward from ``center`` following relationships in both directions."""
    seen: set[uuid.UUID] = {center}
    frontier: set[uuid.UUID] = {center}
    for _ in range(depth):
        if not frontier:
            break
        rows = session.execute(
            select(Relationship.source_id, Relationship.target_id).where(
                or_(
                    Relationship.source_id.in_(frontier),
                    Relationship.target_id.in_(frontier),
                )
            )
        ).all()
        neighbors = {sid for sid, _ in rows} | {tid for _, tid in rows}
        frontier = neighbors - seen
        seen |= neighbors
    return seen


@router.get("/graph", response_model=GraphOut)
def graph(
    center: uuid.UUID | None = Query(None, description="Build an ego network around this entity"),
    depth: int = Query(1, ge=1, le=3),
    limit: int = Query(300, le=2000, description="Max nodes/relationships to return"),
    types: str | None = Query(
        None, description="Comma-separated entity types to include (e.g. vessel,organization)"
    ),
    session: Session = Depends(get_session),
) -> GraphOut:
    type_set = {t.strip() for t in types.split(",") if t.strip()} if types else None

    if center is not None:
        if session.get(Entity, center) is None:
            raise HTTPException(status_code=404, detail="center entity not found")
        node_ids = _ego_ids(session, center, depth)
        nodes = list(session.scalars(select(Entity).where(Entity.id.in_(node_ids))))
        if type_set is not None:
            nodes = [n for n in nodes if n.type in type_set]
        links = _links_among(session, {n.id for n in nodes})
    elif type_set is not None:
        # Type-filtered browse: pull nodes of the selected types plus edges among them.
        # (A single type with no internal edges still shows its nodes.)
        nodes = list(
            session.scalars(select(Entity).where(Entity.type.in_(type_set)).limit(limit))
        )
        links = _links_among(session, {n.id for n in nodes})
    else:
        # Default: seed with a capped set of relationships so nodes come out connected.
        links = list(session.scalars(select(Relationship).limit(limit)))
        node_ids = {r.source_id for r in links} | {r.target_id for r in links}
        nodes = (
            list(session.scalars(select(Entity).where(Entity.id.in_(node_ids))))
            if node_ids
            else []
        )

    return GraphOut(
        nodes=[GraphNode(id=n.id, type=n.type, name=n.name) for n in nodes],
        links=[
            GraphLink(source=r.source_id, target=r.target_id, type=r.type) for r in links
        ],
    )
