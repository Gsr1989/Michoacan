"""
MICHOACÁN — TIMERS DE PAGO (36 h) · SOLO EN RAM.

  · Nada del timer se guarda en Supabase (se quitaron timer_activo,
    timer_expira_en, timer_detenido_en y timer_motivo). Un reinicio de Render
    MATA todos los timers.
  · Al vencer, el folio se borra SOLO si en la BD sigue pendiente de pago
    (estado_pago != VALIDADO y estado no es COMPROBANTE_ENVIADO/TIMER_DETENIDO).
  · Bot de Telegram y panel web usan las mismas funciones de este módulo.
"""
import asyncio
import os
from contextlib import suppress
from datetime import datetime

from config_michoacan import supabase, bot, ENTIDAD, OUTPUT_DIR, BUCKET_NAME

timers_activos = {}   # folio -> {"task", "user_id", "start_time", "nombre"}
user_folios    = {}   # user_id -> [folios]
TOTAL_SEGUNDOS = 36 * 3600

ESTADOS_STOP_PAGO = {"VALIDADO"}
ESTADOS_STOP_GRAL = {"COMPROBANTE_ENVIADO", "TIMER_DETENIDO"}


# ───────────────────────── lectura de la BD (solo lectura) ─────────────────────────
def _leer_estado_folio(folio: str):
    """Devuelve dict, None (no existe) o 'ERROR' (falla de red)."""
    try:
        r = supabase.table("folios_registrados") \
            .select("folio,estado,estado_pago,user_id,nombre") \
            .eq("folio", folio).limit(1).execute()
        return r.data[0] if r.data else None
    except Exception as e:
        print(f"[TIMER] Error leyendo {folio}: {e}")
        return "ERROR"


async def _estado_pendiente(folio: str):
    """True = sigue pendiente de pago · False = ya no (validado/detenido/borrado) · None = error de red."""
    row = await asyncio.to_thread(_leer_estado_folio, folio)
    if row == "ERROR":
        return None
    if row is None:
        return False
    if (row.get("estado_pago") or "") in ESTADOS_STOP_PAGO:
        return False
    if (row.get("estado") or "") in ESTADOS_STOP_GRAL:
        return False
    return True


# ───────────────────────── RAM ─────────────────────────
def cancelar_timer_folio(folio: str) -> bool:
    """Cancela la tarea en RAM. No toca la BD."""
    item = timers_activos.get(folio)
    if not item:
        return False
    with suppress(Exception):
        item["task"].cancel()
    uid = item["user_id"]
    del timers_activos[folio]
    if uid in user_folios and folio in user_folios[uid]:
        user_folios[uid].remove(folio)
        if not user_folios[uid]:
            del user_folios[uid]
    return True


def limpiar_timer_folio(folio: str):
    """Saca el folio de la RAM sin cancelar la tarea (se usa desde la propia tarea)."""
    item = timers_activos.get(folio)
    if not item:
        return
    uid = item["user_id"]
    del timers_activos[folio]
    if uid in user_folios and folio in user_folios[uid]:
        user_folios[uid].remove(folio)
        if not user_folios[uid]:
            del user_folios[uid]


def _restante_seg(item) -> int:
    return max(0, int(TOTAL_SEGUNDOS - (datetime.now() - item["start_time"]).total_seconds()))


