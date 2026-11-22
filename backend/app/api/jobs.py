"""Endpoints relacionados a busca/listagem de vagas."""
from __future__ import annotations

from fastapi import APIRouter

from app.models.job import JobFilter, ScrapeResult, SourceInfo
from app.scrapers.base import registry
from app.services import storage
from app.services.matcher import apply_filter
from app.services.scrape_service import run_scrape

router = APIRouter()


@router.get("/sources", response_model=list[SourceInfo])
async def list_sources() -> list[SourceInfo]:
    """Lista as fontes (scrapers) disponíveis."""
    return registry.info_list()


@router.post("/scrape", response_model=ScrapeResult)
async def scrape(filter_: JobFilter) -> ScrapeResult:
    """Roda uma busca ad-hoc com o filtro fornecido e persiste novas vagas."""
    return await run_scrape(filter_)


@router.post("/jobs/search", response_model=ScrapeResult)
async def search_existing(filter_: JobFilter) -> ScrapeResult:
    """Aplica um filtro sobre vagas já armazenadas (sem fazer scraping)."""
    jobs = storage.load_jobs()
    filtered = apply_filter(jobs, filter_)
    return ScrapeResult(
        total_found=len(filtered),
        new_jobs=0,
        sources_used=[],
        jobs=filtered,
    )


@router.get("/jobs")
async def list_jobs(limit: int = 50, offset: int = 0):
    """Lista vagas persistidas (mais recentes primeiro)."""
    jobs = storage.load_jobs()
    jobs.sort(key=lambda j: (j.posted_at or j.scraped_at), reverse=True)
    total = len(jobs)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [j.model_dump(mode="json") for j in jobs[offset : offset + limit]],
    }
