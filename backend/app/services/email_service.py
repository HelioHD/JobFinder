"""Envio de e-mail via SMTP do Gmail.

Tudo síncrono porque smtplib é síncrono. Pra rodar dentro do FastAPI/scheduler
sem bloquear, exportamos `send_email_async` que usa `asyncio.to_thread`.

Template HTML é gerado por f-string com escape HTML. Mantive simples
intencionalmente — sem Jinja — pra não adicionar mais uma dependência.
"""
from __future__ import annotations

import asyncio
import html
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from typing import Optional

from app.config import get_settings
from app.models.job import Job, SavedFilter


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587  # STARTTLS


# ----------------------- Erros / status ----------------------- #


class EmailError(Exception):
    """Falha conhecida do envio (credenciais inválidas, sem destinatário, etc.)."""


@dataclass
class EmailStatus:
    configured: bool
    user: str
    masked_password: str
    default_recipient: str


def get_status() -> EmailStatus:
    s = get_settings()
    pwd = s.gmail_app_password
    if pwd:
        masked = pwd[:2] + "•" * max(0, len(pwd) - 4) + pwd[-2:] if len(pwd) >= 4 else "•" * len(pwd)
    else:
        masked = ""
    return EmailStatus(
        configured=s.email_configured,
        user=s.gmail_user,
        masked_password=masked,
        default_recipient=s.default_recipient,
    )


# ----------------------- Template HTML ----------------------- #


def _e(value: Optional[str]) -> str:
    """Escape HTML seguro."""
    return html.escape(value or "", quote=True)


def _job_card_html(job: Job) -> str:
    chips: list[str] = []
    if job.is_remote:
        chips.append('<span style="background:#1e293b;color:#7dd3fc;padding:2px 8px;border-radius:4px;font-size:11px;">Remoto</span>')
    for jt in job.job_types:
        label = {
            "full_time": "Full-time",
            "part_time": "Part-time",
            "freelance": "Freelancer",
            "contract": "PJ",
            "internship": "Estágio",
            "temporary": "Temporário",
        }.get(jt.value, jt.value)
        chips.append(f'<span style="background:#1e293b;color:#cbd5e1;padding:2px 8px;border-radius:4px;font-size:11px;margin-left:4px;">{_e(label)}</span>')

    posted = ""
    if job.posted_at:
        posted = f' · postada {_e(job.posted_at.strftime("%d/%m/%Y"))}'

    salary = f"<br><span style='color:#10b981;font-size:13px;font-weight:500;'>{_e(job.salary_text)}</span>" if job.salary_text else ""

    location_line = f"{_e(job.location) or 'Local não informado'}{posted}"

    return f"""
    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:16px;margin-bottom:12px;">
      <div style="display:flex;justify-content:space-between;align-items:start;gap:12px;">
        <div style="flex:1;">
          <a href="{_e(str(job.url))}" style="color:#e2e8f0;font-size:15px;font-weight:600;text-decoration:none;">{_e(job.title)}</a>
          <div style="color:#94a3b8;font-size:13px;margin-top:4px;">{_e(job.company)}</div>
          <div style="color:#64748b;font-size:12px;margin-top:2px;">{location_line}</div>
          {salary}
        </div>
        <div style="text-align:right;">{''.join(chips)}</div>
      </div>
      <div style="margin-top:12px;">
        <a href="{_e(str(job.url))}"
           style="display:inline-block;background:#4f46e5;color:#fff;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:500;">
          Ver vaga →
        </a>
        <span style="color:#64748b;font-size:11px;margin-left:8px;">via {_e(job.source.value)}</span>
      </div>
    </div>
    """


def render_jobs_email(saved_filter: SavedFilter, jobs: list[Job]) -> tuple[str, str]:
    """Retorna (subject, html_body)."""
    count = len(jobs)
    plural = "s" if count != 1 else ""
    subject = f"[JobFinder] {count} vaga{plural} nova{plural} — {saved_filter.name}"

    cards = "\n".join(_job_card_html(j) for j in jobs)
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0;padding:24px 16px;background:#020617;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
      <div style="max-width:680px;margin:0 auto;">
        <div style="margin-bottom:24px;">
          <h1 style="color:#f1f5f9;font-size:20px;margin:0;font-weight:600;">
            {count} vaga{plural} nova{plural} pro filtro <span style="color:#a78bfa;">"{_e(saved_filter.name)}"</span>
          </h1>
          <p style="color:#64748b;font-size:13px;margin:6px 0 0;">
            {now} · JobFinder
          </p>
        </div>

        {cards}

        <div style="margin-top:24px;padding-top:16px;border-top:1px solid #1e293b;">
          <p style="color:#475569;font-size:11px;line-height:1.6;margin:0;">
            Esse e-mail foi enviado porque o filtro <strong>"{_e(saved_filter.name)}"</strong>
            está com alertas ativos. Pra parar de receber, abre o JobFinder e
            desativa ou apaga o filtro.
          </p>
        </div>
      </div>
    </body>
    </html>
    """
    return subject, body


def render_test_email() -> tuple[str, str]:
    subject = "[JobFinder] E-mail de teste"
    body = """
    <!DOCTYPE html>
    <html><body style="margin:0;padding:32px;background:#020617;font-family:sans-serif;">
      <div style="max-width:520px;margin:0 auto;background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:24px;">
        <h1 style="color:#f1f5f9;font-size:18px;margin:0 0 8px;">Tudo funcionando</h1>
        <p style="color:#94a3b8;font-size:14px;line-height:1.5;margin:0;">
          Se você está vendo isso, o JobFinder conseguiu se conectar ao Gmail SMTP
          e mandar e-mail com sucesso. Os alertas automáticos vão usar essa mesma config.
        </p>
      </div>
    </body></html>
    """
    return subject, body


# ----------------------- Envio ----------------------- #


def _send_sync(to: str, subject: str, html_body: str) -> None:
    s = get_settings()
    if not s.email_configured:
        raise EmailError("Credenciais SMTP não configuradas (GMAIL_USER e GMAIL_APP_PASSWORD).")
    if not to:
        raise EmailError("Destinatário não informado.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = s.gmail_user
    msg["To"] = to
    msg.set_content("Esta mensagem requer um cliente que renderize HTML.")
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(s.gmail_user, s.gmail_app_password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise EmailError(f"Falha de autenticação no Gmail SMTP: {e.smtp_code} {e.smtp_error.decode('utf-8', 'ignore') if isinstance(e.smtp_error, bytes) else e.smtp_error}") from e
    except smtplib.SMTPException as e:
        raise EmailError(f"Erro SMTP: {e}") from e
    except OSError as e:
        raise EmailError(f"Erro de rede ao conectar no Gmail: {e}") from e


async def send_email_async(to: str, subject: str, html_body: str) -> None:
    await asyncio.to_thread(_send_sync, to, subject, html_body)