def snapshot_timers() -> list:
    """Timers vivos, para el panel y para /folios."""
    salida = []
    for folio, item in list(timers_activos.items()):
        seg = _restante_seg(item)
        h, m = divmod(seg // 60, 60)
        salida.append({
            "folio": folio, "user_id": item.get("user_id"),
            "nombre": item.get("nombre", ""), "segundos": seg,
            "restante": f"{h}h {m}min",
        })
    salida.sort(key=lambda x: x["segundos"])
    return salida


def folios_activos_usuario(user_id: int) -> list:
    """Timers vivos de UN usuario de Telegram."""
    return [t for t in snapshot_timers() if t["user_id"] == user_id]


# ───────────────────────── vencimiento y recordatorios ─────────────────────────
async def eliminar_folio_automatico(folio: str):
    """Borra el folio SOLO si la BD confirma que sigue pendiente de pago."""
    pend = None
    for _ in range(3):
        pend = await _estado_pendiente(folio)
        if pend is not None:
            break
        await asyncio.sleep(30)          # error de red: reintenta, NUNCA borra a ciegas
    if pend is not True:
        print(f"[TIMER] {folio} no está pendiente (o BD sin respuesta) — NO se borra")
        limpiar_timer_folio(folio)
        return
    try:
        item = timers_activos.get(folio)
        uid = item["user_id"] if item else None
        await asyncio.to_thread(lambda: supabase.table("folios_registrados").delete().eq("folio", folio).execute())
        with suppress(Exception):
            await asyncio.to_thread(lambda: supabase.storage.from_(BUCKET_NAME).remove([f"{folio}.pdf"]))
        ruta_local = os.path.join(OUTPUT_DIR, f"{folio}.pdf")
        if os.path.exists(ruta_local):
            with suppress(Exception):
                os.remove(ruta_local)
        if uid:
            with suppress(Exception):
                await bot.send_message(uid,
                    f"⏰ TIEMPO AGOTADO - MICHOACÁN\n\nEl folio {folio} fue eliminado por no completar el pago en 36 horas.\n\n📋 Use /michoacan para generar otro permiso.")
        limpiar_timer_folio(folio)
        print(f"[TIMER] {folio} eliminado por vencimiento")
    except Exception as e:
        print(f"[ERROR] eliminando folio {folio}: {e}")


async def enviar_recordatorio(folio: str, minutos_restantes: int):
    try:
        item = timers_activos.get(folio)
        if not item or not item.get("user_id"):
            return
        await bot.send_message(item["user_id"],
            f"⚡ RECORDATORIO - MICHOACÁN\n\nFolio: {folio}\nTiempo restante: {minutos_restantes} minutos\n\n📸 Envíe su comprobante de pago.\n\n📋 Use /michoacan para otro permiso.")
    except Exception as e:
        print(f"[ERROR] recordatorio {folio}: {e}")


async def iniciar_timer_36h(user_id: int, folio: str, nombre: str = ""):
    """Arranca el timer de 36 h (solo RAM). Si ya había uno para el folio, lo reemplaza."""
    cancelar_timer_folio(folio)

    async def timer_task():
        restante = TOTAL_SEGUNDOS
        for falta, minutos in [(90 * 60, 90), (60 * 60, 60), (30 * 60, 30), (10 * 60, 10)]:
            espera = restante - falta
            if espera > 0:
                await asyncio.sleep(espera)
                restante = falta
                if await _estado_pendiente(folio) is False:
                    print(f"[TIMER] {folio} ya no está pendiente — task termina")
                    limpiar_timer_folio(folio)
                    return
                await enviar_recordatorio(folio, minutos)
        if restante > 0:
            await asyncio.sleep(restante)
        await eliminar_folio_automatico(folio)

    task = asyncio.create_task(timer_task())
    timers_activos[folio] = {
        "task": task, "user_id": user_id,
        "start_time": datetime.now(), "nombre": nombre,
    }
    user_folios.setdefault(user_id, []).append(folio)
    print(f"[TIMER] Iniciado folio {folio} ({nombre}) — 36 h (solo RAM)")


# ───────────────────────── detener (bot + panel) ─────────────────────────
async def detener_timer_global(folio: str, motivo: str,
                               estado_pago: str = None, estado: str = None) -> dict:
    """Detiene UN timer: cancela la RAM y (si se pide) actualiza estado/estado_pago en la BD."""
    folio = folio.strip().upper()
    row = await asyncio.to_thread(_leer_estado_folio, folio)
    if row in (None, "ERROR"):
        cancelar_timer_folio(folio)
        return {"ok": False, "motivo": "folio no encontrado", "folio": folio,
                "user_id": None, "nombre": "", "cancelado_mem": False}

    parches = {}
    if estado_pago:
        parches["estado_pago"] = estado_pago
    if estado:
        parches["estado"] = estado

    ok_db = True
    if parches:
        try:
            await asyncio.to_thread(
                lambda: supabase.table("folios_registrados").update(parches).eq("folio", folio).execute())
        except Exception as e:
            ok_db = False
            print(f"[TIMER] Error deteniendo {folio} en BD: {e}")

    cancelado = cancelar_timer_folio(folio)
    print(f"[TIMER] STOP {folio} motivo={motivo} db={ok_db} ram={cancelado}")
    return {"ok": ok_db, "folio": folio, "user_id": row.get("user_id"),
            "nombre": row.get("nombre", "") or "", "cancelado_mem": cancelado}


async def detener_timers_lote(folios: list, motivo: str) -> int:
    """
    Mata VARIOS timers de golpe (botón «Cancelar TODOS» del bot y del panel).
    Los deja en estado TIMER_DETENIDO para que nunca se borren solos.
    Devuelve cuántos timers de RAM se cancelaron.
    """
    folios = [f for f in folios if f]
    n = 0
    for f in folios:
        if cancelar_timer_folio(f):
            n += 1
    if folios:
        try:
            await asyncio.to_thread(lambda: supabase.table("folios_registrados")
                .update({"estado": "TIMER_DETENIDO"}).in_("folio", folios).execute())
        except Exception as e:
            print(f"[TIMER] Error BD en lote ({motivo}): {e}")
    print(f"[TIMER] LOTE {motivo}: {n} timers cancelados")
    return n


async def detener_todos_global(motivo: str = "panel_detener_todos") -> int:
    """Mata TODOS los timers vivos, de cualquier usuario de Telegram."""
    return await detener_timers_lote(list(timers_activos.keys()), motivo)
