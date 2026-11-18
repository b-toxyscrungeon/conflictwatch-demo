# Poinemap

Open-source intelligence aggregation over **publicly available** data for conflict
zones, starting with a focus on **Cuba**. It pulls together open data about ships,
aircraft, sanctioned entities, corporations, contracts, and places, and presents it
two ways:

- **Graph view** — an interactive node-link "universe" of entities and the
  relationships between them (who owns what, who is sanctioned under which program,
  what is flagged where).
- **Map view** — a geographic view of entities that have a location (ship/aircraft
  positions, bases, ports, points of interest).

Both views are projections of a single **entity/relationship graph**.

## Live demo

**https://b-toxyscrungeon.github.io/poinemap-demo/**

The demo is a **static snapshot**: no backend runs. Every API answer was exported
once from the database to JSON (`frontend/public/data/`), and search, filtering and
graph expansion run in your browser. The "data as of" badge in the header shows
when the snapshot was taken; hover it for per-source dates.

What's in the snapshot:

- **Sanctions graph**: the full OFAC SDN list (~20k people, organizations, vessels,
  aircraft and programs, ~25k links), not only the Cuba program.
- **Map**: aircraft positions over and around Cuba from OpenSky ADS-B. Vessel (AIS)
  positions aren't in this snapshot.

### Data sources and credits

- Sanctions: [OFAC Specially Designated Nationals list](https://ofac.treasury.gov/specially-designated-nationals-and-blocked-persons-list-sdn-human-readable-lists), U.S. Department of the Treasury.
- Aircraft positions: [The OpenSky Network](https://opensky-network.org).
- Basemap: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.

Being on a sanctions list or appearing in a flight feed is what the source
reports, nothing more; check the original source before relying on any record.

### Rebuilding the snapshot

```bash
# with the backend set up and data ingested (see Quick start below)
cd backend && python -m app.scripts.export_static     # writes frontend/public/data/
cd ../frontend && VITE_STATIC=1 npm run build          # static site in dist/
VITE_STATIC=1 npx vite preview                         # check it locally
```

Pushing to `main` deploys via `.github/workflows/deploy.yml`.

### Visitor counter and privacy

The header shows the total number of unique visitors, counted by
[GoatCounter](https://www.goatcounter.com). GoatCounter doesn't use cookies or
store IP addresses. To turn it on, set a repository variable `GOATCOUNTER_CODE`
to your GoatCounter site code and enable "Allow adding visitor counts on your
website" in GoatCounter's settings. Without the variable, nothing is loaded.

## Architecture

```
backend/   FastAPI + SQLAlchemy + PostGIS
  app/
    models.py        Entity / Relationship / EntityAlias / IngestRun
    ingest/          pluggable source connectors (OFAC now; AIS/ADS-B next)
    api/             entities, graph (node-link), map (GeoJSON)
frontend/  React + Vite + TypeScript
  src/components/    GraphView (react-force-graph), MapView (MapLibre GL)
```

Everything tracked is an **Entity** (person, organization, vessel, aircraft,
location, sanctions program, …). Everything connecting them is a **Relationship**.
The graph view is the node-link projection; the map view is the subset of entities
carrying a PostGIS geometry.

## Data sources

| Domain | Source | Status |
| --- | --- | --- |
| Sanctions | OFAC SDN (Treasury) | ✅ implemented |
| Aircraft | ADS-B (OpenSky) | ✅ implemented (hourly) |
| Ships | AIS (AISStream.io) | ✅ implemented (daily, needs free key) |
| Trade / commodities | UN Comtrade, US Census | planned |
| Contracts | USAspending, SAM.gov | planned |
| Corporations | OpenCorporates, SEC EDGAR | planned |
| Bases / POIs | OpenStreetMap, Wikidata | planned |
| Imagery | Sentinel-2 (Copernicus) | planned |

## Quick start

### 1. Database (PostGIS)

Using Homebrew:

```bash
brew install postgis
brew services start postgresql@16   # or the version brew installed
createuser -s osint 2>/dev/null; createdb -O osint osint
psql -d osint -c "ALTER USER osint WITH PASSWORD 'osint';"
```

Or with Docker: `docker compose up -d db`.

### 2. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head                                # create schema (enables PostGIS)
python -m app.ingest.cli ofac                       # download + load OFAC SDN
python -m app.ingest.cli adsb                        # load live aircraft (OpenSky)
# (offline: python -m app.ingest.cli ofac --file data/cache/sdn.xml)
uvicorn app.main:app --reload                       # http://localhost:8000/docs
python -m app.ingest.scheduler                       # optional: adsb hourly, ais daily
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                                         # http://localhost:5173
```

## Tests

```bash
cd backend && source .venv/bin/activate && pytest
```
