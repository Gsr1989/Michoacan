"""
MICHOACÁN — PANEL: Timers del Bot (RAM).
Lista los timers vivos, detiene/valida uno, reinicia uno y «Detener TODOS».
"""
import asyncio
import html as html_lib
from contextlib import suppress
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config_michoacan import supabase, bot, C1
from ui_michoacan import page
from timers_michoacan import (
    snapshot_timers, detener_timer_global, detener_todos_global,
    iniciar_timer_36h, _leer_estado_folio,
)

router = APIRouter()
_esc = html_lib.escape


@router.get("/panel/timers", response_class=HTMLResponse)
async def panel_timers(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    msg = request.query_params.get("msg", "")
    items = snapshot_timers()

    filas = ""
    for t in items:
        f = _esc(t["folio"])
        color = "#dc3545" if t["segundos"] < 3600 else C1
        filas += f"""<tr>
          <td><strong style="color:{C1}">{f}</strong><br><small style="color:#999">{_esc(t['nombre'] or '')}</small></td>
          <td style="font-size:11px">{_esc(t['user_id'])}</td>
          <td><strong style="color:{color}">{_esc(t['restante'])}</strong></td>
          <td>
            <form method="POST" action="/panel/timer/detener/{f}" style="display:inline">
              <button class="btn btn-warn btn-sm" onclick="return confirm('¿Detener el timer de {f}? El folio NO se borrará.')">⏹️</button>
            </form>
            <form method="POST" action="/panel/validar/{f}" style="display:inline">
              <button class="btn btn-success btn-sm" onclick="return confirm('¿Validar pago de {f}?')">✅</button>
            </form>
          </td>
        </tr>"""

    boton_todos = ""
    if items:
        boton_todos = f"""<form method="POST" action="/panel/timers/detener_todos" class="mt-3"
              onsubmit="return confirm('¿Detener TODOS los {len(items)} timers activos? Esos folios NO se borrarán solos.')">
          <button type="submit" class="btn btn-danger" style="width:100%">🛑 Detener TODOS los timers ({len(items)})</button>
        </form>"""

    contenido = f"""
    <p class="page-title">⏱️ Timers del Bot</p>
    {"<div class='alert alert-ok'>"+_esc(msg)+"</div>" if msg else ""}
    <div class="info-box">
      Los timers viven <strong>solo en la memoria</strong> del servidor (no se guardan en Supabase).
      Si Render se reinicia, todos se pierden y los folios que estaban pendientes se quedan en la BD
      hasta que los borres a mano.<br>
      «Detener TODOS» mata todos los timers que existan en este momento, sin importar de qué usuario de
      Telegram sean. Los timers que se creen DESPUÉS siguen vivos hasta que los detengas.
    </div>
    <div class="tabla-wrap"><table>
      <thead><tr><th>Folio / Titular</th><th>Telegram ID</th><th>Restante</th><th>Acc.</th></tr></thead>
      <tbody>{filas or '<tr><td colspan="4" style="text-align:center;color:#999;padding:20px">Sin timers activos</td></tr>'}</tbody>
    </table></div>
    {boton_todos}
    <div class="mt-3"><a href="/panel/admin" class="btn btn-outline btn-sm">← Panel</a></div>"""
    return HTMLResponse(page("Timers", "Timers del Bot — Michoacán", contenido))


@router.post("/panel/timers/detener_todos")
async def panel_detener_todos(request: Request):
    """Mata TODOS los timers en RAM (cualquier usuario de Telegram)."""
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    n = await detener_todos_global("panel_detener_todos")
    return RedirectResponse(url=f"/panel/timers?msg={quote(f'Se detuvieron {n} timers 🛑')}", status_code=303)


@router.post("/panel/timer/detener/{folio}")
async def panel_detener_timer(request: Request, folio: str):
    """Detiene UN timer desde la web. Mismo efecto que el botón de Telegram."""
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    r = await detener_timer_global(folio, "panel_web_detener", estado="TIMER_DETENIDO")
    if not r["ok"]:
        return RedirectResponse(url=f"/panel/timers?msg={quote(f'⚠️ Folio {folio.upper()} no encontrado')}", status_code=303)
    if r.get("user_id"):
        with suppress(Exception):
            await bot.send_message(r["user_id"],
                f"⏹️ TIMER DETENIDO — MICHOACÁN\nFolio: {r['folio']}\nTitular: {r.get('nombre','')}\n"
                f"Un administrador detuvo el timer. Tu folio NO será eliminado.\n\n📋 Use /michoacan para otro permiso.")
    return RedirectResponse(url=f"/panel/timers?msg={quote('Timer de ' + r['folio'] + ' detenido ⏹️')}", status_code=303)


@router.post("/panel/timer/reiniciar/{folio}")
async def panel_reiniciar_timer(request: Request, folio: str):
    """Vuelve a arrancar un timer de 36 h (solo RAM) para un folio."""
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    folio = folio.strip().upper()
    row = await asyncio.to_thread(_leer_estado_folio, folio)
    if row in (None, "ERROR"):
        return RedirectResponse(url=f"/panel/timers?msg={quote(f'⚠️ Folio {folio} no encontrado')}", status_code=303)
    # Si estaba detenido, vuelve a quedar ACTIVO para que el vencimiento sí lo pueda borrar
    with suppress(Exception):
        await asyncio.to_thread(lambda: supabase.table("folios_registrados")
            .update({"estado": "ACTIVO"}).eq("folio", folio).execute())
    await iniciar_timer_36h(row.get("user_id") or 0, folio, row.get("nombre", "") or "")
    return RedirectResponse(url=f"/panel/timers?msg={quote(f'Timer de {folio} reiniciado (36h)')}", status_code=303)
