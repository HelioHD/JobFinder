"""Aplica um JobFilter sobre uma lista de Job (filtragem em memória).

A maioria dos scrapers já recebe os filtros e tenta filtrar do lado da
fonte (mais eficiente), mas usamos isso como segunda camada para
garantir consistência e suportar filtros que nem toda fonte respeita.

Match de keywords:
  - Por padrão usa "escopo curto": busca no título + tags + primeiros 250
    chars da descrição (evita falsos positivos de techs mencionadas só
    como "diferencial").
  - Aliases reconhecidos: 'nodejs' bate em 'node.js', 'node js', 'node';
    'js' bate em 'javascript', 'typescript' em 'ts', etc.
  - Word boundaries: 'js' não casa dentro de 'jsdoc' ou 'jsx'.
  - Modo ANY (default): basta uma keyword bater. Modo ALL: todas precisam.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone

from app.models.job import Job, JobFilter, LocationMode


def _strip_accents(text: str) -> str:
    """Remove acentos: 'Sênior' -> 'Senior', 'Brasília' -> 'Brasilia'.

    Usado pra comparação só — nunca persistimos texto sem acento, isso é
    apenas pra match de keywords/região não falhar por causa de diacríticos.
    """
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


# ----------------------- Aliases / variantes ----------------------- #

# Mapa: termo "canônico" (chave) -> lista de variantes que devem casar.
# A própria chave também é considerada uma variante.
TECH_ALIASES: dict[str, list[str]] = {
    # Atenção: NÃO incluímos 'js' como alias de 'javascript' nem 'ts' como
    # alias de 'typescript' porque eles casariam com Vue.js, Next.js, ts.json,
    # etc. e gerariam falsos positivos. Quem quer JS/TS escreve por extenso.
    "node":        ["node", "nodejs", "node.js", "node js"],
    "javascript":  ["javascript", "ecmascript"],
    "typescript":  ["typescript"],
    "react":       ["react", "reactjs", "react.js", "react native"],
    "vue":         ["vue", "vuejs", "vue.js"],
    "angular":     ["angular", "angularjs", "angular.js"],
    "next":        ["nextjs", "next.js"],
    "nuxt":        ["nuxtjs", "nuxt.js"],
    "svelte":      ["svelte", "sveltekit"],
    "python":      ["python"],
    "django":      ["django"],
    "flask":       ["flask"],
    "fastapi":     ["fastapi", "fast api"],
    "ruby":        ["ruby"],
    "rails":       ["rails", "ruby on rails"],
    "go":          ["go", "golang"],
    "rust":        ["rust"],
    "java":        ["java"],
    "kotlin":      ["kotlin"],
    "swift":       ["swift"],
    "csharp":      ["c#", "csharp", "c-sharp", ".net", "dotnet"],
    "cpp":         ["c++", "cpp", "c plus plus"],
    "php":         ["php"],
    "laravel":     ["laravel"],
    "symfony":     ["symfony"],
    "scala":       ["scala"],
    "elixir":      ["elixir"],
    "erlang":      ["erlang"],
    "haskell":     ["haskell"],
    "perl":        ["perl"],
    "r":           ["r language", "r lang"],  # 'r' isolado é ambíguo demais
    # Bancos / infra
    "sql":         ["sql"],
    "postgres":    ["postgres", "postgresql", "psql"],
    "mysql":       ["mysql"],
    "mongodb":     ["mongodb", "mongo"],
    "redis":       ["redis"],
    "kafka":       ["kafka"],
    "kubernetes":  ["kubernetes", "k8s"],
    "docker":      ["docker"],
    "aws":         ["aws", "amazon web services"],
    "azure":       ["azure"],
    "gcp":         ["gcp", "google cloud"],
    "terraform":   ["terraform"],
    # Áreas
    "frontend":    ["frontend", "front-end", "front end"],
    "backend":     ["backend", "back-end", "back end"],
    "fullstack":   ["fullstack", "full-stack", "full stack"],
    "devops":      ["devops", "dev ops"],
    "qa":          ["qa", "quality assurance", "qualidade"],
    "data":        ["data", "data engineer", "data scientist", "dados"],
    "ml":          ["machine learning", "ml", "ai", "artificial intelligence"],
    "mobile":      ["mobile", "android", "ios"],
}


def _build_variant_index() -> dict[str, list[str]]:
    """Pra cada variante, quais são suas variantes equivalentes."""
    index: dict[str, list[str]] = {}
    for canonical, variants in TECH_ALIASES.items():
        all_forms = list(set(variants + [canonical]))
        for v in all_forms:
            index.setdefault(v.lower(), []).extend(all_forms)
    # remove duplicatas mantendo ordem estável
    for k, vs in index.items():
        seen = set()
        uniq = []
        for v in vs:
            vl = v.lower()
            if vl not in seen:
                seen.add(vl)
                uniq.append(vl)
        index[k] = uniq
    return index


VARIANT_INDEX = _build_variant_index()


def _expand_keyword(keyword: str) -> list[str]:
    """Recebe 'NodeJS' e devolve ['nodejs', 'node.js', 'node js', 'node']."""
    k = keyword.strip().lower()
    if not k:
        return []
    if k in VARIANT_INDEX:
        return VARIANT_INDEX[k]
    return [k]


# ----------------------- Word-boundary match ----------------------- #

# Caracteres aceitos como "fronteira" (espaço, pontuação, início/fim).
# Importante NÃO usar \b padrão porque ele não funciona com símbolos como
# '#' (c#), '++' (c++), '.' (node.js).
_WORD_CHAR = re.compile(r"\w")


def _contains_term(haystack: str, term: str) -> bool:
    """Faz match com fronteira de palavra customizada (lida com c#, c++, node.js).

    A comparação é case-insensitive E accent-insensitive: 'senior' bate em
    'Sênior', 'Sênior' bate em 'senior', etc.
    """
    if not term:
        return False
    hay_norm = _strip_accents(haystack)
    term_norm = _strip_accents(term)
    if term_norm in {"c#", "c++"}:
        pattern = re.compile(
            r"(?:^|[^\w])" + re.escape(term_norm) + r"(?:$|[^\w])",
            re.IGNORECASE,
        )
        return bool(pattern.search(hay_norm))
    # Caso geral: bordas com não-palavra. Funciona pra "node.js" porque
    # nas bordas (antes do 'n' e depois do 's') esperamos não-palavra.
    pattern = re.compile(
        r"(?<!\w)" + re.escape(term_norm) + r"(?!\w)",
        re.IGNORECASE,
    )
    return bool(pattern.search(hay_norm))


def _matches_keyword(haystack: str, keyword: str) -> bool:
    """Procura QUALQUER variante da keyword no haystack."""
    for term in _expand_keyword(keyword):
        if _contains_term(haystack, term):
            return True
    return False


def _haystack_for(job: Job, scope: str) -> str:
    """Constrói o texto onde procurar keywords, conforme escopo escolhido."""
    if scope == "title_only":
        return f"{job.title} {' '.join(job.tags)}"
    if scope == "everywhere":
        return " ".join([job.title, job.company, job.description, " ".join(job.tags)])
    # default "title_or_short" — título + tags + primeiros 250 chars da descrição
    short_desc = (job.description or "")[:250]
    return f"{job.title} {' '.join(job.tags)} {short_desc}"


# ----------------------- Outros filtros ----------------------- #


def _region_tokens(region: str) -> list[str]:
    """Quebra 'Brasília-DF' em ['brasília', 'brasilia', 'df'] pra match flexível.

    Também quebra por espaço: sem isso, 'Distrito Federal' (sem hífen/vírgula)
    virava um único token colado 'distrito federal' que nunca aparece no
    texto de localização das vagas ('Brasília - DF', 'Taguatinga - DF'...),
    zerando o filtro de região silenciosamente.
    """
    # Preposições/artigos comuns em nomes de lugar ('Rio DE Janeiro', 'Mato
    # Grosso DO Sul') não servem como sinal sozinhos — muito curtos e comuns,
    # dariam falso positivo em qualquer texto que contenha "de"/"do"/etc.
    _STOPWORDS = {"de", "do", "da", "dos", "das", "e"}

    raw = region.strip().lower()
    tokens: list[str] = []
    for part in raw.replace("/", "-").replace(",", "-").replace(" ", "-").split("-"):
        p = part.strip()
        if p and p not in _STOPWORDS:
            tokens.append(p)
            normalized = _strip_accents(p)
            if normalized != p:
                tokens.append(normalized)

    # Caso especial: 'Distrito Federal' é o único UF cujo nome oficial nunca
    # aparece no campo de localização das vagas (que mostra "Brasília - DF"
    # ou a RA, ex. "Taguatinga - DF") — sem isso, digitar o nome completo do
    # estado zerava o filtro pra essa região especificamente.
    if "distrito" in tokens and "federal" in tokens:
        tokens.extend(["brasilia", "df"])

    return tokens


_NATIONAL_HINTS = ("todo brasil", "brasil todo", "brasil", "nacional", "anywhere", "worldwide")


def _matches_location(job: Job, f: JobFilter) -> bool:
    mode = f.location_mode
    if mode == LocationMode.ANY:
        return True
    if mode == LocationMode.REMOTE_WORLDWIDE:
        return job.is_remote
    if mode == LocationMode.REMOTE_BRAZIL:
        if not job.is_remote:
            return False
        loc = job.location.lower()
        return ("brasil" in loc or "brazil" in loc or " br" in loc
                or "anywhere" in loc or "worldwide" in loc or "latam" in loc
                or loc == "" or "todo" in loc)
    if mode in (LocationMode.ON_SITE_REGION, LocationMode.HYBRID_REGION):
        if not f.region:
            return True
        # Inclui tags no haystack: fontes que já filtram por proximidade do
        # lado do servidor (ex.: Indeed com busca por bairro) "carimbam" a
        # região pesquisada como tag mesmo quando o card só mostra a cidade.
        loc = _strip_accents(f"{job.location} {' '.join(job.tags)}".lower())
        for tok in _region_tokens(f.region):
            if len(tok) >= 2 and _strip_accents(tok) in loc:
                return True
        # Modo híbrido aceita também vagas marcadas como nacional/remoto
        # (porque podem ter sede na região e permitir trabalho remoto).
        # Modo presencial (ON_SITE) é estrito: a região tem que aparecer.
        if mode == LocationMode.HYBRID_REGION and job.is_remote and any(
            h in loc or loc == "" for h in _NATIONAL_HINTS
        ):
            return True
        return False
    return True


def _matches_recency(job: Job, days: int | None) -> bool:
    if not days:
        return True
    ref = job.posted_at or job.scraped_at
    if not ref:
        return True
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return ref >= datetime.now(timezone.utc) - timedelta(days=days)


# ----------------------- API pública ----------------------- #


def matches(job: Job, f: JobFilter) -> bool:
    haystack = _haystack_for(job, f.keyword_scope)

    # keywords (ANY ou ALL conforme f.keyword_match)
    if f.keywords:
        if f.keyword_match == "all":
            if not all(_matches_keyword(haystack, kw) for kw in f.keywords):
                return False
        else:  # "any"
            if not any(_matches_keyword(haystack, kw) for kw in f.keywords):
                return False

    # Excludes — sempre buscam em todo o texto pra serem agressivos
    if f.exclude_keywords:
        wide = " ".join([job.title, job.company, job.description, " ".join(job.tags)])
        if any(_matches_keyword(wide, kw) for kw in f.exclude_keywords):
            return False

    if f.job_types and job.job_types and not any(jt in f.job_types for jt in job.job_types):
        return False
    if f.seniorities and job.seniority not in f.seniorities and job.seniority.value != "unknown":
        return False
    if not _matches_location(job, f):
        return False
    if not _matches_recency(job, f.posted_within_days):
        return False
    if f.sources and job.source not in f.sources:
        return False
    return True


def apply_filter(jobs: list[Job], f: JobFilter) -> list[Job]:
    filtered = [j for j in jobs if matches(j, f)]
    if f.sort_by == "recent":
        filtered.sort(key=lambda j: (j.posted_at or j.scraped_at), reverse=True)
    return filtered[: f.limit]
