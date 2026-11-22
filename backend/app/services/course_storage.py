"""Persistência em JSON pro domínio LearnFinder — espelha `storage.py`.

Reaproveita os helpers de baixo nível de `storage.py` (_read_json/_write_json/
_lock_for/_mem_lock), que já são genéricos (não dependem do modelo Job).
"""
from __future__ import annotations

from typing import Iterable

from app.models.course import Course
from app.services.storage import DATA_DIR, _lock_for, _mem_lock, _read_json, _write_json

COURSES_FILE = DATA_DIR / "courses.json"


def load_courses() -> list[Course]:
    raw = _read_json(COURSES_FILE, [])
    out: list[Course] = []
    for item in raw:
        try:
            out.append(Course.model_validate(item))
        except Exception:  # noqa: BLE001 — item corrompido não derruba tudo
            continue
    return out


def save_courses(courses: Iterable[Course]) -> None:
    payload = [c.model_dump(mode="json") for c in courses]
    with _mem_lock, _lock_for(COURSES_FILE):
        _write_json(COURSES_FILE, payload)


def upsert_courses(new_courses: Iterable[Course]) -> tuple[list[Course], int]:
    """Adiciona itens novos (dedup por id). Retorna (lista_completa, qtd_novas)."""
    with _mem_lock, _lock_for(COURSES_FILE):
        existing = load_courses()
        index = {c.id: c for c in existing}
        added = 0
        for course in new_courses:
            if course.id not in index:
                index[course.id] = course
                added += 1
        merged = sorted(index.values(), key=lambda c: c.scraped_at, reverse=True)
        _write_json(COURSES_FILE, [c.model_dump(mode="json") for c in merged])
        return merged, added
