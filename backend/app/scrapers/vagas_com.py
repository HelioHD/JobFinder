"""Scraper para Vagas.com (https://www.vagas.com.br).

Estratégia (HTML server-side, sem Playwright):

  - URL friendly por keyword:
      /vagas-de-{slug-kw}
      /vagas-de-{slug-kw}-em-{slug-uf}        (presencial/híbrido em UF)
      /vagas-de-{slug-kw}-home-office         (remoto BR)

  - Páginas adicionais: ?pagina=N
  - Cada vaga é um <li class="vaga"> com:
        h2.cargo > a       -> título + href (`/vagas/v<id>/<slug>`)
        span.emprVaga      -> empresa
        span.nivelVaga     -> senioridade ('Júnior/Trainee', 'Sênior', etc.)
        .vaga-local        -> localização (com '/' UF)
        .data-publicacao   -> data dd/mm/yyyy
        .detalhes p        -> trecho da descrição

Vagas.com é resiliente a httpx + selectolax: HTML completo no GET, sem JS.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

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

BASE_URL = "https://www.vagas.com.br"

UF_SLUG: dict[str, str] = {
    "ac": "acre",
    "al": "alagoas",
    "am": "amazonas",
    "ap": "amapa",
    "ba": "bahia",
    "ce": "ceara",
    "df": "distrito-federal",
    "es": "espirito-santo",
    "go": "goias",
    "ma": "maranhao",
    "mg": "minas-gerais",
    "ms": "mato-grosso-do-sul",
    "mt": "mato-grosso",
    "pa": "para",
    "pb": "paraiba",
    "pe": "pernambuco",
    "pi": "piaui",
    "pr": "parana",
    "rj": "rio-de-janeiro",
    "rn": "rio-grande-do-norte",
    "ro": "rondonia",
    "rr": "roraima",
    "rs": "rio-grande-do-sul",
    "sc": "santa-catarina",
    "se": "sergipe",
    "sp": "sao-paulo",
    "to": "tocantins",
}

UF_ALIAS_FULL: dict[str, str] = {v.replace("-", " "): k for k, v in UF_SLUG.items()}
UF_ALIAS_FULL.update(
    {
        "distrito federal": "df",
        "brasilia": "df",
        "sao paulo": "sp",
        "rio de janeiro": "rj",
        "minas gerais": "mg",
        "rio grande do sul": "rs",
        "rio grande do norte": "rn",
        "santa catarina": "sc",
        "espirito santo": "es",
        "mato grosso": "mt",
        "mato grosso do sul": "ms",
    }
)

# UF -> slug da capital. Vagas.com tem mais vagas indexadas por cidade
# do que por UF; usamos a capital como heurística.
UF_TO_CAPITAL: dict[str, str] = {
    "ac": "rio-branco",
    "al": "maceio",
    "am": "manaus",
    "ap": "macapa",
    "ba": "salvador",
    "ce": "fortaleza",
    "df": "brasilia",
    "es": "vitoria",
    "go": "goiania",
    "ma": "sao-luis",
    "mg": "belo-horizonte",
    "ms": "campo-grande",
    "mt": "cuiaba",
    "pa": "belem",
    "pb": "joao-pessoa",
    "pe": "recife",
    "pi": "teresina",
    "pr": "curitiba",
    "rj": "rio-de-janeiro",
    "rn": "natal",
    "ro": "porto-velho",
    "rr": "boa-vista",
    "rs": "porto-alegre",
    "sc": "florianopolis",
    "se": "aracaju",
    "sp": "sao-paulo",
    "to": "palmas",
}

SENIORITY_MAP: dict[str, Seniority] = {
    "júnior": Seniority.JUNIOR,
    "junior": Seniority.JUNIOR,
    "júnior/trainee": Seniority.JUNIOR,
    "junior/trainee": Seniority.JUNIOR,
    "trainee": Seniority.JUNIOR,
    "estagiário": Seniority.INTERN,
    "estagiario": Seniority.INTERN,
    "pleno": Seniority.MID,
    "sênior": Seniority.SENIOR,
    "senior": Seniority.SENIOR,
    "líder": Seniority.LEAD,
    "lider": Seniority.LEAD,
    "gerente": Seniority.LEAD,
    "diretor": Seniority.LEAD,
    "coordenador": Seniority.LEAD,
}


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _slugify(value: str) -> str:
    """Slug compatível com URLs do Vagas.com: minúsculas, sem acentos, hifens."""
    norm = _strip_accents(value).lower().strip()
    norm = re.sub(r"[^a-z0-9]+", "-", norm)
    return norm.strip("-")


def _resolve_uf(region: Optional[str]) -> Optional[str]:
    if not region:
        return None
    raw = _strip_accents(region.lower()).strip()
    if not raw:
        return None
    for token in raw.replace("/", " ").replace("-", " ").replace(",", " ").split():
        if len(token) == 2 and token in UF_SLUG:
            return token
    for full, uf in UF_ALIAS_FULL.items():
        if full in raw:
            return uf
    return None


def _city_slug_from_region(region: Optional[str]) -> Optional[str]:
    """Tenta extrair um slug de cidade da região digitada pelo usuário.

    Heurísticas:
      - 'Brasília-DF' / 'Brasília/DF' / 'Brasília' -> brasilia
      - 'São Paulo-SP' / 'São Paulo' -> sao-paulo
      - 'DF' (sem cidade) -> usa capital do UF -> brasilia

    Retorna o slug pronto pra entrar em /vagas-em-{slug} ou
    /vagas-de-{kw}-em-{slug}.
    """
    if not region:
        return None
    raw = _strip_accents(region).strip()
    if not raw:
        return None

    # Separa parte antes do '-' / '/' / ',' que costuma ser a cidade
    for sep in ("/", "-", ","):
        if sep in raw:
            parts = [p.strip() for p in raw.split(sep) if p.strip()]
            if parts:
                first = parts[0]
                # Se a 1ª parte é UF de 2 letras, pula pra capital
                if len(first) == 2 and first.lower() in UF_SLUG:
                    return UF_TO_CAPITAL[first.lower()]
                slug = _slugify(first)
                if slug and slug not in UF_SLUG:  # evita slug que é só UF
                    return slug

    # Sem separador: ou é UF de 2 letras, ou nome de cidade direto
    if len(raw) == 2 and raw.lower() in UF_SLUG:
        return UF_TO_CAPITAL[raw.lower()]
    slug = _slugify(raw)
    if slug:
        # Se for um nome de UF (ex.: 'distrito federal'), usar capital
        for full, uf in UF_ALIAS_FULL.items():
            if _slugify(full) == slug:
                return UF_TO_CAPITAL[uf]
        return slug
    return None


def _parse_date(raw: str) -> Optional[datetime]:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _classify(location: str, modality_text: str = "") -> tuple[bool, list[JobType]]:
    norm = _strip_accents((location + " " + modality_text).lower())
    is_remote = (
        "home office" in norm
        or "remoto" in norm
        or "100% home" in norm
        or "trabalho remoto" in norm
    )
    types: list[JobType] = []
    if "estagio" in norm or "trainee" in norm:
        types.append(JobType.INTERNSHIP)
    if "freela" in norm:
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


def _seniority_from_text(text: str) -> Seniority:
    if not text:
        return Seniority.UNKNOWN
    norm = text.lower().strip()
    return SENIORITY_MAP.get(norm, Seniority.UNKNOWN)


class VagasComScraper(BaseScraper):
    source_id = JobSource.VAGAS_COM
    name = "Vagas.com"
    description = "Portal generalista BR com URLs amigáveis por cargo/UF/home-office."

    async def fetch(self, f: JobFilter) -> list[Job]:
        keywords = f.keywords or [None]  # None = busca por cidade/geral
        results: list[Job] = []
        seen_ids: set[str] = set()

        try:
            client = await self._client()
            async with client:
                for kw in keywords[:5]:
                    base_url = self._build_url(f, kw)
                    pages = max(1, min(3, (f.limit // 30) + 1))
                    for page in range(1, pages + 1):
                        url = base_url
                        if page > 1:
                            sep = "&" if "?" in url else "?"
                            url = f"{url}{sep}pagina={page}"
                        try:
                            r = await client.get(url)
                        except Exception as exc:  # noqa: BLE001
                            raise ScrapeError(
                                self.source_id, f"GET {url} falhou: {exc}"
                            ) from exc
                        # 404 = combinação kw+UF inexistente, segue pra próxima
                        if r.status_code == 404:
                            break
                        if r.status_code != 200:
                            raise ScrapeError(
                                self.source_id, f"HTTP {r.status_code} em {url}"
                            )
                        cards = self._parse_listing(r.text)
                        if not cards:
                            break
                        new_in_page = 0
                        for job in cards:
                            if job.id in seen_ids:
                                continue
                            seen_ids.add(job.id)
                            results.append(job)
                            new_in_page += 1
                        if new_in_page == 0:
                            break
        except ScrapeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScrapeError(self.source_id, f"Erro ao buscar: {exc}") from exc

        return results

    def _build_url(self, f: JobFilter, kw: Optional[str]) -> str:
        slug_kw = _slugify(kw) if kw else None

        if f.location_mode == LocationMode.REMOTE_BRAZIL:
            kw_for_url = slug_kw or "desenvolvedor"
            return f"{BASE_URL}/vagas-de-{kw_for_url}-home-office"

        if f.location_mode in (LocationMode.ON_SITE_REGION, LocationMode.HYBRID_REGION):
            # Vagas.com indexa muito melhor por CIDADE do que por UF.
            city_slug = _city_slug_from_region(f.region)
            if city_slug:
                if slug_kw:
                    return f"{BASE_URL}/vagas-de-{slug_kw}-em-{city_slug}"
                # Sem keyword: pega TUDO da cidade
                return f"{BASE_URL}/vagas-em-{city_slug}"

        # Sem cidade nem keyword: começa pela página inicial
        if not slug_kw:
            return f"{BASE_URL}/vagas-de-desenvolvedor"
        return f"{BASE_URL}/vagas-de-{slug_kw}"

    def _parse_listing(self, html: str) -> list[Job]:
        tree = HTMLParser(html)
        jobs: list[Job] = []
        for card in tree.css("li.vaga"):
            job = self._parse_card(card)
            if job:
                jobs.append(job)
        return jobs

    def _parse_card(self, card) -> Optional[Job]:  # noqa: ANN001
        link = card.css_first("h2.cargo a") or card.css_first("a.link-detalhes-vaga")
        if not link:
            return None
        href = (link.attributes.get("href") or "").strip()
        if not href:
            return None
        url = href if href.startswith("http") else f"{BASE_URL}{href}"

        title_attr = link.attributes.get("title")
        title = (title_attr or link.text(strip=True) or "").strip()
        if not title:
            return None

        company_node = card.css_first("span.emprVaga, .emprVaga")
        company = company_node.text(strip=True) if company_node else ""
        company = " ".join(company.split()) or "Empresa não informada"

        seniority_node = card.css_first("span.nivelVaga, .nivelVaga")
        seniority_text = seniority_node.text(strip=True) if seniority_node else ""
        seniority = _seniority_from_text(seniority_text)

        loc_node = card.css_first(".vaga-local")
        location_raw = loc_node.text(strip=True) if loc_node else ""
        # Remove o tooltip que aparece concatenado ao texto
        location = re.split(r"A empresa aceita", location_raw)[0].strip()
        location = " ".join(location.split())

        date_node = card.css_first(".data-publicacao")
        posted_at = _parse_date(date_node.text(strip=True)) if date_node else None

        desc_node = card.css_first(".detalhes p")
        description = desc_node.text(strip=True) if desc_node else ""
        description = " ".join(description.split())

        is_remote, job_types = _classify(location, description)

        tags: list[str] = []
        if seniority_text:
            tags.append(seniority_text)
        if location and "/" in location:
            tags.append(location.split("/")[-1].strip())  # UF como tag

        return Job(
            id=Job.make_id(self.source_id, url),
            source=self.source_id,
            title=title,
            company=company,
            location=location,
            is_remote=is_remote,
            job_types=job_types,
            seniority=seniority,
            description=description or f"{title} — {company}",
            url=url,
            tags=tags,
            posted_at=posted_at,
        )
