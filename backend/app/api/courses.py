"""Endpoints do LearnFinder (certificações, cursos, pós, faculdade)."""
from __future__ import annotations

from fastapi import APIRouter

from app.models.course import CourseFilter, CourseScrapeResult, CourseSourceInfo
from app.scrapers.course_base import course_registry
from app.services import course_storage
from app.services.course_matcher import apply_filter
from app.services.course_scrape_service import run_course_scrape

router = APIRouter()


@router.get("/course-sources", response_model=list[CourseSourceInfo])
async def list_course_sources() -> list[CourseSourceInfo]:
    """Lista as fontes (scrapers + curadas) disponíveis."""
    return course_registry.info_list()


@router.post("/courses/scrape", response_model=CourseScrapeResult)
async def scrape_courses(filter_: CourseFilter) -> CourseScrapeResult:
    """Roda uma busca ao vivo (Udemy) com o filtro fornecido e persiste."""
    return await run_course_scrape(filter_)


@router.post("/courses/search", response_model=CourseScrapeResult)
async def search_existing_courses(filter_: CourseFilter) -> CourseScrapeResult:
    """Aplica um filtro sobre itens já armazenados (curados + raspados antes),
    sem fazer scraping ao vivo."""
    courses = course_storage.load_courses()
    filtered = apply_filter(courses, filter_)
    return CourseScrapeResult(
        total_found=len(filtered),
        new_courses=0,
        sources_used=[],
        courses=filtered,
    )


@router.get("/courses")
async def list_courses(limit: int = 50, offset: int = 0):
    """Lista itens persistidos (mais recentes primeiro)."""
    courses = course_storage.load_courses()
    courses.sort(key=lambda c: c.scraped_at, reverse=True)
    total = len(courses)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [c.model_dump(mode="json") for c in courses[offset : offset + limit]],
    }
