"""
MICHOACÁN — Bot de Telegram (aiogram 3): FSM de 9 pasos, comprobantes, validación y timers.
Los timers viven en timers_michoacan (solo RAM). Aquí NO se guarda nada del timer en Supabase.
"""
import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import (FSInputFile, ContentType, InlineKeyboardMarkup,
                           InlineKeyboardButton, CallbackQuery)

from config_michoacan import (
    supabase, bot, BASE_URL, ENTIDAD, TZ, FOLIO_NUM_PREF,
)
from folios_michoacan import _generar_folio_async
from pdf_michoacan import generar_pdf, subir_pdf_a_storage
import timers_michoacan as T
from timers_michoacan import (
    iniciar_timer_36h, detener_timer_global, detener_timers_lote,
    folios_activos_usuario, snapshot_timers,
)

storage = MemoryStorage()
dp      = Dispatcher(storage=storage)

pending_comprobantes = {}

BTN_CANCELAR_TODOS = InlineKeyboardButton(text="🛑 Cancelar TODOS los timers", callback_data="cancelar_todos")

async def generar_y_enviar_background(chat_id: int, datos: dict, user_id: int):
    folio = datos["folio"]; nombre = datos["nombre"]
    try:
        pdf_path = await asyncio.to_thread(generar_pdf, datos)
        pdf_url  = await asyncio.to_thread(subir_pdf_a_storage, pdf_path, folio)
        await asyncio.to_thread(lambda: supabase.table("folios_registrados").insert({
            "folio": folio, "marca": datos["marca"], "linea": datos["linea"],
            "anio": datos["anio"], "numero_serie": datos["serie"],
            "numero_motor": datos.get("motor",""),
            "color": datos.get("color",""), "nombre": nombre,
            "fecha_expedicion":  datos["fecha_exp_dt"].date().isoformat(),
            "fecha_vencimiento": (datos["fecha_exp_dt"] + timedelta(days=30)).date().isoformat(),
            "entidad": ENTIDAD, "estado": "ACTIVO", "estado_pago": "PENDIENTE_PAGO",
            "user_id": user_id,
            "creado_por": f"BOT_TG_{datos.get('username','unknown')}",
            "pdf_url": pdf_url,
        }).execute())
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Validar Admin",  callback_data=f"validar_{folio}"),
            InlineKeyboardButton(text="⏹️ Detener Timer", callback_data=f"detener_{folio}")
        ], [BTN_CANCELAR_TODOS]])
        await bot.send_document(chat_id, FSInputFile(pdf_path),
            caption=(
                f"📄 PERMISO — MICHOACÁN\n"
                f"Folio: {folio}\nTitular: {nombre}\n"
                f"Expedición: {datos['fecha_exp']}\nVencimiento: {datos['fecha_ven']}\n\n"
                f"🔗 {BASE_URL}/consulta/{folio}\n\n"
                f"⏰ TIMER ACTIVO (36 horas)"
            ), reply_markup=keyboard)
        # Timer SOLO en RAM
        await iniciar_timer_36h(user_id, folio, nombre)
        await bot.send_message(user_id,
            f"💰 INSTRUCCIONES DE PAGO — MICHOACÁN\n\n"
            f"📄 Folio: {folio}\n⏰ Tiempo límite: 36 horas\n\n"
            f"📸 Envía la foto de tu comprobante aquí mismo.\n"
            f"⚠️ Sin pago en 36h el folio se elimina.\n\n"
            f"📋 Use /michoacan para generar otro permiso.")
    except Exception as e:
        print(f"[ERROR] background folio {folio}: {e}")
        try: await bot.send_message(user_id, f"❌ Error al generar el documento: {e}\n\nUse /michoacan para reintentar.")
        except Exception: pass

# ===================== BOT FSM — 9 pasos =====================
class PermisoForm(StatesGroup):
    marca  = State()
    linea  = State()
    anio   = State()
    serie  = State()
    motor  = State()
    color  = State()
    nombre = State()
    tipo   = State()
    clase  = State()

@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏛️ GOBIERNO DEL ESTADO DE MICHOACÁN\nDirección de Tránsito Estatal\n\n📋 Use /michoacan para generar un permiso de circulación.")

