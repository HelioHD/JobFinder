"""Scraper para Indeed Brasil (https://br.indeed.com).

O maior generalista do Brasil — cobre exatamente o tipo de vaga que os
outros generalistas (InfoJobs, Vagas.com) têm pouco: varejo, alimentação,
atendimento (Barista, Vendedor, Recepcionista, etc.), não só tech.

Diferencial: o parâmetro `l` (location) do Indeed aceita texto livre de
bairro/região ("Asa Norte, Brasília - DF") e faz busca por PROXIMIDADE
geocodificada — não só por cidade/UF como os outros generalistas.
Confirmado manualmente em 2026-08-30: buscar `l=Asa Norte, Brasília - DF`
devolve vagas de fato próximas dali, mesmo que o card da vaga só rotule
a localização como "Brasília, DF" (o Indeed não expõe o bairro na busca).
Por isso os scrapers marcam `f.region` como tag — o matcher usa isso pra
não descartar essas vagas no filtro de localização (ver matcher.py).

Anti-bot: Indeed bloqueia scraping direto agressivamente. Usamos Scrapling
(StealthyFetcher / AsyncStealthySession) com Chromium "undetected"
(patchright) — testado e funciona sem captcha nem bloqueio.

Estratégia:
  - GET https://br.indeed.com/jobs?q=<kw>&l=<location>&start=<n*10>
  - Card: div.job_seen_beacon
      h3.jobTitle a[data-jk]                -> id + título (via span[title])
      span[data-testid="company-name"]      -> empresa
      div[data-testid="text-location"]      -> localização (cidade/UF)
      li[data-testid="attribute_snippet_testid"] -> salário/CLT/turno/benefícios
  - URL canônica: https://br.indeed.com/viewjob?jk=<data-jk>
  - Sessão de browser reaproveitada entre páginas/keywords (1 Chromium por
    fetch(), não 1 por request) — bem mais rápido que abrir um browser novo
    a cada página.
"""
from __future__ import annotations

import asyncio
import logging
import unicodedata
from urllib.parse import urlencode

from app.models.job import Job, JobFilter, JobSource, JobType, LocationMode, Seniority
from app.scrapers.base import BaseScraper, ScrapeError

logger = logging.getLogger(__name__)

BASE_URL = "https://br.indeed.com"
RESULTS_PER_PAGE = 10


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _location_text(f: JobFilter) -> str:
    """Texto pro parâmetro `l`. Região específica (inclusive bairro) tem
    prioridade — é o que dá a busca por proximidade."""
    if f.location_mode in (LocationMode.ON_SITE_REGION, LocationMode.HYBRID_REGION) and f.region:
        return f.region
    return "Brasil"


def _classify(text: str) -> tuple[bool, list[JobType]]:
    norm = _strip_accents(text.lower())
    is_remote = "home office" in norm or "remoto" in norm or "trabalho remoto" in norm
    types: list[JobType] = []
    if "estagio" in norm or "trainee" in norm:
        types.append(JobType.INTERNSHIP)
    if "freelance" in norm or "freela" in norm:
        types.append(JobType.FREELANCE)
    if "temporari" in norm:
        types.append(JobType.TEMPORARY)
    if " pj " in f" {norm} " or "pessoa juridica" in norm:
        types.append(JobType.CONTRACT)
    if "meio periodo" in norm or "part time" in norm or "part-time" in norm:
        types.append(JobType.PART_TIME)
    if not types:
        types.append(JobType.FULL_TIME)
    return is_remote, types


def _seniority_from_title(title: str) -> Seniority:
    norm = _strip_accents(title.lower())
    if "estagi" in norm or "trainee" in norm:
        return Seniority.INTERN
    if "junior" in norm or " jr" in norm:
        return Seniority.JUNIOR
    if "pleno" in norm:
        return Seniority.MID
    if "senior" in norm or " sr" in norm:
        return Seniority.SENIOR
    if "lider" in norm or "coordenador" in norm or "gerente" in norm or "supervisor" in norm:
        return Seniority.LEAD
    return Seniority.UNKNOWN


