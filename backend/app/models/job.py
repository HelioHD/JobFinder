"""Modelos de dados do JobFinder.

Define a "linguagem" dos filtros: tipos de vaga, modos de localização,
senioridade, etc. Esses enums são usados tanto pelos scrapers (para
normalizar dados) quanto pelos filtros do usuário.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class JobType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    FREELANCE = "freelance"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"


class LocationMode(str, Enum):
    """Como tratar localização em uma busca."""

    ON_SITE_REGION = "on_site_region"        # Presencial em região específica (ex.: Brasília-DF)
    HYBRID_REGION = "hybrid_region"          # Híbrido em região
    REMOTE_BRAZIL = "remote_brazil"          # Remoto, mas exigindo Brasil
    REMOTE_WORLDWIDE = "remote_worldwide"    # Remoto de qualquer lugar
    ANY = "any"                              # Qualquer (não filtrar)


class Seniority(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    UNKNOWN = "unknown"


class JobSource(str, Enum):
    """Identificadores das fontes de scraping. Adicionar aqui ao criar novo scraper."""

    ARBEITNOW = "arbeitnow"
    INFOJOBS = "infojobs"
    REMOTIVE = "remotive"
    LINKEDIN = "linkedin"
    GOOGLE_JOBS = "google_jobs"
    VAGAS_COM = "vagas_com"
    TRAMPOS = "trampos"
    WWR = "weworkremotely"
    GITHUB_HN = "github_hn"
    INDEED = "indeed"


class Job(BaseModel):
    """Vaga normalizada — formato comum independente da fonte."""

    id: str = Field(..., description="Hash estável (source + url) para dedup.")
    source: JobSource
    title: str
    company: str
    location: str = ""
    is_remote: bool = False
    job_types: list[JobType] = Field(default_factory=list)
    seniority: Seniority = Seniority.UNKNOWN
    description: str = ""
    description_html: str = ""
    url: HttpUrl
    tags: list[str] = Field(default_factory=list)
    salary_text: Optional[str] = None
    posted_at: Optional[datetime] = None
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("title", "company", "location", "description", "description_html", mode="before")
    @classmethod
    def _strip_strings(cls, v):  # noqa: ANN001
        return v.strip() if isinstance(v, str) else v

    @staticmethod
    def make_id(source: JobSource | str, url: str) -> str:
        src = source.value if isinstance(source, JobSource) else str(source)
        raw = f"{src}::{url.strip().lower()}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# ----------------------- Filtros (busca do usuário) ----------------------- #


class JobFilter(BaseModel):
    """Filtro de busca — esse é o "controle" que o usuário monta na UI.

    Pensado pra ser flexível: o usuário pode salvar isso com um nome e
    o scheduler depois roda novamente periodicamente.
    """

    keywords: list[str] = Field(
        default_factory=list,
        description="Palavras-chave (ex.: ['python', 'django']).",
    )
    keyword_match: Literal["any", "all"] = Field(
        default="any",
        description="'any' = qualquer keyword basta; 'all' = todas precisam casar.",
    )
    keyword_scope: Literal["title_only", "title_or_short", "everywhere"] = Field(
        default="title_or_short",
        description=(
            "Onde procurar a keyword. 'title_only' = só título+tags; "
            "'title_or_short' = título+tags+início da descrição (default); "
            "'everywhere' = qualquer lugar do anúncio."
        ),
    )
    exclude_keywords: list[str] = Field(
        default_factory=list,
        description="Palavras a excluir do título/descrição. Ex.: ['senior', 'php'].",
    )
    job_types: list[JobType] = Field(
        default_factory=list,
        description="Tipos aceitos. Vazio = qualquer.",
    )
    location_mode: LocationMode = LocationMode.ANY
    region: Optional[str] = Field(
        default=None,
        description="Usado quando location_mode é ON_SITE_REGION/HYBRID_REGION. Ex.: 'Brasília-DF'.",
    )
    seniorities: list[Seniority] = Field(default_factory=list)
    min_salary: Optional[float] = None
    posted_within_days: Optional[int] = Field(
        default=None,
        description="Limita a vagas postadas nos últimos N dias.",
    )
    sources: list[JobSource] = Field(
        default_factory=list,
        description="Fontes a usar. Vazio = todas habilitadas.",
    )
    sort_by: Literal["recent", "relevance"] = "recent"
    limit: int = Field(default=50, ge=1, le=500)

    @field_validator("keywords", "exclude_keywords", mode="before")
    @classmethod
    def _split_strings(cls, v):  # noqa: ANN001
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return v


class AlertFrequency(str, Enum):
    """Periodicidade dos alertas. Mapeado pra cron no scheduler."""

    HOURLY = "hourly"          # toda hora cheia
    EVERY_4H = "every_4h"      # de 4 em 4 horas
    DAILY = "daily"             # 1x/dia (default — manhã)
    WEEKLY = "weekly"           # 1x/semana (segunda de manhã)


class SavedFilter(BaseModel):
    """Filtro salvo pelo usuário com configuração de alerta automático."""

    id: str = Field(..., description="UUID curto.")
    name: str = Field(..., min_length=1, max_length=80)
    filter: JobFilter
    alert_enabled: bool = Field(
        default=True,
        description="Se True o scheduler executa esse filtro periodicamente.",
    )
    alert_frequency: AlertFrequency = AlertFrequency.DAILY
    recipient_email: Optional[str] = Field(
        default=None,
        description="E-mail destinatário. Se vazio, usa DEFAULT_RECIPIENT do .env.",
    )
    only_new: bool = Field(
        default=True,
        description="Se True, só envia e-mail quando há vagas que ainda não foram enviadas pra esse filtro.",
    )
    last_run_at: Optional[datetime] = None
    last_email_at: Optional[datetime] = None
    last_run_status: Optional[str] = Field(
        default=None,
        description="Mensagem da última execução: 'ok: 5 vagas / 3 novas', 'sem novas', 'erro: ...'",
    )
    total_emails_sent: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SavedFilterCreate(BaseModel):
    """Payload da criação de um filtro salvo."""

    name: str = Field(..., min_length=1, max_length=80)
    filter: JobFilter
    alert_enabled: bool = True
    alert_frequency: AlertFrequency = AlertFrequency.DAILY
    recipient_email: Optional[str] = None
    only_new: bool = True


class SavedFilterUpdate(BaseModel):
    """Payload de atualização parcial."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    filter: Optional[JobFilter] = None
    alert_enabled: Optional[bool] = None
    alert_frequency: Optional[AlertFrequency] = None
    recipient_email: Optional[str] = None
    only_new: Optional[bool] = None


class FilterRunResult(BaseModel):
    """Resultado de uma execução manual ou agendada de um filtro salvo."""

    filter_id: str
    filter_name: str
    total_found: int
    new_jobs_for_filter: int  # vagas que ainda não foram enviadas pra esse filtro
    emailed: bool
    email_recipient: Optional[str] = None
    errors: list[str] = Field(default_factory=list)
    ran_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ----------------------- Respostas da API ----------------------- #


class ScrapeResult(BaseModel):
    total_found: int
    new_jobs: int
    sources_used: list[JobSource]
    jobs: list[Job]
    errors: list[str] = Field(default_factory=list)


class SourceInfo(BaseModel):
    id: JobSource
    name: str
    description: str
    enabled: bool = True
