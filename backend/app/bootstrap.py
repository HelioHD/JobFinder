"""Inicializa estado global (registry de scrapers) de forma idempotente.

Pode ser chamado tanto pelo `main.py` (quando a API sobe) quanto por
scripts/CLI/scheduler que precisam do registry populado.
"""
from __future__ import annotations

from app.scrapers.arbeitnow import ArbeitnowScraper
from app.scrapers.base import registry
from app.scrapers.google_jobs import GoogleJobsScraper
from app.scrapers.indeed import IndeedScraper
from app.scrapers.infojobs import InfoJobsScraper
from app.scrapers.linkedin import LinkedInScraper
from app.scrapers.remotive import RemotiveScraper
from app.scrapers.trampos import TramposScraper
from app.scrapers.vagas_com import VagasComScraper
from app.scrapers.weworkremotely import WeWorkRemotelyScraper
from app.scrapers.course_base import course_registry
from app.scrapers.curated_courses import CuratedCourseScraper
from app.scrapers.udemy_courses import UdemyCourseScraper
from app.scrapers.web_search_courses import WebSearchCourseScraper
from app.services.course_seed import ensure_seed_data

_initialized = False


def init() -> None:
    global _initialized
    if _initialized:
        return
    # Fontes BR (HTML / JSON server-side, sem JS)
    registry.register(VagasComScraper())
    registry.register(InfoJobsScraper())
    registry.register(TramposScraper())
    registry.register(IndeedScraper())
    # Fontes remotas internacionais (APIs / RSS)
    registry.register(RemotiveScraper())
    registry.register(WeWorkRemotelyScraper())
    registry.register(ArbeitnowScraper())
    # Fontes "experimentais" (sujeitas a anti-bot / podem quebrar)
    registry.register(LinkedInScraper())
    registry.register(GoogleJobsScraper())

    # LearnFinder (certificações/cursos/pós/faculdade)
    course_registry.register(UdemyCourseScraper())
    course_registry.register(WebSearchCourseScraper())
    course_registry.register(CuratedCourseScraper())
    ensure_seed_data()

    _initialized = True
