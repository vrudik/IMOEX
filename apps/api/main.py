from fastapi import FastAPI

from apps.api.routes.health import router as health_router
from apps.api.routes.journal import router as journal_router
from apps.api.routes.quality import router as quality_router
from apps.api.routes.roots import router as roots_router
from apps.api.routes.signals import router as signals_router

app = FastAPI(title="IMOEX signals API", version="0.1.0")

app.include_router(health_router, prefix="/api/v1")
app.include_router(quality_router, prefix="/api/v1")
app.include_router(roots_router, prefix="/api/v1")
app.include_router(signals_router, prefix="/api/v1")
app.include_router(journal_router, prefix="/api/v1")

