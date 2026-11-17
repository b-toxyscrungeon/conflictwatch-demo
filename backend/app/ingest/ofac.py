"""OFAC SDN (Specially Designated Nationals) connector.

Parses Treasury's public legacy ``sdn.xml`` feed into the entity/relationship
graph. One SDN entry becomes an entity (person/organization/vessel/aircraft);
its sanctions programs, vessel flag states, and vessel owners become linked
entities so the graph lights up with real edges out of the box.

Schema reference: the legacy SDN XML uses the namespace
``http://tempuri.org/sdnList.xsd``. We match tags with the ``{*}`` wildcard so
the parser is namespace-agnostic and resilient to feed URL changes.
"""

from __future__ import annotations

import re

import httpx
from lxml import etree

from app.config import settings
from app.ingest.base import IngestBatch, RawEntity, RawRelationship, dedupe_entities

SOURCE_NAME = "ofac_sdn"

_SDN_TYPE_TO_ENTITY = {
    "individual": "person",
    "entity": "organization",
    "vessel": "vessel",
    "aircraft": "aircraft",
}


def _slug(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _compose_name(node: etree._Element) -> str:
    first = (node.findtext("{*}firstName") or "").strip()
    last = (node.findtext("{*}lastName") or "").strip()
    return " ".join(p for p in (first, last) if p)


class OfacSdnConnector:
    source_name = SOURCE_NAME

    def __init__(self, url: str | None = None):
        self.url = url or settings.ofac_sdn_url

    def fetch(self) -> bytes:
        resp = httpx.get(self.url, timeout=60.0, follow_redirects=True)
        resp.raise_for_status()
        return resp.content

    def parse(self, raw: bytes) -> IngestBatch:
        root = etree.fromstring(raw)
        entities: list[RawEntity] = []
        relationships: list[RawRelationship] = []

        for entry in root.iter("{*}sdnEntry"):
            uid = (entry.findtext("{*}uid") or "").strip()
            if not uid:
                continue
            ref = f"sdn:{uid}"
            sdn_type = (entry.findtext("{*}sdnType") or "").strip().lower()
            entity_type = _SDN_TYPE_TO_ENTITY.get(sdn_type, sdn_type or "unknown")
            name = _compose_name(entry) or f"SDN {uid}"

            programs = [
                (p.text or "").strip()
                for p in entry.iterfind("{*}programList/{*}program")
                if (p.text or "").strip()
            ]
            addresses = self._addresses(entry)
            props: dict = {
                "sdn_type": sdn_type,
                "uid": uid,
                "programs": programs,
            }
            if addresses:
                props["addresses"] = addresses
            remarks = (entry.findtext("{*}remarks") or "").strip()
            if remarks:
                props["remarks"] = remarks

            aliases = [
                _compose_name(aka)
                for aka in entry.iterfind("{*}akaList/{*}aka")
                if _compose_name(aka)
            ]

            vessel = entry.find("{*}vesselInfo")
            if vessel is not None:
                props.update(self._vessel_props(vessel))

            entities.append(
                RawEntity(
                    source_ref=ref,
                    type=entity_type,
                    name=name,
                    properties=props,
                    aliases=aliases,
                )
            )

            # sanctioned_under -> each program
            for program in programs:
                prog_ref = f"program:{_slug(program)}"
                entities.append(
                    RawEntity(source_ref=prog_ref, type="program", name=program)
                )
                relationships.append(
                    RawRelationship(
                        ref,
                        prog_ref,
                        "sanctioned_under",
                        description=(
                            f"{name} is designated on the OFAC Specially Designated "
                            f"Nationals list under the {program} sanctions program."
                        ),
                        source_url=self.url,
                        confidence="high",
                    )
                )

            # vessel flag state + owner edges
            if vessel is not None:
                flag = (vessel.findtext("{*}vesselFlag") or "").strip()
                if flag:
                    country_ref = f"country:{_slug(flag)}"
                    entities.append(
                        RawEntity(source_ref=country_ref, type="location", name=flag)
                    )
                    relationships.append(
                        RawRelationship(
                            ref,
                            country_ref,
                            "flagged_in",
                            description=(
                                f"Vessel {name} is registered under the flag state "
                                f"{flag} per its OFAC SDN listing."
                            ),
                            source_url=self.url,
                            confidence="high",
                        )
                    )
                owner = (vessel.findtext("{*}vesselOwner") or "").strip()
                if owner:
                    owner_ref = f"owner:{_slug(owner)}"
                    entities.append(
                        RawEntity(source_ref=owner_ref, type="organization", name=owner)
                    )
                    # owner owns the vessel
                    relationships.append(
                        RawRelationship(
                            owner_ref,
                            ref,
                            "owns",
                            description=(
                                f"{owner} is listed as the registered owner of "
                                f"vessel {name} in the OFAC SDN List."
                            ),
                            source_url=self.url,
                            confidence="high",
                        )
                    )

        return IngestBatch(
            entities=dedupe_entities(entities),
            relationships=relationships,
        )

    @staticmethod
    def _addresses(entry: etree._Element) -> list[dict]:
        out: list[dict] = []
        for addr in entry.iterfind("{*}addressList/{*}address"):
            record = {
                k: (addr.findtext("{*}" + tag) or "").strip()
                for k, tag in (
                    ("address", "address1"),
                    ("city", "city"),
                    ("state", "stateOrProvince"),
                    ("postal_code", "postalCode"),
                    ("country", "country"),
                )
            }
            record = {k: v for k, v in record.items() if v}
            if record:
                out.append(record)
        return out

    @staticmethod
    def _vessel_props(vessel: etree._Element) -> dict:
        fields = {
            "call_sign": "callSign",
            "vessel_type": "vesselType",
            "vessel_flag": "vesselFlag",
            "vessel_owner": "vesselOwner",
            "tonnage": "tonnage",
            "gross_registered_tonnage": "grossRegisteredTonnage",
        }
        out = {
            key: (vessel.findtext("{*}" + tag) or "").strip()
            for key, tag in fields.items()
        }
        return {k: v for k, v in out.items() if v}
