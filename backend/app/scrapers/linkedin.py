"""Scraper para LinkedIn (público, sem login).

Usa o endpoint **guest** que o próprio LinkedIn serve para usuários
deslogados quando rolam a página de busca:

  GET https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
       ?keywords=<kw>
       &location=<loc>
       &geoId=<id>          (opcional — Brasil = 106057199)
       &f_TPR=r604800       (vagas das últimas 7 dias)
       &f_WT=2              (remoto)
       &start=<n>           (paginação 25-em-25)

Resposta: HTML cru com `div.base-card` por vaga. Cada card tem:
  - data-entity-urn=urn:li:jobPosting:<id>
  - <a class="base-card__full-link" href="https://br.linkedin.com/jobs/view/..." />
  - <h3 class="base-search-card__title"> título </h3>
  - <h4 class="base-search-card__subtitle"> empresa </h4>
  - <span class="job-search-card__location"> localização </span>
  - <time datetime="2026-04-25"> data </time>

Limites conhecidos:
  - Sem login não dá pra paginar mais que ~250 vagas.
  - O LinkedIn aplica rate limit (429) por IP no endpoint guest. Quando
    isso acontece, caímos no fallback abaixo em vez de desistir.

Fallback com Scrapling (StealthyFetcher): se o endpoint guest retornar
429 ou vier vazio, raspamos `linkedin.com/jobs/search/` com um browser
Chromium "undetected" (patchright, via a lib Scrapling). Isso também
devolve bem mais vagas por página (~100+ vs ~25 do guest), então vale
mesmo quando o guest funciona mas devolve pouca coisa.
"""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse, parse_qs, urlencode

from selectolax.parser import HTMLParser

from app.models.job import (
    Job,
    JobFilter,
    JobSource,
    JobType,
    LocationMode,
    Seniority,
)
from app.scrapers.base import BaseScraper, ScrapeError

logger = logging.getLogger(__name__)

GUEST_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
SEARCH_URL = "https://www.linkedin.com/jobs/search/"

# geoId conhecidos (LinkedIn usa esses IDs internos pra filtrar área).
# Manter pequeno: só os mais relevantes pro JobFinder hoje.
GEO_IDS: dict[str, str] = {
    "brazil": "106057199",
    "brasil": "106057199",
    "df": "104413991",
    "distrito federal": "104413991",
    "brasilia": "100866946",
    "sao paulo": "104746682",
    "rio de janeiro": "100437352",
    "minas gerais": "104607825",
    "rio grande do sul": "104607826",  # aproximação
    "parana": "104607823",  # aproximação
}

# f_TPR — last N days
LAST_24H = "r86400"
LAST_WEEK = "r604800"
LAST_MONTH = "r2592000"


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _resolve_geo_id(region: Optional[str]) -> Optional[str]:
    if not region:
        return None
    raw = _strip_accents(region.lower()).strip()
    if not raw:
        return None
    # 2 letras = UF
    for token in raw.replace("/", " ").replace("-", " ").replace(",", " ").split():
        if len(token) == 2 and token in GEO_IDS:
            return GEO_IDS[token]
    for key, gid in GEO_IDS.items():
        if key in raw:
            return gid
    return None


def _f_tpr(posted_within_days: Optional[int]) -> Optional[str]:
    if not posted_within_days:
        return LAST_WEEK  # default: últimos 7 dias
    if posted_within_days <= 1:
        return LAST_24H
    if posted_within_days <= 7:
        return LAST_WEEK
    if posted_within_days <= 30:
        return LAST_MONTH
    return None


def _location_text_from_filter(f: JobFilter) -> str:
    """Texto livre que vai no parâmetro 'location' (mais robusto quando
    geoId não casa)."""
    if f.location_mode == LocationMode.REMOTE_WORLDWIDE:
        return "Worldwide"
    if f.region:
        return f.region
    return "Brazil"


def _job_id_from_url(url: str) -> Optional[str]:
    """LinkedIn URL: https://br.linkedin.com/jobs/view/<slug>-<numericId>?...
    O ID numérico vem no fim do path antes do ?."""
    try:
        parsed = urlparse(url)
        path = parsed.path
        m = re.search(r"-(\d{6,})$", path.split("/")[-1] or "")
        if m:
            return m.group(1)
    except Exception:  # noqa: BLE001
        pass
    return None


