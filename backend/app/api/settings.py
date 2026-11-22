"""Endpoint de leitura das configurações (mascaradas) e do scheduler."""
from __future__ import annotations

from fastapi import APIRouter

from app.services import scheduler
from app.services.email_service import get_status

router = APIRouter(tags=["settings"])


@router.get("/settings")
async def get_settings_status() -> dict:
    es = get_status()
    return {
        "email": {
            "configured": es.configured,
            "user": es.user,
            "masked_password": es.masked_password,
            "default_recipient": es.default_recipient,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
        },
        "scheduler": {
            "running": scheduler.get_scheduler().running,
            "scheduled_jobs": scheduler.list_scheduled(),
        },
    }
