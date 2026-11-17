"""ADS-B aircraft connector (OpenSky Network).

Pulls current aircraft state vectors within the area-of-interest bounding box
from OpenSky's public REST API and emits one entity per airframe, with its
live position written to ``geom``. Intended to run hourly. Each aircraft is
also linked to its registration country to enrich the graph.

State-vector array layout (OpenSky ``/states/all``):
    0 icao24  1 callsign  2 origin_country  ... 5 longitude  6 latitude
    7 baro_altitude  8 on_ground  9 velocity  10 true_track  ...
    13 geo_altitude  14 squawk
"""

from __future__ import annotations

import json

import httpx

from app.config import settings
from app.ingest.base import IngestBatch, RawEntity, RawRelationship, dedupe_entities

SOURCE_NAME = "adsb_opensky"


def _slug(text: str) -> str:
    return " ".join((text or "").split()).strip().lower()


class OpenSkyConnector:
    source_name = SOURCE_NAME

    def __init__(
        self,
        url: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ):
        self.url = url or settings.opensky_url
        self.bbox = bbox or settings.aoi  # (lat_min, lon_min, lat_max, lon_max)

    def fetch(self) -> bytes:
        lat_min, lon_min, lat_max, lon_max = self.bbox
        resp = httpx.get(
            self.url,
            params={"lamin": lat_min, "lomin": lon_min, "lamax": lat_max, "lomax": lon_max},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.content

    def parse(self, raw: bytes) -> IngestBatch:
        data = json.loads(raw or b"{}")
        states = data.get("states") or []
        entities: list[RawEntity] = []
        relationships: list[RawRelationship] = []

        for s in states:
            icao24 = (s[0] or "").strip().lower()
            lon, lat = s[5], s[6]
            if not icao24 or lon is None or lat is None:
                continue
            callsign = (s[1] or "").strip()
            country = (s[2] or "").strip()
            ref = f"aircraft:{icao24}"

            props = {
                "icao24": icao24,
                "callsign": callsign,
                "origin_country": country,
                "on_ground": bool(s[8]),
                "velocity_ms": s[9],
                "heading_deg": s[10],
                "geo_altitude_m": s[13] if len(s) > 13 else None,
                "squawk": (s[14] if len(s) > 14 else None),
                "last_contact": s[4],
            }
            props = {k: v for k, v in props.items() if v not in (None, "")}

            entities.append(
                RawEntity(
                    source_ref=ref,
                    type="aircraft",
                    name=callsign or icao24.upper(),
                    properties=props,
                    lonlat=(lon, lat),
                )
            )

            if country:
                country_ref = f"country:{_slug(country)}"
                entities.append(
                    RawEntity(source_ref=country_ref, type="location", name=country)
                )
                display = callsign or icao24.upper()
                relationships.append(
                    RawRelationship(
                        ref,
                        country_ref,
                        "registered_in",
                        description=(
                            f"Aircraft {display} ({icao24}) is registered in {country}, "
                            "per its ADS-B transponder's origin country (OpenSky)."
                        ),
                        source_url=self.url,
                        confidence="medium",
                    )
                )

        return IngestBatch(
            entities=dedupe_entities(entities),
            relationships=relationships,
        )
