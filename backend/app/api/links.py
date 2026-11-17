"""Link (relationship) detail — the why/how/source behind a connection.

A conceptual link is a directed ``(source_id, target_id, type)`` triple. Several
sources may assert the same link; each is its own row, so this endpoint returns
them all as ``assertions`` — that's how corroboration surfaces ("asserted by OFAC
and OpenCorporates").
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Entity, Relationship
from app.schemas import EntitySummary, LinkAssertion, LinkOut

router = APIRouter(prefix="/api", tags=["links"])


@router.get("/link", response_model=LinkOut)
def link(
    source_id: uuid.UUID = Query(..., description="Link's source entity"),
    target_id: uuid.UUID = Query(..., description="Link's target entity"),
    type: str = Query(..., description="Relationship type, e.g. sanctioned_under"),
    session: Session = Depends(get_session),
) -> LinkOut:
    src = session.get(Entity, source_id)
    tgt = session.get(Entity, target_id)
    if src is None or tgt is None:
        raise HTTPException(status_code=404, detail="source or target entity not found")

    rows = list(
        session.scalars(
            select(Relationship).where(
                Relationship.source_id == source_id,
                Relationship.target_id == target_id,
                Relationship.type == type,
            )
        )
    )
    if not rows:
        raise HTTPException(status_code=404, detail="link not found")

    return LinkOut(
        source_entity=EntitySummary(id=src.id, type=src.type, name=src.name),
        target_entity=EntitySummary(id=tgt.id, type=tgt.type, name=tgt.name),
        type=type,
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
