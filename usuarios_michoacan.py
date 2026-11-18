"""MICHOACÁN — portal de usuarios terceros (con cupo de folios): registro y «Mis permisos»."""
import asyncio
import html as html_lib
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from config_michoacan import supabase, ENTIDAD, TZ, C1
from ui_michoacan import page
from folios_michoacan import generar_folio
from pdf_michoacan import generar_subir_y_guardar_pdf

router = APIRouter()
_esc = html_lib.escape

# ===================== REGISTRO USUARIO 3RO =====================
@router.get("/registro_usuario", response_class=HTMLResponse)
async def registro_usuario_get(request: Request):
    if not request.session.get("username") or request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    ud = supabase.table("verificacion_michoacan").select("*").eq("username", request.session["username"]).limit(1).execute()
    if not ud.data: return RedirectResponse(url="/panel/login", status_code=303)
    u = ud.data[0]; asig = int(u.get("folios_asignac",0)); usad = int(u.get("folios_usados",0))
    disp = asig - usad; porc = round((usad/asig*100) if asig else 0, 1)
    tz = ZoneInfo(TZ); hoy = datetime.now(tz).strftime("%Y-%m-%d")
    msg = request.query_params.get("msg",""); err = request.query_params.get("error","")
    form_html = f"""<div class="form-card">
      <form method="POST" action="/registro_usuario">
        <div class="row-2">
          <div class="mb-3"><label class="form-label">Marca *</label><input type="text" name="marca" class="form-control" required style="text-transform:uppercase"></div>
          <div class="mb-3"><label class="form-label">Línea *</label><input type="text" name="linea" class="form-control" required style="text-transform:uppercase"></div>
        </div>
        <div class="row-2">
          <div class="mb-3"><label class="form-label">Tipo *</label><input type="text" name="tipo" class="form-control" required placeholder="PICK-UP, SEDÁN..." style="text-transform:uppercase"></div>
          <div class="mb-3"><label class="form-label">Clase *</label><input type="text" name="clase" class="form-control" required placeholder="CARGA, PASAJEROS..." style="text-transform:uppercase"></div>
        </div>
        <div class="row-3">
          <div class="mb-3"><label class="form-label">Año *</label><input type="number" name="anio" class="form-control" required></div>
          <div class="mb-3" style="grid-column:span 2"><label class="form-label">Color *</label><input type="text" name="color" class="form-control" required style="text-transform:uppercase"></div>
        </div>
        <div class="mb-3"><label class="form-label">Núm. Serie *</label><input type="text" name="serie" class="form-control" required style="text-transform:uppercase"></div>
        <div class="mb-3"><label class="form-label">Núm. Motor *</label><input type="text" name="motor" class="form-control" required style="text-transform:uppercase"></div>
        <div class="mb-3"><label class="form-label">Nombre del titular *</label><input type="text" name="nombre" class="form-control" required style="text-transform:uppercase"></div>
        <div class="mb-4"><label class="form-label">Fecha inicio vigencia</label><input type="date" name="fecha_inicio" class="form-control" value="{hoy}" min="{hoy}"></div>
        <button type="submit" id="btnReg" class="btn btn-primary">Registrar Folio</button>
      </form>
    </div>""" if disp > 0 else '<div class="alert alert-err">Sin folios disponibles. Contacta al administrador.</div>'
    contenido = f"""
    <p class="page-title">Registrar Permiso — Michoacán</p>
    <div class="form-card mb-3">
      <div style="display:flex;justify-content:space-between;margin-bottom:8px">
        <span style="font-weight:700;font-size:14px">Mis Folios</span>
        <span style="font-size:12px;color:#888">{usad} / {asig}</span>
      </div>
      <div class="barra-c"><div class="barra-p" style="width:{porc}%">{porc}%</div></div>
      <div style="display:flex;justify-content:space-between;font-size:11px;color:#888;margin-top:4px">
        <span>Usados: <strong>{usad}</strong></span><span>Total: <strong>{asig}</strong></span><span>Disponibles: <strong style="color:{C1}">{disp}</strong></span>
      </div>
    </div>
    {"<div class='alert alert-ok'>"+_esc(msg)+"</div>" if msg else ""}
    {"<div class='alert alert-err'>"+_esc(err)+"</div>" if err else ""}
    {form_html}
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
      <a href="/mis_permisos" class="btn btn-outline btn-sm">📋 Mis Permisos</a>
      <a href="/consulta_folio" class="btn btn-outline btn-sm">🔍 Consultar</a>
      <a href="/panel/logout" class="btn btn-danger btn-sm">🚪 Salir</a>
    </div>"""
    scripts = """<script>
document.querySelector('form[action="/registro_usuario"]')&&document.querySelector('form[action="/registro_usuario"]').addEventListener('submit',function(){
  const btn=document.getElementById('btnReg');
  if(btn){btn.disabled=true;btn.textContent='⏳ Generando...';}
  setTimeout(()=>{if(btn){btn.disabled=false;btn.textContent='Registrar Folio';}},12000);
});
</script>"""
    return HTMLResponse(page("Registrar Permiso","Registro de Permisos", contenido, scripts))

