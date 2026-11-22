"""Modelos de dados do LearnFinder (certificações, cursos, pós, faculdade).

Domínio paralelo ao de vagas (`job.py`) — mesma "forma" (make_id, filtro com
keywords/sources/limit, ScrapeResult-like), mas sem localização/senioridade;
no lugar entram tipo de formação e preço/certificado.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class CourseType(str, Enum):
    CERTIFICATION = "certification"
    COURSE = "course"
    POSTGRAD = "postgrad"
    COLLEGE = "college"


class CourseSource(str, Enum):
    """Identificadores das fontes. CURATED = dataset estático mantido no repo
    (certificações/pós não têm catálogo raspável — ver backend/data/curated_*.json).
    WEB_SEARCH = busca orgânica no Google (não o widget de jobs/vagas, que é
    outra coisa) — cobre instituições/cursos que não estão em nenhum catálogo
    fechado, ao custo de não ter preço/certificado estruturado."""

    UDEMY = "udemy"
    CURATED = "curated"
    WEB_SEARCH = "web_search"


class Course(BaseModel):
    """Item normalizado — certificação, curso, pós ou faculdade."""

    id: str = Field(..., description="Hash estável (source + url) para dedup.")
    source: CourseSource
    course_type: CourseType
    provider: str
    title: str
    description: str = ""
    url: HttpUrl
    theme_tags: list[str] = Field(default_factory=list)
    price: Optional[float] = Field(
        default=None,
        description="None = preço desconhecido (ex.: busca web, sem dado estruturado).",
    )
    currency: str = "BRL"
    has_certificate: Optional[bool] = Field(
        default=None,
        description="None = desconhecido. False só quando confirmado que não emite.",
    )
    duration_text: Optional[str] = Field(
        default=None, description="Texto livre: '21.5 horas', '~18 meses', etc."
    )
    rating: Optional[float] = Field(default=None, description="0-5, quando a fonte expõe.")
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("title", "provider", "description", mode="before")
    @classmethod
    def _strip_strings(cls, v):  # noqa: ANN001
        return v.strip() if isinstance(v, str) else v

    @staticmethod
    def make_id(source: CourseSource | str, url: str) -> str:
        src = source.value if isinstance(source, CourseSource) else str(source)
        raw = f"{src}::{url.strip().lower()}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


class CourseFilter(BaseModel):
    """Filtro de busca do LearnFinder — tema livre + tipo + teto de preço."""

    keywords: list[str] = Field(
        default_factory=list,
        description="Tema de busca (ex.: ['red team', 'pentest']).",
    )
    keyword_match: Literal["any", "all"] = "any"
    keyword_scope: Literal["title_only", "title_or_short", "everywhere"] = "title_or_short"
    course_types: list[CourseType] = Field(
        default_factory=list, description="Tipos aceitos. Vazio = qualquer."
    )
    max_price: Optional[float] = Field(
        default=0.0,
        description="Teto de preço. None = sem teto; 0 = só gratuito.",
    )
    require_certificate: bool = Field(
        default=True, description="Só inclui itens que emitem certificado."
    )
    sources: list[CourseSource] = Field(default_factory=list)
    sort_by: Literal["relevance", "price_asc", "price_desc", "rating_desc"] = "relevance"
    limit: int = Field(default=50, ge=1, le=500)

    @field_validator("keywords", mode="before")
    @classmethod
    def _split_strings(cls, v):  # noqa: ANN001
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return v


class CourseScrapeResult(BaseModel):
    total_found: int
    new_courses: int
    sources_used: list[CourseSource]
    courses: list[Course]
    errors: list[str] = Field(default_factory=list)


class CourseSourceInfo(BaseModel):
    id: CourseSource
    name: str
    description: str
    enabled: bool = True