@dp.message(Command("michoacan"))
async def michoacan_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    activos = folios_activos_usuario(message.from_user.id)
    if activos:
        texto = "📋 FOLIOS ACTIVOS\n" + "─"*28 + "\n\n"; botones = []
        for t in activos:
            texto += f"Folio: {t['folio']}\n{t['nombre'] or ''}\n{t['restante']} restantes\n\n"
            botones.append([InlineKeyboardButton(text=f"⏹️ Detener {t['folio']}", callback_data=f"detener_{t['folio']}")])
        botones.append([BTN_CANCELAR_TODOS])
        await message.answer(texto.strip(), reply_markup=InlineKeyboardMarkup(inline_keyboard=botones))
        await message.answer("Para NUEVO permiso escribe la MARCA del vehículo:")
    else:
        await message.answer("🚗 NUEVO PERMISO — MICHOACÁN\n\n⏰ Plazo de pago: 36 horas\n\nPaso 1/9: MARCA del vehículo:")
    await state.set_state(PermisoForm.marca)

@dp.message(PermisoForm.marca)
async def get_marca(message: types.Message, state: FSMContext):
    await state.update_data(marca=message.text.strip().upper())
    await message.answer("Paso 2/9: LÍNEA del vehículo (ej. SIERRA, TSURU, AVEO):")
    await state.set_state(PermisoForm.linea)

@dp.message(PermisoForm.linea)
async def get_linea(message: types.Message, state: FSMContext):
    await state.update_data(linea=message.text.strip().upper())
    await message.answer("Paso 3/9: AÑO del vehículo (4 dígitos):")
    await state.set_state(PermisoForm.anio)

@dp.message(PermisoForm.anio)
async def get_anio(message: types.Message, state: FSMContext):
    anio = message.text.strip()
    if not anio.isdigit() or len(anio) != 4:
        await message.answer("⚠️ Año inválido. Usa 4 dígitos (ej. 2021):"); return
    await state.update_data(anio=anio)
    await message.answer("Paso 4/9: NÚMERO DE SERIE:")
    await state.set_state(PermisoForm.serie)

@dp.message(PermisoForm.serie)
async def get_serie(message: types.Message, state: FSMContext):
    await state.update_data(serie=message.text.strip().upper())
    await message.answer("Paso 5/9: NÚMERO DE MOTOR:")
    await state.set_state(PermisoForm.motor)

@dp.message(PermisoForm.motor)
async def get_motor(message: types.Message, state: FSMContext):
    await state.update_data(motor=message.text.strip().upper())
    await message.answer("Paso 6/9: COLOR del vehículo:")
    await state.set_state(PermisoForm.color)

@dp.message(PermisoForm.color)
async def get_color(message: types.Message, state: FSMContext):
    await state.update_data(color=message.text.strip().upper())
    await message.answer("Paso 7/9: NOMBRE COMPLETO del titular:")
    await state.set_state(PermisoForm.nombre)

@dp.message(PermisoForm.nombre)
async def get_nombre_step(message: types.Message, state: FSMContext):
    await state.update_data(nombre=message.text.strip().upper())
    await message.answer("Paso 8/9: TIPO del vehículo (ej. PICK-UP, SEDÁN, SUV):")
    await state.set_state(PermisoForm.tipo)

@dp.message(PermisoForm.tipo)
async def get_tipo(message: types.Message, state: FSMContext):
    await state.update_data(tipo=message.text.strip().upper())
    await message.answer("Paso 9/9: CLASE del vehículo (ej. CARGA, PASAJEROS, PARTICULAR):")
    await state.set_state(PermisoForm.clase)

@dp.message(PermisoForm.clase)
async def get_clase(message: types.Message, state: FSMContext):
    datos = await state.get_data()
    datos["clase"]    = message.text.strip().upper()
    datos["username"] = message.from_user.username or "Sin username"
    datos["folio"]    = await _generar_folio_async()
    tz = ZoneInfo(TZ); hoy = datetime.now(tz); ven = hoy + timedelta(days=30)
    datos["fecha_exp"]    = hoy.strftime("%d/%m/%Y")
    datos["fecha_ven"]    = ven.strftime("%d/%m/%Y")
    datos["fecha_exp_dt"] = hoy
    await state.clear()
    await message.answer(f"🔄 Generando permiso...\n📄 Folio: {datos['folio']}\n👤 Titular: {datos['nombre']}")
    asyncio.create_task(generar_y_enviar_background(message.chat.id, datos, message.from_user.id))

