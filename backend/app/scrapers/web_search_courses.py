"""Scraper de busca orgânica no Google (não confundir com o widget morto de
Google Jobs — este usa o Google normal, `google.com/search?q=...`).

Cobre exatamente o que Udemy e o dataset curado não cobrem: instituições
de pós-graduação/faculdade que nenhum catálogo fechado lista. Testado
manualmente em 2026-08-30 (mesma técnica usada pro Indeed em app/scrapers/
indeed.py) — uma busca por "pós-graduação EAD segurança da informação
cibersegurança" devolveu Senac, Cruzeiro do Sul Virtual, IESB, PUC Minas,
Estácio, Mackenzie, XP Educação, UNINASSAU — nenhuma delas estava no
dataset curado.

Trade-off: sem preço nem confirmação de certificado estruturados (fica
`None` = desconhecido; ver `course_matcher.py` pra como isso é tratado no
filtro — não exclui, mas o card mostra "verificar no site").

Mecânica:
  GET https://www.google.com/search?q=<query>&hl=pt-BR&gl=br&num=20
  Cada resultado: <h3> (título) dentro de um <a href="/goto?url=...">
  (link ofuscado — resolvido com um fetch extra pra pegar a URL real) e,
  no mesmo bloco, `span.VuuXrf` (nome do provedor/site).
"""
from __future__ import annotations

import asyncio
import logging

from app.models.course import Course, CourseFilter, CourseSource, CourseType
from app.scrapers.course_base import BaseCourseScraper, CourseScrapeError

logger = logging.getLogger(__name__)

GOOGLE_BASE = "https://www.google.com"

# Só aplicado quando exatamente 1 tipo está selecionado — evita over-narrow
# quando o usuário deixa "qualquer tipo" ou seleciona vários.
TYPE_QUERY_HINTS: dict[CourseType, str] = {
    CourseType.CERTIFICATION: "certificação",
    CourseType.COURSE: "curso online",
    CourseType.POSTGRAD: "pós-graduação EAD",
    CourseType.COLLEGE: "graduação EAD faculdade",
}

MAX_RESULTS = 6


def _infer_type_from_title(title: str) -> CourseType:
    """Usado só quando o filtro não restringe a 1 tipo (senão o resultado
    poderia ser excluído à toa por um `course_type` chutado errado)."""
    norm = title.lower()
    if any(k in norm for k in ("pós-gradua", "pos-gradua", "mba", "especializa")):
        return CourseType.POSTGRAD
    if any(k in norm for k in ("certifica", "certification")):
        return CourseType.CERTIFICATION
    if any(k in norm for k in ("graduação", "graduacao", "bacharel", "tecnólogo", "tecnologo", "licenciatura")):
        return CourseType.COLLEGE
    return CourseType.COURSE


class WebSearchCourseScraper(BaseCourseScraper):
    source_id = CourseSource.WEB_SEARCH
    name = "Busca no Google"
    description = (
        "Busca orgânica no Google — cobre instituições de pós-graduação/"
        "faculdade que não estão em nenhum catálogo fechado. Sem preço/"
        "certificado estruturado (fica 'verificar no site'). Mais lenta que "
        "as outras fontes (resolve cada link individualmente) e sujeita a "
        "rate-limit do Google sob uso pesado — nesse caso volta vazia."
    )

    async def fetch(self, f: CourseFilter) -> list[Course]:
        if not f.keywords:
            return []
        # "curso" já é bem coberto (e mais rápido) pela Udemy — só vale a
        # latência/risco de rate-limit desta fonte quando o usuário quer
        # certificação/pós/faculdade (ou não restringiu o tipo).
        if f.course_types == [CourseType.COURSE]:
            return []

        from scrapling.fetchers import AsyncStealthySession
        from urllib.parse import quote_plus

        query_terms = list(f.keywords)[:4]
        if len(f.course_types) == 1:
            hint = TYPE_QUERY_HINTS.get(f.course_types[0])
            if hint:
                query_terms.append(hint)
        query = " ".join(query_terms)
        url = f"{GOOGLE_BASE}/search?q={quote_plus(query)}&hl=pt-BR&gl=br&num=20"

        results: list[Course] = []
        seen: set[str] = set()

        try:
            async with AsyncStealthySession(headless=True, max_pages=1) as session:
                try:
                    resp = await session.fetch(
                        url, network_idle=True, timeout=25000, block_ads=True
                    )
                except Exception as exc:  # noqa: BLE001
                    raise CourseScrapeError(
                        self.source_id, f"Falha na busca '{query}': {exc}"
                    ) from exc

                if resp.status != 200:
                    return []

                for h3 in resp.css("h3")[:MAX_RESULTS]:
                    parsed = self._extract_result(h3)
                    if not parsed:
                        continue
                    title, goto_path, provider = parsed

                    real_url = await self._resolve_redirect(session, goto_path)
                    if not real_url:
                        continue

                    course = self._build_course(title, real_url, provider, f)
                    if course.id in seen:
                        continue
                    seen.add(course.id)
                    results.append(course)
                    await asyncio.sleep(0.2)
        except CourseScrapeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CourseScrapeError(self.source_id, f"Erro ao buscar: {exc}") from exc

        return results

    def _extract_result(self, h3):  # noqa: ANN001
        title = h3.get_all_text().strip()
        if not title or title.lower().startswith("ai mode reply"):
            return None

        node = h3
        href = None
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            if node.tag == "a":
                href = node.attrib.get("href")
                break
        if not href or not href.startswith("/goto"):
            return None

        provider = None
        block = h3
        for _ in range(6):
            block = block.parent
            if block is None:
                break
            provs = block.css("span.VuuXrf")
            if provs:
                provider = provs[0].get_all_text().strip()
                break

        return title, href, provider

    async def _resolve_redirect(self, session, goto_path: str) -> str | None:  # noqa: ANN001
        try:
            resp = await session.fetch(
                f"{GOOGLE_BASE}{goto_path}", network_idle=False, timeout=10000
            )
            final_url = str(resp.url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha ao resolver redirect do Google: %s", exc)
            return None
        if not final_url.startswith("http") or "google.com" in final_url:
            return None
        return final_url

    def _build_course(self, title: str, url: str, provider: str | None, f: CourseFilter) -> Course:
        from urllib.parse import urlparse

        if not provider:
            provider = urlparse(url).netloc.replace("www.", "")

        if len(f.course_types) == 1:
            # Filtro já restringe a 1 tipo (e a query foi montada com o hint
            # certo) — usa ele direto em vez de adivinhar pelo título.
            course_type = f.course_types[0]
        else:
            course_type = _infer_type_from_title(title)

        return Course(
            id=Course.make_id(self.source_id, url),
            source=self.source_id,
            course_type=course_type,
            provider=provider,
            title=title,
            description=f"{title} — {provider}",
            url=url,
            theme_tags=list(f.keywords)[:5],
            price=None,
            has_certificate=None,
        )