class IndeedScraper(BaseScraper):
    source_id = JobSource.INDEED
    name = "Indeed Brasil"
    description = (
        "Maior generalista do Brasil — forte em vagas não-tech (varejo, "
        "alimentação, atendimento). Suporta busca por bairro/proximidade."
    )

    async def fetch(self, f: JobFilter) -> list[Job]:
        from scrapling.fetchers import AsyncStealthySession

        keywords = (f.keywords or [""])[:2]
        location = _location_text(f)
        pages = max(1, min(2, (f.limit // RESULTS_PER_PAGE) + 1))

        results: list[Job] = []
        seen: set[str] = set()

        try:
            async with AsyncStealthySession(headless=True, max_pages=1) as session:
                for kw in keywords:
                    for page in range(pages):
                        params = {"q": kw, "l": location}
                        if page > 0:
                            params["start"] = str(page * RESULTS_PER_PAGE)
                        url = f"{BASE_URL}/jobs?{urlencode(params)}"
                        try:
                            resp = await session.fetch(
                                url,
                                network_idle=True,
                                timeout=25000,
                                block_ads=True,
                                disable_resources=True,
                            )
                        except Exception as exc:  # noqa: BLE001
                            raise ScrapeError(
                                self.source_id, f"Falha ao buscar '{kw}': {exc}"
                            ) from exc

                        if resp.status != 200:
                            break
                        new_count = 0
                        for card in resp.css("div.job_seen_beacon"):
                            job = self._parse_card(card, f)
                            if not job or job.id in seen:
                                continue
                            seen.add(job.id)
                            results.append(job)
                            new_count += 1
                        if new_count == 0:
                            break
                        await asyncio.sleep(0.4)
        except ScrapeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScrapeError(self.source_id, f"Erro ao buscar: {exc}") from exc

        return results

    def _parse_card(self, card, f: JobFilter):  # noqa: ANN001
        link = card.css("a[data-jk]")
        if not link:
            return None
        jk = link[0].attrib.get("data-jk", "")
        if not jk:
            return None
        url = f"{BASE_URL}/viewjob?jk={jk}"

        title_el = card.css("span[id^='jobTitle-']")
        title = (title_el[0].attrib.get("title") or title_el[0].get_all_text()).strip() if title_el else ""
        if not title:
            return None

        company_el = card.css("span[data-testid='company-name']")
        company = company_el[0].get_all_text().strip() if company_el else "Empresa não informada"

        location_el = card.css("div[data-testid='text-location']")
        location = location_el[0].get_all_text().strip() if location_el else ""

        salary = None
        meta_texts: list[str] = []
        for li in card.css("li[data-testid*='attribute_snippet_testid']"):
            text = li.get_all_text().strip()
            if not text:
                continue
            meta_texts.append(text)
            if salary is None and "salary-snippet-container" in (li.attrib.get("class") or ""):
                salary = text

        is_remote, job_types = _classify(" ".join([location, *meta_texts]))

        tags = list(meta_texts)
        if location:
            tags.append(location)
        # Região pesquisada (pode ser um bairro) — o Indeed já filtrou por
        # proximidade do lado do servidor, então isso vira um "carimbo" pro
        # matcher aceitar mesmo quando o card só mostra a cidade.
        if f.location_mode in (LocationMode.ON_SITE_REGION, LocationMode.HYBRID_REGION) and f.region:
            tags.append(f.region)

        return Job(
            id=Job.make_id(self.source_id, url),
            source=self.source_id,
            title=title,
            company=company,
            location=location,
            is_remote=is_remote,
            job_types=job_types,
            seniority=_seniority_from_title(title),
            description=f"{title} — {company}" + (f" ({location})" if location else ""),
            url=url,
            tags=tags,
            salary_text=salary,
        )
