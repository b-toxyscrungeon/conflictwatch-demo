from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://osint:osint@localhost:5432/osint"
    cors_origins: str = "http://localhost:5173"
    ofac_sdn_url: str = "https://sanctionslistservice.ofac.treas.gov/api/download/sdn.xml"

    # OpenSky Network state-vectors endpoint (anonymous access is fine).
    opensky_url: str = "https://opensky-network.org/api/states/all"
    # AISStream.io vessel-position stream (free API key required — get one at
    # https://aisstream.io). We open it briefly on a daily cadence for a snapshot.
    aisstream_url: str = "wss://stream.aisstream.io/v0/stream"
    aisstream_api_key: str = ""
    ais_sample_seconds: int = 60

    # Scheduler cadences (see app.ingest.scheduler).
    adsb_interval_minutes: int = 60
    ais_interval_hours: int = 24
    # Shared area of interest for spatial sources: lat_min, lon_min, lat_max, lon_max.
    # Default covers Cuba and its surrounding waters/airspace.
    aoi_bbox: str = "19.0,-85.5,24.0,-73.5"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def aoi(self) -> tuple[float, float, float, float]:
        """(lat_min, lon_min, lat_max, lon_max) parsed from ``aoi_bbox``."""
        lat_min, lon_min, lat_max, lon_max = (float(x) for x in self.aoi_bbox.split(","))
        return lat_min, lon_min, lat_max, lon_max


settings = Settings()
