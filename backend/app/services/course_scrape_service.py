"""Orquestra os scrapers de curso configurados e aplica filtragem/persistência.

Espelha `scrape_service.py` (domínio de vagas).
"""
from __future__ import annotations

import asyncio

from app.models.course import Course, CourseFilter, CourseScrapeResult, CourseSource
from app.scrapers.course_base import CourseScrapeError, course_registry
from app.services import course_storage
from app.services.course_matcher import apply_filter


async def run_course_scrape(f: CourseFilter, *, persist: bool = True) -> CourseScrapeResult:
    scrapers = course_registry.selected(f.sources)
    if not scrapers:
        return CourseScrapeResult(total_found=0, new_courses=0, sources_used=[], courses=[])

    tasks = [scraper.fetch(f) for scraper in scrapers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_courses: list[Course] = []
    errors: list[str] = []
    sources_used: list[CourseSource] = []

    for scraper, result in zip(scrapers, results):
        if isinstance(result, CourseScrapeError):
            errors.append(str(result))
            continue
        if isinstance(result, Exception):
            errors.append(f"[{scraper.source_id.value}] erro inesperado: {result}")
            continue
        sources_used.append(scraper.source_id)
        all_courses.extend(result)

    filtered = apply_filter(all_courses, f)

    new_count = 0
    if persist and filtered:
        _, new_count = course_storage.upsert_courses(filtered)

    return CourseScrapeResult(
        total_found=len(filtered),
        new_courses=new_count,
        sources_used=sources_used,
        courses=filtered,
        errors=errors,
    )
