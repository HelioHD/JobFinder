"""Aplica um CourseFilter sobre uma lista de Course (filtragem em memória).

Reaproveita os helpers de texto de `matcher.py` (domínio-agnósticos: recebem
haystack/keyword, não Job) em vez de duplicar a lógica de word-boundary,
accent-insensitive match, etc.
"""
from __future__ import annotations

from app.models.course import Course, CourseFilter
from app.services.matcher import _matches_keyword, _strip_accents

# Aliases específicos do tema segurança/red-team — os TECH_ALIASES do job.py
# são sobre linguagens/frameworks e não fazem sentido aqui.
SECURITY_ALIASES: dict[str, list[str]] = {
    "pentest": ["pentest", "penetration testing", "teste de invasao", "teste de intrusao"],
    "red team": ["red team", "redteam", "red-team"],
    "blue team": ["blue team", "blueteam", "blue-team"],
    "ceh": ["ceh", "ethical hacking", "hacker etico", "hacking etico"],
    "oscp": ["oscp"],
    "seguranca": ["seguranca da informacao", "cibersegurança", "ciberseguranca", "seguranca"],
    "soc": ["soc", "security operations center"],
}


def _expand_keyword(keyword: str) -> list[str]:
    k = _strip_accents(keyword.strip().lower())
    for canonical, variants in SECURITY_ALIASES.items():
        norm_variants = [_strip_accents(v) for v in variants]
        if k == _strip_accents(canonical) or k in norm_variants:
            return norm_variants
    return [k]


def _haystack_for(course: Course, scope: str) -> str:
    if scope == "title_only":
        return f"{course.title} {' '.join(course.theme_tags)}"
    if scope == "everywhere":
        return " ".join(
            [course.title, course.provider, course.description, " ".join(course.theme_tags)]
        )
    short_desc = (course.description or "")[:250]
    return f"{course.title} {' '.join(course.theme_tags)} {short_desc}"


def _matches_any_variant(haystack: str, keyword: str) -> bool:
    for term in _expand_keyword(keyword):
        if _matches_keyword(haystack, term):
            return True
    return False


def matches(course: Course, f: CourseFilter) -> bool:
    haystack = _haystack_for(course, f.keyword_scope)

    if f.keywords:
        if f.keyword_match == "all":
            if not all(_matches_any_variant(haystack, kw) for kw in f.keywords):
                return False
        else:
            if not any(_matches_any_variant(haystack, kw) for kw in f.keywords):
                return False

    if f.course_types and course.course_type not in f.course_types:
        return False
    # price/has_certificate == None (desconhecido, ex.: busca web sem dado
    # estruturado) não é excluído por um filtro que não dá pra confirmar nem
    # negar — só exclui quando o valor é conhecido e não bate.
    if f.max_price is not None and course.price is not None and course.price > f.max_price:
        return False
    if f.require_certificate and course.has_certificate is False:
        return False
    if f.sources and course.source not in f.sources:
        return False
    return True


def apply_filter(courses: list[Course], f: CourseFilter) -> list[Course]:
    filtered = [c for c in courses if matches(c, f)]
    if f.sort_by == "price_asc":
        filtered.sort(key=lambda c: c.price if c.price is not None else float("inf"))
    elif f.sort_by == "price_desc":
        filtered.sort(key=lambda c: c.price if c.price is not None else -1.0, reverse=True)
    elif f.sort_by == "rating_desc":
        filtered.sort(key=lambda c: (c.rating is not None, c.rating or 0), reverse=True)
    return filtered[: f.limit]
