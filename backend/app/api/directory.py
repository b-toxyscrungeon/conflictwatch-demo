"""Directory — the top entities per type, for the wiki landing page.

Ranks entities within each type by degree (number of connections), so the
landing page surfaces the hubs — the busiest programs, countries, orgs, etc.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import DirectoryGroup, DirectoryItem, DirectoryOut

router = APIRouter(prefix="/api", tags=["directory"])

# Preferred display order; any other types are appended after these.
_TYPE_ORDER = ["program", "location", "organization", "person", "vessel", "aircraft", "commodity"]

# Degree = times an entity appears as either endpoint of a relationship.
_TOP_SQL = text(
    """
    WITH edge_counts AS (
        SELECT source_id AS id FROM relationships
        UNION ALL
        SELECT target_id AS id FROM relationships
    ),
    deg AS (SELECT id, count(*) AS degree FROM edge_counts GROUP BY id),
    ranked AS (
        SELECT e.id, e.type, e.name, COALESCE(d.degree, 0) AS degree,
               row_number() OVER (
                   PARTITION BY e.type ORDER BY COALESCE(d.degree, 0) DESC, e.name
               ) AS rn
        FROM entities e
        LEFT JOIN deg d ON d.id = e.id
    )
    SELECT id, type, name, degree FROM ranked WHERE rn <= :per_type
    """
)


@router.get("/directory", response_model=DirectoryOut)
def directory(
    per_type: int = Query(8, ge=1, le=50, description="Top entities per type"),
    session: Session = Depends(get_session),
) -> DirectoryOut:
    rows = session.execute(_TOP_SQL, {"per_type": per_type}).all()
    totals = dict(
        session.execute(text("SELECT type, count(*) FROM entities GROUP BY type")).all()
    )

    by_type: dict[str, list[DirectoryItem]] = {}
    for id_, type_, name, degree in rows:
        by_type.setdefault(type_, []).append(
            DirectoryItem(id=id_, type=type_, name=name, degree=degree)
        )

    ordered = [t for t in _TYPE_ORDER if t in by_type] + [
        t for t in by_type if t not in _TYPE_ORDER
    ]
    return DirectoryOut(
        groups=[
            DirectoryGroup(type=t, total=totals.get(t, 0), items=by_type[t]) for t in ordered
        ]
    )
