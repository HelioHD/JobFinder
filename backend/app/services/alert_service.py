"""Executa um filtro salvo: faz scrape, separa vagas que ainda não foram
enviadas pra esse filtro, manda e-mail e atualiza estado.

Usado tanto pelo endpoint manual `/filters/{id}/run-now` quanto pelo
scheduler periódico.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.config import get_settings
from app.models.job import FilterRunResult, SavedFilter
from app.services import storage
from app.services.email_service import EmailError, render_jobs_email, send_email_async
from app.services.scrape_service import run_scrape


async def run_saved_filter(saved: SavedFilter) -> FilterRunResult:
    """Roda um filtro salvo e (se houver vagas novas) manda e-mail.

    Retorna sempre um `FilterRunResult` (mesmo em caso de erro de e-mail —
    o erro vai em `errors` e a função NÃO levanta).
    """
    settings = get_settings()
    errors: list[str] = []
    emailed = False
    recipient: str | None = None

    # 1. Faz a busca usando o JobFilter armazenado (não persiste pra não
    #    inflar jobs.json com vagas duplicadas — o scrape do usuário já faz isso).
    scrape = await run_scrape(saved.filter, persist=True)
    errors.extend(scrape.errors)

    # 2. Separa vagas que ainda não foram enviadas PRA ESSE FILTRO.
    sent_ids = storage.get_sent_for(saved.id)
    if saved.only_new:
        new_jobs = [j for j in scrape.jobs if j.id not in sent_ids]
    else:
        new_jobs = list(scrape.jobs)

    # 3. Decide se manda e-mail.
    should_email = bool(new_jobs) and saved.alert_enabled
    if should_email:
        recipient = (saved.recipient_email or settings.default_recipient or "").strip()
        if not recipient:
            errors.append("Sem destinatário (configure recipient_email no filtro ou DEFAULT_RECIPIENT no .env)")
        else:
            try:
                subject, body = render_jobs_email(saved, new_jobs)
                await send_email_async(recipient, subject, body)
                emailed = True
                # Marca essas vagas como enviadas pra esse filtro
                storage.mark_sent_for(saved.id, [j.id for j in new_jobs])
            except EmailError as e:
                errors.append(f"Falha ao enviar e-mail: {e}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"Erro inesperado ao enviar e-mail: {e}")

    # 4. Atualiza last_run_* no filtro
    now = datetime.now(timezone.utc)

    def _update(sf: SavedFilter) -> SavedFilter:
        sf.last_run_at = now
        if emailed:
            sf.last_email_at = now
            sf.total_emails_sent += 1
            sf.last_run_status = f"ok: {scrape.total_found} vagas / {len(new_jobs)} novas → e-mail enviado"
        elif new_jobs:
            sf.last_run_status = (
                f"ok: {scrape.total_found} vagas / {len(new_jobs)} novas (e-mail não enviado: {errors[-1] if errors else 'alerta desativado'})"
            )
        elif scrape.total_found:
            sf.last_run_status = f"sem novas: {scrape.total_found} vagas (todas já enviadas)"
        elif errors:
            sf.last_run_status = f"erro: {errors[0]}"
        else:
            sf.last_run_status = "sem vagas"
        return sf

    storage.update_filter(saved.id, _update)

    return FilterRunResult(
        filter_id=saved.id,
        filter_name=saved.name,
        total_found=scrape.total_found,
        new_jobs_for_filter=len(new_jobs),
        emailed=emailed,
        email_recipient=recipient if emailed else None,
        errors=errors,
        ran_at=now,
    )
