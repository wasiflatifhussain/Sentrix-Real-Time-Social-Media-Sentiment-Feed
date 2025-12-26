from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentiment_service.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Sentiment Service API", version="0.1.0")

    # CORS: allow frontend polling (tighten later)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
