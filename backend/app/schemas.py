from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class EntitySummary(BaseModel):
    id: uuid.UUID
    type: str
    name: str


class RelationshipOut(BaseModel):
    id: uuid.UUID
    type: str
    source_id: uuid.UUID
    target_id: uuid.UUID
    other: EntitySummary
    direction: str  # "out" (this->other) or "in" (other->this)
    # link provenance — the why/how/source of this connection
    description: str | None = None
    source: str
    source_url: str | None = None
    confidence: str | None = None


class LinkAssertion(BaseModel):
    """One source's assertion of a link; several may corroborate the same pair+type."""

    source: str
    description: str | None = None
    source_url: str | None = None
    confidence: str | None = None
    retrieved_at: datetime | None = None
    properties: dict


class LinkOut(BaseModel):
    """A directed link between two entities, with every source that asserts it."""

    source_entity: EntitySummary
    target_entity: EntitySummary
    type: str
    assertions: list[LinkAssertion]


class EntityDetail(EntitySummary):
    properties: dict
    aliases: list[str]
    source: str
    source_ref: str
    relationships: list[RelationshipOut]


class GraphNode(BaseModel):
    id: uuid.UUID
    type: str
    name: str


class GraphLink(BaseModel):
    source: uuid.UUID
    target: uuid.UUID
    type: str


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]


class TypeCount(BaseModel):
    type: str
    count: int


class StatsOut(BaseModel):
    entities: int
    relationships: int
    by_type: list[TypeCount]


class DirectoryItem(BaseModel):
    id: uuid.UUID
    type: str
    name: str
    degree: int  # number of connections


class DirectoryGroup(BaseModel):
    type: str
    total: int  # total entities of this type
    items: list[DirectoryItem]


class DirectoryOut(BaseModel):
    groups: list[DirectoryGroup]
