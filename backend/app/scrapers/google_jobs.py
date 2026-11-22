"""Scraper para Google Jobs.

O Google não tem API pública de jobs. A solução é abrir
`google.com/search?q=...&ibp=htl;jobs` num browser real (Playwright),
deixar o widget renderizar, e raspar os cards do DOM.

Risco: Google bloqueia bots agressivamente, e o seletor pode mudar a
qualquer momento. Tratamos como **fonte experimental**:
  - Se Playwright não estiver disponível -> scrape vazio (sem erro fatal).
  - Se aparecer captcha/consent -> tentamos clicar em "Aceitar" (UE) e,
    se falhar, devolvemos 0 vagas (não derruba o resto).

Reverificado em 2026-08-30 com Scrapling (StealthyFetcher/patchright,
undetected Chromium): `ibp=htl;jobs` continua sendo redirecionado pelo
Google pra `udm=8` sem nenhum marcador do widget de jobs no HTML. Ou
seja, não é um problema de detecção de bot — o Google simplesmente não
serve mais esse widget pra usuários anônimos. Trocar o engine de
scraping (Playwright cru -> Scrapling) não resolve; não vale reescrever
este scraper até o Google trazer o widget de volta.

Saída: card -> { título, empresa, location, snippet, source-link }.
O Google não dá URL canônica direta; cada card tem um menu "View job"
que aponta pro source original. Tentamos extrair esse link.
"""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote_plus

from app.models.job import Job, JobFilter, JobSource, JobType, LocationMode
from app.scrapers.base import BaseScraper, ScrapeError
from app.scrapers._playwright import PlaywrightUnavailable, browser_page

logger = logging.getLogger(__name__)


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _build_query(f: JobFilter) -> str:
    parts: list[str] = []
    if f.keywords:
        parts.append(" ".join(f.keywords[:4]))
    else:
        parts.append("software developer")
    parts.append("jobs")
    if f.location_mode == LocationMode.REMOTE_BRAZIL:
        parts.append("remote brazil")
    elif f.location_mode == LocationMode.REMOTE_WORLDWIDE:
        parts.append("remote")
    elif f.region:
        parts.append(f.region)
    return " ".join(parts)


def _classify_remote(location: str) -> bool:
    norm = _strip_accents(location.lower())
    return (
        "remoto" in norm
        or "remote" in norm
        or "home office" in norm
        or "anywhere" in norm
    )


def _parse_relative_date(text: str) -> Optional[datetime]:
    """Texto tipo 'há 3 dias' / '3 days ago' -> datetime aproximado.

    Não é exato, mas serve pra ordenar e pro filtro `posted_within_days`.
    """
    if not text:
        return None
    norm = _strip_accents(text.lower())
    m = re.search(r"(\d+)\s*(hora|hour|h|dia|day|d|semana|week|w|mes|month|m|ano|year|y)", norm)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    seconds = 0
    if unit.startswith(("hora", "hour", "h")):
        seconds = n * 3600
    elif unit.startswith(("dia", "day", "d")):
        seconds = n * 86400
    elif unit.startswith(("semana", "week", "w")):
        seconds = n * 86400 * 7
    elif unit.startswith(("mes", "month", "m")):
        seconds = n * 86400 * 30
    elif unit.startswith(("ano", "year", "y")):
        seconds = n * 86400 * 365
    return datetime.now(timezone.utc).fromtimestamp(
        datetime.now(timezone.utc).timestamp() - seconds, tz=timezone.utc
    )


