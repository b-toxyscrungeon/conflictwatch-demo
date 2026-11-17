"""Geographic projection: entities carrying a geometry, as GeoJSON."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Entity

router = APIRouter(prefix="/api", tags=["map"])


@router.get("/map")
def map_features(
    type: str | None = Query(None),
    limit: int = Query(5000, le=20000),
    session: Session = Depends(get_session),
) -> dict:
    """FeatureCollection of every entity with a geometry.

    OFAC data is largely aspatial, so this lights up once spatial sources
    (AIS ships, ADS-B flights, mapped bases/POIs) are ingested.
    """
    stmt = select(
        Entity.id,
        Entity.type,
        Entity.name,
        Entity.last_seen,
        func.ST_AsGeoJSON(Entity.geom),
    ).where(Entity.geom.isnot(None))
    if type:
        stmt = stmt.where(Entity.type == type)
    stmt = stmt.limit(limit)

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(geojson),
            "properties": {
                "id": str(eid),
                "type": etype,
                "name": name,
                # ISO8601 so the client can fade contacts by age
                "last_seen": last_seen.isoformat() if last_seen else None,
            },
        }
        for eid, etype, name, last_seen, geojson in session.execute(stmt).all()
    ]
    return {"type": "FeatureCollection", "features": features}
