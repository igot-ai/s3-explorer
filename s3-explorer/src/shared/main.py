"""FastAPI application for S3 Explorer.

This replaces the Flask app_factory.py with a unified FastAPI application
that serves both the S3 Explorer web UI and the ingestion API.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import src.modules.s3_explore
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from src.modules.ingestion.routers import router as ingestion_router
from src.modules.ingestion.wrapper import init_ingestion_wrapper, run_ingestion_pipeline
from src.modules.s3_explore.web.router import router as s3_explore_router
from src.shared._logging import get_logger
from starlette.middleware.sessions import SessionMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting S3 Explorer FastAPI application")

    yield

    # Shutdown: close Temporal client
    logger.info("Shutting down S3 Explorer FastAPI application")
    try:
        from src.shared.temporal_client import close_temporal_client

        await close_temporal_client()
    except Exception as e:
        logger.warning(f"Error closing Temporal client: {e}")


def create_app(app: FastAPI) -> FastAPI:
    # Session middleware (required for login state)
    secret_key = os.environ.get("SECRET_KEY", os.urandom(32).hex())
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_key,
        session_cookie="session",
        max_age=86400,  # 24 hours
        same_site="lax",
        https_only=os.environ.get("PRODUCTION", "false").lower() == "true",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Static files and templates
    s3_explore_root = Path(src.modules.s3_explore.__file__).parent
    s3_explore_web_dir = s3_explore_root / "web"

    app.mount(
        "/static",
        StaticFiles(directory=str(s3_explore_web_dir / "static")),
        name="static",
    )

    # Store templates in app state for use in routes
    app.state.templates = Jinja2Templates(
        directory=str(s3_explore_web_dir / "templates")
    )

    # Initialize ingestion wrapper with Temporal client
    try:
        init_ingestion_wrapper(run_ingestion_pipeline)
        logger.debug("Called init_ingestion_wrapper successfully")
    except Exception as e:
        logger.error(f"Failed to initialize ingestion wrapper: {e}")

    # Include routers
    app.include_router(s3_explore_router)
    app.include_router(ingestion_router)

    return app