@router.post("/registro_usuario")
async def registro_usuario_post(request: Request,
    marca: str = Form(...), linea: str = Form(...), tipo: str = Form(""),
    clase: str = Form(""), anio: str = Form(...), color: str = Form(""),
    serie: str = Form(...), motor: str = Form(""), nombre: str = Form(...),
    fecha_inicio: str = Form(None)):
    if not request.session.get("username") or request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    try:
        ud = supabase.table("verificacion_michoacan").select("*").eq("username", request.session["username"]).limit(1).execute()
        if not ud.data: return RedirectResponse(url="/panel/login", status_code=303)
        u = ud.data[0]; asig = int(u.get("folios_asignac",0)); usad = int(u.get("folios_usados",0))
        if asig - usad <= 0: return RedirectResponse(url=f"/registro_usuario?error={quote('Sin folios disponibles')}", status_code=303)
        tz = ZoneInfo(TZ)
        fe = datetime.strptime(fecha_inicio, "%Y-%m-%d").replace(tzinfo=tz) if fecha_inicio else datetime.now(tz)
        fv = fe + timedelta(days=30); fg = generar_folio()
        # Folio de usuario con cupo: nace VALIDADO y SIN timer
        supabase.table("folios_registrados").insert({"folio": fg, "marca": marca.upper(), "linea": linea.upper(),
            "anio": anio, "numero_serie": serie.upper(), "numero_motor": motor.upper(),
            "color": color.upper(), "nombre": nombre.upper(), "fecha_expedicion": fe.date().isoformat(),
            "fecha_vencimiento": fv.date().isoformat(), "entidad": ENTIDAD, "estado": "ACTIVO",
            "estado_pago": "VALIDADO",
            "user_id": request.session.get("user_id"),
            "creado_por": request.session["username"]}).execute()
        datos_pdf = {"folio": fg, "marca": marca.upper(), "linea": linea.upper(), "anio": anio,
            "tipo": tipo.upper(), "clase": clase.upper(), "serie": serie.upper(),
            "motor": motor.upper(), "color": color.upper(), "nombre": nombre.upper(),
            "fecha_exp": fe.strftime("%d/%m/%Y"), "fecha_ven": fv.strftime("%d/%m/%Y"), "fecha_exp_dt": fe}
        pdf_url = await asyncio.to_thread(generar_subir_y_guardar_pdf, datos_pdf)
        supabase.table("verificacion_michoacan").update({"folios_usados": usad+1}).eq("username", request.session["username"]).execute()
        contenido = f"""
        <p class="page-title">✅ Permiso Generado</p>
        <div class="form-card" style="text-align:center">
          <div style="font-size:52px;margin-bottom:12px">📄</div>
          <h2 style="color:{C1};font-size:24px;font-weight:700;margin-bottom:4px">{fg}</h2>
          <div class="info-box" style="text-align:left">
            <strong>Vehículo:</strong> {marca.upper()} {linea.upper()} {anio}<br>
            <strong>Tipo:</strong> {tipo.upper()} · <strong>Clase:</strong> {clase.upper()}<br>
            <strong>Serie:</strong> {serie.upper()} · <strong>Motor:</strong> {motor.upper()}<br>
            <strong>Color:</strong> {color.upper()}<br>
            <strong>Titular:</strong> {nombre.upper()}<br>
            <strong>Vigencia:</strong> {fe.strftime("%d/%m/%Y")} — {fv.strftime("%d/%m/%Y")}
          </div>
          {"<a href='"+pdf_url+"' target='_blank' class='btn btn-primary mb-3'><i class='fa-solid fa-download'></i> Descargar PDF</a>" if pdf_url else ""}
          <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
            <a href="/mis_permisos" class="btn btn-outline btn-sm">📋 Mis Permisos</a>
            <a href="/registro_usuario" class="btn btn-primary btn-sm" style="width:auto">+ Nuevo</a>
          </div>
        </div>"""
        return HTMLResponse(page("Permiso Generado","Registro Exitoso", contenido))
    except Exception as e:
        print(f"[REG USUARIO] Error: {e}")
        return RedirectResponse(url=f"/registro_usuario?error={quote(str(e))}", status_code=303)

