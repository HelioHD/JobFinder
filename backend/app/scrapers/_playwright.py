"""Helper compartilhado pra scrapers que precisam de browser real (Playwright).

LinkedIn e Google Jobs usam JavaScript pesado / proteções anti-bot que
quebram tentativas de raspagem direta com httpx. Pra eles montamos um
Chromium headless por scrape e o reutilizamos via context manager.

Decisões:
  - Chromium é instalado via `python -m playwright install chromium`. Se
    falhar ao iniciar, lançamos PlaywrightUnavailable e o ScrapeService
    captura como erro (a fonte fica indisponível, sem derrubar o resto).
  - O browser NÃO é mantido vivo entre scrapes — Playwright é caro em
    memória e o JobFinder roda 1 scrape de cada vez. Custo de spin-up
    (~1-2s) é aceitável.
  - User agent e viewport realistas pra reduzir detecção. Sem login,
    sem cookies persistidos.
"""
from __future__ import annotations

import contextlib
from typing import AsyncIterator

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


class PlaywrightUnavailable(RuntimeError):
    """Disparado quando o Chromium não consegue iniciar (não instalado, etc)."""


@contextlib.asynccontextmanager
async def browser_page(*, locale: str = "pt-BR") -> AsyncIterator:
    """Abre Chromium headless + uma página configurada e fecha tudo no fim.

    Uso:
        async with browser_page() as page:
            await page.goto("https://...")
            html = await page.content()
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise PlaywrightUnavailable(
            "Playwright não está instalado (pip install playwright + playwright install chromium)."
        ) from exc

    p = None
    browser = None
    context = None
    try:
        p = await async_playwright().start()
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
        except Exception as exc:  # noqa: BLE001
            raise PlaywrightUnavailable(
                f"Chromium falhou ao iniciar (rode `python -m playwright install chromium`): {exc}"
            ) from exc
        context = await browser.new_context(
            user_agent=DEFAULT_UA,
            locale=locale,
            viewport={"width": 1366, "height": 900},
            extra_http_headers={
                "Accept-Language": f"{locale},pt;q=0.9,en;q=0.8",
            },
        )
        # Reduz detecção 'navigator.webdriver = true'
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await context.new_page()
        # Bloqueia recursos pesados (imagens, fontes) pra reduzir tempo/banda
        await page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in {"image", "media", "font"}
            else route.continue_(),
        )
        yield page
    finally:
        if context is not None:
            with contextlib.suppress(Exception):
                await context.close()
        if browser is not None:
            with contextlib.suppress(Exception):
                await browser.close()
        if p is not None:
            with contextlib.suppress(Exception):
                await p.stop()
