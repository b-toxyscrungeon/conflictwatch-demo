from pathlib import Path

from app.ingest.adsb import OpenSkyConnector

FIXTURE = Path(__file__).parent / "fixtures" / "opensky_sample.json"


def _parse():
    return OpenSkyConnector().parse(FIXTURE.read_bytes())


def test_aircraft_entities_have_position():
    batch = _parse()
    aircraft = [e for e in batch.entities if e.type == "aircraft"]
    # third state has null lat/lon and is skipped
    assert len(aircraft) == 2
    for a in aircraft:
        assert a.lonlat is not None
        lon, lat = a.lonlat
        assert -85.5 <= lon <= -73.5
        assert 19.0 <= lat <= 24.0


def test_callsign_and_fallback_name():
    batch = _parse()
    by_ref = {e.source_ref: e for e in batch.entities if e.type == "aircraft"}
    assert by_ref["aircraft:ad9c1e"].name == "AAL123"  # trimmed
    assert by_ref["aircraft:0d0a1b"].properties["origin_country"] == "Cuba"


def test_registered_in_country_edges():
    batch = _parse()
    countries = {e.name for e in batch.entities if e.type == "location"}
    assert {"United States", "Cuba"} <= countries
    rels = {(r.type) for r in batch.relationships}
    assert "registered_in" in rels


def test_registered_in_provenance():
    batch = _parse()
    reg = next(r for r in batch.relationships if r.type == "registered_in")
    assert "registered in" in reg.description
    assert reg.source_url
    assert reg.confidence == "medium"


def test_skips_positionless_states():
    batch = _parse()
    refs = {e.source_ref for e in batch.entities}
    assert "aircraft:c0ffee" not in refs  # had null coordinates