@router.get("/mis_permisos", response_class=HTMLResponse)
async def mis_permisos(request: Request):
    if not request.session.get("username") or request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    permisos = supabase.table("folios_registrados").select("*").eq("creado_por", request.session["username"]).order("fecha_expedicion", desc=True).execute().data or []
    tz = ZoneInfo(TZ); hoy = datetime.now(tz).date()
    for p in permisos:
        try:
            fv = datetime.fromisoformat(p["fecha_vencimiento"]).date()
            fe = datetime.fromisoformat(p["fecha_expedicion"]).date()
            p["fe_fmt"] = fe.strftime("%d/%m/%Y"); p["estado_calc"] = "VIGENTE" if hoy <= fv else "VENCIDO"
        except: p["fe_fmt"] = p["estado_calc"] = "ERROR"
    ud = supabase.table("verificacion_michoacan").select("folios_asignac,folios_usados").eq("username", request.session["username"]).limit(1).execute().data
    ud = ud[0] if ud else {"folios_asignac":0,"folios_usados":0}
    asig = int(ud.get("folios_asignac",0)); usad = int(ud.get("folios_usados",0))
    vig  = len([p for p in permisos if p.get("estado_calc")=="VIGENTE"])
    filas = ""
    for p in permisos:
        ec  = p.get("estado_calc","")
        be  = f'<span class="bp bp-vig">VIG</span>' if ec=="VIGENTE" else f'<span class="bp bp-ven">VEN</span>'
        pdf = p.get("pdf_url","")
        btn = f'<a href="{pdf}" target="_blank" class="btn btn-sm" style="background:{C1};color:white">📥</a> ' if pdf else ""
        filas += f"""<tr>
          <td><strong style="color:{C1}">{p.get("folio","")}</strong></td>
          <td>{p.get("marca","")} {p.get("linea","")}<br><small>{p.get("anio","")}</small></td>
          <td style="font-size:11px">{p.get("numero_serie","")}</td>
          <td>{p.get("fe_fmt","")}</td><td>{be}</td>
          <td>{btn}<a href="/consulta/{p.get('folio','')}" target="_blank" class="btn btn-sm btn-outline">🔗</a></td>
        </tr>"""
    contenido = f"""
    <p class="page-title">📋 Mis Permisos</p>
    <div class="grid mb-3">
      <div class="stat-card"><div class="stat-num">{asig}</div><div class="stat-lbl">Asignados</div></div>
      <div class="stat-card"><div class="stat-num">{asig-usad}</div><div class="stat-lbl">Disponibles</div></div>
      <div class="stat-card"><div class="stat-num" style="color:#1a6e2e">{vig}</div><div class="stat-lbl">Vigentes</div></div>
      <div class="stat-card"><div class="stat-num" style="color:{C1}">{len(permisos)}</div><div class="stat-lbl">Total</div></div>
    </div>
    <div class="tabla-wrap"><table>
      <thead><tr><th>Folio</th><th>Vehículo</th><th>Serie</th><th>Fecha</th><th>Estado</th><th>Acc.</th></tr></thead>
      <tbody>{filas or '<tr><td colspan="6" style="text-align:center;color:#999;padding:20px">Sin permisos</td></tr>'}</tbody>
    </table></div>
    <div style="display:flex;gap:8px;margin-top:12px">
      <a href="/registro_usuario" class="btn btn-primary btn-sm" style="width:auto">+ Nuevo</a>
      <a href="/panel/logout" class="btn btn-danger btn-sm">🚪 Salir</a>
    </div>"""
    return HTMLResponse(page("Mis Permisos","Mis Permisos — Michoacán", contenido))
