"""Interface base para scrapers de curso/certificação + registry.

Espelha `app/scrapers/base.py` (domínio de vagas) — mantido como um arquivo
paralelo em vez de generalizar o original, pra não arriscar quebrar os
scrapers de vaga já em produção por uma abstração compartilhada.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import ClassVar

import httpx

from app.models.course import Course, CourseFilter, CourseSource, CourseSourceInfo


@dataclass
class CourseScrapeError(Exception):
    source: CourseSource
    message: str

    def __str__(self) -> str:
        return f"[{self.source.value}] {self.message}"


class BaseCourseScraper(abc.ABC):
    source_id: ClassVar[CourseSource]
    name: ClassVar[str]
    description: ClassVar[str]
    enabled: ClassVar[bool] = True

    DEFAULT_HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }

    def info(self) -> CourseSourceInfo:
        return CourseSourceInfo(
            id=self.source_id,
            name=self.name,
            description=self.description,
            enabled=self.enabled,
        )

    async def _client(self, **kwargs) -> httpx.AsyncClient:  # noqa: ANN003
        headers = {**self.DEFAULT_HEADERS, **kwargs.pop("headers", {})}
        return httpx.AsyncClient(headers=headers, timeout=20.0, follow_redirects=True, **kwargs)

    @abc.abstractmethod
    async def fetch(self, f: CourseFilter) -> list[Course]:
        """Busca itens que provavelmente batem com o filtro (best-effort)."""


class CourseScraperRegistry:
    def __init__(self) -> None:
        self._scrapers: dict[CourseSource, BaseCourseScraper] = {}

    def register(self, scraper: BaseCourseScraper) -> None:
        self._scrapers[scraper.source_id] = scraper

    def all(self) -> list[BaseCourseScraper]:
        return list(self._scrapers.values())

    def get(self, source: CourseSource) -> BaseCourseScraper | None:
        return self._scrapers.get(source)

    def selected(self, sources: list[CourseSource]) -> list[BaseCourseScraper]:
        if not sources:
            return [s for s in self._scrapers.values() if s.enabled]
        return [
            self._scrapers[src]
            for src in sources
            if src in self._scrapers and self._scrapers[src].enabled
        ]

    def info_list(self) -> list[CourseSourceInfo]:
        return [s.info() for s in self._scrapers.values()]


course_registry = CourseScraperRegistry()
