"""Entrypoint da API FastAPI do JobFinder."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.courses import router as courses_router
from app.api.filters import router as filters_router
from app.api.jobs import router as jobs_router
from app.api.settings import router as settings_router
from app.bootstrap import init as init_app
from app.config import get_settings
from app.scrapers.base import registry
from app.services import scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

settings = get_settings()
init_app()


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(
    title="JobFinder API",
    description="Busca de vagas multi-fonte com filtros customizáveis e alertas por e-mail.",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "version": app.version,
        "email_configured": settings.email_configured,
        "scheduler_running": scheduler.get_scheduler().running,
        "registered_sources": [s.id.value for s in registry.info_list()],
    }


app.include_router(jobs_router, tags=["jobs"])
app.include_router(filters_router)
app.include_router(settings_router)
app.include_router(courses_router, tags=["courses"])
