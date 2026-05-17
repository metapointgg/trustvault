from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from trustvault.api.routes import (
    api_status,
    audit,
    comparison,
    completeness,
    containers,
    customers,
    dashboard,
    entities,
    evidence,
    export,
    extraction,
    fits,
    health,
    ingestion,
    integrity,
    jobs,
    licence,
    query,
    retention,
    rulesets,
)
from trustvault.db.bootstrap import initialise_database
from trustvault.settings import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="TrustVault production API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    initialise_database()


app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(api_status.router)
app.include_router(query.router)
app.include_router(customers.router)
app.include_router(comparison.router)
app.include_router(rulesets.router)
app.include_router(completeness.router)
app.include_router(extraction.router)
app.include_router(retention.router)
app.include_router(integrity.router)
app.include_router(export.router)
app.include_router(entities.router)
app.include_router(evidence.router)
app.include_router(fits.router)
app.include_router(ingestion.router)
app.include_router(containers.router)
app.include_router(jobs.router)
app.include_router(audit.router)
app.include_router(licence.router)
