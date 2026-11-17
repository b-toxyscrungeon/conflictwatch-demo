from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import directory, entities, graph, links
from app.api import map as map_api
from app.config import settings

app = FastAPI(
    title="ConflictWatch API",
    description="OSINT aggregation over public conflict-zone data (Cuba focus).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(entities.router)
app.include_router(graph.router)
app.include_router(map_api.router)
app.include_router(links.router)
app.include_router(directory.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
