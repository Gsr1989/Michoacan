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

# ===================== CONFIG =====================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
BASE_URL     = os.getenv("BASE_URL", "https://https-michoacan-gob-mx-tramites-permiso.onrender.com").rstrip("/")
ENTIDAD      = "michoacan"
TZ           = "America/Mexico_City"

ADMIN_USER = "Serg890105tm3"
ADMIN_PASS = "Serg890105tm3"

STATIC_DIR = "static"
os.makedirs(STATIC_DIR, exist_ok=True)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===================== COLORES =====================
C1 = "#4a001f"
C2 = "#3a0018"
C3 = "#6A0F49"

# ===================== LOGIN HTML =====================
def login_html(error: bool = False) -> str:
    err = '<div class="alert-err mb-3"><i class="fa-solid fa-triangle-exclamation me-2"></i>Usuario o contraseña incorrectos</div>' if error else ""
    return f"""<!DOCTYPE html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Acceso — Michoacán Tránsito</title>
<link rel="icon" href="https://michoacan.gob.mx/wp-content/uploads/2021/09/cropped-LogoGobMich-Escudo-Guinda-600-600-32x32.png" sizes="32x32"/>
<link href="https://michoacan.gob.mx/cdn/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css">
<style>
*{{font-family:'Segoe UI',sans-serif;}}
body{{background:{C1};min-height:100vh;margin:0;display:flex;flex-direction:column;}}
.lh{{background:white;padding:12px 20px;text-align:center;border-bottom:4px solid {C3};}}
.lh img{{height:60px;object-fit:contain;}}
.lw{{flex:1;display:flex;align-items:center;justify-content:center;padding:30px 15px;}}
.lc{{background:white;border-radius:14px;padding:35px;max-width:380px;width:100%;box-shadow:0 10px 40px rgba(0,0,0,.3);}}
.le{{text-align:center;margin-bottom:16px;}}
.le img{{height:65px;}}
.lt{{text-align:center;font-size:19px;font-weight:700;color:{C1};margin-bottom:4px;}}
.ls{{text-align:center;font-size:12px;color:#666;margin-bottom:22px;}}
.form-label{{font-weight:600;font-size:14px;}}
.form-control{{display:block;width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:6px;font-size:14px;margin-top:4px;box-sizing:border-box;}}
.form-control:focus{{border-color:{C1};outline:none;box-shadow:0 0 0 3px rgba(74,0,31,.12);}}
.mb-3{{margin-bottom:16px;}}
.mb-4{{margin-bottom:22px;}}
.btn-ingresar{{background:{C1};border:none;color:white;width:100%;padding:13px;font-weight:700;font-size:15px;border-radius:6px;cursor:pointer;transition:.2s;}}
.btn-ingresar:hover{{background:{C2};}}
.alert-err{{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;border-radius:6px;padding:10px 14px;font-size:13px;font-weight:600;}}
.lf{{background:rgba(0,0,0,.2);color:rgba(255,255,255,.7);text-align:center;padding:14px;font-size:12px;}}
</style></head><body>
<div class="lh">
  <img src="https://michoacan.gob.mx/cdn/img/logo.svg?ver=6" alt="Michoacán">
</div>
<div class="lw"><div class="lc">
  <div class="le">
    <img src="https://michoacan.gob.mx/wp-content/uploads/2021/09/cropped-LogoGobMich-Escudo-Guinda-600-600-192x192.png" alt="Escudo">
  </div>
  <div class="lt">Tránsito Estatal</div>
  <div class="ls">Gobierno del Estado de Michoacán<br>Sistema Administrativo</div>
  {err}
  <form method="POST" action="/panel/login">
    <div class="mb-3">
      <label class="form-label">Usuario</label>
      <input type="text" name="username" class="form-control" required autofocus autocomplete="off">
    </div>
    <div class="mb-4">
      <label class="form-label">Contraseña</label>
      <input type="password" name="password" class="form-control" required>
    </div>
    <button type="submit" class="btn-ingresar">
      <i class="fa-solid fa-right-to-bracket me-2"></i>Ingresar al Sistema
    </button>
  </form>
</div></div>
<div class="lf">Dirección de Tránsito Estatal — Gobierno del Estado de Michoacán © 2026</div>
<script src="https://michoacan.gob.mx/cdn/js/jquery-3.6.0.min.js"></script>
<script src="https://michoacan.gob.mx/cdn/js/bootstrap.min.js"></script>
</body></html>"""

# ===================== LIFESPAN =====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[SISTEMA] Michoacán — Login listo")
    yield

app = FastAPI(lifespan=lifespan, title="Tránsito Michoacán", version="1.0")
app.add_middleware(SessionMiddleware, secret_key="michoacan_clave_super_segura_123456")

try:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
except Exception:
    pass

# ===================== RUTAS =====================
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if request.session.get("admin") or request.session.get("username"):
        return RedirectResponse(url="/panel/admin", status_code=303)
    return RedirectResponse(url="/panel/login", status_code=303)

@app.get("/panel/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if request.session.get("admin") or request.session.get("username"):
        return RedirectResponse(url="/panel/admin", status_code=303)
    return HTMLResponse(login_html(bool(request.query_params.get("error", ""))))

@app.post("/panel/login")
async def login_post(request: Request,
    username: str = Form(...), password: str = Form(...)):

    # Admin hardcodeado
    if username == ADMIN_USER and password == ADMIN_PASS:
        request.session["admin"]    = True
        request.session["username"] = username
        request.session["rol"]      = "admin"
        return RedirectResponse(url="/panel/admin", status_code=303)

    # Usuario 3ro contra Supabase
    try:
        res = supabase.table("verificacion_michoacan").select("*") \
            .eq("username", username).eq("password", password).execute()
        if res.data:
            u = res.data[0]
            request.session["admin"]    = False
            request.session["username"] = u["username"]
            request.session["user_id"]  = u.get("id")
            request.session["rol"]      = "usuario"
            return RedirectResponse(url="/registro_usuario", status_code=303)
    except Exception as e:
        print(f"[LOGIN] Error Supabase: {e}")

    return RedirectResponse(url="/panel/login?error=1", status_code=303)

@app.get("/panel/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/panel/login", status_code=303)

# Placeholder temporal
@app.get("/panel/admin", response_class=HTMLResponse)
async def panel_admin(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(url="/panel/login", status_code=303)
    return HTMLResponse(f"<h2 style='font-family:sans-serif;color:{C1};padding:30px'>✅ Login OK — Panel en construcción</h2><a href='/panel/logout'>Salir</a>")

@app.get("/registro_usuario", response_class=HTMLResponse)
async def registro_usuario(request: Request):
    if not request.session.get("username") or request.session.get("admin"):
        return RedirectResponse(url="/panel/login", status_code=303)
    return HTMLResponse(f"<h2 style='font-family:sans-serif;color:{C1};padding:30px'>✅ Login 3ro OK — Hola {request.session['username']}<br>Formulario en construcción</h2><a href='/panel/logout'>Salir</a>")

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0-login", "entidad": ENTIDAD}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"[ARRANQUE] Michoacán v1.0 — puerto {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
