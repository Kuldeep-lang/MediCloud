"""MediCloud API - application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.core.metrics import PrometheusMiddleware, register_collectors

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "MediCloud API %s (%s) starting in %s mode",
        settings.app_version,
        settings.git_commit,
        settings.app_env,
    )
    yield
    from app.db.session import engine

    engine.dispose()
    logger.info("MediCloud API stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="MediCloud API",
        description="Cloud-native hospital management system (synthetic data only).",
        version=settings.app_version,
        docs_url="/api/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.enable_docs else None,
        lifespan=lifespan,
    )

    # Production traffic is same-origin; CORS only matters for local dev tooling.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(PrometheusMiddleware)  # added last = outermost, so it times everything

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse({"detail": exc.message}, status_code=exc.status_code)

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        # A DB constraint caught something the service layer did not (e.g. a race).
        logger.warning("Integrity error: %s", exc.orig)
        return JSONResponse({"detail": "The request conflicts with existing data"}, status_code=409)

    app.include_router(health_router)
    app.include_router(api_router, prefix="/api/v1")

    register_collectors(settings.app_version, settings.git_commit, settings.app_env)
    return app


app = create_app()