def _clean_url(url: str) -> str:
    """Remove parâmetros de tracking; mantém apenas o path canônico."""
    if not url:
        return url
    try:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}{p.path}"
    except Exception:  # noqa: BLE001
        return url


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _seniority_from_title(title: str) -> Seniority:
    norm = _strip_accents(title.lower())
    if any(x in norm for x in (" estagio", "intern", "estagiari")):
        return Seniority.INTERN
    if " junior" in norm or "jr" in norm.split():
        return Seniority.JUNIOR
    if " pleno" in norm:
        return Seniority.MID
    if any(x in norm for x in ("senior", "sr ", " sr.")):
        return Seniority.SENIOR
    if any(x in norm for x in ("lead", "principal", "staff")):
        return Seniority.LEAD
    return Seniority.UNKNOWN


def _classify_remote(location: str, title: str = "") -> bool:
    """LinkedIn raramente diz 'Remote' explicitamente no card; precisamos
    olhar localização + título.

    Heurísticas:
      - 'Brasil' sozinho (sem cidade) costuma indicar vaga aberta a todo
        Brasil = remota.
      - Título com '(Remote)', 'Remote', 'Trabalho Remoto', 'Home Office'.
      - Localização com 'Anywhere', 'Worldwide', 'Remote'.
    """
    loc_norm = _strip_accents(location.lower()).strip()
    title_norm = _strip_accents(title.lower())
    # Sinais explícitos
    explicit = (
        "remoto" in loc_norm
        or "remote" in loc_norm
        or "home office" in loc_norm
        or "home-office" in loc_norm
        or "anywhere" in loc_norm
        or "worldwide" in loc_norm
        or "trabalho remoto" in title_norm
        or "home office" in title_norm
        or "remote" in title_norm
    )
    if explicit:
        return True
    # 'Brasil' isolado (sem cidade) no card do LinkedIn = remoto BR
    if loc_norm in ("brasil", "brazil", "br"):
        return True
    return False


