"""CLI entrypoint for running ingests.

    python -m app.ingest.cli ofac                 # download + load live feed
    python -m app.ingest.cli ofac --file snap.xml  # load a local snapshot
"""

from __future__ import annotations

import argparse
import sys

from app.db import SessionLocal
from app.ingest.adsb import OpenSkyConnector
from app.ingest.ais import AisStreamConnector
from app.ingest.loader import load
from app.ingest.ofac import OfacSdnConnector

CONNECTORS = {
    "ofac": OfacSdnConnector,
    "adsb": OpenSkyConnector,
    "ais": AisStreamConnector,
}


class _FileConnector:
    """Wraps a connector to read bytes from a local file instead of the network."""

    def __init__(self, connector, path: str):
        self._c = connector
        self.source_name = connector.source_name
        self._path = path

    def fetch(self) -> bytes:
        with open(self._path, "rb") as fh:
            return fh.read()

    def parse(self, raw: bytes):
        return self._c.parse(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an OSINT source ingest")
    parser.add_argument("source", choices=sorted(CONNECTORS))
    parser.add_argument("--file", help="Load from a local snapshot instead of downloading")
    args = parser.parse_args(argv)

    connector = CONNECTORS[args.source]()
    if args.file:
        connector = _FileConnector(connector, args.file)

    session = SessionLocal()
    try:
        run = load(session, connector)
    except Exception as exc:  # noqa: BLE001 — surface a clean message, not a traceback
        print(f"[{connector.source_name}] error: {exc}")
        return 1
    finally:
        session.close()

    print(f"[{run.source}] {run.status}: {run.stats}")
    return 0 if run.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
