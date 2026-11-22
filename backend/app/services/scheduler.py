"""Scheduler que executa os filtros salvos periodicamente.

Usa APScheduler em modo async dentro do mesmo loop do FastAPI. Cada filtro
ativo vira um job com cron próprio conforme `alert_frequency`.

A cada mudança em `filters.json` (criar/editar/deletar), chamamos
`reload_jobs()` pra rebuild da agenda. Reload é idempotente.
"""
from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.models.job import AlertFrequency, SavedFilter
from app.services import storage
from app.services.alert_service import run_saved_filter

logger = logging.getLogger("jobfinder.scheduler")

_scheduler: Optional[AsyncIOScheduler] = None


def _trigger_for(freq: AlertFrequency) -> CronTrigger:
    """Mapeia frequência → cron. Horário pensado pra fuso BR (UTC-3).

    APScheduler herda timezone do sistema; configurar pra America/Sao_Paulo
    no startup deixa os horários previsíveis.
    """
    # Diário/semanal: mandamos cedo (8h) pra você ler ao acordar.
    if freq == AlertFrequency.HOURLY:
        return CronTrigger(minute=5)  # toda hora cheia + 5min (evita coincidir com cron de servidor)
    if freq == AlertFrequency.EVERY_4H:
        return CronTrigger(hour="0,4,8,12,16,20", minute=5)
    if freq == AlertFrequency.WEEKLY:
        return CronTrigger(day_of_week="mon", hour=8, minute=5)
    # default: diário às 8:05
    return CronTrigger(hour=8, minute=5)


async def _job_runner(filter_id: str) -> None:
    """Função que o scheduler chama. Recarrega o filtro do storage
    pra pegar a versão mais atual (caso o usuário tenha editado).
    """
    sf = storage.get_filter(filter_id)
    if not sf:
        logger.warning("filtro %s sumiu antes da execução agendada", filter_id)
        return
    if not sf.alert_enabled:
        logger.info("pulando filtro %s (%s) — alerta desativado", filter_id, sf.name)
        return
    try:
        result = await run_saved_filter(sf)
        logger.info(
            "filtro %s (%s) executado: %d vagas, %d novas, emailed=%s",
            filter_id, sf.name, result.total_found, result.new_jobs_for_filter, result.emailed,
        )
    except Exception:  # noqa: BLE001
        logger.exception("erro inesperado executando filtro %s", filter_id)


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    return _scheduler


def start() -> None:
    sch = get_scheduler()
    if not sch.running:
        sch.start()
        logger.info("scheduler iniciado (timezone=America/Sao_Paulo)")
    reload_jobs()


def shutdown() -> None:
    sch = get_scheduler()
    if sch.running:
        sch.shutdown(wait=False)
        logger.info("scheduler encerrado")


def reload_jobs() -> None:
    """Reconstrói a agenda baseado nos filtros salvos atuais."""
    sch = get_scheduler()
    sch.remove_all_jobs()
    filters = storage.load_filters()
    active = [f for f in filters if f.alert_enabled]
    for sf in active:
        sch.add_job(
            _job_runner,
            trigger=_trigger_for(sf.alert_frequency),
            args=[sf.id],
            id=f"filter:{sf.id}",
            name=f"alert:{sf.name}",
            replace_existing=True,
            misfire_grace_time=3600,  # se o servidor estava down, ainda roda dentro de 1h
            coalesce=True,
        )
    logger.info("scheduler reload: %d filtros ativos agendados", len(active))


def list_scheduled() -> list[dict]:
    """Retorna info dos jobs agendados (pra debug/UI)."""
    sch = get_scheduler()
    out: list[dict] = []
    for job in sch.get_jobs():
        out.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        })
    return out
