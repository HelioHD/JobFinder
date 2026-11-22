"""Scraper para Udemy (https://www.udemy.com).

Único catálogo de curso com busca por tema livre + preço real por item que
se mostrou raspável nesta investigação (DIO fica inteiro atrás de login
Keycloak, sem navegação anônima — não vale a pena tentar).

Confirmado manualmente em 2026-08-30 com Scrapling (StealthyFetcher):
  GET https://www.udemy.com/courses/search/?q=<kw>&p=<page>[&price=price-free]

  Card: section[class*="course-product-card--card"]  (Udemy usa hash de
  build no sufixo da classe — o seletor `[class*=...]` é resiliente a isso,
  mas pode quebrar se o nome-base do componente mudar; mesmo caveat dos
  outros scrapers baseados em CSS deste projeto)
    h2[class*="card-title-module--title"]      -> título
    a[href*="/course/"]                        -> link (relativo, precisa
                                                   urljoin com o host)
    div[data-purpose="course-price-text"]      -> "R$ 220,90" ou "Gratuito"

  `?price=price-free` filtra só cursos gratuitos — usado quando
  `f.max_price == 0`. Paginação: `&p=2`, 24 cards por página.

  Udemy emite certificado de conclusão em qualquer curso (pago ou
  gratuito) -> `has_certificate=True` sempre pra essa fonte.
"""
from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlencode, urljoin

from app.models.course import Course, CourseFilter, CourseSource, CourseType
from app.scrapers.course_base import BaseCourseScraper, CourseScrapeError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.udemy.com"
SEARCH_PATH = "/courses/search/"
RESULTS_PER_PAGE = 24


def _parse_price(text: str) -> float:
    if not text:
        return 0.0
    norm = text.strip().lower()
    if "gratuito" in norm or "free" in norm:
        return 0.0
    m = re.search(r"(\d{1,3}(?:\.\d{3})*),(\d{2})", text)
    if m:
        integer_part = m.group(1).replace(".", "")
        return float(f"{integer_part}.{m.group(2)}")
    m2 = re.search(r"(\d+)", text)
    if m2:
        return float(m2.group(1))
    return 0.0


def _parse_rating(text: str) -> float | None:
    m = re.search(r"(\d[.,]\d)\s*de\s*5", text or "", re.IGNORECASE)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


class UdemyCourseScraper(BaseCourseScraper):
    source_id = CourseSource.UDEMY
    name = "Udemy"
    description = (
        "Maior catálogo de cursos por tema livre, com preço real por item e "
        "filtro nativo de gratuito. Certificado de conclusão em qualquer curso."
    )

    async def fetch(self, f: CourseFilter) -> list[Course]:
        from scrapling.fetchers import AsyncStealthySession

        # Udemy só tem "curso" — não tem certificação/pós/faculdade de
        # verdade. Se o usuário restringiu o tipo a algo que não inclui
        # "curso", nem vale a pena buscar (e evita rotular curso da Udemy
        # como se fosse pós-graduação).
        if f.course_types and CourseType.COURSE not in f.course_types:
            return []

        keywords = (f.keywords or [""])[:2]
        pages = max(1, min(2, (f.limit // RESULTS_PER_PAGE) + 1))
        free_only = f.max_price is not None and f.max_price <= 0

        results: list[Course] = []
        seen: set[str] = set()

        try:
            async with AsyncStealthySession(headless=True, max_pages=1) as session:
                for kw in keywords:
                    for page in range(1, pages + 1):
                        params: dict[str, str] = {"q": kw, "p": str(page)}
                        if free_only:
                            params["price"] = "price-free"
                        url = f"{BASE_URL}{SEARCH_PATH}?{urlencode(params)}"
                        try:
                            resp = await session.fetch(
                                url,
                                network_idle=True,
                                timeout=25000,
                                block_ads=True,
                                wait_selector='a[href*="/course/"]',
                                wait_selector_state="attached",
                                wait=3000,
                            )
                        except Exception as exc:  # noqa: BLE001
                            raise CourseScrapeError(
                                self.source_id, f"Falha ao buscar '{kw}': {exc}"
                            ) from exc

                        if resp.status != 200:
                            break
                        new_count = 0
                        for card in resp.css('section[class*="course-product-card--card"]'):
                            course = self._parse_card(card, f)
                            if not course or course.id in seen:
                                continue
                            seen.add(course.id)
                            results.append(course)
                            new_count += 1
                        if new_count == 0:
                            break
                        await asyncio.sleep(0.4)
        except CourseScrapeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CourseScrapeError(self.source_id, f"Erro ao buscar: {exc}") from exc

        return results

    def _parse_card(self, card, f: CourseFilter):  # noqa: ANN001
        title_el = card.css('h2[class*="card-title-module--title"]')
        title = title_el[0].get_all_text().strip() if title_el else ""
        if not title:
            return None

        link_el = card.css('a[href*="/course/"]')
        if not link_el:
            return None
        href = link_el[0].attrib.get("href", "")
        if not href:
            return None
        url = urljoin(BASE_URL, href)

        price_el = card.css('div[data-purpose="course-price-text"]')
        price_text = price_el[0].get_all_text() if price_el else ""
        price = _parse_price(price_text)

        rating = _parse_rating(card.get_all_text())

        return Course(
            id=Course.make_id(self.source_id, url),
            source=self.source_id,
            course_type=CourseType.COURSE,
            provider="Udemy",
            title=title,
            description=title,
            url=url,
            theme_tags=list(f.keywords)[:5],
            price=price,
            currency="BRL",
            has_certificate=True,
            rating=rating,
        )