@dp.message(lambda m: m.text and m.text.strip().upper().startswith("SERO"))
async def codigo_admin(message: types.Message):
    texto = message.text.strip().upper(); folio = texto.replace("SERO","",1).strip()
    if not folio or not folio.startswith(FOLIO_NUM_PREF):
        await message.answer(f"⚠️ Formato: SERO{FOLIO_NUM_PREF}X\n\n📋 Use /michoacan para otro permiso."); return
    r = await detener_timer_global(folio, "admin_telegram_SERO", estado_pago="VALIDADO")
    if not r["ok"]:
        await message.answer(f"⚠️ Folio {folio} no encontrado en la base.\n\n📋 Use /michoacan para otro permiso."); return
    with suppress(Exception):
        await asyncio.to_thread(lambda: supabase.table("folios_registrados").update({
            "fecha_comprobante": datetime.now().isoformat()
        }).eq("folio", r["folio"]).execute())
    await message.answer(
        f"✅ Validación admin\nFolio: {folio}\n⏹️ Timer detenido (sincronizado con el panel web)"
        f"\n\n📋 Use /michoacan para otro permiso.")

@dp.message(lambda m: m.content_type == ContentType.PHOTO)
async def recibir_comprobante(message: types.Message):
    uid = message.from_user.id
    folios = [t["folio"] for t in folios_activos_usuario(uid)]
    if not folios:
        await message.answer("ℹ️ No tienes folios pendientes.\n\n📋 Use /michoacan para generar un permiso."); return
    if len(folios) > 1:
        lista = "\n".join(f"• {f}" for f in folios); pending_comprobantes[uid] = "waiting_folio"
        await message.answer(f"📄 Varios folios activos:\n\n{lista}\n\nResponde con el NÚMERO DE FOLIO.\n\n📋 Use /michoacan para otro permiso."); return
    folio = folios[0]
    await detener_timer_global(folio, "comprobante_telegram", estado="COMPROBANTE_ENVIADO")
    with suppress(Exception):
        await asyncio.to_thread(lambda: supabase.table("folios_registrados").update({
            "fecha_comprobante": datetime.now().isoformat()
        }).eq("folio", folio).execute())
    await message.answer(f"✅ Comprobante recibido\nFolio: {folio}\n⏹️ Timer detenido.\n\n📋 Use /michoacan para otro permiso.")

@dp.message(lambda m: m.from_user.id in pending_comprobantes and pending_comprobantes[m.from_user.id] == "waiting_folio")
async def especificar_folio_comprobante(message: types.Message):
    uid = message.from_user.id; fe = message.text.strip().upper()
    fl = [t["folio"] for t in folios_activos_usuario(uid)]
    if fe not in fl:
        await message.answer("❌ Folio no en tu lista.\n\n📋 Use /michoacan para otro permiso."); return
    await detener_timer_global(fe, "comprobante_telegram", estado="COMPROBANTE_ENVIADO")
    with suppress(Exception):
        await asyncio.to_thread(lambda: supabase.table("folios_registrados").update({
            "fecha_comprobante": datetime.now().isoformat()
        }).eq("folio", fe).execute())
    pending_comprobantes.pop(uid, None)
    await message.answer(f"✅ Comprobante asociado.\nFolio: {fe}\n⏹️ Timer detenido.\n\n📋 Use /michoacan para otro permiso.")

