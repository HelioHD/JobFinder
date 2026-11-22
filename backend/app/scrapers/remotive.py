"""Scraper para Remotive (https://remotive.com).

API pública JSON, sem autenticação:
  GET https://remotive.com/api/remote-jobs?search=<kw>&category=<cat>&limit=<n>

Resposta:
  { "jobs": [ {id, url, title, company_name, category, tags, job_type,
               publication_date, candidate_required_location, salary,
               description, ...}, ... ] }

Todas as vagas do Remotive são remotas. A coluna `candidate_required_location`
diz onde o candidato precisa estar (ex.: "USA", "Worldwide", "Brazil").
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.job import Job, JobFilter, JobSource, JobType, LocationMode
from app.scrapers.base import BaseScraper, ScrapeError

API_URL = "https://remotive.com/api/remote-jobs"

_TYPE_MAP = {
    "full_time": JobType.FULL_TIME,
    "fulltime": JobType.FULL_TIME,
    "part_time": JobType.PART_TIME,
    "parttime": JobType.PART_TIME,
    "freelance": JobType.FREELANCE,
    "contract": JobType.CONTRACT,
    "internship": JobType.INTERNSHIP,
    "intern": JobType.INTERNSHIP,
}


def _strip_html(html: str) -> str:
    if not html:
        return ""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_date(s: Any) -> datetime | None:
    if not isinstance(s, str):
        return None
    s = s.strip()
    fmts = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    )
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _accepts_brazil(required_loc: str) -> bool:
    """Heurística: a vaga aceita candidato no Brasil?"""
    if not required_loc:
        return True
    s = required_loc.lower()
    if "worldwide" in s or "anywhere" in s:
        return True
    if "brazil" in s or "brasil" in s or "latam" in s or "latin america" in s:
        return True
    if "americas" in s or "global" in s:
        return True
    return False


class RemotiveScraper(BaseScraper):
    source_id = JobSource.REMOTIVE
    name = "Remotive"
    description = "Vagas 100% remotas (worldwide). API pública JSON."

    async def fetch(self, f: JobFilter) -> list[Job]:
        # Remotive só faz sentido em modos remotos.
        if f.location_mode in (LocationMode.ON_SITE_REGION, LocationMode.HYBRID_REGION):
            return []

        params: dict[str, str] = {"limit": str(min(f.limit * 2, 100))}
        if f.keywords:
            # Remotive aceita 1 termo de busca; juntamos as keywords com espaço.
            params["search"] = " ".join(f.keywords[:3])

        try:
            client = await self._client()
            async with client:
                r = await client.get(API_URL, params=params)
                if r.status_code != 200:
                    raise ScrapeError(self.source_id, f"HTTP {r.status_code}")
                data = r.json()
        except ScrapeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScrapeError(self.source_id, f"Erro ao buscar: {exc}") from exc

        out: list[Job] = []
        for raw in data.get("jobs", []):
            job = self._parse_job(raw)
            if not job:
                continue
            # Se o usuário pediu remoto BR, filtra por aceitar Brasil
            if f.location_mode == LocationMode.REMOTE_BRAZIL:
                if not _accepts_brazil(raw.get("candidate_required_location") or ""):
                    continue
            out.append(job)
        return out

    def _parse_job(self, raw: dict[str, Any]) -> Job | None:
        url = raw.get("url") or ""
        if not url:
            return None
        try:
            jt = _TYPE_MAP.get(str(raw.get("job_type", "")).lower())
            location = raw.get("candidate_required_location") or "Remoto"
            return Job(
                id=Job.make_id(self.source_id, url),
                source=self.source_id,
                title=raw.get("title") or "",
                company=raw.get("company_name") or "",
                location=location,
                is_remote=True,
                job_types=[jt] if jt else [JobType.FULL_TIME],
                description_html=raw.get("description") or "",
                description=_strip_html(raw.get("description") or "")[:600],
                url=url,
                tags=[t for t in (raw.get("tags") or []) if isinstance(t, str)][:8],
                salary_text=raw.get("salary") or None,
                posted_at=_parse_date(raw.get("publication_date")),
            )
        except Exception:  # noqa: BLE001
            return None
