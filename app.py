"""
MICHOACÁN v5.0 — arranque. Todo vive en módulos:

  config_michoacan.py        variables, constantes, Supabase, Bot
  folios_michoacan.py        generador de folios
  pdf_michoacan.py           QR + PDF + Storage
  timers_michoacan.py        timers de 36 h (SOLO RAM) + detener / detener todos
  bot_michoacan.py           bot de Telegram (aiogram)
  consulta_michoacan.py      consulta pública (QR y folio manual, interfaz oficial)
  ui_michoacan.py            CSS / layout del panel
  panel_michoacan.py         panel admin (login, folios, registro, test fechas)
  panel_timers_michoacan.py  panel: timers del bot + «Detener TODOS»
  usuarios_michoacan.py      portal de usuarios terceros
  tablas_michoacan.py        editor de tablas de Supabase

Start command en Render (OJO -w 1: los timers viven en la RAM de UN solo proceso):
    gunicorn main:app -k uvicorn.workers.UvicornWorker -w 1 --timeout 120
"""
import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from config_michoacan import (
    supabase, bot, BASE_URL, ENTIDAD, TZ, FOLIO_NUM_PREF, STATIC_DIR, SESSION_SECRET,
)
from folios_michoacan import _sb_inicializar_folio, _folio_counter
from timers_michoacan import timers_activos
from bot_michoacan import procesar_update
from consulta_michoacan import crear_router_consulta
import panel_michoacan, panel_timers_michoacan, usuarios_michoacan, tablas_michoacan

_keep_task = None


async def keep_alive():
    while True:
        await asyncio.sleep(600)
        print(f"[HEARTBEAT] Michoacán activo — timers en RAM: {len(timers_activos)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _keep_task
    await asyncio.to_thread(_sb_inicializar_folio)
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(f"{BASE_URL}/webhook", allowed_updates=["message", "callback_query"])
    _keep_task = asyncio.create_task(keep_alive())
    print(f"[SISTEMA] Michoacán v5.0 listo — siguiente folio: {FOLIO_NUM_PREF}{_folio_counter['siguiente']}")
    yield
    if _keep_task:
        _keep_task.cancel()
        with suppress(asyncio.CancelledError):
            await _keep_task
    await bot.session.close()


app = FastAPI(lifespan=lifespan, title="Tránsito Michoacán", version="5.0")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
try:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
except Exception:
    pass

# ── módulos ──
app.include_router(crear_router_consulta(supabase, ENTIDAD, TZ))
app.include_router(panel_michoacan.router)
app.include_router(panel_timers_michoacan.router)
app.include_router(usuarios_michoacan.router)
app.include_router(tablas_michoacan.router)


@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        await procesar_update(data)
        return {"ok": True}
    except Exception as e:
        print(f"[WEBHOOK] Error: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if request.session.get("admin"): return RedirectResponse(url="/panel/admin", status_code=303)
    if request.session.get("username"): return RedirectResponse(url="/registro_usuario", status_code=303)
    return RedirectResponse(url="/panel/login", status_code=303)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "5.0", "entidad": ENTIDAD,
            "timers_ram": len(timers_activos),
            "siguiente_folio": f"{FOLIO_NUM_PREF}{_folio_counter['siguiente']}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