@dp.callback_query(lambda c: c.data and c.data.startswith("validar_"))
async def callback_validar(callback: CallbackQuery):
    folio = callback.data.replace("validar_","")
    r = await detener_timer_global(folio, "callback_validar_telegram", estado_pago="VALIDADO")
    if not r["ok"]:
        await callback.answer("❌ Folio no encontrado en la base", show_alert=True); return
    with suppress(Exception):
        await asyncio.to_thread(lambda: supabase.table("folios_registrados").update({
            "fecha_comprobante": datetime.now().isoformat()
        }).eq("folio", r["folio"]).execute())
    await callback.answer("✅ Folio validado", show_alert=True)
    with suppress(Exception):
        await callback.message.edit_reply_markup(reply_markup=None)
    if r.get("user_id"):
        with suppress(Exception):
            await bot.send_message(r["user_id"],
                f"✅ PAGO VALIDADO — MICHOACÁN\nFolio: {r['folio']}\nTitular: {r.get('nombre','')}\n"
                f"Tu permiso está activo.\n\n📋 Use /michoacan para otro permiso.")

@dp.callback_query(lambda c: c.data and c.data.startswith("detener_"))
async def callback_detener(callback: CallbackQuery):
    folio = callback.data.replace("detener_","")
    r = await detener_timer_global(folio, "callback_detener_telegram", estado="TIMER_DETENIDO")
    if not r["ok"]:
        await callback.answer("❌ Folio no encontrado en la base", show_alert=True); return
    await callback.answer("⏹️ Timer detenido", show_alert=True)
    with suppress(Exception):
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"⏹️ TIMER DETENIDO\nFolio: {r['folio']}\nTitular: {r.get('nombre','')}\n"
        f"(sincronizado con el panel web)\n\n📋 Use /michoacan para otro permiso.")

@dp.message(Command("folios"))
async def ver_folios_activos(message: types.Message):
    activos = folios_activos_usuario(message.from_user.id)
    if not activos:
        await message.answer("ℹ️ No hay folios activos.\n\n📋 Use /michoacan para generar uno."); return
    lista = []; botones = []
    for t in activos:
        lista.append(f"• {t['folio']} — {t['nombre'] or ''}\n  {t['restante']} restantes")
        botones.append([InlineKeyboardButton(text=f"⏹️ Detener {t['folio']}", callback_data=f"detener_{t['folio']}")])
    botones.append([BTN_CANCELAR_TODOS])
    await message.answer(f"📋 FOLIOS ACTIVOS ({len(activos)})\n\n" + "\n\n".join(lista) + "\n\n📋 Use /michoacan para otro permiso.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=botones))

# ── Cancelar TODOS los timers (del usuario que pulsa) ──
@dp.callback_query(lambda c: c.data == "cancelar_todos")
async def callback_cancelar_todos(callback: CallbackQuery):
    n = len(folios_activos_usuario(callback.from_user.id))
    if n == 0:
        await callback.answer("No tienes timers activos.", show_alert=True); return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Sí, cancelar todos", callback_data="cancelar_todos_si"),
        InlineKeyboardButton(text="❌ No", callback_data="cancelar_todos_no"),
    ]])
    await callback.answer()
    await callback.message.answer(
        f"⚠️ CANCELAR TODOS LOS TIMERS\n\nSe detendrán {n} timer(es). Esos folios YA NO se eliminarán "
        f"automáticamente a las 36 horas.\n\n¿Confirmas?", reply_markup=kb)

@dp.callback_query(lambda c: c.data == "cancelar_todos_no")
async def callback_cancelar_todos_no(callback: CallbackQuery):
    await callback.answer("Cancelado, tus timers siguen activos.")
    with suppress(Exception):
        await callback.message.edit_reply_markup(reply_markup=None)

@dp.callback_query(lambda c: c.data == "cancelar_todos_si")
async def callback_cancelar_todos_si(callback: CallbackQuery):
    folios = [t["folio"] for t in folios_activos_usuario(callback.from_user.id)]
    n = await detener_timers_lote(folios, "bot_cancelar_todos")
    await callback.answer("Timers detenidos", show_alert=True)
    with suppress(Exception):
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"🛑 TIMERS DETENIDOS\n\nSe detuvieron {n} timer(es). Esos folios ya NO se eliminarán automáticamente.\n\n📋 Use /michoacan para otro permiso.")

@dp.message()
async def fallback(message: types.Message):
    await message.answer("🏛️ Gobierno del Estado de Michoacán — Tránsito Estatal.\n\n📋 Use /michoacan para generar un permiso.")

async def procesar_update(data: dict):
    """La llama main.py desde /webhook."""
    await dp.feed_webhook_update(bot, types.Update(**data))
