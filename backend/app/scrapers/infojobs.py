"""Scraper para InfoJobs Brasil (https://www.infojobs.com.br).

Estratégia:
  - Pra busca por região, usamos a URL "amigável" que realmente filtra:
      /empregos-em-{slug-uf}.aspx?palabra=<kw>
    Ex.: /empregos-em-distrito-federal.aspx?palabra=desenvolvedor
  - Pra remoto, usamos `?teletrabajo=true` (ou home-office na URL).
  - Sem região e sem remoto: /empregos.aspx?palabra=<kw>.
  - Cada página retorna ~20 cards <div class="...js_vacancyLoad...">
    com data-id, data-href, h2 (título), <a href*='/empresa-'> (empresa),
    div.mb-8 (localização), .js_date data-value (data) e os 4 "campos sem
    classe" (salário, experiência, escolaridade, modalidade).

InfoJobs serve HTML completo no GET, então httpx + selectolax bastam.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

from selectolax.parser import HTMLParser

from app.models.job import Job, JobFilter, JobSource, JobType, LocationMode
from app.scrapers.base import BaseScraper, ScrapeError

BASE_URL = "https://www.infojobs.com.br"

# Mapeamento UF -> slug usado na URL friendly do InfoJobs.
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

# Aliases de nome cheio -> UF
UF_ALIAS_FULL: dict[str, str] = {v.replace("-", " "): k for k, v in UF_SLUG.items()}
UF_ALIAS_FULL.update({
    "distrito federal": "df",
    "são paulo": "sp",
    "rio de janeiro": "rj",
    "minas gerais": "mg",
    "rio grande do sul": "rs",
    "rio grande do norte": "rn",
    "santa catarina": "sc",
    "espírito santo": "es",
    "mato grosso": "mt",
    "mato grosso do sul": "ms",
    "paraná": "pr",
    "paraíba": "pb",
    "ceará": "ce",
    "goiás": "go",
    "amapá": "ap",
    "pará": "pa",
    "piauí": "pi",
    "rondônia": "ro",
    "maranhão": "ma",
    "tocantins": "to",
    "amazonas": "am",
    "roraima": "rr",
    "acre": "ac",
    "alagoas": "al",
    "bahia": "ba",
    "pernambuco": "pe",
    "sergipe": "se",
})


def _resolve_uf(region: str | None) -> str | None:
    """Recebe 'Brasília-DF', 'DF', 'Distrito Federal' etc. e retorna 'df' (chave do UF_SLUG)."""
    if not region:
        return None
    raw = region.strip().lower()
    if not raw:
        return None
    # Procura UF de 2 letras em qualquer posição (separadores comuns: -, /, ,, espaço)
    for token in raw.replace("/", " ").replace("-", " ").replace(",", " ").split():
        if len(token) == 2 and token in UF_SLUG:
            return token
    # Tenta nome completo
    for full, uf in UF_ALIAS_FULL.items():
        if full in raw:
            return uf
    return None


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    fmts = ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d")
    for fmt in fmts:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _classify_modality(modality: str, location: str) -> tuple[bool, list[JobType]]:
    """Retorna (is_remote, job_types) a partir do texto de modalidade do card."""
    t = modality.lower() + " " + location.lower()
    is_remote = (
        "home office" in t
        or "remoto" in t
        or "100% remoto" in t
        or "todo brasil" in t  # geralmente nacional/remoto
        or "trabalho remoto" in t
    )
    types: list[JobType] = []
    if "estágio" in t or "estagio" in t or "trainee" in t:
        types.append(JobType.INTERNSHIP)
    if "freela" in t:
        types.append(JobType.FREELANCE)
    if "temporári" in t or "temporario" in t:
        types.append(JobType.TEMPORARY)
    if " pj " in f" {t} " or "pessoa jur" in t:
        types.append(JobType.CONTRACT)
    if "meio período" in t or "meio periodo" in t or "part time" in t or "part-time" in t:
        types.append(JobType.PART_TIME)
    if not types:
        types.append(JobType.FULL_TIME)
    return is_remote, types


def _looks_like_salary(s: str) -> bool:
    s = s.lower()
    return "r$" in s or "a combinar" in s


def _looks_like_modality(s: str) -> bool:
    s = s.lower()
    return any(k in s for k in ("presencial", "híbrido", "hibrido", "home office", "remoto"))


class InfoJobsScraper(BaseScraper):
    source_id = JobSource.INFOJOBS
    name = "InfoJobs Brasil"
    description = "Maior portal generalista BR. Filtra por UF (via URL amigável) e remoto."

    async def fetch(self, f: JobFilter) -> list[Job]:
        results: list[Job] = []
        keywords_to_try = f.keywords or [""]

        try:
            client = await self._client()
            async with client:
                for kw in keywords_to_try[:5]:
                    url_template = self._build_url(f, kw)
                    target = max(1, min(3, (f.limit // 20) + 1))
                    for page in range(1, target + 1):
                        url = url_template
                        if page > 1:
                            sep = "&" if "?" in url else "?"
                            url = f"{url}{sep}page={page}"
                        try:
                            r = await client.get(url)
                        except Exception as exc:  # noqa: BLE001
                            raise ScrapeError(self.source_id, f"GET {url} falhou: {exc}") from exc
                        if r.status_code != 200:
                            raise ScrapeError(
                                self.source_id, f"HTTP {r.status_code} em {url}"
                            )
                        page_jobs = self._parse_listing(r.text)
                        if not page_jobs:
                            break
                        results.extend(page_jobs)
        except ScrapeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScrapeError(self.source_id, f"Erro ao buscar: {exc}") from exc

        # Dedup por id
        seen: set[str] = set()
        unique: list[Job] = []
        for j in results:
            if j.id in seen:
                continue
            seen.add(j.id)
            unique.append(j)
        return unique

    def _build_url(self, f: JobFilter, kw: str) -> str:
        params: dict[str, str] = {}
        if kw:
            params["palabra"] = kw

        # Caso 1: usuário pediu região
        if f.location_mode in (LocationMode.ON_SITE_REGION, LocationMode.HYBRID_REGION):
            uf = _resolve_uf(f.region)
            if uf:
                slug = UF_SLUG[uf]
                qs = f"?{urlencode(params)}" if params else ""
                return f"{BASE_URL}/empregos-em-{slug}.aspx{qs}"

        # Caso 2: remoto BR — usa parâmetro home-office
        if f.location_mode == LocationMode.REMOTE_BRAZIL:
            params["teletrabajo"] = "true"

        qs = f"?{urlencode(params)}" if params else ""
        return f"{BASE_URL}/empregos.aspx{qs}"

    def _parse_listing(self, html: str) -> list[Job]:
        tree = HTMLParser(html)
        jobs: list[Job] = []
        for card in tree.css("div[class*='js_vacancyLoad']"):
            job = self._parse_card(card)
            if job:
                jobs.append(job)
        return jobs

    def _parse_card(self, card) -> Job | None:  # noqa: ANN001
        href = (card.attributes.get("data-href") or "").strip()
        if not href:
            return None
        url = href if href.startswith("http") else f"{BASE_URL}{href}"

        title_node = card.css_first("h2, h3")
        title = title_node.text(strip=True) if title_node else ""
        if not title:
            return None

        company = ""
        for a in card.css("a[href*='/empresa-']"):
            t = a.text(strip=True)
            if t:
                company = " ".join(t.split())
                break

        date_node = card.css_first(".js_date")
        posted_at = _parse_date(date_node.attributes.get("data-value")) if date_node else None

        loc_node = card.css_first("div.mb-8")
        location_raw = loc_node.text(strip=True) if loc_node else ""
        # Tira sufixo "0Km de você." que aparece em algumas vagas
        location = location_raw.split(",0Km")[0].strip()
        location = " ".join(location.split())

        salary = None
        modality = ""
        for div in card.css("div"):
            cls = (div.attributes.get("class") or "").strip()
            # Os campos importantes ficam em divs sem classe e folhas
            if cls or div.css("div") or div.css("span"):
                continue
            text = " ".join(div.text(deep=True, strip=True).split())
            if not text or len(text) > 80:
                continue
            if salary is None and _looks_like_salary(text):
                salary = text
            elif not modality and _looks_like_modality(text):
                modality = text

        is_remote, job_types = _classify_modality(modality, location)

        # Tags úteis pra UI
        tags: list[str] = []
        if modality:
            tags.append(modality)
        if location and location.lower() != "todo brasil":
            tags.append(location)

        return Job(
            id=Job.make_id(self.source_id, url),
            source=self.source_id,
            title=title,
            company=company or "Empresa não informada",
            location=location,
            is_remote=is_remote,
            job_types=job_types,
            description=f"{title} — {company} ({location})" if company else title,
            url=url,
            tags=tags,
            salary_text=salary,
            posted_at=posted_at,
        )
