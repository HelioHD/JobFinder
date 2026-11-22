"""Scraper para Trampos.co (https://trampos.co).

Trampos é uma SPA Ember mas pra SEO/noscript ele incorpora um bloco
JavaScript com TODAS as vagas pré-renderizadas:

    window.initialLoad = function(store) {
      return {
        config: {
          highlighted_opportunities: [...],
          opportunity_groups: [
            { name: "mais recentes!", opportunities: [...] },
            ...
          ],
          ...
        }
      };
    }

Cada `opportunity` tem o suficiente pra montar um Job:
  id, name, type_name, type_slug, category_name, category_slug,
  company_name, state, city, home_office, published_at

URL pública da vaga: https://trampos.co/oportunidades/{id}

Estratégia:
  - Buscar a página de listagem por categoria/slug (`/oportunidades`)
    ou por categoria (`/oportunidades/categoria/{slug}`).
  - Extrair o JSON via regex.
  - Achatar `highlighted_opportunities` + todas as listas de
    `opportunity_groups[].opportunities`.

Sem dependência externa pesada — basta httpx + json + regex.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from typing import Any, Iterable, Optional

from app.models.job import Job, JobFilter, JobSource, JobType, LocationMode
from app.scrapers.base import BaseScraper, ScrapeError

BASE_URL = "https://trampos.co"

CATEGORY_SLUGS: list[str] = [
    "ti",
    "design",
    "dados",
    "marketing",
    "midia",
    "criacao",
    "produto",
    "comercial",
]

# Mapeia type_slug do Trampos -> JobType
TYPE_MAP: dict[str, JobType] = {
    "emprego": JobType.FULL_TIME,
    "estagio": JobType.INTERNSHIP,
    "freela": JobType.FREELANCE,
    "freelancer": JobType.FREELANCE,
    "temporario": JobType.TEMPORARY,
    "pj": JobType.CONTRACT,
}

# UF -> abreviação 2 letras
UF_NAMES: dict[str, str] = {
    "ac": "AC", "al": "AL", "am": "AM", "ap": "AP", "ba": "BA",
    "ce": "CE", "df": "DF", "es": "ES", "go": "GO", "ma": "MA",
    "mg": "MG", "ms": "MS", "mt": "MT", "pa": "PA", "pb": "PB",
    "pe": "PE", "pi": "PI", "pr": "PR", "rj": "RJ", "rn": "RN",
    "ro": "RO", "rr": "RR", "rs": "RS", "sc": "SC", "se": "SE",
    "sp": "SP", "to": "TO",
}

# Captura: window.initialLoad = function(store) { return { config: {...} }; }
INITIAL_LOAD_RE = re.compile(
    r"return\s*\{\s*config:\s*(\{.*?\})\s*\}\s*;?\s*\}",
    re.DOTALL,
)


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _resolve_uf(region: Optional[str]) -> Optional[str]:
    if not region:
        return None
    raw = _strip_accents(region.lower()).strip()
    for token in raw.replace("/", " ").replace("-", " ").replace(",", " ").split():
        if len(token) == 2 and token.upper() in UF_NAMES.values():
            return token.upper()
    return None


def _balanced_json(text: str, start: int) -> Optional[str]:
    """Extrai o objeto JSON balanceando chaves (a regex sozinha falha em
    aninhados profundos). Recebe o índice de uma '{' e devolve até a '}' par.
    Retorna None se não fechar."""
    depth = 0
    in_str = False
    escape = False
    i = start
    while i < len(text):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        i += 1
    return None


def _extract_initial_config(html: str) -> Optional[dict[str, Any]]:
    """Localiza `window.initialLoad` e devolve o objeto `config`."""
    marker = "window.initialLoad"
    idx = html.find(marker)
    if idx < 0:
        return None
    # Avança até o primeiro 'config:' depois desse marker
    cfg_idx = html.find("config:", idx)
    if cfg_idx < 0:
        return None
    brace = html.find("{", cfg_idx)
    if brace < 0:
        return None
    raw = _balanced_json(html, brace)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _norm_state(value: Any) -> str:
    if not value or not isinstance(value, str):
        return ""
    if len(value) == 2 and value.upper() in UF_NAMES.values():
        return value.upper()
    return value


def _location_text(state: Any, city: Any, home_office: bool) -> str:
    if home_office:
        return "Home Office (BR)"
    state_norm = _norm_state(state) if state else ""
    parts: list[str] = []
    # No JSON do Trampos `city` muitas vezes vem como o nome da empresa
    # quando não tem cidade real. Heurística: só usa se contém letra
    # minúscula (cidade real geralmente vem 'São Paulo', 'Belo Horizonte'…).
    if isinstance(city, str) and city and not city.isupper() and not state_norm == city:
        parts.append(city.strip())
    if state_norm:
        parts.append(state_norm)
    return " / ".join(parts) if parts else ""


def _flatten_unique(value: Any) -> str:
    """type_name/category_name vêm às vezes como string, às vezes lista."""
    if isinstance(value, list):
        return ", ".join(str(x) for x in value if x)
    if isinstance(value, str):
        return value
    return ""


def _parse_published(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    # Formato ISO com tz: 2026-04-27T17:40:06Z ou +0000 ou -03:00
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        pass
    return None


class TramposScraper(BaseScraper):
    source_id = JobSource.TRAMPOS
    name = "Trampos.co"
    description = "Portal BR de vagas em comunicação e tech (JSON embutido na página)."

    async def fetch(self, f: JobFilter) -> list[Job]:
        # Trampos é majoritariamente brasileiro. Se o usuário pediu remoto
        # mundo, ainda valemos a pena (vagas BR remotas são úteis), mas
        # precisamos avisar que não cobre worldwide além do Brasil.
        results: list[Job] = []
        seen_ids: set[str] = set()
        urls = self._build_urls(f)

        try:
            client = await self._client()
            async with client:
                for url in urls:
                    try:
                        r = await client.get(url)
                    except Exception:
                        continue
                    if r.status_code != 200:
                        continue
                    cfg = _extract_initial_config(r.text)
                    if not cfg:
                        continue
                    for raw in self._iter_opportunities(cfg):
                        job = self._parse_opportunity(raw, f)
                        if not job:
                            continue
                        if job.id in seen_ids:
                            continue
                        seen_ids.add(job.id)
                        results.append(job)
        except Exception as exc:  # noqa: BLE001
            raise ScrapeError(self.source_id, f"Erro ao buscar: {exc}") from exc

        return results

    def _build_urls(self, f: JobFilter) -> list[str]:
        urls: list[str] = []
        if f.location_mode == LocationMode.REMOTE_BRAZIL:
            urls.append(f"{BASE_URL}/oportunidades/home-office")
        urls.append(f"{BASE_URL}/oportunidades/categoria/ti")
        urls.append(f"{BASE_URL}/oportunidades/categoria/dados")
        urls.append(f"{BASE_URL}/oportunidades/categoria/produto")
        urls.append(f"{BASE_URL}/oportunidades")
        # Dedup mantendo ordem
        seen: set[str] = set()
        unique: list[str] = []
        for u in urls:
            if u in seen:
                continue
            seen.add(u)
            unique.append(u)
        return unique

    def _iter_opportunities(self, cfg: dict[str, Any]) -> Iterable[dict[str, Any]]:
        for item in cfg.get("highlighted_opportunities") or []:
            if isinstance(item, dict):
                yield item
        for grp in cfg.get("opportunity_groups") or []:
            if not isinstance(grp, dict):
                continue
            for item in grp.get("opportunities") or []:
                if isinstance(item, dict):
                    yield item

    def _parse_opportunity(self, raw: dict[str, Any], f: JobFilter) -> Optional[Job]:
        op_id = raw.get("id")
        if op_id is None:
            return None
        url = f"{BASE_URL}/oportunidades/{op_id}"
        name = (raw.get("name") or "").strip()
        if not name:
            return None
        title = name.title() if name == name.lower() else name

        company_field = raw.get("company_name")
        if isinstance(company_field, list):
            company = next(
                (str(x).strip() for x in company_field if x),
                "Empresa não informada",
            )
        else:
            company = str(company_field or "Empresa não informada").strip()

        type_slug = (raw.get("type_slug") or "").lower()
        job_type = TYPE_MAP.get(type_slug, JobType.FULL_TIME)
        types = [job_type]

        is_remote = bool(raw.get("home_office"))
        if f.location_mode == LocationMode.REMOTE_BRAZIL and not is_remote:
            return None

        location = _location_text(raw.get("state"), raw.get("city"), is_remote)
        # Filtro de região server-side (best-effort)
        if f.location_mode in (LocationMode.ON_SITE_REGION, LocationMode.HYBRID_REGION):
            target_uf = _resolve_uf(f.region)
            if target_uf:
                cur_uf = _norm_state(raw.get("state"))
                if cur_uf and cur_uf != target_uf:
                    return None

        type_name = _flatten_unique(raw.get("type_name"))
        category = _flatten_unique(raw.get("category_name"))
        tags = [t for t in (type_name, category) if t]

        published_at = _parse_published(raw.get("published_at"))

        description_parts: list[str] = []
        if type_name:
            description_parts.append(type_name)
        if category:
            description_parts.append(category)
        if location:
            description_parts.append(location)
        description = " — ".join(description_parts) or title

        return Job(
            id=Job.make_id(self.source_id, url),
            source=self.source_id,
            title=title,
            company=company,
            location=location,
            is_remote=is_remote,
            job_types=types,
            description=description,
            url=url,
            tags=tags,
            posted_at=published_at,
        )
