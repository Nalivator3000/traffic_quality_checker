from fastapi import FastAPI

from app.api.analysis import router as analysis_router
from app.api.upload import router as upload_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Traffic Quality Checker API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    app.include_router(upload_router)
    app.include_router(analysis_router)

    @app.get("/health", tags=["ops"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