class LinkedInScraper(BaseScraper):
    source_id = JobSource.LINKEDIN
    name = "LinkedIn"
    description = "Vagas públicas (sem login). Sujeito a rate-limit do LinkedIn."

    async def fetch(self, f: JobFilter) -> list[Job]:
        keywords = f.keywords or [""]
        results: list[Job] = []
        seen: set[str] = set()
        location_text = _location_text_from_filter(f)
        geo_id = _resolve_geo_id(f.region) if f.region else None
        f_tpr = _f_tpr(f.posted_within_days)

        # Quantas páginas vamos pedir por keyword. O endpoint guest devolve
        # ~10-25 cards por página; limitamos pra não tomar 429.
        pages = max(1, min(2, (f.limit // 25) + 1))
        blocked = False

        try:
            client = await self._client(
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "Referer": "https://www.linkedin.com/jobs/search/",
                },
            )
            async with client:
                for kw in keywords[:3]:
                    for page in range(pages):
                        params: dict[str, str] = {
                            "keywords": kw,
                            "location": location_text,
                            "start": str(page * 25),
                        }
                        if geo_id:
                            params["geoId"] = geo_id
                        if f_tpr:
                            params["f_TPR"] = f_tpr
                        if f.location_mode == LocationMode.REMOTE_WORLDWIDE:
                            params["f_WT"] = "2"
                        elif f.location_mode == LocationMode.REMOTE_BRAZIL:
                            params["f_WT"] = "2"

                        try:
                            r = await client.get(GUEST_URL, params=params)
                        except Exception as exc:  # noqa: BLE001
                            raise ScrapeError(
                                self.source_id,
                                f"Falha de rede em página {page}: {exc}",
                            ) from exc

                        if r.status_code == 429:
                            # Rate-limit: para tudo dessa keyword, marca
                            # como bloqueado pra acionar o fallback depois.
                            blocked = True
                            break
                        if r.status_code != 200:
                            # Outros erros: para de paginar mas mantém
                            # resultados anteriores.
                            break
                        cards = self._parse_listing(r.text)
                        if not cards:
                            break
                        for job in cards:
                            if job.id in seen:
                                continue
                            seen.add(job.id)
                            results.append(job)
                        # Backoff entre páginas pra reduzir chance de 429.
                        await asyncio.sleep(0.6)
        except ScrapeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScrapeError(self.source_id, f"Erro ao buscar: {exc}") from exc

        # Fallback: guest endpoint bloqueou ou não devolveu nada útil.
        # Raspa a página real de busca com um browser "undetected".
        if blocked or not results:
            try:
                fallback_jobs = await self._fetch_with_browser(
                    keywords[0] if keywords else "", location_text, geo_id, f_tpr, f
                )
                for job in fallback_jobs:
                    if job.id in seen:
                        continue
                    seen.add(job.id)
                    results.append(job)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LinkedIn fallback (browser) falhou: %s", exc)

        return results

    async def _fetch_with_browser(
        self,
        keyword: str,
        location_text: str,
        geo_id: Optional[str],
        f_tpr: Optional[str],
        f: JobFilter,
    ) -> list[Job]:
        """Raspa `linkedin.com/jobs/search/` com Scrapling (StealthyFetcher).

        Usado quando o endpoint guest bloqueia (429) ou devolve pouco.
        A página real renderiza ~100+ vagas de uma vez (sem paginação
        manual), então um fetch já cobre o `limit` na maioria dos casos.
        """
        from scrapling.fetchers import StealthyFetcher

        params: dict[str, str] = {"keywords": keyword, "location": location_text}
        if geo_id:
            params["geoId"] = geo_id
        if f_tpr:
            params["f_TPR"] = f_tpr
        if f.location_mode in (LocationMode.REMOTE_WORLDWIDE, LocationMode.REMOTE_BRAZIL):
            params["f_WT"] = "2"
        url = f"{SEARCH_URL}?{urlencode(params)}"

        resp = await StealthyFetcher.async_fetch(
            url,
            headless=True,
            network_idle=True,
            timeout=25000,
            block_ads=True,
            disable_resources=True,
        )
        if resp.status != 200:
            return []
        return self._parse_listing(resp.body)

    def _parse_listing(self, html: str) -> list[Job]:
        tree = HTMLParser(html)
        jobs: list[Job] = []
        for card in tree.css("div.base-card, li.jobs-search__results-list"):
            job = self._parse_card(card)
            if job:
                jobs.append(job)
        return jobs

    def _parse_card(self, card) -> Optional[Job]:  # noqa: ANN001
        link = card.css_first("a.base-card__full-link") or card.css_first("a")
        if not link:
            return None
        href_raw = (link.attributes.get("href") or "").strip()
        if not href_raw or "linkedin.com/jobs/view" not in href_raw:
            return None
        url = _clean_url(href_raw)

        title_node = card.css_first("h3.base-search-card__title")
        title = title_node.text(strip=True) if title_node else ""
        if not title:
            return None

        company_node = card.css_first("h4.base-search-card__subtitle a") or card.css_first(
            "h4.base-search-card__subtitle"
        )
        company = company_node.text(strip=True) if company_node else "Empresa não informada"

        loc_node = card.css_first("span.job-search-card__location")
        location = loc_node.text(strip=True) if loc_node else ""
        location = " ".join(location.split())

        time_node = card.css_first("time")
        posted_at = _parse_iso(time_node.attributes.get("datetime")) if time_node else None

        is_remote = _classify_remote(location, title)
        seniority = _seniority_from_title(title)

        tags: list[str] = []
        if location:
            tags.append(location)

        return Job(
            id=Job.make_id(self.source_id, url),
            source=self.source_id,
            title=title,
            company=company,
            location=location,
            is_remote=is_remote,
            job_types=[JobType.FULL_TIME],  # LinkedIn não expõe tipo no card
            seniority=seniority,
            description=f"{title} — {company}{(' · ' + location) if location else ''}",
            url=url,
            tags=tags,
            posted_at=posted_at,
        )
