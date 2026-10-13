"""Application factory for ddx-omr-server.

Run with ``uvicorn ddx_omr_server.api.app:create_app --factory``. The model is
verified and loaded inside the factory, so a missing or mismatched weights
file stops the process before the port opens.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ddx_omr_server.api.routes import build_router
from ddx_omr_server.api.settings import Settings, load_settings
from ddx_omr_server.core.model import CheckboxModel

LICENSE_ID = "AGPL-3.0-or-later"


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    model_loaded: bool
    model_sha256: str
    model_revision: str


class SourceResponse(BaseModel):
    license: str
    source_url: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Raises when the weights are missing or unverified."""
    config = settings or load_settings()
    model = CheckboxModel(config.model_path, config.model_sha256, config.model_revision)

    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        description=(
            "Scores checkbox crops with the AGPL-3.0 hermitkk/omr-checkbox-classifier. "
            "Returns raw probabilities only; the caller decides ticked, empty or unsure. "
            "Source: GET /source."
        ),
    )

    # Fail CLOSED: an empty CORS_ORIGINS allows no cross-origin caller.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

    app.state.settings = config
    app.state.model = model
    app.include_router(build_router(config))

    # Unauthenticated liveness: a monitor must not need the secret.
    @app.get("/health", response_model=HealthResponse, tags=["platform"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            app=config.app_name,
            version=config.app_version,
            model_loaded=True,
            model_sha256=model.info.sha256,
            model_revision=model.info.revision,
        )

    # AGPL-3.0 section 13: offer the Corresponding Source to network users.
    @app.get("/source", response_model=SourceResponse, tags=["platform"])
    async def source() -> SourceResponse:
        return SourceResponse(license=LICENSE_ID, source_url=config.source_url)

    return app


def main() -> None:
    """Console entry point; start.sh is the supported launcher."""
    import uvicorn

    config = load_settings()
    uvicorn.run(
        "ddx_omr_server.api.app:create_app",
        factory=True,
        host=config.host,
        port=config.port,
        log_level=config.log_level,
    )
