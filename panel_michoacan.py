"""
MICHOACÁN — PANEL ADMIN: login, inicio, folios, validar pago, PDF, registro admin,
crear usuario y test de fechas. (Timers -> panel_timers_michoacan.py)
"""
import asyncio
import html as html_lib
import os
from contextlib import suppress
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from config_michoacan import (
    supabase, bot, ENTIDAD, TZ, ADMIN_USER, ADMIN_PASS, FOLIO_NUM_PREF,
    OUTPUT_DIR, C1,
)
from ui_michoacan import page, login_html
from folios_michoacan import _folio_counter, generar_folio
from pdf_michoacan import generar_subir_y_guardar_pdf
from timers_michoacan import timers_activos, detener_timer_global, iniciar_timer_36h

router = APIRouter()
_esc = html_lib.escape


def _pdf_seguro(url: str) -> str:
    """Solo se acepta un link http(s) para el modal de descarga (evita javascript:)."""
    url = (url or "").strip()
    return url if url.lower().startswith(("http://", "https://")) else ""

@router.get("/panel/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if request.session.get("admin"): return RedirectResponse(url="/panel/admin", status_code=303)
    return HTMLResponse(login_html(bool(request.query_params.get("error",""))))

@router.post("/panel/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        request.session["admin"] = True; request.session["username"] = username
        return RedirectResponse(url="/panel/admin", status_code=303)
    try:
        res = supabase.table("verificacion_michoacan").select("*").eq("username",username).eq("password",password).execute()
        if res.data:
            u = res.data[0]; request.session["admin"] = False
            request.session["username"] = u["username"]; request.session["user_id"] = u.get("id")
            return RedirectResponse(url="/registro_usuario", status_code=303)
    except Exception as e: print(f"[LOGIN] Error: {e}")
    return RedirectResponse(url="/panel/login?error=1", status_code=303)

@router.get("/panel/logout")
async def logout(request: Request):
    request.session.clear(); return RedirectResponse(url="/panel/login", status_code=303)

# ===================== PANEL ADMIN =====================
@router.get("/panel/admin", response_class=HTMLResponse)
async def panel_admin(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    pendientes = 0
    try:
        r = supabase.table("folios_registrados").select("folio").eq("estado_pago","PENDIENTE_PAGO").eq("entidad",ENTIDAD).execute()
        pendientes = len(r.data or [])
    except Exception: pass
    timers_ram = len(timers_activos)
    color_pend = "#dc3545" if pendientes else "#1a6e2e"
    contenido = f"""
    <div class="row-2 mb-3">
      <div class="stat-card"><div class="stat-num">{timers_ram}</div><div class="stat-lbl">Timers Activos (RAM)</div></div>
      <div class="stat-card"><div class="stat-num" style="color:{color_pend}">{pendientes}</div><div class="stat-lbl">Pendientes Pago</div></div>
    </div>
    <div class="stat-card mb-3"><div class="stat-num">{FOLIO_NUM_PREF}{_folio_counter['siguiente']}</div><div class="stat-lbl">Siguiente Folio</div></div>
    <div class="grid">
      <a href="/panel/folios" class="menu-btn"><i class="fa-solid fa-list-check"></i><span>Ver Folios</span></a>
      <a href="/panel/timers" class="menu-btn"><i class="fa-solid fa-stopwatch"></i><span>Timers del Bot</span></a>
      <a href="/panel/registro_admin" class="menu-btn"><i class="fa-solid fa-file-circle-plus"></i><span>Registrar Permiso</span></a>
      <a href="/panel/crear_usuario" class="menu-btn"><i class="fa-solid fa-user-plus"></i><span>Crear Usuario</span></a>
      <a href="/panel/tablas" class="menu-btn"><i class="fa-solid fa-database"></i><span>Tablas BD</span></a>
      <a href="/consulta_folio" class="menu-btn"><i class="fa-solid fa-magnifying-glass"></i><span>Consultar Folio</span></a>
      <a href="/panel/test_fechas" class="menu-btn"><i class="fa-solid fa-flask"></i><span>Test Fechas</span></a>
      <a href="/panel/logout" class="menu-btn danger"><i class="fa-solid fa-right-from-bracket"></i><span>Cerrar Sesión</span></a>
    </div>"""
    return HTMLResponse(page("Panel Admin","Panel de Administración — Tránsito Michoacán", contenido))


# ===================== FOLIOS =====================
@router.get("/panel/folios", response_class=HTMLResponse)
async def admin_folios(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    filtro  = request.query_params.get("filtro","").strip()
    crit    = request.query_params.get("criterio","folio")
    ep_fil  = request.query_params.get("estado_pago","todos")
    ev_fil  = request.query_params.get("estado_vigencia","todos")
    msg     = request.query_params.get("msg","")
    pdf_url = _pdf_seguro(request.query_params.get("pdf",""))
    modal_html = ""
    if pdf_url:
        modal_html = f"""<div class="modal-overlay" id="mD">
  <div class="modal-box">
    <div style="font-size:48px;margin-bottom:12px">📄</div>
    <h2 style="color:{C1};font-size:18px;font-weight:700;margin-bottom:8px">Permiso Generado</h2>
    <p style="color:#666;font-size:13px;margin-bottom:20px">¿Deseas descargar el PDF?</p>
    <div style="display:flex;gap:8px;justify-content:center">
      <a href="{_esc(pdf_url)}" target="_blank" class="btn btn-primary btn-sm" onclick="document.getElementById('mD').remove()" style="width:auto"><i class="fa-solid fa-download"></i> Descargar</a>
      <button class="btn btn-outline btn-sm" onclick="document.getElementById('mD').remove()">Cerrar</button>
    </div>
  </div>
</div>"""
    try:
        q = supabase.table("folios_registrados").select("*").eq("entidad",ENTIDAD)
        if filtro: q = q.ilike(crit, f"%{filtro}%")
        if ep_fil != "todos": q = q.eq("estado_pago", ep_fil)
        folios = q.order("fecha_expedicion", desc=True).execute().data or []
        tz = ZoneInfo(TZ); hoy = datetime.now(tz).date()
        for f in folios:
            try:
                fv = datetime.fromisoformat(f["fecha_vencimiento"]).date()
                f["estado_calc"] = "VIGENTE" if hoy <= fv else "VENCIDO"
            except: f["estado_calc"] = "ERROR"
        if ev_fil != "todos": folios = [f for f in folios if f.get("estado_calc","") == ev_fil]
    except Exception as e: folios = []; print(f"[FOLIOS] Error: {e}")
    msg_html = f'<div class="alert alert-ok">{_esc(msg)}</div>' if msg else ""
    filas = ""
    for f in folios:
        folio_id = f.get("folio","")
        pago = f.get("estado_pago","VALIDADO") or "VALIDADO"
        ec   = f.get("estado_calc","")
        bp   = f'<span class="bp bp-p">PEND</span>' if pago=="PENDIENTE_PAGO" else f'<span class="bp bp-v">OK</span>'
        be   = f'<span class="bp bp-vig">VIG</span>' if ec=="VIGENTE" else f'<span class="bp bp-ven">VEN</span>'
        if folio_id in timers_activos:
            bt = '<span class="bp bp-t">⏱ ON</span>'
            btn_timer = f'<form method="POST" action="/panel/timer/detener/{folio_id}" style="display:inline"><button class="btn btn-warn btn-sm" onclick="return confirm(\'¿Detener timer? El folio NO se borra.\')">⏹️</button></form> '
        else:
            bt = '<span class="bp bp-td">⏱ OFF</span>'
            btn_timer = ""
        bval = f'<form method="POST" action="/panel/validar/{folio_id}" style="display:inline"><button class="btn btn-success btn-sm" onclick="return confirm(\'¿Validar?\')">✅</button></form> ' if pago=="PENDIENTE_PAGO" else ""
        pdf  = f.get("pdf_url","")
        bpdf = f'<a href="{pdf}" target="_blank" class="btn btn-sm" style="background:{C1};color:white">📄</a> ' if pdf else ""
        filas += f"""<tr>
          <td><strong style="color:{C1}">{folio_id}</strong><br><small style="color:#999">{f.get("creado_por","")}</small></td>
          <td>{(f.get("nombre","") or "")[:18]}</td>
          <td>{f.get("marca","")} {f.get("linea","")}<br><small>{f.get("anio","")}</small></td>
          <td>{str(f.get("fecha_expedicion",""))[:10]}<br>{str(f.get("fecha_vencimiento",""))[:10]}</td>
          <td>{be} {bp}<br>{bt}</td>
          <td>{btn_timer}{bval}{bpdf}<a href="/consulta/{folio_id}" target="_blank" class="btn btn-sm btn-outline">🔗</a></td>
        </tr>"""
    filtros = f"""<div class="filter-bar">
      <form method="GET" style="display:contents">
        <input type="text" name="filtro" class="form-control" value="{_esc(filtro)}" placeholder="Buscar...">
        <select name="criterio" class="form-control" style="max-width:100px">
          <option value="folio" {"selected" if crit=="folio" else ""}>Folio</option>
          <option value="nombre" {"selected" if crit=="nombre" else ""}>Nombre</option>
          <option value="numero_serie" {"selected" if crit=="numero_serie" else ""}>Serie</option>
        </select>
        <select name="estado_pago" class="form-control" style="max-width:100px">
          <option value="todos" {"selected" if ep_fil=="todos" else ""}>Todos</option>
          <option value="PENDIENTE_PAGO" {"selected" if ep_fil=="PENDIENTE_PAGO" else ""}>Pendiente</option>
          <option value="VALIDADO" {"selected" if ep_fil=="VALIDADO" else ""}>Validado</option>
        </select>
        <select name="estado_vigencia" class="form-control" style="max-width:100px">
          <option value="todos" {"selected" if ev_fil=="todos" else ""}>Todos</option>
          <option value="VIGENTE" {"selected" if ev_fil=="VIGENTE" else ""}>Vigente</option>
          <option value="VENCIDO" {"selected" if ev_fil=="VENCIDO" else ""}>Vencido</option>
        </select>
        <button type="submit" class="btn btn-primary btn-sm" style="width:auto">Filtrar</button>
        <a href="/panel/folios" class="btn btn-outline btn-sm">✕</a>
      </form>
      <span style="font-size:12px;color:#888">{len(folios)} resultados</span>
    </div>"""
    contenido = f"""{modal_html}
    <p class="page-title">Folios Registrados</p>
    {msg_html}{filtros}
    <div class="tabla-wrap"><table>
      <thead><tr><th>Folio</th><th>Titular</th><th>Vehículo</th><th>Fechas</th><th>Estado</th><th>Acc.</th></tr></thead>
      <tbody>{filas or '<tr><td colspan="6" style="text-align:center;color:#999;padding:20px">Sin folios</td></tr>'}</tbody>
    </table></div>"""
    return HTMLResponse(page("Folios","Folios Registrados — Michoacán", contenido))

@router.post("/panel/validar/{folio}")
async def validar_pago(request: Request, folio: str):
    """Valida el pago desde la web. Detiene el timer igual que el bot de Telegram."""
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    r = await detener_timer_global(folio, "panel_web_validar", estado_pago="VALIDADO")
    if not r["ok"]:
        return RedirectResponse(url=f"/panel/folios?msg={quote(f'⚠️ Folio {folio.upper()} no encontrado')}", status_code=303)
    with suppress(Exception):
        await asyncio.to_thread(lambda: supabase.table("folios_registrados").update({
            "fecha_comprobante": datetime.now().isoformat()
        }).eq("folio", r["folio"]).execute())
    if r.get("user_id"):
        with suppress(Exception):
            await bot.send_message(r["user_id"],
                f"✅ PAGO VALIDADO — MICHOACÁN\nFolio: {r['folio']}\nTitular: {r.get('nombre','')}\n"
                f"Tu permiso está activo.\n\n📋 Use /michoacan para otro permiso.")
    aviso = "Folio " + r["folio"] + " validado ✅ (timer detenido en Telegram también)"
    return RedirectResponse(url=f"/panel/folios?msg={quote(aviso)}", status_code=303)

@router.get("/panel/pdf/{folio}")
async def descargar_pdf_panel(folio: str, request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    folio = folio.strip().upper()
    try:
        res = supabase.table("folios_registrados").select("pdf_url").eq("folio",folio).execute()
        if res.data and res.data[0].get("pdf_url"): return RedirectResponse(url=res.data[0]["pdf_url"])
    except Exception: pass
    ruta = os.path.join(OUTPUT_DIR, f"{folio}.pdf")
    if os.path.exists(ruta):
        from fastapi.responses import FileResponse
        return FileResponse(ruta, media_type="application/pdf", filename=f"{folio}_michoacan.pdf")
    return HTMLResponse(f"<p>PDF no encontrado.</p><a href='/panel/folios'>← Volver</a>", status_code=404)

# ===================== REGISTRO ADMIN =====================
@router.get("/panel/registro_admin", response_class=HTMLResponse)
async def registro_admin_get(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    tz = ZoneInfo(TZ); hoy = datetime.now(tz).strftime("%Y-%m-%d")
    err = request.query_params.get("error","")
    err_html = f'<div class="alert alert-err">{_esc(err)}</div>' if err else ""
    contenido = f"""
    <p class="page-title">Registrar Permiso</p>{err_html}
    <div class="form-card">
      <form method="POST" action="/panel/registro_admin">
        <div class="mb-3"><label class="form-label">Folio manual <small style="color:#999;font-weight:400">(vacío = auto)</small></label>
          <input type="text" name="folio" class="form-control" placeholder="{FOLIO_NUM_PREF}1234" style="text-transform:uppercase"></div>
        <div class="row-2">
          <div class="mb-3"><label class="form-label">Marca *</label><input type="text" name="marca" class="form-control" required style="text-transform:uppercase"></div>
          <div class="mb-3"><label class="form-label">Línea *</label><input type="text" name="linea" class="form-control" required style="text-transform:uppercase"></div>
        </div>
        <div class="row-2">
          <div class="mb-3"><label class="form-label">Tipo *</label><input type="text" name="tipo" class="form-control" required placeholder="PICK-UP, SEDÁN..." style="text-transform:uppercase"></div>
          <div class="mb-3"><label class="form-label">Clase *</label><input type="text" name="clase" class="form-control" required placeholder="CARGA, PASAJEROS..." style="text-transform:uppercase"></div>
        </div>
        <div class="row-3">
          <div class="mb-3"><label class="form-label">Año *</label><input type="text" name="anio" class="form-control" maxlength="4" required></div>
          <div class="mb-3" style="grid-column:span 2"><label class="form-label">Color *</label><input type="text" name="color" class="form-control" required style="text-transform:uppercase"></div>
        </div>
        <div class="mb-3"><label class="form-label">Núm. Serie *</label><input type="text" name="numero_serie" class="form-control" required style="text-transform:uppercase"></div>
        <div class="mb-3"><label class="form-label">Núm. Motor *</label><input type="text" name="numero_motor" class="form-control" required style="text-transform:uppercase"></div>
        <div class="mb-3"><label class="form-label">Nombre del titular *</label><input type="text" name="nombre" class="form-control" required style="text-transform:uppercase"></div>
        <div class="row-2">
          <div class="mb-3"><label class="form-label">Fecha expedición</label><input type="date" name="fecha_expedicion" class="form-control" value="{hoy}"></div>
          <div class="mb-3"><label class="form-label">Vencimiento <small style="color:#999">(vacío=+30d)</small></label><input type="date" name="fecha_vencimiento" class="form-control"></div>
        </div>
        <button type="submit" class="btn btn-primary mt-3"><i class="fa-solid fa-file-circle-plus"></i> Generar Permiso</button>
      </form>
    </div>"""
    return HTMLResponse(page("Registrar Permiso","Registrar Permiso — Michoacán", contenido))

@router.post("/panel/registro_admin")
async def registro_admin_post(request: Request,
    folio: str = Form(None), marca: str = Form(...), linea: str = Form(...),
    tipo: str = Form(""), clase: str = Form(""), anio: str = Form(...),
    color: str = Form(""), numero_serie: str = Form(...), numero_motor: str = Form(""),
    nombre: str = Form(...), fecha_expedicion: str = Form(None), fecha_vencimiento: str = Form(None)):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    try:
        tz = ZoneInfo(TZ)
        fg = folio.strip().upper() if folio and folio.strip() else generar_folio()
        fe = datetime.fromisoformat(fecha_expedicion).date() if fecha_expedicion and fecha_expedicion.strip() else datetime.now(tz).date()
        fv = datetime.fromisoformat(fecha_vencimiento).date() if fecha_vencimiento and fecha_vencimiento.strip() else fe + timedelta(days=30)
        datos_pdf = {"folio": fg, "marca": marca.upper(), "linea": linea.upper(), "anio": anio,
            "tipo": tipo.upper(), "clase": clase.upper(),
            "serie": numero_serie.upper(), "motor": numero_motor.upper(),
            "color": color.upper(), "nombre": nombre.upper(),
            "fecha_exp": fe.strftime("%d/%m/%Y"), "fecha_ven": fv.strftime("%d/%m/%Y"),
            "fecha_exp_dt": datetime.combine(fe, datetime.min.time()).replace(tzinfo=tz)}
        # Permiso de admin: nace VALIDADO y SIN timer
        supabase.table("folios_registrados").insert({"folio": fg, "marca": marca.upper(), "linea": linea.upper(),
            "anio": anio, "numero_serie": numero_serie.upper(), "numero_motor": numero_motor.upper(),
            "color": color.upper(), "nombre": nombre.upper(), "fecha_expedicion": fe.isoformat(),
            "fecha_vencimiento": fv.isoformat(), "entidad": ENTIDAD, "estado": "ACTIVO",
            "estado_pago": "VALIDADO",
            "creado_por": request.session.get("username","admin")}).execute()
        pdf_url = await asyncio.to_thread(generar_subir_y_guardar_pdf, datos_pdf)
        return RedirectResponse(url=f"/panel/folios?msg={quote(f'Permiso {fg} generado ✅')}&pdf={quote(pdf_url or '')}", status_code=303)
    except Exception as e:
        print(f"[REGISTRO ADMIN] Error: {e}")
        return RedirectResponse(url=f"/panel/registro_admin?error={quote(str(e))}", status_code=303)

# ===================== CREAR USUARIO =====================
@router.get("/panel/crear_usuario", response_class=HTMLResponse)
async def crear_usuario_get(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    msg = request.query_params.get("msg",""); err = request.query_params.get("error","")
    contenido = f"""
    <p class="page-title">Crear Usuario</p>
    {"<div class='alert alert-ok'>"+_esc(msg)+"</div>" if msg else ""}
    {"<div class='alert alert-err'>"+_esc(err)+"</div>" if err else ""}
    <div class="form-card">
      <form method="POST" action="/panel/crear_usuario">
        <div class="mb-3"><label class="form-label">Usuario *</label><input type="text" name="username" class="form-control" required autocomplete="off"></div>
        <div class="mb-3"><label class="form-label">Contraseña *</label><input type="password" name="password" class="form-control" required></div>
        <div class="mb-4"><label class="form-label">Folios asignados *</label><input type="number" name="folios" class="form-control" min="1" required></div>
        <button type="submit" class="btn btn-primary"><i class="fa-solid fa-user-plus"></i> Crear Usuario</button>
      </form>
    </div>"""
    return HTMLResponse(page("Crear Usuario","Crear Usuario — Michoacán", contenido))

@router.post("/panel/crear_usuario")
async def crear_usuario_post(request: Request,
    username: str = Form(...), password: str = Form(...), folios: int = Form(...)):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    try:
        existe = supabase.table("verificacion_michoacan").select("id").eq("username", username).execute()
        if existe.data: return RedirectResponse(url=f"/panel/crear_usuario?error={quote('El usuario ya existe')}", status_code=303)
        supabase.table("verificacion_michoacan").insert({"username": username, "password": password, "folios_asignac": folios, "folios_usados": 0}).execute()
        return RedirectResponse(url=f"/panel/crear_usuario?msg={quote(f'Usuario {username} creado con {folios} folios ✅')}", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/panel/crear_usuario?error={quote(str(e))}", status_code=303)

# ===================== TEST FECHAS =====================
@router.get("/panel/test_fechas", response_class=HTMLResponse)
async def test_fechas_get(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    fb = request.query_params.get("folio","").strip().upper()
    msg = request.query_params.get("msg",""); resultado = None
    if fb:
        try:
            r = supabase.table("folios_registrados").select("*").eq("folio",fb).execute()
            resultado = (r.data or [None])[0]
        except Exception as e: msg = f"Error: {e}"
    info_html = acc_html = ""
    if resultado:
        timer_txt = "🟢 ACTIVO (RAM)" if resultado.get("folio") in timers_activos else "⚪ SIN TIMER"
        info_html = f"""<div class="info-box">
          <strong>Folio:</strong> {resultado.get("folio","")}<br>
          <strong>Estado pago:</strong> {resultado.get("estado_pago","")}<br>
          <strong>Estado:</strong> {resultado.get("estado","")}<br>
          <strong>Timer:</strong> {timer_txt}<br>
          <strong>Expedición:</strong> {str(resultado.get("fecha_expedicion",""))[:10]}<br>
          <strong>Vencimiento:</strong> {str(resultado.get("fecha_vencimiento",""))[:10]}<br>
          <a href="/consulta/{resultado.get('folio','')}" target="_blank" style="color:{C1}">🔗 Ver consulta pública</a>
        </div>"""
        acc_html = f"""<form method="POST" action="/panel/test_fechas">
          <input type="hidden" name="folio" value="{resultado.get('folio','')}">
          <button type="submit" name="accion" value="vencer" class="btn mb-3" style="background:#b38b00;color:white;width:100%">⏰ Marcar VENCIDO</button>
          <button type="submit" name="accion" value="restaurar" class="btn" style="background:#1a6e2e;color:white;width:100%">✅ Restaurar vigencia</button>
        </form>
        <form method="POST" action="/panel/timer/detener/{resultado.get('folio','')}" class="mt-3">
          <button type="submit" class="btn btn-warn" style="width:100%">⏹️ Detener timer (sincroniza con Telegram)</button>
        </form>
        <form method="POST" action="/panel/timer/reiniciar/{resultado.get('folio','')}" class="mt-3">
          <button type="submit" class="btn" style="background:#2980b9;color:white;width:100%">🔄 Reiniciar timer 36h</button>
        </form>"""
    contenido = f"""
    <p class="page-title">🧪 Test Fechas</p>
    {"<div class='alert alert-ok'>"+_esc(msg)+"</div>" if msg else ""}
    <div class="form-card">
      <form method="GET">
        <div class="mb-3"><label class="form-label">Folio</label>
          <input type="text" name="folio" class="form-control" placeholder="{FOLIO_NUM_PREF}1234" value="{_esc(fb)}" style="text-transform:uppercase"></div>
        <button type="submit" class="btn btn-primary mb-3">Buscar</button>
      </form>{info_html}{acc_html}
    </div>"""
    return HTMLResponse(page("Test Fechas","Test Fechas — Michoacán", contenido))

@router.post("/panel/test_fechas")
async def test_fechas_post(request: Request, folio: str = Form(...), accion: str = Form(...)):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    folio = folio.strip().upper(); tz = ZoneInfo(TZ); msg = ""
    try:
        if accion == "vencer":
            supabase.table("folios_registrados").update({"fecha_vencimiento":(datetime.now(tz)-timedelta(days=1)).date().isoformat()}).eq("folio",folio).execute()
            msg = f"Folio {folio} marcado VENCIDO."
        elif accion == "restaurar":
            hoy = datetime.now(tz)
            supabase.table("folios_registrados").update({"fecha_expedicion":hoy.date().isoformat(),"fecha_vencimiento":(hoy+timedelta(days=30)).date().isoformat()}).eq("folio",folio).execute()
            msg = f"Folio {folio} restaurado."
    except Exception as e: msg = f"Error: {e}"
    return RedirectResponse(url=f"/panel/test_fechas?folio={folio}&msg={quote(msg)}", status_code=303)
