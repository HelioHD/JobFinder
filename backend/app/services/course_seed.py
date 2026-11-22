"""Carrega o dataset curado (certificações, pós, faculdade) pro storage.

Certificações e pós-graduação BR não têm catálogo raspável (são páginas de
marketing, não listagens filtráveis por tema/preço) — por isso viram um
dataset estático mantido à mão em `backend/data/curated_*.json`. `id` é
hash estável de (source, url), então rodar isso de novo no próximo boot é
idempotente (upsert, não duplica).
"""
from __future__ import annotations

import json
import logging

from app.config import BACKEND_DIR
from app.models.course import Course
from app.services.course_storage import upsert_courses

logger = logging.getLogger(__name__)

CURATED_FILES = [
    BACKEND_DIR / "data" / "curated_certifications.json",
    BACKEND_DIR / "data" / "curated_postgrad.json",
]


def ensure_seed_data() -> None:
    courses: list[Course] = []
    for path in CURATED_FILES:
        if not path.exists():
            logger.warning("Seed curado não encontrado: %s", path)
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Falha ao ler seed curado %s: %s", path, exc)
            continue
        for item in raw:
            try:
                courses.append(Course.model_validate(item))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Item curado inválido em %s: %s", path, exc)
    if courses:
        upsert_courses(courses)
