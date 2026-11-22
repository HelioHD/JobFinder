"""Endpoints CRUD de filtros salvos + ações (run-now, test-email)."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException

from app.models.job import (
    FilterRunResult,
    SavedFilter,
    SavedFilterCreate,
    SavedFilterUpdate,
)
from app.services import scheduler, storage
from app.services.alert_service import run_saved_filter
from app.services.email_service import (
    EmailError,
    render_test_email,
    send_email_async,
)

router = APIRouter(prefix="/filters", tags=["filters"])


def _gen_id() -> str:
    return secrets.token_urlsafe(8)


@router.get("", response_model=list[SavedFilter])
async def list_filters() -> list[SavedFilter]:
    return storage.load_filters()


@router.post("", response_model=SavedFilter)
async def create_filter(payload: SavedFilterCreate) -> SavedFilter:
    sf = SavedFilter(
        id=_gen_id(),
        name=payload.name.strip(),
        filter=payload.filter,
        alert_enabled=payload.alert_enabled,
        alert_frequency=payload.alert_frequency,
        recipient_email=(payload.recipient_email or None),
        only_new=payload.only_new,
    )
    storage.add_filter(sf)
    scheduler.reload_jobs()
    return sf


@router.get("/{filter_id}", response_model=SavedFilter)
async def get_filter(filter_id: str) -> SavedFilter:
    sf = storage.get_filter(filter_id)
    if not sf:
        raise HTTPException(404, "filtro não encontrado")
    return sf


@router.patch("/{filter_id}", response_model=SavedFilter)
async def update_filter(filter_id: str, payload: SavedFilterUpdate) -> SavedFilter:
    def mutator(sf: SavedFilter) -> SavedFilter:
        if payload.name is not None:
            sf.name = payload.name.strip()
        if payload.filter is not None:
            sf.filter = payload.filter
        if payload.alert_enabled is not None:
            sf.alert_enabled = payload.alert_enabled
        if payload.alert_frequency is not None:
            sf.alert_frequency = payload.alert_frequency
        if payload.recipient_email is not None:
            # string vazia = limpar (volta a usar default)
            sf.recipient_email = payload.recipient_email or None
        if payload.only_new is not None:
            sf.only_new = payload.only_new
        return sf

    updated = storage.update_filter(filter_id, mutator)
    if not updated:
        raise HTTPException(404, "filtro não encontrado")
    scheduler.reload_jobs()
    return updated


@router.delete("/{filter_id}")
async def delete_filter(filter_id: str) -> dict:
    ok = storage.delete_filter(filter_id)
    if not ok:
        raise HTTPException(404, "filtro não encontrado")
    storage.remove_sent_for(filter_id)
    scheduler.reload_jobs()
    return {"deleted": filter_id}


@router.post("/{filter_id}/run-now", response_model=FilterRunResult)
async def run_now(filter_id: str) -> FilterRunResult:
    """Executa o filtro AGORA (ignora schedule). Útil pra testar."""
    sf = storage.get_filter(filter_id)
    if not sf:
        raise HTTPException(404, "filtro não encontrado")
    return await run_saved_filter(sf)


@router.post("/{filter_id}/reset-sent")
async def reset_sent(filter_id: str) -> dict:
    """Limpa o histórico de envios desse filtro — próximo run vai considerar tudo como novo."""
    sf = storage.get_filter(filter_id)
    if not sf:
        raise HTTPException(404, "filtro não encontrado")
    storage.remove_sent_for(filter_id)
    return {"reset": filter_id}


@router.post("/test-email")
async def test_email(payload: dict = Body(default_factory=dict)) -> dict:
    """Manda um e-mail de teste pra validar credenciais SMTP.

    Body opcional: {"to": "outro@email.com"}. Se omitido, usa DEFAULT_RECIPIENT.
    """
    from app.config import get_settings  # import tardio pra pegar reload de .env
    s = get_settings()
    to = (payload.get("to") or s.default_recipient or s.gmail_user or "").strip()
    if not to:
        raise HTTPException(400, "Sem destinatário (forneça 'to' no body ou configure DEFAULT_RECIPIENT)")

    subject, body = render_test_email()
    try:
        await send_email_async(to, subject, body)
    except EmailError as e:
        raise HTTPException(502, f"Falha ao enviar: {e}") from e
    return {
        "sent": True,
        "to": to,
        "at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/_/scheduled")
async def list_scheduled() -> list[dict]:
    """Lista jobs agendados no scheduler (debug)."""
    return scheduler.list_scheduled()
