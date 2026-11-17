from pathlib import Path

from app.ingest.ofac import OfacSdnConnector

FIXTURE = Path(__file__).parent / "fixtures" / "sdn_sample.xml"


def _parse():
    return OfacSdnConnector().parse(FIXTURE.read_bytes())


def test_entities_by_type():
    batch = _parse()
    by_type: dict[str, list[str]] = {}
    for e in batch.entities:
        by_type.setdefault(e.type, []).append(e.name)

    assert "Juan Perez" in by_type["person"]
    # non-individual name lives in lastName only
    assert "CUBAEXPORT" in by_type["organization"]
    assert "PILAR" in by_type["vessel"]
    # program + flag country synthesized as their own entities
    assert "CUBA" in by_type["program"]
    assert "Panama" in by_type["location"]


def test_program_entity_deduped():
    batch = _parse()
    programs = [e for e in batch.entities if e.type == "program" and e.name == "CUBA"]
    assert len(programs) == 1  # three entries share one CUBA program node


def test_aliases_parsed():
    batch = _parse()
    perez = next(e for e in batch.entities if e.name == "Juan Perez")
    assert "Juanito Gonzalez" in perez.aliases


def test_vessel_properties():
    batch = _parse()
    pilar = next(e for e in batch.entities if e.name == "PILAR")
    assert pilar.properties["vessel_flag"] == "Panama"
    assert pilar.properties["call_sign"] == "ABCD"
    assert pilar.properties["gross_registered_tonnage"] == "3200"


def test_relationships():
    batch = _parse()
    kinds = {(r.type) for r in batch.relationships}
    assert {"sanctioned_under", "flagged_in", "owns"} <= kinds

    # owner -> owns -> vessel, resolved by source_ref
    refs = {e.source_ref: e for e in batch.entities}
    owns = [r for r in batch.relationships if r.type == "owns"]
    assert owns, "expected an owns relationship"
    owner = refs[owns[0].source_ref]
    vessel = refs[owns[0].target_ref]
    assert owner.type == "organization"
    assert vessel.name == "PILAR"


def test_relationship_provenance():
    batch = _parse()
    sanctioned = next(r for r in batch.relationships if r.type == "sanctioned_under")
    assert "OFAC" in sanctioned.description
    assert "CUBA" in sanctioned.description
    assert sanctioned.source_url  # points at the SDN feed
    assert sanctioned.confidence == "high"

    # every OFAC-emitted link carries a human description
    assert all(r.description for r in batch.relationships)
