"""AIS vessel connector (AISStream.io).

AISStream delivers vessel messages over a WebSocket. Rather than hold an
always-on connection, we open the stream briefly (``ais_sample_seconds``) on a
daily cadence, harvest the latest position per vessel inside the area of
interest, then disconnect — a low-overhead daily snapshot that just repositions
each vessel's dot.

Two message types are consumed:
- ``PositionReport`` — live lat/lon, speed, course, heading (keyed by MMSI).
- ``ShipStaticData`` — name, IMO, callsign, ship type (enriches the vessel).

A free API key is required (https://aisstream.io); set ``AISSTREAM_API_KEY``.
Cross-linking these vessels to OFAC-sanctioned vessels by name/IMO is deferred
to the Phase 2 entity-resolution layer; here each MMSI is its own vessel entity.
"""

from __future__ import annotations

import asyncio
import json

import websockets

from app.config import settings
from app.ingest.base import IngestBatch, RawEntity


class AisStreamConnector:
    source_name = "ais_aisstream"

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        sample_seconds: int | None = None,
    ):
        self.url = url or settings.aisstream_url
        self.api_key = api_key if api_key is not None else settings.aisstream_api_key
        self.bbox = bbox or settings.aoi  # (lat_min, lon_min, lat_max, lon_max)
        self.sample_seconds = sample_seconds or settings.ais_sample_seconds

    def fetch(self) -> bytes:
        if not self.api_key:
            raise RuntimeError(
                "AISSTREAM_API_KEY is not set. Get a free key at https://aisstream.io "
                "and add it to backend/.env."
            )
        messages = asyncio.run(self._collect())
        return json.dumps(messages).encode()

    async def _collect(self) -> list[dict]:
        lat_min, lon_min, lat_max, lon_max = self.bbox
        subscribe = {
            "APIKey": self.api_key,
            # AISStream bounding box corners are [lat, lon] pairs.
            "BoundingBoxes": [[[lat_min, lon_min], [lat_max, lon_max]]],
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
        }
        collected: list[dict] = []
        async with websockets.connect(self.url, ping_interval=None) as ws:
            await ws.send(json.dumps(subscribe))
            try:
                async with asyncio.timeout(self.sample_seconds):
                    async for raw in ws:
                        collected.append(json.loads(raw))
            except TimeoutError:
                pass
        return collected

    def parse(self, raw: bytes) -> IngestBatch:
        messages = json.loads(raw or b"[]")
        vessels: dict[str, dict] = {}

        for msg in messages:
            meta = msg.get("MetaData") or {}
            mmsi = meta.get("MMSI")
            if mmsi is None:
                continue
            key = str(mmsi)
            body = msg.get("Message") or {}
            v = vessels.setdefault(key, {"props": {"mmsi": key}, "lonlat": None, "name": None})

            name = (meta.get("ShipName") or "").strip()
            if name:
                v["name"] = name

            if msg.get("MessageType") == "PositionReport":
                report = body.get("PositionReport") or {}
                lon = report.get("Longitude", meta.get("longitude"))
                lat = report.get("Latitude", meta.get("latitude"))
                if lon is not None and lat is not None:
                    v["lonlat"] = (lon, lat)  # last report wins
                    v["props"].update(
                        {
                            "sog_knots": report.get("Sog"),
                            "cog_deg": report.get("Cog"),
                            "heading_deg": report.get("TrueHeading"),
                            "time_utc": meta.get("time_utc"),
                        }
                    )
            elif msg.get("MessageType") == "ShipStaticData":
                static = body.get("ShipStaticData") or {}
                v["props"].update(
                    {
                        "imo": static.get("ImoNumber"),
                        "call_sign": (static.get("CallSign") or "").strip() or None,
                        "ship_type": static.get("Type"),
                        "destination": (static.get("Destination") or "").strip() or None,
                    }
                )

        entities: list[RawEntity] = []
        for key, v in vessels.items():
            if v["lonlat"] is None:
                continue  # need a position to place it on the map
            props = {k: val for k, val in v["props"].items() if val not in (None, "")}
            entities.append(
                RawEntity(
                    source_ref=f"mmsi:{key}",
                    type="vessel",
                    name=v["name"] or f"MMSI {key}",
                    properties=props,
                    lonlat=v["lonlat"],
                )
            )

        return IngestBatch(entities=entities, relationships=[])
