"""Orquestra os scrapers configurados e aplica filtragem/persistência."""
from __future__ import annotations

import asyncio

from app.models.job import Job, JobFilter, JobSource, ScrapeResult
from app.scrapers.base import ScrapeError, registry
from app.services import storage
from app.services.matcher import apply_filter


async def run_scrape(f: JobFilter, *, persist: bool = True) -> ScrapeResult:
    scrapers = registry.selected(f.sources)
    if not scrapers:
        return ScrapeResult(total_found=0, new_jobs=0, sources_used=[], jobs=[])

    tasks = [scraper.fetch(f) for scraper in scrapers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_jobs: list[Job] = []
    errors: list[str] = []
    sources_used: list[JobSource] = []

    for scraper, result in zip(scrapers, results):
        if isinstance(result, ScrapeError):
            errors.append(str(result))
            continue
        if isinstance(result, Exception):
            errors.append(f"[{scraper.source_id.value}] erro inesperado: {result}")
            continue
        sources_used.append(scraper.source_id)
        all_jobs.extend(result)

    filtered = apply_filter(all_jobs, f)

    new_count = 0
    if persist and filtered:
        _, new_count = storage.upsert_jobs(filtered)

    return ScrapeResult(
        total_found=len(filtered),
        new_jobs=new_count,
        sources_used=sources_used,
        jobs=filtered,
        errors=errors,
    )