class GoogleJobsScraper(BaseScraper):
    source_id = JobSource.GOOGLE_JOBS
    name = "Google Jobs"
    description = (
        "Widget de empregos do Google (descontinuado em muitas regiões "
        "desde 2023). Disponível pra ativação manual mas sem garantia."
    )
    # Desabilitado por padrão: o widget de Jobs do Google parou de
    # mostrar resultados pra usuários anônimos (BR e UE confirmados).
    # Manter aqui pra reativar se o Google trouxer de volta.
    enabled = False

    async def fetch(self, f: JobFilter) -> list[Job]:
        try:
            return await self._fetch_with_browser(f)
        except PlaywrightUnavailable as exc:
            logger.warning("Google Jobs indisponível: %s", exc)
            return []
        except ScrapeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScrapeError(self.source_id, f"Erro ao buscar: {exc}") from exc

    async def _fetch_with_browser(self, f: JobFilter) -> list[Job]:
        query = _build_query(f)
        # ibp=htl;jobs força o widget de jobs. uule é opcional pra geo.
        url = (
            f"https://www.google.com/search?q={quote_plus(query)}"
            "&ibp=htl;jobs&hl=pt-BR&gl=br"
        )

        results: list[Job] = []
        seen: set[str] = set()

        async with browser_page() as page:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Google Jobs: timeout no goto (%s)", exc)
                return []

            # Lida com tela de consentimento (UE) — clica em "Aceitar tudo"
            for label in (
                "Aceitar tudo",
                "Accept all",
                "Concordo",
                "I agree",
            ):
                try:
                    btn = page.get_by_role("button", name=label)
                    if await btn.count() > 0:
                        await btn.first.click(timeout=2000)
                        await page.wait_for_load_state("domcontentloaded", timeout=5000)
                        break
                except Exception:  # noqa: BLE001
                    continue

            # Espera pelo widget de jobs renderizar
            try:
                await page.wait_for_selector(
                    "div[role='listitem'], li.iFjolb, div.PwjeAc",
                    timeout=8000,
                )
            except Exception:  # noqa: BLE001
                # Sem widget => provavelmente captcha. Devolvemos vazio.
                logger.info("Google Jobs: widget não renderizou (captcha?)")
                return []

            # Faz scroll pra carregar mais cards (Google carrega lazy)
            for _ in range(3):
                try:
                    await page.mouse.wheel(0, 2000)
                    await asyncio.sleep(0.5)
                except Exception:  # noqa: BLE001
                    break

            # Pega os cards
            cards = await page.query_selector_all("li.iFjolb, div[role='listitem']")
            for card in cards:
                try:
                    job = await self._parse_card(card)
                except Exception:  # noqa: BLE001
                    job = None
                if not job:
                    continue
                if job.id in seen:
                    continue
                seen.add(job.id)
                results.append(job)
                if len(results) >= f.limit:
                    break

        return results

    async def _parse_card(self, card) -> Optional[Job]:  # noqa: ANN001
        # Título
        title = ""
        for sel in ("div.BjJfJf", "h2", "[role='heading']"):
            el = await card.query_selector(sel)
            if el:
                title = (await el.inner_text()).strip()
                if title:
                    break
        if not title:
            return None

        # Empresa / location ficam em divs com classes tipo vNEEBe / Qk80Jf
        company = ""
        location = ""
        meta_els = await card.query_selector_all("div.vNEEBe, div.Qk80Jf, span.vNEEBe")
        if meta_els:
            company = (await meta_els[0].inner_text()).strip() if len(meta_els) >= 1 else ""
            if len(meta_els) >= 2:
                location = (await meta_els[1].inner_text()).strip()

        # Snippet/descrição
        description = ""
        snippet_el = await card.query_selector("span.HBvzbc")
        if snippet_el:
            description = (await snippet_el.inner_text()).strip()

        # Data relativa
        posted_at = None
        date_el = await card.query_selector("span.LL4CDc")
        if date_el:
            posted_at = _parse_relative_date(await date_el.inner_text())

        # Link external — primeiro <a> com href que NÃO é googleusercontent
        url = ""
        link_els = await card.query_selector_all("a[href]")
        for link in link_els:
            href = (await link.get_attribute("href")) or ""
            if href.startswith("http") and "google.com" not in href:
                url = href
                break
        if not url:
            # Como fallback usamos o título + empresa pra criar um id estável
            # e linkamos para a página de busca do Google Jobs.
            slug = re.sub(r"\s+", "-", f"{title}-{company}".lower())[:100]
            url = f"https://www.google.com/search?ibp=htl;jobs#{quote_plus(slug)}"

        is_remote = _classify_remote(location)
        tags = [t for t in (location,) if t]

        return Job(
            id=Job.make_id(self.source_id, url),
            source=self.source_id,
            title=title,
            company=company or "Empresa não informada",
            location=location,
            is_remote=is_remote,
            job_types=[JobType.FULL_TIME],
            description=description[:600] if description else f"{title} — {company}",
            url=url,
            tags=tags,
            posted_at=posted_at,
        )
