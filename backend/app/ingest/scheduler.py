"""Standalone ingest scheduler.

Runs the spatial connectors on their cadences (ADS-B hourly, AIS daily) in a
dedicated process, separate from the API so it can't double-fire under multiple
web workers. Start it alongside the API:

    python -m app.ingest.scheduler

Each run reuses the same idempotent loader as the CLI, so positions are updated
in place and last_seen is refreshed. A failing run is logged and the schedule
keeps going (a missing AIS key just logs an error until you add one).

Prefer cron? Equivalent crontab lines:
    0 * * * *  cd .../backend && .venv/bin/python -m app.ingest.cli adsb
    17 3 * * * cd .../backend && .venv/bin/python -m app.ingest.cli ais
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import settings
from app.db import SessionLocal
from app.ingest.adsb import OpenSkyConnector
from app.ingest.ais import AisStreamConnector
from app.ingest.loader import load

log = logging.getLogger("scheduler")


def run_ingest(connector_cls) -> None:
    connector = connector_cls()
    session = SessionLocal()
    try:
        result = load(session, connector)
        log.info("%s: %s %s", result.source, result.status, result.stats)
    except Exception as exc:  # noqa: BLE001 — keep the scheduler alive on failures
        log.error("%s ingest failed: %s", connector.source_name, exc)
    finally:
        session.close()


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="UTC")
    # ADS-B hourly, firing once immediately so there's fresh data on startup.
    scheduler.add_job(
        run_ingest,
        "interval",
        minutes=settings.adsb_interval_minutes,
        args=[OpenSkyConnector],
        id="adsb",
        next_run_time=datetime.now(UTC),
        max_instances=1,
        coalesce=True,
    )
    # AIS daily (no immediate run — it needs an API key and a sampling window).
    scheduler.add_job(
        run_ingest,
        "interval",
        hours=settings.ais_interval_hours,
        args=[AisStreamConnector],
        id="ais",
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    scheduler = build_scheduler()
    log.info(
        "scheduler started: adsb every %dm, ais every %dh",
        settings.adsb_interval_minutes,
        settings.ais_interval_hours,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler stopped")


if __name__ == "__main__":
    main()
