"""Connector interface shared by every data source.

A connector is pure and DB-free: it turns a raw source (a downloaded file, an
API response, a websocket frame) into ``RawEntity`` / ``RawRelationship`` value
objects. The loader (``app.ingest.loader``) is the only piece that touches the
database, so parsers stay trivially unit-testable.

Within a single source, entities are referenced by ``source_ref``; relationships
point at those refs. The loader resolves refs to real entity ids at load time.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RawEntity:
    source_ref: str
    type: str
    name: str
    properties: dict = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    # optional (lon, lat) in WGS84 for mappable entities
    lonlat: tuple[float, float] | None = None


@dataclass
class RawRelationship:
    source_ref: str  # source entity, by source_ref
    target_ref: str  # target entity, by source_ref
    type: str
    properties: dict = field(default_factory=dict)
    # link provenance — the human "why/how", where it came from, how sure
    description: str | None = None
    source_url: str | None = None
    confidence: str | None = None


@dataclass
class IngestBatch:
    entities: list[RawEntity] = field(default_factory=list)
    relationships: list[RawRelationship] = field(default_factory=list)


class Connector(Protocol):
    #: stable short name stored on every row's ``source`` column
    source_name: str

    def fetch(self) -> bytes:
        """Return raw source bytes (download or read a local snapshot)."""

    def parse(self, raw: bytes) -> IngestBatch:
        """Turn raw bytes into entities + relationships. No DB access."""


def dedupe_entities(entities: Iterable[RawEntity]) -> list[RawEntity]:
    """Collapse entities sharing a source_ref, merging aliases/properties.

    Sources like OFAC synthesize refs (e.g. one program entity referenced by
    many sanctioned parties); this keeps the last-writer name but unions aliases.
    """
    by_ref: dict[str, RawEntity] = {}
    for e in entities:
        existing = by_ref.get(e.source_ref)
        if existing is None:
            by_ref[e.source_ref] = e
            continue
        existing.aliases = sorted({*existing.aliases, *e.aliases})
        existing.properties = {**existing.properties, **e.properties}
        if e.lonlat and not existing.lonlat:
            existing.lonlat = e.lonlat
    return list(by_ref.values())
