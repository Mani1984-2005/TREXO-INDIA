from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .config import API_PREFIX, CORS_ORIGINS, REPO_ROOT, SERVICE_NAME
from .routers import auth, health, ml, models, store
from .security import ApiError
from .store.db import StoreDB
from .store.service import StoreError, StoreService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("trexo.api")


def create_app(db_path: Path | str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.db = StoreDB(db_path) if db_path else StoreDB()
        app.state.store = StoreService(app.state.db)
        logger.info("store database ready at %s", app.state.db.path)
        yield

    app = FastAPI(
        title="TREXO-INDIA API",
        version=__version__,
        description=(
            "Unified store-operations and machine-learning API. "
            "ML endpoints surface audited, versioned model outputs; all recommendations "
            "require human approval."
        ),
        lifespan=lifespan,
    )
    app.state.db_path = db_path

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Admin-Token"],
    )

    @app.middleware("http")
    async def timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    # ---- error envelopes -------------------------------------------------
    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(StoreError)
    async def store_error(_: Request, exc: StoreError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": jsonable_encoder(exc.errors()),
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            body = {"error": detail}
        else:
            body = {"error": {"code": f"HTTP_{exc.status_code}", "message": str(detail)}}
        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Unexpected server error"}},
        )

    @app.get("/", include_in_schema=False)
    def root():
        return {
            "service": SERVICE_NAME,
            "version": __version__,
            "docs": "/docs",
            "health": f"{API_PREFIX}/health",
        }

    @app.get("/livez", include_in_schema=False)
    def livez():
        return PlainTextResponse("ok")

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(store.router, prefix=API_PREFIX)
    app.include_router(ml.router, prefix=API_PREFIX)
    app.include_router(ml.retail_router, prefix=API_PREFIX)
    app.include_router(models.router, prefix=API_PREFIX)

    dist = REPO_ROOT / "frontend" / "dist"
    if dist.exists():  # pragma: no cover - only in built deployments
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")

    return app


app = create_app()
