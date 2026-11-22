"""Persistência em JSON com lock multi-processo.

Modelo simples: cada "tabela" (jobs, filters, sent, config) vira um arquivo
JSON em DATA_DIR. Operações de escrita usam filelock para evitar corrida
quando o scheduler e a API mexem ao mesmo tempo.

Vagas são deduplicadas pelo campo `id` (hash de source+url).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Iterable, Optional

from filelock import FileLock

from app.config import get_settings
from app.models.job import Job, SavedFilter

_settings = get_settings()
DATA_DIR: Path = _settings.data_dir
JOBS_FILE = DATA_DIR / "jobs.json"
FILTERS_FILE = DATA_DIR / "filters.json"
SENT_FILE = DATA_DIR / "sent.json"
CONFIG_FILE = DATA_DIR / "config.json"

# Lock em memória além do filelock (eficiente para acessos do mesmo processo).
_mem_lock = RLock()


def _lock_for(path: Path) -> FileLock:
    return FileLock(str(path) + ".lock", timeout=10)


def _read_json(path: Path, default):  # noqa: ANN001
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data) -> None:  # noqa: ANN001
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    tmp.replace(path)


# ----------------------- Jobs ----------------------- #


def load_jobs() -> list[Job]:
    raw = _read_json(JOBS_FILE, [])
    out: list[Job] = []
    for item in raw:
        try:
            out.append(Job.model_validate(item))
        except Exception:  # noqa: BLE001 — vaga corrompida não deve derrubar tudo
            continue
    return out


def save_jobs(jobs: Iterable[Job]) -> None:
    payload = [j.model_dump(mode="json") for j in jobs]
    with _mem_lock, _lock_for(JOBS_FILE):
        _write_json(JOBS_FILE, payload)


def upsert_jobs(new_jobs: Iterable[Job]) -> tuple[list[Job], int]:
    """Adiciona vagas novas (dedup por id). Retorna (lista_completa, qtd_novas)."""
    with _mem_lock, _lock_for(JOBS_FILE):
        existing = load_jobs()
        index = {j.id: j for j in existing}
        added = 0
        for job in new_jobs:
            if job.id not in index:
                index[job.id] = job
                added += 1
        merged = sorted(
            index.values(),
            key=lambda j: (j.posted_at or j.scraped_at),
            reverse=True,
        )
        _write_json(JOBS_FILE, [j.model_dump(mode="json") for j in merged])
        return merged, added


# ----------------------- Saved Filters ----------------------- #


def load_filters() -> list[SavedFilter]:
    raw = _read_json(FILTERS_FILE, [])
    out: list[SavedFilter] = []
    for item in raw:
        try:
            out.append(SavedFilter.model_validate(item))
        except Exception:  # noqa: BLE001 — filtro corrompido não derruba o app
            continue
    return out


def save_filters(filters: Iterable[SavedFilter]) -> None:
    with _mem_lock, _lock_for(FILTERS_FILE):
        _write_json(FILTERS_FILE, [f.model_dump(mode="json") for f in filters])


def get_filter(filter_id: str) -> Optional[SavedFilter]:
    return next((f for f in load_filters() if f.id == filter_id), None)


def add_filter(sf: SavedFilter) -> SavedFilter:
    with _mem_lock, _lock_for(FILTERS_FILE):
        items = load_filters()
        items.append(sf)
        _write_json(FILTERS_FILE, [f.model_dump(mode="json") for f in items])
    return sf


def update_filter(filter_id: str, mutator) -> Optional[SavedFilter]:  # noqa: ANN001
    """Aplica `mutator(SavedFilter) -> SavedFilter` atomicamente."""
    with _mem_lock, _lock_for(FILTERS_FILE):
        items = load_filters()
        for idx, sf in enumerate(items):
            if sf.id == filter_id:
                updated = mutator(sf)
                updated.updated_at = datetime.now(timezone.utc)
                items[idx] = updated
                _write_json(FILTERS_FILE, [f.model_dump(mode="json") for f in items])
                return updated
    return None


def delete_filter(filter_id: str) -> bool:
    with _mem_lock, _lock_for(FILTERS_FILE):
        items = load_filters()
        new_items = [f for f in items if f.id != filter_id]
        if len(new_items) == len(items):
            return False
        _write_json(FILTERS_FILE, [f.model_dump(mode="json") for f in new_items])
        return True


# ----------------------- Sent (histórico de e-mail por filtro) ----------------------- #
#
# Formato: {filter_id: [job_id, ...]}. Salvar por filtro é importante: se eu
# tenho 2 alertas com critérios parecidos, o segundo precisa receber vagas
# mesmo que o primeiro já tenha enviado.


def _load_sent_map() -> dict[str, list[str]]:
    raw = _read_json(SENT_FILE, {})
    if isinstance(raw, dict):
        return {k: list(v) for k, v in raw.items() if isinstance(v, list)}
    # Compat com formato antigo (lista global) — migra silenciosamente.
    if isinstance(raw, list):
        return {"_legacy": list(raw)}
    return {}


def get_sent_for(filter_id: str) -> set[str]:
    return set(_load_sent_map().get(filter_id, []))


def mark_sent_for(filter_id: str, job_ids: Iterable[str]) -> None:
    if not filter_id:
        return
    job_ids_list = list(job_ids)
    if not job_ids_list:
        return
    with _mem_lock, _lock_for(SENT_FILE):
        sent = _load_sent_map()
        existing = set(sent.get(filter_id, []))
        existing.update(job_ids_list)
        sent[filter_id] = sorted(existing)
        _write_json(SENT_FILE, sent)


def remove_sent_for(filter_id: str) -> None:
    """Limpa o histórico de envios de um filtro (usado quando se deleta)."""
    with _mem_lock, _lock_for(SENT_FILE):
        sent = _load_sent_map()
        if filter_id in sent:
            del sent[filter_id]
            _write_json(SENT_FILE, sent)


# ----------------------- Config geral ----------------------- #


def load_config() -> dict:
    return _read_json(CONFIG_FILE, {})


def save_config(cfg: dict) -> None:
    with _mem_lock, _lock_for(CONFIG_FILE):
        _write_json(CONFIG_FILE, cfg)
