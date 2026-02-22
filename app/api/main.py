from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.analysis import router as analysis_router
from app.api.leads import router as leads_router
from app.api.reports import router as reports_router
from app.api.upload import router as upload_router
from app.scheduler import setup_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    sched = setup_scheduler()
    sched.start()
    yield
    sched.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Traffic Quality Checker API",
        version="0.3.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.include_router(upload_router)
    app.include_router(leads_router)
    app.include_router(analysis_router)
    app.include_router(reports_router)

    @app.get("/health", tags=["ops"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
