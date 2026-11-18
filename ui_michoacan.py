"""MICHOACÁN — piezas de interfaz del panel (CSS, navbar, layout, login)."""
from config_michoacan import C1, C2, C3

CSS = f"""
*{{font-family:'Segoe UI',sans-serif;box-sizing:border-box;}}
body{{margin:0;background:#f4f4f4;}}
.navbar{{background:white;padding:12px 16px;display:flex;align-items:center;justify-content:space-between;border-bottom:3px solid {C3};position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.08);}}
.navbar img{{height:55px;object-fit:contain;max-width:220px;}}
.hamburger{{display:flex;flex-direction:column;gap:5px;cursor:pointer;padding:4px;}}
.hamburger span{{display:block;width:26px;height:3px;background:{C1};border-radius:2px;}}
.sidenav{{position:fixed;top:0;right:-280px;width:280px;height:100%;background:white;z-index:200;transition:.3s;box-shadow:-4px 0 20px rgba(0,0,0,.15);overflow-y:auto;}}
.sidenav.open{{right:0;}}
.sidenav-header{{background:{C1};padding:20px 16px;color:white;}}
.sidenav-header img{{height:45px;filter:brightness(10);margin-bottom:8px;display:block;}}
.sidenav-header p{{margin:0;font-size:13px;opacity:.85;}}
.sidenav ul{{list-style:none;margin:0;padding:8px 0;}}
.sidenav ul li a{{display:flex;align-items:center;gap:12px;padding:14px 20px;color:#333;text-decoration:none;font-size:14px;font-weight:600;transition:.15s;border-bottom:1px solid #f0f0f0;}}
.sidenav ul li a:hover{{background:#fef5f7;color:{C1};}}
.sidenav ul li a i{{color:{C1};width:18px;text-align:center;}}
.sidenav ul li a.danger{{color:#c00;}}.sidenav ul li a.danger i{{color:#c00;}}
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
.menu-btn.danger i{{color:#dc3545;}}.menu-btn.danger:hover{{border-color:#dc3545;color:#dc3545;}}
table{{font-size:12px;width:100%;border-collapse:collapse;}}
thead th{{background:{C1};color:white;padding:10px 8px;text-align:left;white-space:nowrap;}}
tbody td{{padding:9px 8px;vertical-align:middle;border-bottom:1px solid #eee;}}
tbody tr:last-child td{{border-bottom:none;}}tbody tr:hover td{{background:#fef5f7;}}
.tabla-wrap{{overflow-x:auto;background:white;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.08);}}
.bp{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;color:white;}}
.bp-p{{background:#dc3545;}}.bp-v{{background:#1a6e2e;}}.bp-vig{{background:#1a6e2e;}}.bp-ven{{background:{C1};}}
.bp-t{{background:#e67e22;}}.bp-td{{background:#7f8c8d;}}
.form-card{{background:white;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.08);}}
.form-label{{font-weight:600;font-size:14px;display:block;margin-bottom:4px;}}
.form-control{{display:block;width:100%;padding:10px 12px;border:1.5px solid #ddd;border-radius:8px;font-size:14px;transition:.2s;font-family:inherit;}}
.form-control:focus{{border-color:{C1};outline:none;box-shadow:0 0 0 3px rgba(74,0,31,.1);}}
select.form-control{{appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23666' d='M6 8L1 3h10z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 12px center;padding-right:32px;}}
.mb-3{{margin-bottom:14px;}}.mb-4{{margin-bottom:20px;}}.mt-3{{margin-top:14px;}}
.btn{{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:11px 20px;border-radius:8px;font-weight:700;font-size:14px;border:none;cursor:pointer;text-decoration:none;transition:.2s;font-family:inherit;}}
.btn-primary{{background:{C1};color:white;width:100%;}}
.btn-primary:hover{{background:{C2};}}
.btn-sm{{padding:5px 12px;font-size:11px;border-radius:6px;}}
.btn-outline{{background:white;border:1.5px solid #ddd;color:#444;}}
.btn-outline:hover{{border-color:{C1};color:{C1};}}
.btn-danger{{background:#dc3545;color:white;}}.btn-success{{background:#1a6e2e;color:white;}}
.btn-warn{{background:#e67e22;color:white;}}
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
.filter-bar{{background:white;border-radius:12px;padding:14px;box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:14px;display:flex;flex-wrap:wrap;gap:8px;align-items:flex-end;}}
.page-title{{font-size:20px;font-weight:700;color:{C1};margin-bottom:16px;}}
.modal-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;}}
.modal-box{{background:white;border-radius:16px;padding:28px;max-width:360px;width:100%;text-align:center;}}
.dato-row{{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #f0f0f0;font-size:13px;}}
.dato-row:last-child{{border-bottom:none;}}
.dato-label{{color:#888;font-weight:600;}}
.dato-valor{{font-weight:600;text-align:right;max-width:60%;}}
"""

FA    = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css">'
JS_NAV = """<script>
function openNav(){document.getElementById('sidenav').classList.add('open');document.getElementById('overlay').classList.add('show');}
function closeNav(){document.getElementById('sidenav').classList.remove('open');document.getElementById('overlay').classList.remove('show');}
document.addEventListener('DOMContentLoaded',function(){document.getElementById('overlay').addEventListener('click',closeNav);});
</script>"""

def head(titulo):
    return f"""<!DOCTYPE html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titulo} — Michoacán</title>
<link rel="icon" href="https://michoacan.gob.mx/wp-content/uploads/2021/09/cropped-LogoGobMich-Escudo-Guinda-600-600-32x32.png" sizes="32x32"/>
{FA}<style>{CSS}</style></head><body>"""

def navbar():
    return f"""<nav class="navbar">
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
    <li><a href="/panel/timers"><i class="fa-solid fa-stopwatch"></i>Timers Activos</a></li>
    <li><a href="/panel/registro_admin"><i class="fa-solid fa-file-circle-plus"></i>Registrar Permiso</a></li>
    <li><a href="/panel/crear_usuario"><i class="fa-solid fa-user-plus"></i>Crear Usuario</a></li>
    <li><a href="/panel/tablas"><i class="fa-solid fa-database"></i>Tablas BD</a></li>
    <li><a href="/consulta_folio"><i class="fa-solid fa-magnifying-glass"></i>Consultar Folio</a></li>
    <li><a href="/panel/test_fechas"><i class="fa-solid fa-flask"></i>Test Fechas</a></li>
    <li><a href="/panel/logout" class="danger"><i class="fa-solid fa-right-from-bracket"></i>Cerrar Sesión</a></li>
  </ul>
</div>"""

def admin_bar(seccion):
    return f'<div class="admin-bar"><i class="fa-solid fa-shield-halved"></i> {seccion}</div>'

def footer(scripts=""):
    return f"""{scripts}{JS_NAV}</body></html>"""

def page(titulo, seccion, contenido, scripts=""):
    return head(titulo) + navbar() + admin_bar(seccion) + f'<div class="content">{contenido}</div>' + footer(scripts)

def login_html(error=False):
    err = '<div class="alert alert-err"><i class="fa-solid fa-triangle-exclamation"></i> Usuario o contraseña incorrectos</div>' if error else ""
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
.alert{{padding:11px 13px;border-radius:8px;font-size:13px;font-weight:600;margin-bottom:14px;}}
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