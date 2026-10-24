from fastapi import FastAPI

from app.api.routes.incidents import router as incidents_router
from app.api.routes.ai import router as ai_router
from app.api.routes.requests import router as requests_router
from app.core.config import settings

app = FastAPI(
    title="SMS Disaster Resource Coordinator API",
    version="0.1.0",
    description="Backend API for coordinating disaster resource requests.",
)

app.include_router(requests_router)
app.include_router(incidents_router)
app.include_router(ai_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Report whether the API process is running."""
    return {"status": "ok"}


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    """Provide a simple API welcome response."""
    return {"message": f"{settings.app_name} is running"}
