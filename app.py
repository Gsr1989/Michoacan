from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from supabase import create_client, Client
import os
from contextlib import asynccontextmanager, suppress
from starlette.middleware.sessions import SessionMiddleware
import asyncio
import random

# ===================== CONFIG =====================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
BASE_URL     = os.getenv("BASE_URL", "https://https-michoacan-gob-mx-tramites-permiso.onrender.com").rstrip("/")
ENTIDAD      = "michoacan"
TZ           = "America/Mexico_City"

ADMIN_USER = "Serg890105tm3"
ADMIN_PASS = "Serg890105tm3"

STATIC_DIR    = "static"
BUCKET_NAME   = "permisos-michoacan"
OUTPUT_DIR    = "documentos"
PLANTILLA_PDF = "michoacan_permiso.pdf"

FOLIO_PREFIJO  = "MCH"
FOLIO_NUM_PREF = "620"
_folio_counter = {"siguiente": 1}
_folio_lock    = asyncio.Lock()

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

C1 = "#4a001f"
C2 = "#3a0018"
C3 = "#6A0F49"

PAGE_SIZE = 100

TABLAS_DISPONIBLES = {
    "folios_registrados": {
        "nombre": "Folios Registrados", "pk_col": "folio",
        "columnas": ["folio","marca","linea","anio","numero_serie","numero_motor","color","nombre",
                     "fecha_expedicion","fecha_vencimiento","entidad","estado","estado_pago","creado_por","pdf_url"],
    },
    "verificacion_michoacan": {
        "nombre": "Usuarios del Sistema", "pk_col": "id",
        "columnas": ["id","username","password","folios_asignac","folios_usados"],
    },
    "folio_watermark": {
        "nombre": "Watermark Folios", "pk_col": "prefijo",
        "columnas": ["prefijo","ultimo_asignado"],
    },
}

# ===================== FOLIOS =====================
def _sb_leer_watermark():
    try:
        r = supabase.table("folio_watermark").select("ultimo_asignado").eq("prefijo", FOLIO_PREFIJO).execute()
        return r.data[0]["ultimo_asignado"] if r.data else None
    except: return None

def _sb_guardar_watermark(numero):
    try:
        supabase.table("folio_watermark").upsert({"prefijo": FOLIO_PREFIJO, "ultimo_asignado": numero}).execute()
    except Exception as e: print(f"[ERROR] guardar_watermark: {e}")

def _sb_inicializar_folio():
    wm = _sb_leer_watermark()
    if wm is not None:
        _folio_counter["siguiente"] = wm + 1
        print(f"[FOLIO] Desde watermark: siguiente={_folio_counter['siguiente']}"); return
    try:
        resp = supabase.table("folios_registrados").select("folio").eq("entidad", ENTIDAD).like("folio", f"{FOLIO_NUM_PREF}%").execute()
        nums = []
        for row in resp.data or []:
            f = row.get("folio","")
            if isinstance(f, str) and f.startswith(FOLIO_NUM_PREF):
                suf = f[len(FOLIO_NUM_PREF):]
                if suf.isdigit(): nums.append(int(suf))
        if nums:
            maximo = max(nums); _folio_counter["siguiente"] = maximo + 1; _sb_guardar_watermark(maximo)
        else:
            _folio_counter["siguiente"] = 1
    except Exception as e: print(f"[ERROR] inicializar_folio: {e}")

def _folio_existe(folio):
    try:
        r = supabase.table("folios_registrados").select("folio").eq("folio", folio).execute()
        return len(r.data) > 0
    except: return False

def _generar_folio_sync():
    candidato = _folio_counter["siguiente"]
    for _ in range(100_000):
        folio = f"{FOLIO_NUM_PREF}{candidato}"
        if not _folio_existe(folio):
            _folio_counter["siguiente"] = candidato + 1
            _sb_guardar_watermark(candidato)
            print(f"[FOLIO] Asignado: {folio}"); return folio
        candidato += 1
    return f"{FOLIO_NUM_PREF}{random.randint(50000,99999)}"

def generar_folio(): return _generar_folio_sync()

