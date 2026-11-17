from pathlib import Path

from app.ingest.ais import AisStreamConnector

FIXTURE = Path(__file__).parent / "fixtures" / "ais_sample.json"


def _parse():
    return AisStreamConnector(api_key="test").parse(FIXTURE.read_bytes())


def test_latest_position_wins():
    batch = _parse()
    vessels = {e.source_ref: e for e in batch.entities}
    # two position reports for the same MMSI -> keep the last one
    nile = vessels["mmsi:356005000"]
    assert nile.lonlat == (-82.4, 23.1)
    assert nile.name == "MAERSK NILE"  # trimmed


def test_static_data_merged():
    batch = _parse()
    nile = next(e for e in batch.entities if e.source_ref == "mmsi:356005000")
    assert nile.properties["imo"] == 9784271
    assert nile.properties["call_sign"] == "3EHM8"
    assert nile.properties["destination"] == "HAVANA"
    assert nile.properties["sog_knots"] == 12.1


def test_vessel_without_position_skipped():
    batch = _parse()
    refs = {e.source_ref for e in batch.entities}
    # had ShipStaticData but no PositionReport -> not mappable, dropped
    assert "mmsi:211222330" not in refs


def test_all_vessels_type_and_geom():
    batch = _parse()
    assert batch.entities  # at least one
    for e in batch.entities:
        assert e.type == "vessel"
        assert e.lonlat is not None
