"""Fonte "curated" — não é um scraper de verdade, só um registro informativo.

Certificações e pós/faculdade não têm catálogo raspável (ver docstring de
`app/services/course_seed.py`); os dados já entram no storage no boot via
`ensure_seed_data()`. Esta classe existe só pra "curated" aparecer em
`GET /course-sources` como fonte desabilitada (não roda em scrape ao vivo —
`enabled = False` já garante isso via `CourseScraperRegistry.selected()`).
"""
from __future__ import annotations

from app.models.course import Course, CourseFilter, CourseSource
from app.scrapers.course_base import BaseCourseScraper


class CuratedCourseScraper(BaseCourseScraper):
    source_id = CourseSource.CURATED
    name = "Dataset curado (certificações, pós, faculdade)"
    description = (
        "Mantido à mão no repositório — certificações e pós/faculdade BR não "
        "têm catálogo raspável. Já carregado no storage, não é 'raspado' ao vivo."
    )
    enabled = False

    async def fetch(self, f: CourseFilter) -> list[Course]:
        return []