# ===================== HTML BASE =====================
CSS = f"""
*{{font-family:'Segoe UI',sans-serif;box-sizing:border-box;}}
body{{margin:0;background:#f4f4f4;}}
.navbar{{background:white;padding:12px 16px;display:flex;align-items:center;justify-content:space-between;border-bottom:3px solid {C3};position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.08);}}
.navbar img{{height:55px;object-fit:contain;max-width:220px;}}
.hamburger{{display:flex;flex-direction:column;gap:5px;cursor:pointer;padding:4px;}}
.hamburger span{{display:block;width:26px;height:3px;background:{C1};border-radius:2px;}}
.sidenav{{position:fixed;top:0;right:-280px;width:280px;height:100%;background:white;z-index:200;transition:.3s;box-shadow:-4px 0 20px rgba(0,0,0,.15);}}
.sidenav.open{{right:0;}}
.sidenav-header{{background:{C1};padding:20px 16px;color:white;}}
.sidenav-header img{{height:45px;filter:brightness(10);margin-bottom:8px;display:block;}}
.sidenav-header p{{margin:0;font-size:13px;opacity:.85;}}
.sidenav ul{{list-style:none;margin:0;padding:8px 0;}}
.sidenav ul li a{{display:flex;align-items:center;gap:12px;padding:14px 20px;color:#333;text-decoration:none;font-size:14px;font-weight:600;transition:.15s;border-bottom:1px solid #f0f0f0;}}
.sidenav ul li a:hover{{background:#fef5f7;color:{C1};}}
.sidenav ul li a i{{color:{C1};width:18px;text-align:center;}}
.sidenav ul li a.danger{{color:#c00;}} .sidenav ul li a.danger i{{color:#c00;}}
.overlay{{position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:199;display:none;}}
.overlay.show{{display:block;}}
.admin-bar{{background:{C1};color:white;padding:10px 16px;font-weight:700;font-size:13px;display:flex;align-items:center;gap:8px;}}
.content{{padding:16px;max-width:600px;margin:0 auto;}}
.stat-card{{background:white;border-radius:12px;padding:20px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:8px;}}
.stat-num{{font-size:36px;font-weight:700;color:{C1};line-height:1;}}
.stat-lbl{{font-size:11px;color:#888;font-weight:700;text-transform:uppercase;margin-top:6px;}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;}}
.grid-full{{grid-column:1/-1;}}
.menu-btn{{background:white;border:1.5px solid #e8e8e8;border-radius:12px;padding:22px 12px;text-align:center;text-decoration:none;color:#1d1d1b;display:block;transition:.2s;}}
.menu-btn:hover{{border-color:{C1};color:{C1};transform:translateY(-2px);box-shadow:0 4px 14px rgba(74,0,31,.15);}}
.menu-btn i{{font-size:28px;display:block;margin-bottom:8px;color:{C1};}}
.menu-btn span{{font-size:13px;font-weight:600;}}
.menu-btn.danger{{border-color:#e8e8e8;}}
.menu-btn.danger i{{color:#dc3545;}}
.menu-btn.danger:hover{{border-color:#dc3545;color:#dc3545;}}
table{{font-size:12px;width:100%;border-collapse:collapse;}}
thead th{{background:{C1};color:white;padding:10px 8px;text-align:left;white-space:nowrap;}}
tbody td{{padding:9px 8px;vertical-align:middle;border-bottom:1px solid #eee;}}
tbody tr:last-child td{{border-bottom:none;}} tbody tr:hover td{{background:#fef5f7;}}
.tabla-wrap{{overflow-x:auto;background:white;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.08);}}
.bp{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;color:white;}}
.bp-p{{background:#dc3545;}}.bp-v{{background:#1a6e2e;}}.bp-vig{{background:#1a6e2e;}}.bp-ven{{background:{C1};}}
.form-card{{background:white;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.08);}}
.form-label{{font-weight:600;font-size:14px;display:block;margin-bottom:4px;}}
.form-control{{display:block;width:100%;padding:10px 12px;border:1.5px solid #ddd;border-radius:8px;font-size:14px;transition:.2s;}}
.form-control:focus{{border-color:{C1};outline:none;box-shadow:0 0 0 3px rgba(74,0,31,.1);}}
.mb-3{{margin-bottom:14px;}} .mb-4{{margin-bottom:20px;}} .mt-3{{margin-top:14px;}} .mt-4{{margin-top:20px;}}
.btn{{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:11px 20px;border-radius:8px;font-weight:700;font-size:14px;border:none;cursor:pointer;text-decoration:none;transition:.2s;}}
.btn-primary{{background:{C1};color:white;width:100%;}}
.btn-primary:hover{{background:{C2};}}
.btn-sm{{padding:5px 12px;font-size:11px;border-radius:6px;}}
.btn-outline{{background:white;border:1.5px solid #ddd;color:#444;}}
.btn-outline:hover{{border-color:{C1};color:{C1};}}
.btn-danger{{background:#dc3545;color:white;}} .btn-danger:hover{{background:#b02a37;}}
.btn-success{{background:#1a6e2e;color:white;}} .btn-success:hover{{background:#145523;}}
.alert{{padding:12px 14px;border-radius:8px;margin-bottom:14px;font-size:13px;font-weight:600;}}
.alert-ok{{background:#d4edda;color:#155724;border:1px solid #c3e6cb;}}
.alert-err{{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;}}
.barra-c{{width:100%;height:24px;background:rgba(74,0,31,.12);border-radius:12px;overflow:hidden;margin:8px 0;}}
.barra-p{{height:100%;background:{C1};border-radius:12px;display:flex;align-items:center;justify-content:center;color:white;font-size:11px;font-weight:700;}}
.info-box{{background:#f8f8f8;border-radius:8px;padding:14px;font-size:13px;margin-bottom:14px;line-height:1.7;}}
.cv{{display:inline-block;min-width:50px;max-width:180px;overflow:hidden;text-overflow:ellipsis;cursor:text;padding:2px 4px;border-radius:4px;border:1px solid transparent;color:#333;}}
.cv:hover{{border-color:#ccc;background:#fff8f8;}}.cv.nv{{color:#ccc;font-style:italic;}}
.cell-input{{border:2px solid {C1};border-radius:4px;padding:3px 6px;font-size:12px;min-width:100px;max-width:220px;outline:none;background:#fff8f8;}}
.del-btn{{background:#fff;border:1px solid #ccc;color:#c00;border-radius:4px;padding:2px 7px;font-size:11px;cursor:pointer;}}
.del-btn:hover{{background:#c00;color:#fff;}}
.toast-f{{position:fixed;bottom:20px;right:16px;z-index:999;padding:10px 16px;border-radius:8px;font-size:13px;opacity:0;transition:opacity .25s;pointer-events:none;border:1px solid transparent;max-width:260px;}}
.toast-f.show{{opacity:1;}}.toast-f.ok{{background:#e6ffee;border-color:#060;color:#060;}}.toast-f.err{{background:#fff0f0;border-color:#c00;color:#c00;}}
.row-2{{display:grid;grid-template-columns:1fr 1fr;gap:12px;}}
.row-3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;}}
select.form-control{{appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23666' d='M6 8L1 3h10z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 12px center;padding-right:32px;}}
.filter-bar{{background:white;border-radius:12px;padding:14px;box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:14px;display:flex;flex-wrap:wrap;gap:8px;align-items:flex-end;}}
.filter-bar input,.filter-bar select{{flex:1;min-width:120px;}}
.page-title{{font-size:20px;font-weight:700;color:{C1};margin-bottom:16px;}}
.modal-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;}}
.modal-box{{background:white;border-radius:16px;padding:28px;max-width:360px;width:100%;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.3);}}
"""

JS_NAV = """
<script>
function openNav(){document.getElementById('sidenav').classList.add('open');document.getElementById('overlay').classList.add('show');}
function closeNav(){document.getElementById('sidenav').classList.remove('open');document.getElementById('overlay').classList.remove('show');}
document.addEventListener('DOMContentLoaded',function(){
  document.getElementById('overlay').addEventListener('click',closeNav);
});
</script>"""

FA = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css">'

def head(titulo):
    return f"""<!DOCTYPE html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titulo} — Michoacán</title>
<link rel="icon" href="https://michoacan.gob.mx/wp-content/uploads/2021/09/cropped-LogoGobMich-Escudo-Guinda-600-600-32x32.png" sizes="32x32"/>
{FA}
<style>{CSS}</style></head><body>"""

def navbar():
    return f"""
<nav class="navbar">
  <img src="https://michoacan.gob.mx/cdn/img/logo.svg?ver=6" alt="Michoacán">
  <div class="hamburger" onclick="openNav()"><span></span><span></span><span></span></div>
</nav>
<div class="overlay" id="overlay"></div>
<div class="sidenav" id="sidenav">
  <div class="sidenav-header">
    <img src="https://michoacan.gob.mx/cdn/img/logo.svg?ver=6" alt="Michoacán">
    <p>Dirección de Tránsito Estatal</p>
  </div>
  <ul>
    <li><a href="/panel/admin"><i class="fa-solid fa-house"></i>Inicio</a></li>
    <li><a href="/panel/folios"><i class="fa-solid fa-list-check"></i>Ver Folios</a></li>
    <li><a href="/panel/registro_admin"><i class="fa-solid fa-file-circle-plus"></i>Registrar Permiso</a></li>
    <li><a href="/panel/crear_usuario"><i class="fa-solid fa-user-plus"></i>Crear Usuario</a></li>
    <li><a href="/panel/tablas"><i class="fa-solid fa-database"></i>Tablas BD</a></li>
    <li><a href="/consulta_folio"><i class="fa-solid fa-magnifying-glass"></i>Consultar Folio</a></li>
    <li><a href="/panel/test_fechas"><i class="fa-solid fa-flask"></i>Test Fechas</a></li>
    <li><a href="/panel/logout" class="danger"><i class="fa-solid fa-right-from-bracket"></i>Cerrar Sesión</a></li>
  </ul>
</div>"""

def admin_bar(seccion):
    return f'<div class="admin-bar"><i class="fa-solid fa-shield-halved me-2"></i>{seccion}</div>'

def footer(scripts=""):
    return f"""{scripts}{JS_NAV}</body></html>"""

def page(titulo, seccion, contenido, scripts=""):
    return head(titulo) + navbar() + admin_bar(seccion) + f'<div class="content">{contenido}</div>' + footer(scripts)

