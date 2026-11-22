"""Interface base para scrapers + registry.

Cada fonte (Arbeitnow, LinkedIn, etc.) implementa BaseScraper.fetch(filter)
e retorna List[Job] já normalizado. O ScraperRegistry mantém um mapa
JobSource -> instância e expõe helpers para descobrir/filtrar.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import ClassVar

import httpx

from app.models.job import Job, JobFilter, JobSource, SourceInfo


@dataclass
class ScrapeError(Exception):
    source: JobSource
    message: str

    def __str__(self) -> str:
        return f"[{self.source.value}] {self.message}"


class BaseScraper(abc.ABC):
    """Cada scraper concreto deve definir source_id, name, description."""

    source_id: ClassVar[JobSource]
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

    def info(self) -> SourceInfo:
        return SourceInfo(
            id=self.source_id,
            name=self.name,
            description=self.description,
            enabled=self.enabled,
        )

    async def _client(self, **kwargs) -> httpx.AsyncClient:  # noqa: ANN003
        headers = {**self.DEFAULT_HEADERS, **kwargs.pop("headers", {})}
        return httpx.AsyncClient(headers=headers, timeout=20.0, follow_redirects=True, **kwargs)

    @abc.abstractmethod
    async def fetch(self, f: JobFilter) -> list[Job]:
        """Busca vagas que provavelmente batem com o filtro.

        Implementações devem fazer best-effort para filtrar do lado da fonte,
        mas o matcher.apply_filter() roda depois para garantir.
        """


class ScraperRegistry:
    def __init__(self) -> None:
        self._scrapers: dict[JobSource, BaseScraper] = {}

    def register(self, scraper: BaseScraper) -> None:
        self._scrapers[scraper.source_id] = scraper

    def all(self) -> list[BaseScraper]:
        return list(self._scrapers.values())

    def get(self, source: JobSource) -> BaseScraper | None:
        return self._scrapers.get(source)

    def selected(self, sources: list[JobSource]) -> list[BaseScraper]:
        if not sources:
            return [s for s in self._scrapers.values() if s.enabled]
        return [self._scrapers[src] for src in sources if src in self._scrapers and self._scrapers[src].enabled]

    def info_list(self) -> list[SourceInfo]:
        return [s.info() for s in self._scrapers.values()]


registry = ScraperRegistry()
