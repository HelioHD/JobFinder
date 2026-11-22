"""Scraper para Arbeitnow.

API pública e gratuita, sem autenticação. Retorna vagas EU/DACH e
remotas worldwide. Útil pra testar o pipeline ponta-a-ponta.

Docs: https://documenter.getpostman.com/view/18545278/UVJbJdKh
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.job import Job, JobFilter, JobSource, JobType, LocationMode
from app.scrapers.base import BaseScraper, ScrapeError

API_URL = "https://www.arbeitnow.com/api/job-board-api"


_TYPE_MAP = {
    "full-time": JobType.FULL_TIME,
    "fulltime": JobType.FULL_TIME,
    "part-time": JobType.PART_TIME,
    "parttime": JobType.PART_TIME,
    "freelance": JobType.FREELANCE,
    "freelancer": JobType.FREELANCE,
    "contract": JobType.CONTRACT,
    "contractor": JobType.CONTRACT,
    "internship": JobType.INTERNSHIP,
    "intern": JobType.INTERNSHIP,
    "temporary": JobType.TEMPORARY,
}


def _map_types(items: list[str] | None) -> list[JobType]:
    if not items:
        return []
    out: list[JobType] = []
    for item in items:
        key = item.lower().replace("_", "-").strip()
        mapped = _TYPE_MAP.get(key)
        if mapped and mapped not in out:
            out.append(mapped)
    return out


def _parse_timestamp(ts: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


class ArbeitnowScraper(BaseScraper):
    source_id = JobSource.ARBEITNOW
    name = "Arbeitnow"
    description = "API pública gratuita com vagas EU/DACH e remotas worldwide."

    async def fetch(self, f: JobFilter) -> list[Job]:
        # A API só aceita filtros simples; pegamos páginas e filtramos depois no matcher.
        # Quando há keywords ou filtro de localização, buscamos mais páginas
        # porque o pós-filtro vai descartar muita coisa.
        if f.keywords or f.location_mode != LocationMode.ANY:
            max_pages = 4
        else:
            max_pages = max(1, min(3, (f.limit // 30) + 1))
        results: list[Job] = []

        # Headers extras p/ não cair em rate-limit / WAF do Arbeitnow.
        client_kwargs = {
            "headers": {
                "Accept": "application/json",
                "Referer": "https://www.arbeitnow.com/",
            },
        }

        try:
            import asyncio
            client = await self._client(**client_kwargs)
            async with client:
                for page in range(1, max_pages + 1):
                    if page > 1:
                        # Pequeno backoff entre páginas — o servidor é sensível.
                        await asyncio.sleep(0.5)
                    resp = await client.get(API_URL, params={"page": page})
                    if resp.status_code == 403 and page > 1:
                        # Já temos resultados das páginas anteriores; seguimos sem erro.
                        break
                    if resp.status_code != 200:
                        raise ScrapeError(
                            self.source_id,
                            f"HTTP {resp.status_code} na página {page}",
                        )
                    payload = resp.json()
                    data = payload.get("data") or []
                    if not data:
                        break
                    for raw in data:
                        job = self._parse_job(raw)
                        if job:
                            results.append(job)
        except ScrapeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScrapeError(self.source_id, f"Erro ao buscar: {exc}") from exc

        # Pre-filtragem rápida por modo remoto (economiza trabalho do matcher).
        if f.location_mode == LocationMode.REMOTE_WORLDWIDE:
            results = [j for j in results if j.is_remote]

        return results

    def _parse_job(self, raw: dict[str, Any]) -> Job | None:
        url = raw.get("url") or ""
        if not url:
            return None
        try:
            return Job(
                id=Job.make_id(self.source_id, url),
                source=self.source_id,
                title=raw.get("title") or "",
                company=raw.get("company_name") or "",
                location=raw.get("location") or "",
                is_remote=bool(raw.get("remote")),
                job_types=_map_types(raw.get("job_types")),
                description_html=raw.get("description") or "",
                description=_strip_html(raw.get("description") or ""),
                url=url,
                tags=[t for t in (raw.get("tags") or []) if isinstance(t, str)],
                posted_at=_parse_timestamp(raw.get("created_at")),
            )
        except Exception:  # noqa: BLE001 — se um item específico falhar, pula
            return None


def _strip_html(html: str) -> str:
    """Remove tags HTML de forma rasteira (boa o suficiente pra busca textual)."""
    if not html:
        return ""
    import re

    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