# ===================== LOGIN =====================
def login_html(error=False):
    err = '<div class="alert alert-err mb-3"><i class="fa-solid fa-triangle-exclamation"></i> Usuario o contraseña incorrectos</div>' if error else ""
    return f"""<!DOCTYPE html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Acceso — Michoacán Tránsito</title>
<link rel="icon" href="https://michoacan.gob.mx/wp-content/uploads/2021/09/cropped-LogoGobMich-Escudo-Guinda-600-600-32x32.png" sizes="32x32"/>
{FA}
<style>
*{{font-family:'Segoe UI',sans-serif;box-sizing:border-box;}}
body{{background:{C1};min-height:100vh;margin:0;display:flex;flex-direction:column;}}
.lh{{background:white;padding:12px 20px;text-align:center;border-bottom:4px solid {C3};}}
.lh img{{height:60px;object-fit:contain;}}
.lw{{flex:1;display:flex;align-items:center;justify-content:center;padding:30px 15px;}}
.lc{{background:white;border-radius:16px;padding:32px;max-width:380px;width:100%;box-shadow:0 12px 40px rgba(0,0,0,.3);}}
.le{{text-align:center;margin-bottom:16px;}}.le img{{height:65px;}}
.lt{{text-align:center;font-size:20px;font-weight:700;color:{C1};margin-bottom:4px;}}
.ls{{text-align:center;font-size:12px;color:#777;margin-bottom:22px;}}
.form-label{{font-weight:600;font-size:14px;display:block;margin-bottom:4px;}}
.form-control{{display:block;width:100%;padding:11px 13px;border:1.5px solid #ddd;border-radius:8px;font-size:14px;font-family:inherit;}}
.form-control:focus{{border-color:{C1};outline:none;box-shadow:0 0 0 3px rgba(74,0,31,.1);}}
.mb-3{{margin-bottom:14px;}}.mb-4{{margin-bottom:20px;}}
.alert{{padding:11px 13px;border-radius:8px;font-size:13px;font-weight:600;}}
.alert-err{{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;}}
.btn-in{{background:{C1};border:none;color:white;width:100%;padding:13px;font-weight:700;font-size:15px;border-radius:8px;cursor:pointer;font-family:inherit;}}
.btn-in:hover{{background:{C2};}}
.lf{{background:rgba(0,0,0,.2);color:rgba(255,255,255,.7);text-align:center;padding:14px;font-size:12px;}}
</style></head><body>
<div class="lh"><img src="https://michoacan.gob.mx/cdn/img/logo.svg?ver=6" alt="Michoacán"></div>
<div class="lw"><div class="lc">
  <div class="le"><img src="https://michoacan.gob.mx/wp-content/uploads/2021/09/cropped-LogoGobMich-Escudo-Guinda-600-600-192x192.png" alt="Escudo"></div>
  <div class="lt">Tránsito Estatal</div>
  <div class="ls">Gobierno del Estado de Michoacán<br>Sistema Administrativo</div>
  {err}
  <form method="POST" action="/panel/login">
    <div class="mb-3"><label class="form-label">Usuario</label><input type="text" name="username" class="form-control" required autofocus autocomplete="off"></div>
    <div class="mb-4"><label class="form-label">Contraseña</label><input type="password" name="password" class="form-control" required></div>
    <button type="submit" class="btn-in"><i class="fa-solid fa-right-to-bracket"></i> &nbsp;Ingresar al Sistema</button>
  </form>
</div></div>
<div class="lf">Dirección de Tránsito Estatal — Gobierno del Estado de Michoacán © 2026</div>
</body></html>"""

# ===================== LIFESPAN =====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(_sb_inicializar_folio)
    print(f"[SISTEMA] Michoacán v1.0 — siguiente folio: {FOLIO_NUM_PREF}{_folio_counter['siguiente']}")
    yield

app = FastAPI(lifespan=lifespan, title="Tránsito Michoacán", version="1.0")
app.add_middleware(SessionMiddleware, secret_key="michoacan_clave_super_segura_123456")
try: app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
except Exception: pass

# ===================== AUTH =====================
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if request.session.get("admin"): return RedirectResponse(url="/panel/admin", status_code=303)
    if request.session.get("username"): return RedirectResponse(url="/registro_usuario", status_code=303)
    return RedirectResponse(url="/panel/login", status_code=303)

