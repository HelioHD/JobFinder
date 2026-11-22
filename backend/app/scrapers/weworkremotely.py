"""Scraper para WeWorkRemotely (https://weworkremotely.com).

Usa os feeds RSS oficiais por categoria — sem login, sem JS, sem rate limit
agressivo. Cada feed traz ~20-25 vagas mais recentes.

Categorias usadas (selecionadas por relevância pra dev/tech):
  remote-programming-jobs
  remote-design-jobs
  remote-customer-support-jobs
  remote-devops-sysadmin-jobs
  remote-marketing-programming-jobs (raro mas inclui growth/marketing tech)

Como todas as vagas são remotas worldwide, este scraper ignora filtros de
região presencial (devolve [] se o usuário pediu ON_SITE_REGION ou
HYBRID_REGION). Pra REMOTE_BRAZIL, faz best-effort: aceita "Anywhere",
"Worldwide", "USA Only" -> mantém; região explicitamente fora do Brasil
(ex.: "Europe Only") seria filtrada pelo matcher.

Formato do RSS:
  <item>
    <title>Empresa: Cargo</title>
    <region>Anywhere in the World</region>
    <category>Front-End Programming</category>
    <pubDate>Mon, 27 Apr 2026 12:00:00 +0000</pubDate>
    <guid>https://weworkremotely.com/remote-jobs/<id>-<slug></guid>
    <link>https://weworkremotely.com/remote-jobs/<id>-<slug></link>
    <description>HTML escaped — começa com <strong>Headquarters:</strong></description>
  </item>
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable

from app.models.job import Job, JobFilter, JobSource, JobType, LocationMode
from app.scrapers.base import BaseScraper, ScrapeError

BASE_FEED = "https://weworkremotely.com/categories"

DEFAULT_CATEGORIES: list[str] = [
    "remote-programming-jobs",
    "remote-design-jobs",
    "remote-devops-sysadmin-jobs",
    "remote-customer-support-jobs",
    "remote-product-jobs",
    "remote-management-and-finance-jobs",
    "remote-marketing-programming-jobs",
]

ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL | re.IGNORECASE)


def _xml_field(item: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", item, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    raw = m.group(1).strip()
    # Strip CDATA quando presente
    if raw.startswith("<![CDATA[") and raw.endswith("]]>"):
        raw = raw[9:-3]
    return raw.strip()


def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_pubdate(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _split_company_title(rss_title: str) -> tuple[str, str]:
    """RSS coloca 'Empresa: Cargo' (às vezes 'Cargo' sem empresa)."""
    if not rss_title:
        return "Empresa", "Vaga"
    if ":" in rss_title:
        company, _, role = rss_title.partition(":")
        return company.strip() or "Empresa", role.strip() or "Vaga"
    return "Empresa", rss_title.strip()


def _accepts_brazil(region: str) -> bool:
    if not region:
        return True
    r = region.lower()
    if "anywhere" in r or "worldwide" in r:
        return True
    if "americas" in r or "latam" in r or "latin america" in r:
        return True
    if "global" in r:
        return True
    if "brazil" in r or "brasil" in r:
        return True
    return False


def _job_types_from_text(text: str) -> list[JobType]:
    """Extrai tipos da descrição (best-effort — RSS não tem campo dedicado)."""
    norm = text.lower()
    types: list[JobType] = []
    if "part-time" in norm or "part time" in norm:
        types.append(JobType.PART_TIME)
    if "internship" in norm or "intern " in norm:
        types.append(JobType.INTERNSHIP)
    if "freelanc" in norm:
        types.append(JobType.FREELANCE)
    if "contract" in norm and "contractor" in norm:
        types.append(JobType.CONTRACT)
    if not types:
        types.append(JobType.FULL_TIME)
    return types


class WeWorkRemotelyScraper(BaseScraper):
    source_id = JobSource.WWR
    name = "We Work Remotely"
    description = "Vagas 100% remotas worldwide via RSS oficial. Foco em tech."

    async def fetch(self, f: JobFilter) -> list[Job]:
        # Faz sentido apenas em modos remotos / qualquer
        if f.location_mode in (LocationMode.ON_SITE_REGION, LocationMode.HYBRID_REGION):
            return []

        results: list[Job] = []
        seen: set[str] = set()

        try:
            client = await self._client(headers={"Accept": "application/rss+xml,application/xml"})
            async with client:
                for cat in DEFAULT_CATEGORIES:
                    url = f"{BASE_FEED}/{cat}.rss"
                    try:
                        r = await client.get(url)
                    except Exception as exc:  # noqa: BLE001
                        # Categoria com erro não derruba os outros feeds
                        continue
                    if r.status_code != 200:
                        continue
                    for item_xml in ITEM_RE.findall(r.text):
                        job = self._parse_item(item_xml)
                        if not job:
                            continue
                        if job.id in seen:
                            continue
                        seen.add(job.id)
                        # Filtro de remoto BR — checa region/headquarters
                        if f.location_mode == LocationMode.REMOTE_BRAZIL:
                            if not _accepts_brazil(job.location):
                                continue
                        results.append(job)
        except Exception as exc:  # noqa: BLE001
            raise ScrapeError(self.source_id, f"Erro ao buscar: {exc}") from exc

        return results

    def _parse_item(self, item_xml: str) -> Job | None:
        link = _xml_field(item_xml, "link") or _xml_field(item_xml, "guid")
        if not link or not link.startswith("http"):
            return None

        rss_title = _xml_field(item_xml, "title")
        company, title = _split_company_title(rss_title)
        region = _xml_field(item_xml, "region") or "Anywhere"
        category = _xml_field(item_xml, "category")

        desc_html = _xml_field(item_xml, "description")
        desc_text = _strip_html(desc_html)

        posted_at = _parse_pubdate(_xml_field(item_xml, "pubDate"))

        tags: list[str] = []
        if category:
            tags.append(category)
        if region:
            tags.append(region)

        return Job(
            id=Job.make_id(self.source_id, link),
            source=self.source_id,
            title=title,
            company=company,
            location=region,
            is_remote=True,
            job_types=_job_types_from_text(desc_text),
            description=desc_text[:600],
            description_html=desc_html,
            url=link,
            tags=tags,
            posted_at=posted_at,
        )
