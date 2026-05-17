from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from trustvault.api.routes import audit, dashboard, entities, health, ingestion, jobs, licence
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
app.include_router(entities.router)
app.include_router(ingestion.router)
app.include_router(jobs.router)
app.include_router(audit.router)
app.include_router(licence.router)