@app.get("/panel/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if request.session.get("admin"): return RedirectResponse(url="/panel/admin", status_code=303)
    return HTMLResponse(login_html(bool(request.query_params.get("error",""))))

@app.post("/panel/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        request.session["admin"] = True; request.session["username"] = username
        return RedirectResponse(url="/panel/admin", status_code=303)
    try:
        res = supabase.table("verificacion_michoacan").select("*").eq("username",username).eq("password",password).execute()
        if res.data:
            u = res.data[0]
            request.session["admin"] = False; request.session["username"] = u["username"]; request.session["user_id"] = u.get("id")
            return RedirectResponse(url="/registro_usuario", status_code=303)
    except Exception as e: print(f"[LOGIN] Error: {e}")
    return RedirectResponse(url="/panel/login?error=1", status_code=303)

@app.get("/panel/logout")
async def logout(request: Request):
    request.session.clear(); return RedirectResponse(url="/panel/login", status_code=303)

# ===================== PANEL ADMIN =====================
@app.get("/panel/admin", response_class=HTMLResponse)
async def panel_admin(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    pendientes = 0
    try:
        r = supabase.table("folios_registrados").select("folio").eq("estado_pago","PENDIENTE_PAGO").eq("entidad",ENTIDAD).execute()
        pendientes = len(r.data or [])
    except Exception: pass
    color_pend = "#dc3545" if pendientes else "#1a6e2e"
    contenido = f"""
    <div class="row-2 mb-3">
      <div class="stat-card"><div class="stat-num">0</div><div class="stat-lbl">Timers Activos</div></div>
      <div class="stat-card"><div class="stat-num" style="color:{color_pend}">{pendientes}</div><div class="stat-lbl">Pendientes Pago</div></div>
    </div>
    <div class="stat-card mb-3"><div class="stat-num">{FOLIO_NUM_PREF}{_folio_counter['siguiente']}</div><div class="stat-lbl">Siguiente Folio</div></div>
    <div class="grid">
      <a href="/panel/folios" class="menu-btn"><i class="fa-solid fa-list-check"></i><span>Ver Folios</span></a>
      <a href="/panel/registro_admin" class="menu-btn"><i class="fa-solid fa-file-circle-plus"></i><span>Registrar Permiso</span></a>
      <a href="/panel/crear_usuario" class="menu-btn"><i class="fa-solid fa-user-plus"></i><span>Crear Usuario</span></a>
      <a href="/panel/tablas" class="menu-btn"><i class="fa-solid fa-database"></i><span>Tablas BD</span></a>
      <a href="/consulta_folio" class="menu-btn"><i class="fa-solid fa-magnifying-glass"></i><span>Consultar Folio</span></a>
      <a href="/panel/test_fechas" class="menu-btn"><i class="fa-solid fa-flask"></i><span>Test Fechas</span></a>
      <a href="/panel/logout" class="menu-btn danger grid-full"><i class="fa-solid fa-right-from-bracket"></i><span>Cerrar Sesión</span></a>
    </div>"""
    return HTMLResponse(page("Panel Admin","Panel de Administración — Tránsito Michoacán", contenido))

# ===================== FOLIOS =====================
@app.get("/panel/folios", response_class=HTMLResponse)
async def admin_folios(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    filtro  = request.query_params.get("filtro","").strip()
    crit    = request.query_params.get("criterio","folio")
    ep_fil  = request.query_params.get("estado_pago","todos")
    ev_fil  = request.query_params.get("estado_vigencia","todos")
    msg     = request.query_params.get("msg","")
    pdf_url = request.query_params.get("pdf","")
    modal_html = ""
    if pdf_url:
        modal_html = f"""<div class="modal-overlay" id="mD">
  <div class="modal-box">
    <div style="font-size:48px;margin-bottom:12px">📄</div>
    <h2 style="color:{C1};font-size:18px;font-weight:700;margin-bottom:8px">Permiso Generado</h2>
    <p style="color:#666;font-size:13px;margin-bottom:20px">¿Deseas descargar el PDF?</p>
    <div style="display:flex;gap:8px;justify-content:center">
      <a href="{pdf_url}" target="_blank" class="btn btn-primary btn-sm" onclick="document.getElementById('mD').remove()" style="width:auto"><i class="fa-solid fa-download"></i> Descargar</a>
      <button class="btn btn-outline btn-sm" onclick="document.getElementById('mD').remove()">No, cerrar</button>
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
    msg_html = f'<div class="alert alert-ok">{msg}</div>' if msg else ""
    filas = ""
    for f in folios:
        pago = f.get("estado_pago","VALIDADO") or "VALIDADO"
        ec   = f.get("estado_calc","")
        bp   = f'<span class="bp bp-p">PEND</span>' if pago=="PENDIENTE_PAGO" else f'<span class="bp bp-v">OK</span>'
        be   = f'<span class="bp bp-vig">VIG</span>' if ec=="VIGENTE" else f'<span class="bp bp-ven">VEN</span>'
        bval = f'<form method="POST" action="/panel/validar/{f["folio"]}" style="display:inline"><button class="btn btn-success btn-sm" onclick="return confirm(\'¿Validar?\')">✅</button></form> ' if pago=="PENDIENTE_PAGO" else ""
        pdf  = f.get("pdf_url","")
        bpdf = f'<a href="{pdf}" target="_blank" class="btn btn-sm" style="background:{C1};color:white">📄</a> ' if pdf else ""
        filas += f"""<tr>
          <td><strong style="color:{C1}">{f.get("folio","")}</strong><br><small style="color:#999">{f.get("creado_por","")}</small></td>
          <td>{f.get("nombre","")[:20]}</td>
          <td>{f.get("marca","")} {f.get("linea","")}<br><small>{f.get("anio","")}</small></td>
          <td>{str(f.get("fecha_expedicion",""))[:10]}<br>{str(f.get("fecha_vencimiento",""))[:10]}</td>
          <td>{be} {bp}</td>
          <td>{bval}{bpdf}<a href="/consulta/{f.get('folio','')}" target="_blank" class="btn btn-sm btn-outline">🔗</a></td>
        </tr>"""
    filtros = f"""<div class="filter-bar">
      <form method="GET" style="display:contents">
        <input type="text" name="filtro" class="form-control" value="{filtro}" placeholder="Buscar folio, nombre...">
        <select name="criterio" class="form-control" style="max-width:110px">
          <option value="folio" {"selected" if crit=="folio" else ""}>Folio</option>
          <option value="nombre" {"selected" if crit=="nombre" else ""}>Nombre</option>
          <option value="numero_serie" {"selected" if crit=="numero_serie" else ""}>Serie</option>
        </select>
        <select name="estado_pago" class="form-control" style="max-width:110px">
          <option value="todos" {"selected" if ep_fil=="todos" else ""}>Todos</option>
          <option value="PENDIENTE_PAGO" {"selected" if ep_fil=="PENDIENTE_PAGO" else ""}>Pendiente</option>
          <option value="VALIDADO" {"selected" if ep_fil=="VALIDADO" else ""}>Validado</option>
        </select>
        <select name="estado_vigencia" class="form-control" style="max-width:110px">
          <option value="todos" {"selected" if ev_fil=="todos" else ""}>Todos</option>
          <option value="VIGENTE" {"selected" if ev_fil=="VIGENTE" else ""}>Vigente</option>
          <option value="VENCIDO" {"selected" if ev_fil=="VENCIDO" else ""}>Vencido</option>
        </select>
        <button type="submit" class="btn btn-primary btn-sm" style="width:auto">Filtrar</button>
        <a href="/panel/folios" class="btn btn-outline btn-sm">✕</a>
      </form>
      <span style="font-size:12px;color:#888;margin-left:auto">{len(folios)} resultados</span>
    </div>"""
    contenido = f"""{modal_html}
    <p class="page-title">Folios Registrados</p>
    {msg_html}{filtros}
    <div class="tabla-wrap"><table>
      <thead><tr><th>Folio</th><th>Titular</th><th>Vehículo</th><th>Fechas</th><th>Estado</th><th>Acc.</th></tr></thead>
      <tbody>{filas or '<tr><td colspan="6" style="text-align:center;color:#999;padding:20px">Sin folios</td></tr>'}</tbody>
    </table></div>"""
    return HTMLResponse(page("Folios","Folios Registrados — Michoacán", contenido))

@app.post("/panel/validar/{folio}")
async def validar_pago(request: Request, folio: str):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    folio = folio.strip().upper()
    try: supabase.table("folios_registrados").update({"estado_pago":"VALIDADO"}).eq("folio",folio).execute()
    except Exception as e: print(f"[VALIDAR] Error: {e}")
    from urllib.parse import quote
    return RedirectResponse(url=f"/panel/folios?msg={quote(f'Folio {folio} validado ✅')}", status_code=303)

@app.get("/panel/pdf/{folio}")
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
    return HTMLResponse(f"<p>PDF {folio} no encontrado.</p><a href='/panel/folios'>← Volver</a>", status_code=404)

# ===================== REGISTRO ADMIN =====================
@app.get("/panel/registro_admin", response_class=HTMLResponse)
async def registro_admin_get(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    tz = ZoneInfo(TZ); hoy = datetime.now(tz).strftime("%Y-%m-%d")
    err = request.query_params.get("error","")
    err_html = f'<div class="alert alert-err">{err}</div>' if err else ""
    contenido = f"""
    <p class="page-title">Registrar Permiso</p>
    {err_html}
    <div class="form-card">
      <form method="POST" action="/panel/registro_admin">
        <div class="mb-3"><label class="form-label">Folio manual <small style="color:#999;font-weight:400">(vacío = auto)</small></label>
          <input type="text" name="folio" class="form-control" placeholder="{FOLIO_NUM_PREF}1234" style="text-transform:uppercase"></div>
        <div class="row-2">
          <div class="mb-3"><label class="form-label">Marca *</label><input type="text" name="marca" class="form-control" required style="text-transform:uppercase"></div>
          <div class="mb-3"><label class="form-label">Línea *</label><input type="text" name="linea" class="form-control" required style="text-transform:uppercase"></div>
        </div>
        <div class="row-3">
          <div class="mb-3"><label class="form-label">Año *</label><input type="text" name="anio" class="form-control" maxlength="4" required></div>
          <div class="mb-3" style="grid-column:span 2"><label class="form-label">Color</label><input type="text" name="color" class="form-control" style="text-transform:uppercase"></div>
        </div>
        <div class="row-2">
          <div class="mb-3"><label class="form-label">Núm. Serie *</label><input type="text" name="numero_serie" class="form-control" required style="text-transform:uppercase"></div>
          <div class="mb-3"><label class="form-label">Núm. Motor *</label><input type="text" name="numero_motor" class="form-control" required style="text-transform:uppercase"></div>
        </div>
        <div class="mb-3"><label class="form-label">Nombre del titular *</label><input type="text" name="nombre" class="form-control" required style="text-transform:uppercase"></div>
        <div class="row-2">
          <div class="mb-3"><label class="form-label">Fecha expedición</label><input type="date" name="fecha_expedicion" class="form-control" value="{hoy}"></div>
          <div class="mb-3"><label class="form-label">Vencimiento <small style="color:#999">(vacío=+30d)</small></label><input type="date" name="fecha_vencimiento" class="form-control"></div>
        </div>
        <button type="submit" class="btn btn-primary mt-3"><i class="fa-solid fa-file-circle-plus"></i> Generar Permiso</button>
      </form>
    </div>"""
    return HTMLResponse(page("Registrar Permiso","Registrar Permiso — Michoacán", contenido))

@app.post("/panel/registro_admin")
async def registro_admin_post(request: Request,
    folio: str = Form(None), marca: str = Form(...), linea: str = Form(...),
    anio: str = Form(...), color: str = Form(""), numero_serie: str = Form(...),
    numero_motor: str = Form(...), nombre: str = Form(...),
    fecha_expedicion: str = Form(None), fecha_vencimiento: str = Form(None)):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    from urllib.parse import quote
    try:
        tz = ZoneInfo(TZ)
        fg = folio.strip().upper() if folio and folio.strip() else generar_folio()
        fe = datetime.fromisoformat(fecha_expedicion).date() if fecha_expedicion and fecha_expedicion.strip() else datetime.now(tz).date()
        fv = datetime.fromisoformat(fecha_vencimiento).date() if fecha_vencimiento and fecha_vencimiento.strip() else fe + timedelta(days=30)
        supabase.table("folios_registrados").insert({
            "folio": fg, "marca": marca.upper(), "linea": linea.upper(), "anio": anio,
            "numero_serie": numero_serie.upper(), "numero_motor": numero_motor.upper(),
            "color": color.upper(), "nombre": nombre.upper(),
            "fecha_expedicion": fe.isoformat(), "fecha_vencimiento": fv.isoformat(),
            "entidad": ENTIDAD, "estado": "ACTIVO", "estado_pago": "VALIDADO",
            "creado_por": request.session.get("username","admin")
        }).execute()
        return RedirectResponse(url=f"/panel/folios?msg={quote(f'Permiso {fg} generado ✅')}", status_code=303)
    except Exception as e:
        print(f"[REGISTRO ADMIN] Error: {e}")
        return RedirectResponse(url=f"/panel/registro_admin?error={quote(str(e))}", status_code=303)

# ===================== CREAR USUARIO =====================
@app.get("/panel/crear_usuario", response_class=HTMLResponse)
async def crear_usuario_get(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    msg = request.query_params.get("msg",""); err = request.query_params.get("error","")
    msg_html = f'<div class="alert alert-ok">{msg}</div>' if msg else ""
    err_html = f'<div class="alert alert-err">{err}</div>' if err else ""
    contenido = f"""
    <p class="page-title">Crear Usuario</p>
    {msg_html}{err_html}
    <div class="form-card">
      <form method="POST" action="/panel/crear_usuario">
        <div class="mb-3"><label class="form-label">Usuario *</label><input type="text" name="username" class="form-control" required autocomplete="off"></div>
        <div class="mb-3"><label class="form-label">Contraseña *</label><input type="password" name="password" class="form-control" required></div>
        <div class="mb-4"><label class="form-label">Folios asignados *</label><input type="number" name="folios" class="form-control" min="1" required></div>
        <button type="submit" class="btn btn-primary"><i class="fa-solid fa-user-plus"></i> Crear Usuario</button>
      </form>
    </div>"""
    return HTMLResponse(page("Crear Usuario","Crear Usuario — Michoacán", contenido))

@app.post("/panel/crear_usuario")
async def crear_usuario_post(request: Request,
    username: str = Form(...), password: str = Form(...), folios: int = Form(...)):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    from urllib.parse import quote
    try:
        existe = supabase.table("verificacion_michoacan").select("id").eq("username", username).execute()
        if existe.data: return RedirectResponse(url=f"/panel/crear_usuario?error={quote('El usuario ya existe')}", status_code=303)
        supabase.table("verificacion_michoacan").insert({"username": username, "password": password, "folios_asignac": folios, "folios_usados": 0}).execute()
        return RedirectResponse(url=f"/panel/crear_usuario?msg={quote(f'Usuario {username} creado con {folios} folios ✅')}", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/panel/crear_usuario?error={quote(str(e))}", status_code=303)

# ===================== REGISTRO USUARIO 3RO =====================
@app.get("/registro_usuario", response_class=HTMLResponse)
async def registro_usuario_get(request: Request):
    if not request.session.get("username") or request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    ud = supabase.table("verificacion_michoacan").select("*").eq("username", request.session["username"]).limit(1).execute()
    if not ud.data: return RedirectResponse(url="/panel/login", status_code=303)
    u = ud.data[0]; asig = int(u.get("folios_asignac",0)); usad = int(u.get("folios_usados",0))
    disp = asig - usad; porc = round((usad/asig*100) if asig else 0, 1)
    tz = ZoneInfo(TZ); hoy = datetime.now(tz).strftime("%Y-%m-%d")
    msg = request.query_params.get("msg",""); err = request.query_params.get("error","")
    msg_html = f'<div class="alert alert-ok">{msg}</div>' if msg else ""
    err_html = f'<div class="alert alert-err">{err}</div>' if err else ""
    form_html = f"""<div class="form-card">
      <form method="POST" action="/registro_usuario">
        <div class="row-2">
          <div class="mb-3"><label class="form-label">Marca *</label><input type="text" name="marca" class="form-control" required style="text-transform:uppercase"></div>
          <div class="mb-3"><label class="form-label">Línea *</label><input type="text" name="linea" class="form-control" required style="text-transform:uppercase"></div>
        </div>
        <div class="row-3">
          <div class="mb-3"><label class="form-label">Año *</label><input type="number" name="anio" class="form-control" required></div>
          <div class="mb-3" style="grid-column:span 2"><label class="form-label">Color</label><input type="text" name="color" class="form-control" style="text-transform:uppercase"></div>
        </div>
        <div class="row-2">
          <div class="mb-3"><label class="form-label">Núm. Serie *</label><input type="text" name="serie" class="form-control" required style="text-transform:uppercase"></div>
          <div class="mb-3"><label class="form-label">Núm. Motor *</label><input type="text" name="motor" class="form-control" required style="text-transform:uppercase"></div>
        </div>
        <div class="mb-3"><label class="form-label">Nombre del titular *</label><input type="text" name="nombre" class="form-control" required style="text-transform:uppercase"></div>
        <div class="mb-4"><label class="form-label">Fecha inicio vigencia</label><input type="date" name="fecha_inicio" class="form-control" value="{hoy}" min="{hoy}"></div>
        <button type="submit" id="btnReg" class="btn btn-primary">Registrar Folio</button>
      </form>
    </div>""" if disp > 0 else '<div class="alert alert-err">Sin folios disponibles. Contacta al administrador.</div>'
    contenido = f"""
    <p class="page-title">Registrar Permiso — Michoacán</p>
    <div class="form-card mb-3">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <span style="font-weight:700;font-size:14px">Mis Folios</span>
        <span style="font-size:12px;color:#888">{usad} / {asig}</span>
      </div>
      <div class="barra-c"><div class="barra-p" style="width:{porc}%">{porc}%</div></div>
      <div style="display:flex;justify-content:space-between;font-size:11px;color:#888;margin-top:4px">
        <span>Usados: <strong>{usad}</strong></span><span>Total: <strong>{asig}</strong></span><span>Disponibles: <strong style="color:{C1}">{disp}</strong></span>
      </div>
    </div>
    {msg_html}{err_html}{form_html}
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

@app.post("/registro_usuario")
async def registro_usuario_post(request: Request,
    marca: str = Form(...), linea: str = Form(...), anio: str = Form(...),
    color: str = Form(""), serie: str = Form(...), motor: str = Form(...),
    nombre: str = Form(...), fecha_inicio: str = Form(None)):
    if not request.session.get("username") or request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    from urllib.parse import quote
    try:
        ud = supabase.table("verificacion_michoacan").select("*").eq("username", request.session["username"]).limit(1).execute()
        if not ud.data: return RedirectResponse(url="/panel/login", status_code=303)
        u = ud.data[0]; asig = int(u.get("folios_asignac",0)); usad = int(u.get("folios_usados",0))
        if asig - usad <= 0: return RedirectResponse(url=f"/registro_usuario?error={quote('Sin folios disponibles')}", status_code=303)
        tz = ZoneInfo(TZ)
        fe = datetime.strptime(fecha_inicio, "%Y-%m-%d").replace(tzinfo=tz) if fecha_inicio else datetime.now(tz)
        fv = fe + timedelta(days=30); fg = generar_folio()
        supabase.table("folios_registrados").insert({
            "folio": fg, "marca": marca.upper(), "linea": linea.upper(), "anio": anio,
            "numero_serie": serie.upper(), "numero_motor": motor.upper(),
            "color": color.upper(), "nombre": nombre.upper(),
            "fecha_expedicion": fe.date().isoformat(), "fecha_vencimiento": fv.date().isoformat(),
            "entidad": ENTIDAD, "estado": "ACTIVO", "estado_pago": "VALIDADO",
            "user_id": request.session.get("user_id"), "creado_por": request.session["username"]
        }).execute()
        supabase.table("verificacion_michoacan").update({"folios_usados": usad+1}).eq("username", request.session["username"]).execute()
        contenido = f"""
        <p class="page-title">✅ Permiso Generado</p>
        <div class="form-card" style="text-align:center">
          <div style="font-size:52px;margin-bottom:12px">📄</div>
          <h2 style="color:{C1};font-size:24px;font-weight:700;margin-bottom:4px">{fg}</h2>
          <p style="color:#888;font-size:13px;margin-bottom:16px">Folio de circulación generado correctamente</p>
          <div class="info-box" style="text-align:left">
            <strong>Vehículo:</strong> {marca.upper()} {linea.upper()} {anio}<br>
            <strong>Serie:</strong> {serie.upper()}<br>
            <strong>Titular:</strong> {nombre.upper()}<br>
            <strong>Expedición:</strong> {fe.strftime("%d/%m/%Y")}<br>
            <strong>Vencimiento:</strong> {fv.strftime("%d/%m/%Y")}
          </div>
          <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
            <a href="/mis_permisos" class="btn btn-outline btn-sm">📋 Mis Permisos</a>
            <a href="/registro_usuario" class="btn btn-primary btn-sm" style="width:auto">+ Nuevo</a>
          </div>
        </div>"""
        return HTMLResponse(page("Permiso Generado","Registro Exitoso", contenido))
    except Exception as e:
        print(f"[REG USUARIO] Error: {e}")
        return RedirectResponse(url=f"/registro_usuario?error={quote(str(e))}", status_code=303)

@app.get("/mis_permisos", response_class=HTMLResponse)
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
          <td>{p.get("fe_fmt","")}</td>
          <td>{be}</td>
          <td>{btn}<a href="/consulta/{p.get('folio','')}" target="_blank" class="btn btn-sm btn-outline">🔗</a></td>
        </tr>"""
    contenido = f"""
    <p class="page-title">📋 Mis Permisos</p>
    <div class="grid mb-3">
      <div class="stat-card"><div class="stat-num">{asig}</div><div class="stat-lbl">Asignados</div></div>
      <div class="stat-card"><div class="stat-num">{asig-usad}</div><div class="stat-lbl">Disponibles</div></div>
      <div class="stat-card"><div class="stat-num" style="color:#1a6e2e">{len([p for p in permisos if p.get("estado_calc")=="VIGENTE"])}</div><div class="stat-lbl">Vigentes</div></div>
      <div class="stat-card"><div class="stat-num" style="color:{C1}">{len(permisos)}</div><div class="stat-lbl">Total</div></div>
    </div>
    <div class="tabla-wrap"><table>
      <thead><tr><th>Folio</th><th>Vehículo</th><th>Serie</th><th>Fecha</th><th>Estado</th><th>Acc.</th></tr></thead>
      <tbody>{filas or '<tr><td colspan="6" style="text-align:center;color:#999;padding:20px">Sin permisos</td></tr>'}</tbody>
    </table></div>
    <div style="display:flex;gap:8px;margin-top:12px">
      <a href="/registro_usuario" class="btn btn-primary btn-sm" style="width:auto">+ Nuevo Permiso</a>
      <a href="/panel/logout" class="btn btn-danger btn-sm">🚪 Salir</a>
    </div>"""
    return HTMLResponse(page("Mis Permisos","Mis Permisos — Michoacán", contenido))

# ===================== CONSULTA FOLIO =====================
@app.get("/consulta_folio", response_class=HTMLResponse)
async def consulta_folio_form(request: Request):
    contenido = f"""
    <p class="page-title">🔍 Consultar Folio</p>
    <div class="form-card">
      <form method="POST" action="/consulta_folio">
        <div class="mb-3"><label class="form-label">Número de Folio</label>
          <input type="text" name="folio" class="form-control" placeholder="{FOLIO_NUM_PREF}1234" required autofocus style="text-transform:uppercase"></div>
        <button type="submit" class="btn btn-primary"><i class="fa-solid fa-magnifying-glass"></i> Buscar</button>
      </form>
    </div>"""
    return HTMLResponse(page("Consultar Folio","Consultar Folio", contenido))

@app.post("/consulta_folio")
async def consulta_folio_post(request: Request, folio: str = Form(...)):
    return RedirectResponse(url=f"/consulta/{folio.strip().upper()}", status_code=303)

@app.get("/consulta/{folio}", response_class=HTMLResponse)
async def consulta_publica(folio: str):
    folio = folio.strip().upper()
    try:
        res = supabase.table("folios_registrados").select("*").eq("folio", folio).execute()
        if not res.data:
            resultado_html = f"""
            <div style="background:#c0392b;color:white;padding:14px 18px;border-radius:10px;font-size:15px;font-weight:700;text-align:center;margin-bottom:18px">
              <i class="fa-solid fa-circle-xmark"></i> EL FOLIO {folio} NO SE ENCUENTRA EN SISTEMA
            </div>"""
        else:
            f = res.data[0]; tz=ZoneInfo(TZ); hoy=datetime.now(tz).date()
            fv=datetime.fromisoformat(f["fecha_vencimiento"]).date()
            fe=datetime.fromisoformat(f["fecha_expedicion"]).date()
            vigente=hoy<=fv
            badge_color="#1a6e2e" if vigente else "#b38b00"
            badge_text=f"FOLIO {folio} ACTIVO" if vigente else f"FOLIO {folio} VENCIDO"
            badge_icon="fa-circle-check" if vigente else "fa-clock"
            validez=f'<div style="background:#e8f5e9;border:1px solid #a5d6a7;color:#1b5e20;border-radius:8px;padding:11px;text-align:center;font-weight:700;font-size:13px;margin-bottom:14px"><i class="fa-solid fa-circle-check"></i> PERMISO VIGENTE</div>' if vigente else '<div style="background:#fff8e1;border:1px solid #ffe082;color:#b38b00;border-radius:8px;padding:11px;text-align:center;font-weight:700;font-size:13px;margin-bottom:14px"><i class="fa-solid fa-clock"></i> PERMISO VENCIDO</div>'
            def fila_dato(label, valor):
                return f'<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f0f0f0;font-size:13px"><span style="color:#888;font-weight:600">{label}</span><span style="font-weight:600">{valor}</span></div>'
            resultado_html = f"""
            <div style="background:{badge_color};color:white;padding:14px 18px;border-radius:10px;font-size:15px;font-weight:700;text-align:center;margin-bottom:16px">
              <i class="fa-solid {badge_icon}"></i> {badge_text}
            </div>
            {validez}
            <div style="background:white;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:14px">
              <div style="background:{C1};color:white;padding:10px 14px;font-weight:700;font-size:13px"><i class="fa-solid fa-car me-2"></i>Datos del Vehículo</div>
              <div style="padding:0 14px">
                {fila_dato("Marca", f.get("marca",""))}
                {fila_dato("Línea", f.get("linea",""))}
                {fila_dato("Año", f.get("anio",""))}
                {fila_dato("Núm. Serie", f.get("numero_serie",""))}
                {fila_dato("Color", f.get("color",""))}
              </div>
            </div>
            <div style="background:white;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:14px">
              <div style="background:{C1};color:white;padding:10px 14px;font-weight:700;font-size:13px"><i class="fa-solid fa-file-shield me-2"></i>Datos del Permiso</div>
              <div style="padding:0 14px">
                {fila_dato("Folio", f'<span style="color:{C1};font-weight:700">{folio}</span>')}
                {fila_dato("Titular", f.get("nombre",""))}
                {fila_dato("Expedición", fe.strftime("%d/%m/%Y"))}
                {fila_dato("Vencimiento", fv.strftime("%d/%m/%Y"))}
              </div>
            </div>"""
        html = f"""<!DOCTYPE html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Consulta de Folio — Michoacán</title>
<link rel="icon" href="https://michoacan.gob.mx/wp-content/uploads/2021/09/cropped-LogoGobMich-Escudo-Guinda-600-600-32x32.png" sizes="32x32"/>
{FA}
<style>{CSS}</style></head><body>
<nav class="navbar"><img src="https://michoacan.gob.mx/cdn/img/logo.svg?ver=6" alt="Michoacán"></nav>
<div class="admin-bar"><i class="fa-solid fa-shield-halved me-2"></i>Verificación de Permiso — Michoacán</div>
<div class="content" style="max-width:500px">
  {resultado_html}
  <a href="https://michoacan.gob.mx/tramites-vehiculares/" class="btn btn-primary mt-3">
    <i class="fa-solid fa-arrow-left"></i> Volver a Trámites Vehiculares
  </a>
</div>
<footer style="margin-top:30px;background:#1a1a1a;color:#aaa;padding:18px;text-align:center;font-size:12px">
  © Gobierno del Estado de Michoacán 2026 — Tránsito Estatal
</footer>
</body></html>"""
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f"<p>Error: {e}</p>", status_code=500)

# ===================== TEST FECHAS =====================
@app.get("/panel/test_fechas", response_class=HTMLResponse)
async def test_fechas_get(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    fb = request.query_params.get("folio","").strip().upper()
    msg = request.query_params.get("msg",""); resultado = None
    if fb:
        try:
            r = supabase.table("folios_registrados").select("*").eq("folio",fb).execute()
            resultado = (r.data or [None])[0]
        except Exception as e: msg = f"Error: {e}"
    msg_html = f'<div class="alert alert-ok">{msg}</div>' if msg else ""
    info_html = acc_html = ""
    if resultado:
        info_html = f"""<div class="info-box">
          <strong>Folio:</strong> {resultado.get("folio","")}<br>
          <strong>Estado pago:</strong> {resultado.get("estado_pago","")}<br>
          <strong>Expedición:</strong> {str(resultado.get("fecha_expedicion",""))[:10]}<br>
          <strong>Vencimiento:</strong> {str(resultado.get("fecha_vencimiento",""))[:10]}<br>
          <a href="/consulta/{resultado.get('folio','')}" target="_blank" style="color:{C1}">🔗 Ver consulta pública</a>
        </div>"""
        acc_html = f"""<form method="POST" action="/panel/test_fechas">
          <input type="hidden" name="folio" value="{resultado.get('folio','')}">
          <button type="submit" name="accion" value="vencer" class="btn mb-3" style="background:#b38b00;color:white;width:100%">⏰ Marcar VENCIDO</button>
          <button type="submit" name="accion" value="restaurar" class="btn" style="background:#1a6e2e;color:white;width:100%">✅ Restaurar vigencia</button>
        </form>"""
    contenido = f"""
    <p class="page-title">🧪 Test Fechas</p>
    {msg_html}
    <div class="form-card">
      <form method="GET">
        <div class="mb-3"><label class="form-label">Folio a probar</label>
          <input type="text" name="folio" class="form-control" placeholder="{FOLIO_NUM_PREF}1234" value="{fb}" style="text-transform:uppercase"></div>
        <button type="submit" class="btn btn-primary mb-3">Buscar</button>
      </form>
      {info_html}{acc_html}
    </div>"""
    return HTMLResponse(page("Test Fechas","Test Fechas — Michoacán", contenido))

@app.post("/panel/test_fechas")
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
    from urllib.parse import quote
    return RedirectResponse(url=f"/panel/test_fechas?folio={folio}&msg={quote(msg)}", status_code=303)

# ===================== TABLAS BD =====================
@app.get("/panel/tablas", response_class=HTMLResponse)
async def admin_tablas(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    cards = "".join([f"""<div class="form-card mb-3">
      <div style="font-size:20px;margin-bottom:6px">🗄️</div>
      <strong style="color:{C1}">{info['nombre']}</strong>
      <p style="font-size:12px;color:#888;margin:4px 0 12px"><code>{nombre}</code> · {len(info['columnas'])} columnas</p>
      <a href="/panel/tabla/{nombre}" class="btn btn-primary btn-sm" style="width:auto">Ver y editar →</a>
    </div>""" for nombre, info in TABLAS_DISPONIBLES.items()])
    contenido = f'<p class="page-title">🗄️ Tablas Base de Datos</p>{cards}'
    return HTMLResponse(page("Tablas BD","Tablas BD — Michoacán", contenido))

@app.get("/panel/tabla/{nombre_tabla}", response_class=HTMLResponse)
async def admin_tabla_detalle(nombre_tabla: str, request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    if nombre_tabla not in TABLAS_DISPONIBLES: return RedirectResponse(url="/panel/tablas", status_code=303)
    info = TABLAS_DISPONIBLES[nombre_tabla]; pk_col = info["pk_col"]
    q = request.query_params.get("q","").strip(); page_n = max(1, int(request.query_params.get("page","1") or 1))
    try:
        todos = supabase.table(nombre_tabla).select("*").limit(20000).execute().data or []
        filtrados = [r for r in todos if any(q.lower() in str(v).lower() for v in r.values() if v is not None)] if q else todos
        total = len(filtrados); offset = (page_n-1)*PAGE_SIZE; registros = filtrados[offset:offset+PAGE_SIZE]
    except: todos=filtrados=registros=[]; total=offset=0
    columnas = list(registros[0].keys()) if registros else (list(todos[0].keys()) if todos else info["columnas"])
    total_pages = max(1,(total+PAGE_SIZE-1)//PAGE_SIZE)
    th = "".join(f"<th>{c}</th>" for c in columnas) + "<th></th>"
    def _fila(i, reg):
        celdas = f'<td style="color:#bbb;font-size:10px">{offset+i+1}</td>'
        for col in columnas:
            val = reg.get(col); disp = str(val) if val is not None else "null"
            cls = "cv nv" if val is None else "cv"
            celdas += f'<td><span class="{cls}" data-col="{col}" data-pk="{str(reg.get(pk_col,""))}" data-val="{str(val or "")}" onclick="editCell(this)">{disp[:30]}</span></td>'
        celdas += f'<td><button class="del-btn" onclick="delRow(this,\'{str(reg.get(pk_col,""))}\',\'row{i}\')">✕</button></td>'
        return f'<tr id="row{i}">{celdas}</tr>'
    tbody = "".join(_fila(i, registros[i]) for i in range(len(registros))) or "<tr><td colspan='20' style='text-align:center;padding:20px;color:#999'>Sin registros</td></tr>"
    pag = ""
    if total_pages > 1:
        pag = '<div style="display:flex;gap:8px;justify-content:center;padding:14px">'
        if page_n>1: pag += f'<a href="?q={q}&page={page_n-1}" class="btn btn-outline btn-sm">← Ant</a>'
        pag += f'<span class="btn btn-sm" style="background:{C1};color:white">{page_n}/{total_pages}</span>'
        if page_n<total_pages: pag += f'<a href="?q={q}&page={page_n+1}" class="btn btn-outline btn-sm">Sig →</a>'
        pag += '</div>'
    contenido = f"""
    <p class="page-title">📊 {info['nombre']}</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;align-items:center">
      <form method="GET" style="display:contents">
        <input type="text" name="q" value="{q}" placeholder="Buscar..." class="form-control" style="max-width:240px">
        <button type="submit" class="btn btn-primary btn-sm" style="width:auto">🔍</button>
        {"<a href='/panel/tabla/"+nombre_tabla+"' class='btn btn-outline btn-sm'>✕</a>" if q else ""}
      </form>
      <span style="font-size:12px;color:#888;margin-left:auto">{total} registros</span>
    </div>
    <div class="tabla-wrap"><table id="tbl"><thead><tr><th>#</th>{th}</tr></thead><tbody>{tbody}</tbody></table>
    {pag}</div>
    <div class="mt-3"><a href="/panel/tablas" class="btn btn-outline btn-sm">← Tablas</a></div>
    <div class="toast-f" id="toast"></div>"""
    scripts = f"""<script>
const TABLA="{nombre_tabla}",PK_COL="{pk_col}";
function editCell(span){{const col=span.dataset.col,pk=span.dataset.pk,orig=span.dataset.val;const inp=document.createElement('input');inp.type='text';inp.className='cell-input';inp.value=orig;inp._span=span;inp._orig=orig;inp._col=col;inp._pk=pk;span.parentNode.insertBefore(inp,span);span.style.display='none';inp.focus();inp.select();inp.addEventListener('blur',()=>fin(inp));inp.addEventListener('keydown',e=>{{if(e.key==='Enter'){{e.preventDefault();inp.blur();}}if(e.key==='Escape'){{inp._cancel=true;inp.blur();}}}});}}
function fin(inp){{const span=inp._span,nv=inp.value.trim(),orig=inp._orig;inp.remove();span.style.display='';if(inp._cancel||nv===orig)return;span.textContent=nv||'null';span.dataset.val=nv;span.classList.toggle('nv',!nv);fetch('/panel/api/update_cell',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{tabla:TABLA,pk_col:PK_COL,pk_val:inp._pk,col:inp._col,val:nv}})}}).then(r=>r.json()).then(d=>{{if(d.ok)toast('✓ guardado',true);else{{span.textContent=orig||'null';span.dataset.val=orig;toast('Error: '+(d.error||'?'),false);}}}}).catch(()=>{{span.textContent=orig||'null';toast('Error de red',false);}});}}
function delRow(btn,pk,rowId){{if(!confirm('¿Eliminar?'))return;btn.disabled=true;fetch('/panel/api/delete_row',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{tabla:TABLA,pk_col:PK_COL,pk_val:pk}})}}).then(r=>r.json()).then(d=>{{if(d.ok){{const tr=document.getElementById(rowId);if(tr){{tr.style.opacity='0';setTimeout(()=>tr.remove(),250);}}toast('Eliminado',true);}}else{{btn.disabled=false;toast('Error: '+(d.error||'?'),false);}}}}).catch(()=>{{btn.disabled=false;toast('Error de red',false);}});}}
let tt;function toast(msg,ok){{const t=document.getElementById('toast');t.textContent=msg;t.className='toast-f show '+(ok?'ok':'err');clearTimeout(tt);tt=setTimeout(()=>t.classList.remove('show'),2500);}}
</script>"""
    return HTMLResponse(page(info["nombre"], info["nombre"], contenido, scripts))

@app.post("/panel/api/update_cell")
async def api_update_cell(request: Request):
    if not request.session.get("admin"): return {"ok":False,"error":"no autorizado"}
    d = await request.json(); tabla=d.get("tabla"); pk_col=d.get("pk_col"); pk_val=d.get("pk_val"); col=d.get("col"); val=d.get("val","")
    if tabla not in TABLAS_DISPONIBLES or not col or not pk_val: return {"ok":False,"error":"datos inválidos"}
    try: supabase.table(tabla).update({col:val or None}).eq(pk_col,pk_val).execute(); return {"ok":True}
    except Exception as e: return {"ok":False,"error":str(e)}

@app.post("/panel/api/delete_row")
async def api_delete_row(request: Request):
    if not request.session.get("admin"): return {"ok":False,"error":"no autorizado"}
    d = await request.json(); tabla=d.get("tabla"); pk_col=d.get("pk_col"); pk_val=d.get("pk_val")
    if tabla not in TABLAS_DISPONIBLES or not pk_val: return {"ok":False,"error":"datos inválidos"}
    try: supabase.table(tabla).delete().eq(pk_col,pk_val).execute(); return {"ok":True}
    except Exception as e: return {"ok":False,"error":str(e)}

# ===================== WEBHOOK / HEALTH =====================
@app.post("/webhook")
async def webhook(request: Request):
    return {"ok": True}

@app.get("/health")
async def health():
    return {"status":"healthy","version":"1.0","entidad":ENTIDAD,"siguiente_folio":f"{FOLIO_NUM_PREF}{_folio_counter['siguiente']}"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
