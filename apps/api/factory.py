from __future__ import annotations

import time
from uuid import uuid4

from fastapi import FastAPI, Request

from apps.api.routes.admin import router as admin_router
from apps.api.routes.dashboard import router as dashboard_router
from apps.api.routes.health import router as health_router
from apps.api.routes.journal import router as journal_router
from apps.api.routes.notifications import router as notifications_router
from apps.api.routes.quality import router as quality_router
from apps.api.routes.roots import router as roots_router
from apps.api.routes.signals import router as signals_router
from libs.runtime.feature_flags import is_feature_enabled
from libs.runtime.metrics import get_runtime_metrics_registry
from libs.utils.logging import configure_logging, get_logger


def create_app() -> FastAPI:
    configure_logging()
    logger = get_logger("imoex.api")
    app = FastAPI(title="IMOEX signals API", version="0.1.0")

    @app.middleware("http")
    async def instrument_requests(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid4())
        started_at = time.perf_counter()
        path = request.url.path
        method = request.method
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000
            get_runtime_metrics_registry().record_request(
                method=method,
                path=path,
                status_code=500,
                duration_ms=duration_ms,
            )
            if is_feature_enabled("structured_logging"):
                logger.exception(
                    "http_request_failed",
                    extra={
                        "event": "http_request_failed",
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "status_code": 500,
                        "duration_ms": round(duration_ms, 6),
                    },
                )
            raise

        duration_ms = (time.perf_counter() - started_at) * 1000
        response.headers["x-request-id"] = request_id
        get_runtime_metrics_registry().record_request(
            method=method,
            path=path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        if is_feature_enabled("structured_logging"):
            logger.info(
                "http_request_completed",
                extra={
                    "event": "http_request_completed",
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 6),
                },
            )
        return response

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(quality_router, prefix="/api/v1")
    app.include_router(roots_router, prefix="/api/v1")
    app.include_router(signals_router, prefix="/api/v1")
    app.include_router(journal_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(dashboard_router)
    return app
