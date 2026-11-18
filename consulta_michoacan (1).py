"""
MICHOACÁN — CONSULTA PÚBLICA DE FOLIO.

La página es la OFICIAL «GEM | Trámites vehiculares» de michoacan.gob.mx, COMPLETA
(navbar, banner, tarjetas, footer, modales...). Lo único que se agrega es el cajón de
consulta justo debajo del banner «Trámites vehiculares»:

  · /consulta_folio   -> página oficial + cuadro para escribir el folio a mano
  · /consulta/{folio} -> la MISMA página con el resultado (es lo que abre el QR)

Misma interfaz en los dos casos (gemelas). No lleva botones de Salir/Regresar/Atrás.

USO en main.py:
    from consulta_michoacan import crear_router_consulta
    app.include_router(crear_router_consulta(supabase, ENTIDAD, TZ))
"""
import re
import html as html_lib
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse

SITIO = "https://michoacan.gob.mx"

CSS_CONSULTA = """
.mc-wrap{max-width:620px;margin:0 auto;padding:30px 16px 10px;font-family:'Segoe UI',Arial,sans-serif;color:#333;text-align:left}
.mc-wrap *{box-sizing:border-box;font-family:inherit}
.mc-box{background:#fff;border-radius:14px;box-shadow:0 4px 18px rgba(0,0,0,.10);padding:22px;margin-bottom:18px}
.mc-box h3{margin:0 0 4px;color:#4a001f;font-size:20px;font-weight:700}
.mc-box p{margin:0 0 14px;color:#777;font-size:13px}
.mc-form{display:flex;gap:10px;flex-wrap:wrap}
.mc-form input{flex:1 1 220px;padding:12px 14px;border:1.5px solid #ddd;border-radius:8px;font-size:16px;text-transform:uppercase;outline:none}
.mc-form input:focus{border-color:#4a001f;box-shadow:0 0 0 3px rgba(74,0,31,.12)}
.mc-form button{flex:0 0 auto;padding:12px 24px;border:0;border-radius:8px;background:#4a001f;color:#fff;font-weight:700;font-size:15px;cursor:pointer}
.mc-form button:hover{background:#3a0018}
.mc-badge{color:#fff;padding:16px 18px;border-radius:12px;font-size:15px;font-weight:700;text-align:center;margin-bottom:16px}
.mc-badge i{font-size:26px;display:block;margin-bottom:6px}
.mc-ok{background:#1a6e2e}.mc-venc{background:#b38b00}.mc-err{background:#c0392b}
.mc-card{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:14px}
.mc-card-h{background:#4a001f;color:#fff;padding:10px 16px;font-weight:700;font-size:13px}
.mc-card-b{padding:0 16px}
.mc-row{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid #f0f0f0;font-size:13px}
.mc-row:last-child{border-bottom:none}
.mc-l{color:#888!important;font-weight:600;opacity:1!important;visibility:visible!important}
.mc-v{color:#222!important;font-weight:600;text-align:right;max-width:62%;overflow-wrap:anywhere;opacity:1!important;visibility:visible!important}
@media(max-width:480px){.mc-form button{width:100%}.mc-wrap{padding-top:20px}}
"""


def _e(valor) -> str:
    return html_lib.escape(str(valor)) if valor not in (None, "") else "—"


def _pagina(contenido: str) -> str:
    """HTML oficial completo + el cajón de consulta."""
    extra_head = ('<meta name="robots" content="noindex, nofollow">\n'
                  "<style>" + CSS_CONSULTA + "</style>\n")
    pagina = _BASE.replace("</head>", extra_head + "</head>", 1)
    return pagina.replace("__RESULTADO__", contenido, 1)


def _formulario(titulo="Consulta de permiso") -> str:
    return f"""
<div class="mc-box">
  <h3>{titulo}</h3>
  <p>Escribe el número de folio de tu permiso para verificar su vigencia.</p>
  <form class="mc-form" method="post" action="/consulta_folio"
        onsubmit="var f=this.folio.value.trim().toUpperCase();if(!f){{return false;}}window.location.href='/consulta/'+encodeURIComponent(f);return false;">
    <input type="text" name="folio" placeholder="Ej. 6201234" required autocomplete="off" autocapitalize="characters">
    <button type="submit"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;"><circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5"/></svg> Consultar</button>
  </form>
</div>"""


def _row(label, valor) -> str:
    return f'<div class="mc-row"><span class="mc-l">{label}</span><span class="mc-v">{valor}</span></div>'


def _envolver(cuerpo: str) -> str:
    return f'<div class="mc-wrap">{cuerpo}</div>'


def crear_router_consulta(supabase, entidad: str, timezone: str) -> APIRouter:
    router = APIRouter()

    @router.get("/consulta_folio", response_class=HTMLResponse)
    async def consulta_folio_form():
        return HTMLResponse(_pagina(_envolver(_formulario())))

    @router.post("/consulta_folio")
    async def consulta_folio_post(folio: str = Form(...)):
        # Respaldo por si el navegador no ejecuta el JS del formulario
        return RedirectResponse(url=f"/consulta/{folio.strip().upper()}", status_code=303)

    @router.get("/consulta/{folio}", response_class=HTMLResponse)
    async def consulta_publica(folio: str):
        folio = folio.strip().upper()
        try:
            res = await asyncio.to_thread(lambda: supabase.table("folios_registrados")
                                          .select("*").eq("folio", folio).execute())

            if not res.data:
                badge = f"""<div class="mc-badge mc-err">
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;display:block;margin:0 auto 6px"><circle cx="12" cy="12" r="10"/><path d="M9 9l6 6M15 9l-6 6"/></svg>EL FOLIO {_e(folio)} NO ESTÁ REGISTRADO</div>"""
                return HTMLResponse(_pagina(_envolver(_formulario("Consultar otro folio") + badge)))

            f = res.data[0]
            hoy = datetime.now(ZoneInfo(timezone)).date()
            try:
                fv = datetime.fromisoformat(str(f["fecha_vencimiento"])[:10]).date()
                fe = datetime.fromisoformat(str(f["fecha_expedicion"])[:10]).date()
                vigente = hoy <= fv
            except Exception:
                vigente = False
                fe = fv = None

            if vigente:
                badge = f"""<div class="mc-badge mc-ok">
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;display:block;margin:0 auto 6px"><circle cx="12" cy="12" r="10"/><path d="M8 12l3 3 5-6"/></svg>EL FOLIO {_e(folio)} ESTÁ VIGENTE</div>"""
            else:
                badge = f"""<div class="mc-badge mc-venc">
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;display:block;margin:0 auto 6px"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>EL FOLIO {_e(folio)} ESTÁ VENCIDO</div>"""

            datos = f"""
<div class="mc-card">
  <div class="mc-card-h"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;"><path d="M3 13l2-6h14l2 6v5h-3v-2H6v2H3z"/><circle cx="7.5" cy="13.5" r=".8"/><circle cx="16.5" cy="13.5" r=".8"/></svg> Datos del Vehículo</div>
  <div class="mc-card-b">
    {_row("Marca", _e(f.get("marca")))}
    {_row("Línea", _e(f.get("linea")))}
    {_row("Año", _e(f.get("anio")))}
    {_row("Núm. Serie", _e(f.get("numero_serie")))}
    {_row("Núm. Motor", _e(f.get("numero_motor")))}
    {_row("Color", _e(f.get("color")))}
  </div>
</div>
<div class="mc-card">
  <div class="mc-card-h"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;"><path d="M6 2h9l4 4v16H6z"/><path d="M9 13l2 2 4-4"/></svg> Datos del Permiso</div>
  <div class="mc-card-b">
    {_row("Folio", '<span style="color:#4a001f;font-weight:700">' + _e(folio) + '</span>')}
    {_row("Titular", _e(f.get("nombre")))}
    {_row("Fecha de Expedición", fe.strftime("%d/%m/%Y") if fe else "—")}
    {_row("Fecha de Vencimiento", fv.strftime("%d/%m/%Y") if fv else "—")}
  </div>
</div>"""
            return HTMLResponse(_pagina(_envolver(_formulario("Consultar otro folio") + badge + datos)))

        except Exception as e:
            print(f"[CONSULTA] Error consultando {folio}: {e!r}")
            badge = """<div class="mc-badge mc-err">
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;display:block;margin:0 auto 6px"><path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/></svg>NO FUE POSIBLE REALIZAR LA CONSULTA. Inténtalo de nuevo en unos minutos.</div>"""
            return HTMLResponse(_pagina(_envolver(_formulario() + badge)), status_code=500)

    return router


# ============================================================
# HTML OFICIAL «GEM | Trámites vehiculares» (michoacan.gob.mx) — tal cual.
# Único cambio: el marcador __RESULTADO__ debajo del banner de «Trámites vehiculares».
# ============================================================
_PLANTILLA = r"""<!DOCTYPE html><html lang="es">
<head>
<title>GEM | Trámites vehiculares</title>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=3.0, user-scalable=1" />
<meta name="description" content="Portal ciudadano del Gobierno del Estado de Michoacán">
<meta name="keywords" content="gobierno, michoacan, portal, sitio web, dependencia michoacan, cgcs, comunicacion social">
<meta name="author" content="Coordinación General de Comunicación Social">
<meta http-equiv="X-UA-Compatible" content="IE=EmulateIE7, IE=9"/>
<meta http-equiv="X-UA-Compatible" content="IE=edge"/>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Michoacán">
<meta name="twitter:card" value="summary">
<meta property="og:title" content="Trámites vehiculares" />
<meta property="og:type" content="article"/>
<meta property="og:image" content="https://michoacan.gob.mx/images/michog.jpg"/>
<meta property="og:description" content="GEM" />
<link rel="pingback" href="https://michoacan.gob.mx/xmlrpc.php">


  <!-- Bootstrap -->
  <link href="https://michoacan.gob.mx/cdn/css/bootstrap.min.css" rel="stylesheet">
  <!-- Fancy Box -->
  <link href="https://michoacan.gob.mx/plugins/fancybox/jquery.fancybox.min.css" rel="stylesheet">
  <!-- CUSTOM CSS -->
  <link href="https://michoacan.gob.mx/cdn/css/portalmich.css?ver=2.0" rel="stylesheet">
  <!-- OWL CAROUSEL BANNERS CSS -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/OwlCarousel2/2.3.4/assets/owl.carousel.min.css">
  <!-- <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css"> -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css">
  <!-- ANIMACIONES -->
  <link rel="stylesheet" href="https://unpkg.com/aos@next/dist/aos.css" />
  <!-- FAVICON -->
  <link rel="shortcut icon" href="https://michoacan.gob.mx/cdn/img/favicon/favicon.ico" type="image/x-icon" />
  <link rel="apple-touch-icon" href="https://michoacan.gob.mx/cdn/img/favicon/apple-touch-icon.png" />
  <link rel="apple-touch-icon" sizes="57x57" href="https://michoacan.gob.mx/cdn/img/favicon/apple-touch-icon-57x57.png" />
  <link rel="apple-touch-icon" sizes="72x72" href="https://michoacan.gob.mx/cdn/img/favicon/apple-touch-icon-72x72.png" />
  <link rel="apple-touch-icon" sizes="76x76" href="https://michoacan.gob.mx/cdn/img/favicon/apple-touch-icon-76x76.png" />
  <link rel="apple-touch-icon" sizes="114x114" href="https://michoacan.gob.mx/cdn/img/favicon/apple-touch-icon-114x114.png" />
  <link rel="apple-touch-icon" sizes="120x120" href="https://michoacan.gob.mx/cdn/img/favicon/apple-touch-icon-120x120.png" />
  <link rel="apple-touch-icon" sizes="144x144" href="https://michoacan.gob.mx/cdn/img/favicon/apple-touch-icon-144x144.png" />
  <link rel="apple-touch-icon" sizes="152x152" href="https://michoacan.gob.mx/cdn/img/favicon/apple-touch-icon-152x152.png" />
  <link rel="apple-touch-icon" sizes="180x180" href="https://michoacan.gob.mx/cdn/img/favicon/apple-touch-icon-180x180.png" />

<script async src="https://www.googletagmanager.com/gtag/js?id=UA-5426449-1"></script>
<script>  window.dataLayer = window.dataLayer || [];  function gtag(){dataLayer.push(arguments)};  gtag('js', new Date());  gtag('config', 'UA-5426449-1');</script>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-5T424M46RJ"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-5T424M46RJ');
</script>
<meta name='robots' content='max-image-preview:large' />
<link rel='dns-prefetch' href='//s.w.org' />
		<script type="text/javascript">
			window._wpemojiSettings = {"baseUrl":"https:\/\/s.w.org\/images\/core\/emoji\/13.1.0\/72x72\/","ext":".png","svgUrl":"https:\/\/s.w.org\/images\/core\/emoji\/13.1.0\/svg\/","svgExt":".svg","source":{"concatemoji":"https:\/\/michoacan.gob.mx\/wp-includes\/js\/wp-emoji-release.min.js?ver=5.8.1"}};
			!function(e,a,t){var n,r,o,i=a.createElement("canvas"),p=i.getContext&&i.getContext("2d");function s(e,t){var a=String.fromCharCode;p.clearRect(0,0,i.width,i.height),p.fillText(a.apply(this,e),0,0);e=i.toDataURL();return p.clearRect(0,0,i.width,i.height),p.fillText(a.apply(this,t),0,0),e===i.toDataURL()}function c(e){var t=a.createElement("script");t.src=e,t.defer=t.type="text/javascript",a.getElementsByTagName("head")[0].appendChild(t)}for(o=Array("flag","emoji"),t.supports={everything:!0,everythingExceptFlag:!0},r=0;r<o.length;r++)t.supports[o[r]]=function(e){if(!p||!p.fillText)return!1;switch(p.textBaseline="top",p.font="600 32px Arial",e){case"flag":return s([127987,65039,8205,9895,65039],[127987,65039,8203,9895,65039])?!1:!s([55356,56826,55356,56819],[55356,56826,8203,55356,56819])&&!s([55356,57332,56128,56423,56128,56418,56128,56421,56128,56430,56128,56423,56128,56447],[55356,57332,8203,56128,56423,8203,56128,56418,8203,56128,56421,8203,56128,56430,8203,56128,56423,8203,56128,56447]);case"emoji":return!s([10084,65039,8205,55357,56613],[10084,65039,8203,55357,56613])}return!1}(o[r]),t.supports.everything=t.supports.everything&&t.supports[o[r]],"flag"!==o[r]&&(t.supports.everythingExceptFlag=t.supports.everythingExceptFlag&&t.supports[o[r]]);t.supports.everythingExceptFlag=t.supports.everythingExceptFlag&&!t.supports.flag,t.DOMReady=!1,t.readyCallback=function(){t.DOMReady=!0},t.supports.everything||(n=function(){t.readyCallback()},a.addEventListener?(a.addEventListener("DOMContentLoaded",n,!1),e.addEventListener("load",n,!1)):(e.attachEvent("onload",n),a.attachEvent("onreadystatechange",function(){"complete"===a.readyState&&t.readyCallback()})),(n=t.source||{}).concatemoji?c(n.concatemoji):n.wpemoji&&n.twemoji&&(c(n.twemoji),c(n.wpemoji)))}(window,document,window._wpemojiSettings);
		</script>
		<style type="text/css">
img.wp-smiley,
img.emoji {
	display: inline !important;
	border: none !important;
	box-shadow: none !important;
	height: 1em !important;
	width: 1em !important;
	margin: 0 .07em !important;
	vertical-align: -0.1em !important;
	background: none !important;
	padding: 0 !important;
}
</style>
	<link rel='stylesheet' id='wp-block-library-css'  href='https://michoacan.gob.mx/wp-includes/css/dist/block-library/style.min.css?ver=5.8.1' type='text/css' media='all' />
<link rel='stylesheet' id='pojo-a11y-css'  href='https://michoacan.gob.mx/wp-content/plugins/pojo-accessibility/assets/css/style.min.css?ver=1.0.0' type='text/css' media='all' />
<script type='text/javascript' src='https://michoacan.gob.mx/wp-includes/js/jquery/jquery.min.js?ver=3.6.0' id='jquery-core-js'></script>
<script type='text/javascript' src='https://michoacan.gob.mx/wp-includes/js/jquery/jquery-migrate.min.js?ver=3.3.2' id='jquery-migrate-js'></script>
<link rel="https://api.w.org/" href="https://michoacan.gob.mx/wp-json/" /><link rel="alternate" type="application/json" href="https://michoacan.gob.mx/wp-json/wp/v2/pages/6216" /><link rel="EditURI" type="application/rsd+xml" title="RSD" href="https://michoacan.gob.mx/xmlrpc.php?rsd" />
<link rel="wlwmanifest" type="application/wlwmanifest+xml" href="https://michoacan.gob.mx/wp-includes/wlwmanifest.xml" /> 
<meta name="generator" content="WordPress 5.8.1" />
<link rel="canonical" href="https://michoacan.gob.mx/tramites-vehiculares/" />
<link rel='shortlink' href='https://michoacan.gob.mx/?p=6216' />
<link rel="alternate" type="application/json+oembed" href="https://michoacan.gob.mx/wp-json/oembed/1.0/embed?url=https%3A%2F%2Fmichoacan.gob.mx%2Ftramites-vehiculares%2F" />
<link rel="alternate" type="text/xml+oembed" href="https://michoacan.gob.mx/wp-json/oembed/1.0/embed?url=https%3A%2F%2Fmichoacan.gob.mx%2Ftramites-vehiculares%2F&#038;format=xml" />
<style type="text/css">
#pojo-a11y-toolbar .pojo-a11y-toolbar-toggle a{ background-color: #4a001f;	color: #ffffff;}
#pojo-a11y-toolbar .pojo-a11y-toolbar-overlay, #pojo-a11y-toolbar .pojo-a11y-toolbar-overlay ul.pojo-a11y-toolbar-items.pojo-a11y-links{ border-color: #4a001f;}
body.pojo-a11y-focusable a:focus{ outline-style: solid !important;	outline-width: 1px !important;	outline-color: #ffc3d0 !important;}
#pojo-a11y-toolbar{ top: 106px !important;}
#pojo-a11y-toolbar .pojo-a11y-toolbar-overlay{ background-color: #4a001f;}
#pojo-a11y-toolbar .pojo-a11y-toolbar-overlay ul.pojo-a11y-toolbar-items li.pojo-a11y-toolbar-item a, #pojo-a11y-toolbar .pojo-a11y-toolbar-overlay p.pojo-a11y-toolbar-title{ color: #ffc3d0;}
#pojo-a11y-toolbar .pojo-a11y-toolbar-overlay ul.pojo-a11y-toolbar-items li.pojo-a11y-toolbar-item a.active{ background-color: #4a001f;	color: #4a001f;}
@media (max-width: 767px) { #pojo-a11y-toolbar { top: 50px !important; } }</style><link rel="icon" href="https://michoacan.gob.mx/wp-content/uploads/2021/09/cropped-LogoGobMich-Escudo-Guinda-600-600-32x32.png" sizes="32x32" />
<link rel="icon" href="https://michoacan.gob.mx/wp-content/uploads/2021/09/cropped-LogoGobMich-Escudo-Guinda-600-600-192x192.png" sizes="192x192" />
<link rel="apple-touch-icon" href="https://michoacan.gob.mx/wp-content/uploads/2021/09/cropped-LogoGobMich-Escudo-Guinda-600-600-180x180.png" />
<meta name="msapplication-TileImage" content="https://michoacan.gob.mx/wp-content/uploads/2021/09/cropped-LogoGobMich-Escudo-Guinda-600-600-270x270.png" />
		<style type="text/css" id="wp-custom-css">
			.textoGuinda a{
	color: #4A001F;
}		</style>
		</head>

<body class="body-wrapper">

<!-- overlay !-->
<div id="search" class="fade">
    <a href="#" class="close-btn" id="close-search">
        <em class="fa fa-times"></em>
    </a>
     <form id="searchform" method="get" action="https://michoacan.gob.mx/">
        <input type="text" class="search-field" name="s" placeholder="¿Qué estás buscando?" id="searchbox" value="">
        <input type="submit" class="btnRosa" value="Buscar" style="display: block; margin: 0 auto; margin-top: 8px;">
    </form>
</div>
<!--- /overlay -->

<nav class="navbar main-nav fixed-top navbar-expand-lg" style="border-bottom: 5px solid #6A0F49;">
  <div class="container-fluid">
      <a class="navbar-brand" href="https://michoacan.gob.mx">
        <img src="https://michoacan.gob.mx/cdn/img/logo.svg?ver=6" height="75px;" style="max-width: 280px !important; " alt="logo">
      </a>
      <button class="navbar-toggler collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="navbarNav">
      <ul class="navbar-nav ml-auto">
        <li class="nav-item">
          <a class="nav-link" href="https://michoacan.gob.mx">Inicio</a>
        </li>
        
        
        <li class="nav-item linkancla">
                    <a class="nav-link" href="https://michoacan.gob.mx/#noticias">Noticias</a>
                </li>
        <li class="nav-item">
          <a class="nav-link" href="http://tramites.michoacan.gob.mx" target="_blank">Trámites</a>
        </li>
        <li class="nav-item">
          <a class="nav-link" data-bs-toggle="modal" data-bs-target="#avisoDePrivacidad" style="cursor:pointer;">Transparencia</a>
        </li>
        <li class="nav-item">
            <a class="nav-link" href="" data-bs-toggle="modal" data-bs-target="#transparenciafinanciera">Transparencia Financiera</a>
        </li>
        <li class="nav-item linkancla">
                    <a class="nav-link" href="https://michoacan.gob.mx/#contacto">Contacto</a>
                </li>
        <li class="nav-item">
          <a class="nav-link" href="https://www.facebook.com/gobmichoacan" target="_blank"><i class="fab fa-facebook-f"></i></a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="https://twitter.com/GobMichoacan" target="_blank"><i class="fab fa-twitter"></i></a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href='#search'>
              <em class="fa fa-search"></em>
          </a>
        </li>
      </ul>
      </div>
  </div>
</nav>   <!--=================================
=            Menú            =
==================================-->


<style>
  
.tramites
{
  padding: 50px 0px;
  text-align: center;

}

.tramites h1
{
    color: #777;
    display: inline;
    font-size: 38px;
    font-weight: inherit;
}

.tramites label
{
    background: #e02217;
    padding: 0px 12px;
    border-radius: 6px;
    font-weight: bolder;
    color: white;
    font-size: 38px;
    margin-right: 6px;
 
}
.tramites p
{
    color: #666;
    font-size: 14px;
    margin: 15px 0px 0px 0px;
    
}



.tramites .tramites-block .tramites-box
{
    display: inline-block;
    height: 250px;
    width: 262px;
    margin: 0px 13px;
    cursor:pointer;
    text-align: center;
    border-radius: 5px;
    position: relative;
    padding: 90px 5px;
    margin-bottom: 30px;
    border: 1px solid rgba(238, 238, 238, 0.65);
    box-shadow: 0px 8px 40px 0px rgba(0, 0, 0, 0.08);
    -webkit-transition: 0.36s;
    transition: 0.36s;
    background-color: #fff;

}
.tramites .tramites-block .tramites-box:hover
{
    border: 1px solid #fff;

    transform: scale(1.05); border: 1px solid #fff;
    background:#4A001F;

    box-shadow: -1px -1px 15px 0px rgba(0,0,0,0.75);
-webkit-box-shadow: -1px -1px 15px 0px rgba(0,0,0,0.75);
-moz-box-shadow: -1px -1px 15px 0px rgba(0,0,0,0.75);
}


.tramites .tramites-block .tramites-box:hover h2
{
    color: white;
    
    color: #fff;
}
.tramites .tramites-block .tramites-box:hover i {
    color: white;
    /* left: 0; */
    
    color: #fff;
    /* right: 0; */
    /* top: 150px; */
    /* position: absolute; */
   
    /* transition: all 600ms cubic-bezier(0.68, -0.55, 0.265, 1.55) 0s; */
}
.tramites .tramites-block .tramites-box:hover  p
{
 
    color: white;
 }

.tramites .tramites-block .tramites-box:before
{
    position: absolute;
    content: "";
    height: 25%;
    width: 25%;
    left: 10px;
    top: 10px;
    border-top-left-radius: 5px;
    border-top: 1px solid #4A001F;
    border-left: 1px solid #4A001F;
}
.tramites .tramites-block .tramites-box:after
{
  position: absolute;
    content: "";
    height: 25%;
    width: 25%;
    bottom: 10px;
    right: 10px;
    border-bottom-right-radius: 5px;
    border-bottom: 1px solid #4A001F;
    border-right: 1px solid #4A001F;
}
.tramites .tramites-block .tramites-box h2
{
  text-transform: capitalize;
    color: #4A001F;
    top: 120px;
    font-size: 18px;
   
    left: 0;
    right: 0;
   
    font-size: 20px;
    position: absolute;
   

}

.tramites .tramites-block .tramites-box p
{
  position: absolute;
    opacity: 1;
  color:#4A001F;
    top: 130px;
    right: 0px;
    left: 0px;
    transform: scale(0.6);
    margin: 5px auto;
    padding: 0px 5px;
      font-size:25px;

}
   
.tramites .tramites-block .tramites-box span i {
    font-size: 40px;
    color: #4A001F;
    position: absolute;
    left: 0;
    right: 0;
    top: 70px;
    position: absolute;
  
}



</style>




<section style="clear:both">

<div class="container-fluid fondoGuinda" style="padding:100px 0px 10px 0;">
    <div class="row">
      <div class="col-12">
        <div class="section-title">
          <br><br>
          <h2 class="textoGuinda"  style="margin-bottom: 0 !important;">Trámites<span class="" style="padding-top: 15px !important;color: #FFC3D0; font-size: .6em;"> vehiculares</span></h2>

        </div>
      </div>
    </div>
  </div>



__RESULTADO__

        <div class="tramites">
          <div class="tramites-block">
            <!--<a href="https://www.michoacan.gob.mx/noticias/tramite-en-linea-reemplacamiento-2023/" target="_blank">
              <div class="tramites-box" >
                  <h2>Trámite remplacamiento</h2>
                    <span><i class="fas fa-car-side"></i></span>
                  <p>2023 en línea</p>
              </div>
            </a> -->
            <a href="https://www.michoacan.gob.mx/tramites/bienvenido-consulte-sus-adeudos-de-tenencia-y-o-refrendo/" target="_blank">
              <div class="tramites-box" >
                  <h2>Refrendo</h2>
                    <span><i class="fas fa-car-side"></i></span>
                  <p>vehicular</p>
              </div>
            </a>
            <a href="https://www.michoacan.gob.mx/tramites/licencias/" target="_blank">
            <div class="tramites-box">
              <h2>Licencia</h2>
              <span><i class="fas fa-id-card"></i></span>
              <p>de conducir</p>
            </div>
            </a>
            <a href="https://www.michoacan.gob.mx/tramites/cambio-de-propietario/" target="_blank">
                  <div class="tramites-box">
                    <h2>Cambio </h2>
                    <span><i class="fas fa-people-arrows"></i></span>
                    <p>de propietario</p>
                </div>
            </a>
            

          
          </div>
        </div>


        <div class="tramites">
          <div class="tramites-block">
            
            <a href="https://www.michoacan.gob.mx/tramites/alta-de-vehiculo/" target="_blank">
            <div class="tramites-box" >
              <h2>Alta</h2>
              <span><i class="fas fa-copy"></i></span>
              <p>de vehículo</p>
            </div>
          </a>
           <a href="https://www.michoacan.gob.mx/tramites/baja-de-vehiculo/" target="_blank">
            <div class="tramites-box" >
              <h2>Baja</h2>
              <span><i class="fas fa-user-times"></i></span>
              <p>de vehículos</p>
            </div>
          </a>
           <a href="https://www.michoacan.gob.mx/tramites/dotacion-de-placas/" target="_blank">
            <div class="tramites-box" >
              <h2>Dotación</h2>
              <span><i class="fas fa-car"></i></span>
              <p>de placas</p>
            </div>
          </a>
           <a href="https://www.michoacan.gob.mx/tramites/ubicacion-de-oficinas-de-rentas-morelia/" target="_blank">
            <div class="tramites-box" >
              <h2>Oficinas</h2>
              <span><i class="fas fa-building"></i></span>
              <p>de rentas Morelia</p>
            </div>
          </a>
          </div>
        </div>


    </section>

<!--=================================
=            Menú            =
==================================-->


<footer>
    <div class="container footer-main">
      <div class="row">
        <div class="col-lg-4 text-center">
          <div class="footer-logo">
            <img src="https://michoacan.gob.mx/cdn/img/logo-gris.svg?1222259157.415" height="85px;" class="logoFooter" alt="footer-logo">
          </div>
          
        </div>
        <div class="col-lg-4 text-center">
          <!-- Social Icons -->
          <ul class="social-icons list-inline">
            <li class="list-inline-item">
              <br>
             <a href="https://twitter.com/GobMichoacan" target="_blank"><i class="fab fa-2x fa-twitter"></i></a>&nbsp;&nbsp;
            </li>
            <li class="list-inline-item">
              <br>
             <a href="https://www.facebook.com/gobmichoacan/" target="_blank"><i class="fab fa-2x fa-facebook"></i></a>&nbsp;&nbsp;
            </li>
            <li class="list-inline-item">
              <br>
             <a href="https://www.instagram.com/gobmichoacan/?hl=es" target="_blank"><i class="fab fa-2x fa-instagram"></i></a>&nbsp;&nbsp;
            </li>
             <li class="list-inline-item">
              <br>
             <a href="https://t.me/GobiernodeMichoacan" target="_blank"><i class="fab fa-2x fa-telegram-plane"></i></a>&nbsp;&nbsp;
            </li>
            <li class="list-inline-item">
              <br>
             <a href="https://open.spotify.com/user/rr3zgtpveoxmy02i5t9bj9l7z" target="_blank"><i class="fab fa-2x fa-spotify"></i></a>&nbsp;&nbsp;
            </li>
          </ul>
          <!-- Footer Links -->
          <a class="textoGuinda" href="http://smo.michoacan.gob.mx">Correo institucional</a><br>
          <a class="textoGuinda" href="https://michoacan.gob.mx/aviso-de-privacidad/">Aviso de privacidad</a> <br>
         </div>
         <div class="col-lg-4 text-center">
          <br>
          <h4 class="textoGris">#MichoacanEsMejor</h4>
         </div>
         <div class="col-12">
           <hr>
         </div>
         <div class="col-12 text-center">
           © Desarrollado por la Coordinación de Comunicación | <b class="textoGuinda">Gobierno del Estado de Michoacán 2026</b>
         </div>
      </div>
    </div>
    <div class="container-fluid footer-pleca">
      <div class="row">
        <div class="col">
          <br><br>
        </div>
      </div>
    </div>
</footer>

  <!-- JAVASCRIPTS -->
  
  <script src="https://michoacan.gob.mx/cdn/js/jquery-3.6.0.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.0.4/popper.js"></script>
  <script src="https://michoacan.gob.mx/cdn/js/bootstrap.min.js"></script>
  <script src="https://michoacan.gob.mx/plugins/slick/slick.min.js"></script> 
  <script src="https://cdnjs.cloudflare.com/ajax/libs/OwlCarousel2/2.3.4/owl.carousel.min.js"></script>
<!-- animaciones -->
  <script src="https://unpkg.com/aos@next/dist/aos.js"></script>
  <script src="https://michoacan.gob.mx/cdn/js/init.js?ver=00.2"></script> 

  <!-- Modal: gabinete -->
<div class="modal fade" id="modalCarlosT" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
            <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/carlos-torres.jpg" class="img-fluid" loading="lazy" alt="carlos torres piña">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/carlos-torres-movil.jpg" class="img-fluid" loading="lazy" alt="carlos torres piña">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->


<!-- Modal: gabinete -->
<div class="modal fade" id="modalJoseA" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
             <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/jose-ortega.jpg" class="img-fluid" loading="lazy" alt="jose ortega">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/jose-ortega-movil.jpg" class="img-fluid" loading="lazy" alt="jose ortega">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->


<!-- Modal: gabinete -->
<div class="modal fade" id="modalClaudioM" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
             <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/claudio-mendez.jpg" class="img-fluid" loading="lazy" alt="claudio mendez">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/claudio-mendez-movil.jpg" class="img-fluid" loading="lazy" alt="claudio mendez">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->



<!-- Modal: gabinete -->
<div class="modal fade" id="modalAndreaS" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: white; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
             <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/andrea-serna1.jpg" class="img-fluid" loading="lazy" alt="Andrea Janet Serna Hernández">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/andrea-serba1-movil.jpg" class="img-fluid" loading="lazy" alt="Andrea Janet Serna Hernández">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->


<!-- Modal: gabinete -->
<div class="modal fade" id="modalLuisN" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
              <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/luis-navarro.jpg" class="img-fluid" loading="lazy" alt="luis navarro">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/luis-navarro-movil.jpg" class="img-fluid" loading="lazy" alt="luis navarro">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->





<!-- Modal: gabinete -->
<div class="modal fade" id="modalAzucenaM" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
              <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/azucena-marin.jpg" class="img-fluid" loading="lazy" alt="azucena marin">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/azucena-marin-movil.jpg" class="img-fluid" loading="lazy" alt="azucena marin">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->

<!-- Modal: gabinete -->
<div class="modal fade" id="modalJoseZ" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
              <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/jose-zavala.jpg" class="img-fluid" loading="lazy" alt="josé zavala">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/jose-zavala-movil.jpg" class="img-fluid" loading="lazy" alt="josé zavala">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->



<!-- Modal: gabinete -->
<div class="modal fade" id="modalAlfredoA" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
              <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/alfredo-anaya.jpg" class="img-fluid" loading="lazy" alt="alfredo anaya">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/alfredo-anaya-movil.jpg" class="img-fluid" loading="lazy" alt="alfredo anaya">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->

<!-- Modal: gabinete -->
<div class="modal fade" id="modalGladyzB" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
              <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/gladyz-butanda.jpg" class="img-fluid" loading="lazy" alt="gladyz butanda">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/gladyz-butanda-movil.jpg" class="img-fluid" loading="lazy" alt="gladyz butanda">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->

<!-- Modal: gabinete -->
<div class="modal fade" id="modalGabrielaM" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
              <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/gabriela-molina.jpg" class="img-fluid" loading="lazy" alt="gabriela molina">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/gabriela-molina-movil.jpg" class="img-fluid" loading="lazy" alt="gabriela molina">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->


<!-- Modal: gabinete -->
<div class="modal fade" id="modalEliasI" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
             <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/elias-ibarra.jpg" class="img-fluid" loading="lazy" alt="elias ibarra">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/elias-ibarra-movil.jpg" class="img-fluid" loading="lazy" alt="elias ibarra">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->


<!-- Modal: gabinete -->
<div class="modal fade" id="modalRobertoM" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
             <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/roberto-monroy.jpg" class="img-fluid" loading="lazy" alt="roberto monroy">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/roberto-monroy-movil.jpg" class="img-fluid" loading="lazy" alt="roberto monroy">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->


<!-- Modal: gabinete -->
<div class="modal fade" id="modalSandraR" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
              <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/sandra-rangel.jpg" class="img-fluid" loading="lazy" alt="sandra rangel">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/sandra-rangel-movil.jpg" class="img-fluid" loading="lazy" alt="sandra rangel">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->


<!-- Modal: gabinete -->
<div class="modal fade" id="modalTamaraS" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
             <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/tamara-sosa.jpg" class="img-fluid" loading="lazy" alt="tamara sosa">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/tamara-sosa-movil.jpg" class="img-fluid" loading="lazy" alt="tamara sosa">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->



<!-- Modal: gabinete -->
<div class="modal fade" id="modalCuahutemocR" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
             <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/cuauhtemoc-ramirez.jpg" class="img-fluid" loading="lazy" alt="cuauhtemoc ramirez">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/cuauhtemoc-ramirez-movil.jpg" class="img-fluid" loading="lazy" alt="cuauhtemoc ramirez">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->


<!-- Modal: gabinete -->
<div class="modal fade" id="modalJoseZ" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
             <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/jose-zavala.jpg" class="img-fluid" loading="lazy" alt="jose zavala">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/jose-zavala-movil.jpg" class="img-fluid" loading="lazy" alt="jose zavala">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->



<!-- Modal: gabinete -->
<div class="modal fade" id="modalYarabiA" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
             <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/yarabi-avila.jpg" class="img-fluid" loading="lazy" alt="yarabi avila">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/yarabi-avila-movil.jpg" class="img-fluid" loading="lazy" alt="yarabi avila">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->


<!-- Modal: gabinete -->
<div class="modal fade" id="modalBrendaF" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
              <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/brenda-fraga.jpg" class="img-fluid" loading="lazy" alt="brenda fraga">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/brenda-fraga-movil.jpg" class="img-fluid" loading="lazy" alt="brenda fraga">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->




<!-- Modal: gabinete -->
<div class="modal fade" id="modalAlejandroM" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-lg" role="document">
    <div class="modal-content">
      <!--Header-->
      <!--<div class="modal-header">
        <h4 class="modal-title" id="myModalLabel">Comentários da Lead</h4>
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">×</span>
        </button>
      </div> -->
      <!--Body-->
      <div class="modal-body  modal-lg" style="position: relative;">
  
          <span style="position: absolute; top: 15px; z-index: 999 !important; right: 15px; color: #6A0F49; font-size: 24px; cursor: pointer;" data-bs-dismiss="modal" aria-label="Close" aria-hidden="true">×</span>


        <div class="row d-flex justify-content-center mt-7 mb-7">
          <div class="col-md-12">
              <div class="d-none d-sm-none d-md-block d-lg-block">
              <img src="https://michoacan.gob.mx/images/gabinete/alejandro-mendez.jpg" class="img-fluid" loading="lazy" alt="alejandro mendez">
            </div>
            <div class="d-block d-sm-block d-md-none d-lg-none">
              <img src="https://michoacan.gob.mx/images/gabinete/alejandro-mendez-movil.jpg" class="img-fluid" loading="lazy" alt="alejandro mendez">
            </div>
              </div>
            </div>
          

      </div>
      <!--Footer-->
      <!--<div class="modal-footer">
        <button type="button" class="btn btn-outline-primary" data-bs-dismiss="modal">Fechar</button>
        <button class="btn btn-primary">Novo Comentario</button>
      </div> -->
    </div>
  </div>
</div>
<!-- Modal: gabinete -->





<div class="modal modal-fullscreen fade" id="segMenu" tabindex="-1" role="dialog" aria-labelledby="segMenu">
  <div class="modal-dialog" role="document">
    <div class="modal-content">
      <div class="modal-header">
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
        <h2 class="textoGuinda modal-title" style="margin-bottom: 0 !important;">Seguridad <span class="" style="padding-top: 15px !important;color: #6D807F; font-size: .6em;">y asistencia</span></h2>
      </div>
      <div class="modal-body">
        <div class="row">

          <div class="col-12">
            <br>
          </div>
   
            <div class="col-md-4 col-sm-6 col-12 text-center">
              <center>
                <a  class="modal-card">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fab fa-whatsapp"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Whatsapp 070 <br>4432315908</h3>
                </div>
              </div>
              </a>
              </center>
            </div>
            <div class="col-md-4 col-sm-6 col-12 text-center">
              <center>
                <a href="https://comisionnacionaldebusqueda.com/" class="modal-card" target="_blank">
              <!-- <a href="/red-de-personas" class="modal-card" target="_blank"> -->
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-user-circle"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Red de Busqueda de Personas Desaparecidas</h3>
                </div>
              </div>
              </a>
              </center>
            </div>
  
            <div class="col-md-4 col-sm-6 col-12 text-center">
              <center>
                <a href="tel:4431136700"  class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-heartbeat"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">44-31-13-67-00<br/>Linea de atención para las mujeres</h3>
                </div>
              </div>
              </a>
              </center>
            </div>

        </div>


        <div class="row">
          <div class="col-12">
            <br><br>
          </div>
     
            <div class="col-12 text-center">
              <h3 class="textoGuinda tituloModal">Números de emergencia <br><small>marca desde aquí</small></h3>
              <br>
            </div>
            <div class="clearfix"></div>
            <br>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
              <a href="tel:911"  class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-ambulance"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">911 <br>Emergencias</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
              <a href="tel:018005533000" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-phone"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">01 (800) 553 3000<br/>Denuncia contra la trata</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
              <a href="tel:018006142323" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-phone"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">01 (800) 614 2323<br/>Personas desaparecidas</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
              <a href="tel:089" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-phone"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">089<br/>Denuncia anónima</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="clearfix"></div>
            <div class="col-12">
              <br><br>
            </div>

            <div class="col-md-4 col-sm-6 col-12">
              <center>
              <a href="tel:911" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-bus"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">911 <br>Bomberos</h3>
                </div>
              </div>
              </a>
            </div>
            
            <div class="col-md-4 col-sm-6 col-12">
              <center>
              <a href="tel:4433224800" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-truck"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">44-33-22-48-00<br>Protección Civil</h3>
                </div>
              </div>
              </a>
            </div>
            <div class="col-md-4 col-sm-6 col-12">
              <center>
              <a href="tel:065" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-ambulance"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">065 <br>Cruz Roja</h3>
                </div>
              </div>
              </a>
            </div>

            <div class="col-12">
              <br><br>
              <center>
                <button data-bs-dismiss="modal" aria-label="Close" class="btnRosa">Cerrar</button>
              </center>
            </div>




            
         
        </div>
      </div>
    </div>
  </div>
</div>



<!-- modal trámites -->

<div class="modal modal-fullscreen fade" id="tramitesyservicios" tabindex="-1" role="dialog" aria-labelledby="tramitesyservicios">
  <div class="modal-dialog" role="document">
    <div class="modal-content">
      <div class="modal-header">
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
        <h2 class="textoGuinda modal-title" style="margin-bottom: 0 !important;">Trámites <span class="" style="padding-top: 15px !important;color: #6D807F; font-size: .6em;">y servicios</span></h2>
      </div>
      <div class="modal-body">
    

        <div class="row">

            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="https://michoacan.gob.mx/guias-refrendo-digital/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-car-side"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Refrendo digital</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="https://michoacan.gob.mx/tramites/bienvenido-consulte-sus-adeudos-de-tenencia-y-o-refrendo/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-car-side"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Refrendo</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="https://michoacan.gob.mx/tramites/licencias/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-id-card"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Licencia de conducir</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="https://michoacan.gob.mx/tramites/cambio-de-propietario/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-people-arrows"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Cambio de propietario</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="https://michoacan.gob.mx/tramites/alta-de-vehiculo/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-copy"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Alta de vehiculos</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="https://michoacan.gob.mx/tramites/baja-de-vehiculo/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-user-times"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Baja de vehiculos</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
              <a href="https://michoacan.gob.mx/tramites/dotacion-de-placas/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-car"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Dotación de placas</h3>
                </div>
              </div>
              </a>
            </center>
            </div>

             <div class="col-md-3 col-sm-6 col-12">
              <center>
              <a href="https://intra.secoem.michoacan.gob.mx/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-user-check"></i></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Certificados no inhabilitación</h3>
                </div>
              </div>
              </a>
            </center>
            </div>


            <div class="col-md-4 col-sm-6 col-12">
              <center>
              <a href="https://michoacan.gob.mx/tramites/acta-de-nacimiento-michoacan/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-file-alt"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Acta de nacimiento</h3>
                </div>
              </div>
              </a>
            </center>
            </div>

           

            

  
            <div class="col-md-4 col-sm-12 col-12">
              <center>
                <a href="https://michoacan.gob.mx/tramites/ubicacion-de-oficinas-de-rentas-morelia/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-building"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Ubicación de Oficinas de Rentas Morelia</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-4 col-sm-12 col-12">
              <center>
                <a href="https://michoacan.gob.mx/declaracion-patrimonial/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-balance-scale"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Declaración patrimonial</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
 
        </div>
        <div class="row">

            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="https://sfa.michoacan.gob.mx/nomina12/ini_nomina.php" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa">$</i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Pago de Impuesto sobre Nómina y Hospedaje</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="http://repecos.michoacan.gob.mx/pagos_internet/index.php" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-file"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Repecos, Intermedios, IEPS y Notarios</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="http://sfa.michoacan.gob.mx/isan/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-car"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title"><br>ISAN</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="http://sfa.michoacan.gob.mx/rifasSorteos/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-ticket-alt"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title"><br>Rifas, sorteos y loterias</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="http://sfa.michoacan.gob.mx/portalservicios/portal.php" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-mouse-pointer"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Servicios de Protección Civil y SEDECO</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
    
       
    
            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="http://sfa.michoacan.gob.mx/cobrossee/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-credit-card"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Portal de Cobro de Servicios de la SEE</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="http://sfa.michoacan.gob.mx/impuestos2020/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-leaf"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Portal de cobro de Impuestos Ecológicos</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            
            <div class="col-md-3 col-sm-6 col-12">
              <center>
                <a href="http://tramites.michoacan.gob.mx" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-plus"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Más trámites</h3>
                </div>
              </div>
              </a>
            </center>
            </div>
            <div class="col-12">
              <br><br>
              <center>
                <button data-bs-dismiss="modal" aria-label="Close" class="btnRosa">Cerrar</button>
              </center>
            </div>
            
    
        </div>
      </div>
    </div>
  </div>
</div>

<div class="modal modal-fullscreen fade" id="infOfi" tabindex="-1" role="dialog" aria-labelledby="#infOfi">
  <div class="modal-dialog" role="document">
    <div class="modal-content">
      <div class="modal-header">
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
        <h2 class="textoGuinda modal-title" style="margin-bottom: 0 !important;">Información <span class="" style="padding-top: 15px !important;color: #6D807F; font-size: .6em;">oficial</span></h2>
      </div>
      <div class="modal-body">


        <div class="row">
        
            
            <div class="clearfix"></div><br>
            <div class="col-md-3 col-xs-12"></div>
            <div class="col-md-3 col-sm-6 col-xs-12">
              <a href="http://periodicooficial.michoacan.gob.mx" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fas fa-newspaper"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Periódico Oficial</h3>
                </div>
              </div>
              </a>
            </div>
            <div class="col-md-3 col-sm-6 col-xs-12">
              <a href="https://michoacan.gob.mx/informacion/calendario-escolar-2026-2027-educacion/" class="modal-card" target="_blank">
              <div class="wrapper">
                <div class="icon-wrapper">
                  <span><i class="fa fa-calendar"></i></span>
                </div>
                <div class="text-center">
                  <h3 class="title">Calendario Escolar</h3>
                </div>
              </div>
              </a>
            </div>
            <div class="col-md-3 col-sm-6 col-xs-12"></div>
            <div class="clearfix"></div>
            <div class="col-md-3 col-sm-6 col-xs-12"></div>
            <div class="col-12">
              <br><br>
              <center>
                <button data-bs-dismiss="modal" aria-label="Close" class="btnRosa">Cerrar</button>
              </center>
            </div>
            

        </div>

      </div>
    </div>
  </div>
</div>


<div class="modal fade" id="avisoDePrivacidad" tabindex="-1" role="dialog" aria-labelledby="#avisoDePrivacidad">
  <div class="modal-dialog" role="document">
    <div class="modal-content">
      <div class="modal-header">
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
        <h2 class="textoGuinda modal-title" style="margin-bottom: 0 !important;">Transparencia <span class="" style="padding-top: 15px !important;color: #6D807F; font-size: .6em;"></span></h2>
      </div>
      <div class="modal-body">


        <div class="row text-center" style="padding:20px;">
<div class="col-xs-12"><a class="btn btn-primary" href="https://www.michoacan.gob.mx/aviso-de-privacidad-integral-del-despacho-del-gobernador/" target="_blank">Aviso de Privacidad</a> <p></p>
<hr>
<p>
<a href="https://consultapublicamx.plataformadetransparencia.org.mx/vut-web/?idSujetoObigadoParametro=3366&amp;idEntidadParametro=16&amp;idSectorParametro=21" targe="_blank"><img class="img-fluid" src="https://web.archive.org/web/20240104233253im_/https://www.michoacan.gob.mx/wp-content/uploads/2023/11/pnt.png" alt="plataforma nacional de transparencia"><br>
</a><button class="btn-primary btn-xs"><a href="https://consultapublicamx.plataformadetransparencia.org.mx/vut-web/?idSujetoObigadoParametro=3366&amp;idEntidadParametro=16&amp;idSectorParametro=21" targe="_blank">Ir a la Plataforma Nacional de Transparencia</a></button></p></div>
</div>

      </div>
    </div>
  </div>
</div>



<!-- modal transparencia financiera -->

<div class="modal modal-fullscreen fade" id="transparenciafinanciera" tabindex="-1" role="dialog" aria-labelledby="transparenciafinanciera">
  <div class="modal-dialog" role="document">
    <div class="modal-content">
      <div class="modal-header">
        <button type="button" class="close" data-bs-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
        <h2 class="textoGuinda modal-title" style="margin-bottom: 0 !important;">Transparencia Financiera</h2>
      </div>
      <div class="modal-body">


        <div class="row">

          <div class="col-12">
            <br>
          </div>

          <div class="col-md-4 col-sm-6 col-12">
            <center>
              <a href="https://secfinanzas.michoacan.gob.mx/categoria/paquete-fiscal-estatal/" class="modal-card" target="_blank">
                <div class="wrapper">
                  <div class="icon-wrapper">
                    <img src="https://michoacan.gob.mx/wp-content/uploads/2026/09/ley-de-ingresos.svg"
                  alt="ley de ingresos">
                  </div>
                  <div class="text-center">
                    <h3 class="title">LEY DE INGRESOS DEL ESTADO DE MICHOACÁN</h3>
                  </div>
                </div>
              </a>
            </center>
          </div>
          <div class="col-md-4 col-sm-6 col-12">
            <center>
              <a href="https://gestormichoacan.sfa.michoacan.gob.mx/Cuenta%20P%C3%BAblica/" class="modal-card" target="_blank">
                <div class="wrapper">
                 <div class="icon-wrapper">
                 <img src="https://michoacan.gob.mx/wp-content/uploads/2026/09/Ley-General-Contabilidad.svg"
                  alt="Contabilidad Gubernamental">
                  </div>
                  <div class="text-center">
                    <h3 class="title">LEY GENERAL DE CONTABILIDAD GUBERNAMENTAL</h3>
                  </div>
                </div>
              </a>
            </center>
          </div>
          <div class="col-md-4 col-sm-6 col-12">
            <center>
              <a href="https://gestormichoacan.sfa.michoacan.gob.mx/Cuenta%20P%C3%BAblica/" class="modal-card" target="_blank">
                <div class="wrapper">
                  <div class="icon-wrapper">
                  <img src="https://michoacan.gob.mx/wp-content/uploads/2026/09/Cuenta-Publica.svg"
                  alt="Cuenta Pública">
                  </div>
                  <div class="text-center">
                    <h3 class="title">CUENTA PÚBLICA</h3>
                  </div>
                </div>
              </a>
            </center>
          </div>
          <div class="col-md-4 col-sm-6 col-12">
            <center>
              <a href="https://secfinanzas.michoacan.gob.mx/categoria/paquete-fiscal-estatal/" class="modal-card" target="_blank">
                <div class="wrapper">
                  <div class="icon-wrapper">
                 <img src="https://michoacan.gob.mx/wp-content/uploads/2026/09/Decreto-del-Presupuesto.svg"
                  alt="Presupuesto Egresos">
                  </div>
                  <div class="text-center">
                    <h3 class="title">DECRETO DE PRESUPUESTO DE EGRESOS DEL ESTADO DE MICHOACÁN</h3>
                  </div>
                </div>
              </a>
            </center>
          </div>
          <div class="col-md-4 col-sm-6 col-12">
            <center>
              <a href="https://gestormichoacan.sfa.michoacan.gob.mx/Cuenta%20P%C3%BAblica/" class="modal-card" target="_blank">
                <div class="wrapper">
                  <div class="icon-wrapper">
                  <img src="https://michoacan.gob.mx/wp-content/uploads/2026/09/LDF.svg"
                  alt="LDF">
                  </div>
                  <div class="text-center">
                    <h3 class="title">LEY DE DISCIPLINA FINANCIERA DE LAS ENTIDADES FEDERATIVAS Y LOS MUNICPIOS</h3>
                  </div>
                </div>
              </a>
            </center>
          </div>
          <div class="col-md-4 col-sm-6 col-12">
            <center>
              <a href="https://secfinanzas.michoacan.gob.mx/wp-content/uploads/2026/06/LEY-DE-TRANSPARENCIA-Y-ACCESO-A-LA-INFORMACIO%CC%81N-2026-1.pdf" class="modal-card" target="_blank">
                <div class="wrapper">
                  <div class="icon-wrapper">
                  <img src="https://michoacan.gob.mx/wp-content/uploads/2026/09/LTAIP.svg"
                  alt="Transparencia">
                  </div>
                  <div class="text-center">
                    <h3 class="title">LEY DE TRANSPARENCIA Y ACCESO A LA INFORMACIÓN PUBLICA</h3>
                  </div>
                </div>
              </a>
            </center>
          </div>
          

        </div>
      </div>
    </div>
  </div>
</div><script type='text/javascript' id='pojo-a11y-js-extra'>
/* <![CDATA[ */
var PojoA11yOptions = {"focusable":"","remove_link_target":"","add_role_links":"","enable_save":"","save_expiration":""};
/* ]]> */
</script>
<script type='text/javascript' src='https://michoacan.gob.mx/wp-content/plugins/pojo-accessibility/assets/js/app.min.js?ver=1.0.0' id='pojo-a11y-js'></script>
<script type='text/javascript' src='https://michoacan.gob.mx/wp-includes/js/wp-embed.min.js?ver=5.8.1' id='wp-embed-js'></script>
		<a id="pojo-a11y-skip-content" class="pojo-skip-link pojo-skip-content" tabindex="1" accesskey="s" href="#content">Skip to content</a>
				<nav id="pojo-a11y-toolbar" class="pojo-a11y-toolbar-right" role="navigation">
			<div class="pojo-a11y-toolbar-toggle">
				<a class="pojo-a11y-toolbar-link pojo-a11y-toolbar-toggle-link" href="javascript:void(0);" title="Herramientas de Accesibilidad">
					<span class="pojo-sr-only sr-only">Open toolbar</span>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="currentColor" width="1em">
						<path d="M50 .8c5.7 0 10.4 4.7 10.4 10.4S55.7 21.6 50 21.6s-10.4-4.7-10.4-10.4S44.3.8 50 .8zM92.2 32l-21.9 2.3c-2.6.3-4.6 2.5-4.6 5.2V94c0 2.9-2.3 5.2-5.2 5.2H60c-2.7 0-4.9-2.1-5.2-4.7l-2.2-24.7c-.1-1.5-1.4-2.5-2.8-2.4-1.3.1-2.2 1.1-2.4 2.4l-2.2 24.7c-.2 2.7-2.5 4.7-5.2 4.7h-.5c-2.9 0-5.2-2.3-5.2-5.2V39.4c0-2.7-2-4.9-4.6-5.2L7.8 32c-2.6-.3-4.6-2.5-4.6-5.2v-.5c0-2.6 2.1-4.7 4.7-4.7h.5c19.3 1.8 33.2 2.8 41.7 2.8s22.4-.9 41.7-2.8c2.6-.2 4.9 1.6 5.2 4.3v1c-.1 2.6-2.1 4.8-4.8 5.1z"/>					</svg>
				</a>
			</div>
			<div class="pojo-a11y-toolbar-overlay">
				<div class="pojo-a11y-toolbar-inner">
					<p class="pojo-a11y-toolbar-title">Herramientas de Accesibilidad</p>
					
					<ul class="pojo-a11y-toolbar-items pojo-a11y-tools">
																			<li class="pojo-a11y-toolbar-item">
								<a href="#" class="pojo-a11y-toolbar-link pojo-a11y-btn-resize-font pojo-a11y-btn-resize-plus" data-action="resize-plus" data-action-group="resize" tabindex="-1">
									<span class="pojo-a11y-toolbar-icon"><svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="1em" viewBox="0 0 448 448"><path fill="currentColor" d="M256 200v16c0 4.25-3.75 8-8 8h-56v56c0 4.25-3.75 8-8 8h-16c-4.25 0-8-3.75-8-8v-56h-56c-4.25 0-8-3.75-8-8v-16c0-4.25 3.75-8 8-8h56v-56c0-4.25 3.75-8 8-8h16c4.25 0 8 3.75 8 8v56h56c4.25 0 8 3.75 8 8zM288 208c0-61.75-50.25-112-112-112s-112 50.25-112 112 50.25 112 112 112 112-50.25 112-112zM416 416c0 17.75-14.25 32-32 32-8.5 0-16.75-3.5-22.5-9.5l-85.75-85.5c-29.25 20.25-64.25 31-99.75 31-97.25 0-176-78.75-176-176s78.75-176 176-176 176 78.75 176 176c0 35.5-10.75 70.5-31 99.75l85.75 85.75c5.75 5.75 9.25 14 9.25 22.5z""></path></svg></span><span class="pojo-a11y-toolbar-text">Aumentar tamaño texto</span>								</a>
							</li>
							
							<li class="pojo-a11y-toolbar-item">
								<a href="#" class="pojo-a11y-toolbar-link pojo-a11y-btn-resize-font pojo-a11y-btn-resize-minus" data-action="resize-minus" data-action-group="resize" tabindex="-1">
									<span class="pojo-a11y-toolbar-icon"><svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="1em" viewBox="0 0 448 448"><path fill="currentColor" d="M256 200v16c0 4.25-3.75 8-8 8h-144c-4.25 0-8-3.75-8-8v-16c0-4.25 3.75-8 8-8h144c4.25 0 8 3.75 8 8zM288 208c0-61.75-50.25-112-112-112s-112 50.25-112 112 50.25 112 112 112 112-50.25 112-112zM416 416c0 17.75-14.25 32-32 32-8.5 0-16.75-3.5-22.5-9.5l-85.75-85.5c-29.25 20.25-64.25 31-99.75 31-97.25 0-176-78.75-176-176s78.75-176 176-176 176 78.75 176 176c0 35.5-10.75 70.5-31 99.75l85.75 85.75c5.75 5.75 9.25 14 9.25 22.5z"></path></svg></span><span class="pojo-a11y-toolbar-text">Reducir tamaño texto</span>								</a>
							</li>
						
													<li class="pojo-a11y-toolbar-item">
								<a href="#" class="pojo-a11y-toolbar-link pojo-a11y-btn-background-group pojo-a11y-btn-grayscale" data-action="grayscale" data-action-group="schema" tabindex="-1">
									<span class="pojo-a11y-toolbar-icon"><svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="1em" viewBox="0 0 448 448"><path fill="currentColor" d="M15.75 384h-15.75v-352h15.75v352zM31.5 383.75h-8v-351.75h8v351.75zM55 383.75h-7.75v-351.75h7.75v351.75zM94.25 383.75h-7.75v-351.75h7.75v351.75zM133.5 383.75h-15.5v-351.75h15.5v351.75zM165 383.75h-7.75v-351.75h7.75v351.75zM180.75 383.75h-7.75v-351.75h7.75v351.75zM196.5 383.75h-7.75v-351.75h7.75v351.75zM235.75 383.75h-15.75v-351.75h15.75v351.75zM275 383.75h-15.75v-351.75h15.75v351.75zM306.5 383.75h-15.75v-351.75h15.75v351.75zM338 383.75h-15.75v-351.75h15.75v351.75zM361.5 383.75h-15.75v-351.75h15.75v351.75zM408.75 383.75h-23.5v-351.75h23.5v351.75zM424.5 383.75h-8v-351.75h8v351.75zM448 384h-15.75v-352h15.75v352z"></path></svg></span><span class="pojo-a11y-toolbar-text">Escala de grises</span>								</a>
							</li>
						
													<li class="pojo-a11y-toolbar-item">
								<a href="#" class="pojo-a11y-toolbar-link pojo-a11y-btn-background-group pojo-a11y-btn-high-contrast" data-action="high-contrast" data-action-group="schema" tabindex="-1">
									<span class="pojo-a11y-toolbar-icon"><svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="1em" viewBox="0 0 448 448"><path fill="currentColor" d="M192 360v-272c-75 0-136 61-136 136s61 136 136 136zM384 224c0 106-86 192-192 192s-192-86-192-192 86-192 192-192 192 86 192 192z""></path></svg></span><span class="pojo-a11y-toolbar-text">Alto contraste</span>								</a>
							</li>
						
						<li class="pojo-a11y-toolbar-item">
							<a href="#" class="pojo-a11y-toolbar-link pojo-a11y-btn-background-group pojo-a11y-btn-negative-contrast" data-action="negative-contrast" data-action-group="schema" tabindex="-1">

								<span class="pojo-a11y-toolbar-icon"><svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="1em" viewBox="0 0 448 448"><path fill="currentColor" d="M416 240c-23.75-36.75-56.25-68.25-95.25-88.25 10 17 15.25 36.5 15.25 56.25 0 61.75-50.25 112-112 112s-112-50.25-112-112c0-19.75 5.25-39.25 15.25-56.25-39 20-71.5 51.5-95.25 88.25 42.75 66 111.75 112 192 112s149.25-46 192-112zM236 144c0-6.5-5.5-12-12-12-41.75 0-76 34.25-76 76 0 6.5 5.5 12 12 12s12-5.5 12-12c0-28.5 23.5-52 52-52 6.5 0 12-5.5 12-12zM448 240c0 6.25-2 12-5 17.25-46 75.75-130.25 126.75-219 126.75s-173-51.25-219-126.75c-3-5.25-5-11-5-17.25s2-12 5-17.25c46-75.5 130.25-126.75 219-126.75s173 51.25 219 126.75c3 5.25 5 11 5 17.25z"></path></svg></span><span class="pojo-a11y-toolbar-text">Contraste negativo</span>							</a>
						</li>

													<li class="pojo-a11y-toolbar-item">
								<a href="#" class="pojo-a11y-toolbar-link pojo-a11y-btn-background-group pojo-a11y-btn-light-background" data-action="light-background" data-action-group="schema" tabindex="-1">
									<span class="pojo-a11y-toolbar-icon"><svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="1em" viewBox="0 0 448 448"><path fill="currentColor" d="M184 144c0 4.25-3.75 8-8 8s-8-3.75-8-8c0-17.25-26.75-24-40-24-4.25 0-8-3.75-8-8s3.75-8 8-8c23.25 0 56 12.25 56 40zM224 144c0-50-50.75-80-96-80s-96 30-96 80c0 16 6.5 32.75 17 45 4.75 5.5 10.25 10.75 15.25 16.5 17.75 21.25 32.75 46.25 35.25 74.5h57c2.5-28.25 17.5-53.25 35.25-74.5 5-5.75 10.5-11 15.25-16.5 10.5-12.25 17-29 17-45zM256 144c0 25.75-8.5 48-25.75 67s-40 45.75-42 72.5c7.25 4.25 11.75 12.25 11.75 20.5 0 6-2.25 11.75-6.25 16 4 4.25 6.25 10 6.25 16 0 8.25-4.25 15.75-11.25 20.25 2 3.5 3.25 7.75 3.25 11.75 0 16.25-12.75 24-27.25 24-6.5 14.5-21 24-36.75 24s-30.25-9.5-36.75-24c-14.5 0-27.25-7.75-27.25-24 0-4 1.25-8.25 3.25-11.75-7-4.5-11.25-12-11.25-20.25 0-6 2.25-11.75 6.25-16-4-4.25-6.25-10-6.25-16 0-8.25 4.5-16.25 11.75-20.5-2-26.75-24.75-53.5-42-72.5s-25.75-41.25-25.75-67c0-68 64.75-112 128-112s128 44 128 112z"></path></svg></span><span class="pojo-a11y-toolbar-text">Fondo de titulo claro</span>								</a>
							</li>
						
													<li class="pojo-a11y-toolbar-item">
								<a href="#" class="pojo-a11y-toolbar-link pojo-a11y-btn-links-underline" data-action="links-underline" data-action-group="toggle" tabindex="-1">
									<span class="pojo-a11y-toolbar-icon"><svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="1em" viewBox="0 0 448 448"><path fill="currentColor" d="M364 304c0-6.5-2.5-12.5-7-17l-52-52c-4.5-4.5-10.75-7-17-7-7.25 0-13 2.75-18 8 8.25 8.25 18 15.25 18 28 0 13.25-10.75 24-24 24-12.75 0-19.75-9.75-28-18-5.25 5-8.25 10.75-8.25 18.25 0 6.25 2.5 12.5 7 17l51.5 51.75c4.5 4.5 10.75 6.75 17 6.75s12.5-2.25 17-6.5l36.75-36.5c4.5-4.5 7-10.5 7-16.75zM188.25 127.75c0-6.25-2.5-12.5-7-17l-51.5-51.75c-4.5-4.5-10.75-7-17-7s-12.5 2.5-17 6.75l-36.75 36.5c-4.5 4.5-7 10.5-7 16.75 0 6.5 2.5 12.5 7 17l52 52c4.5 4.5 10.75 6.75 17 6.75 7.25 0 13-2.5 18-7.75-8.25-8.25-18-15.25-18-28 0-13.25 10.75-24 24-24 12.75 0 19.75 9.75 28 18 5.25-5 8.25-10.75 8.25-18.25zM412 304c0 19-7.75 37.5-21.25 50.75l-36.75 36.5c-13.5 13.5-31.75 20.75-50.75 20.75-19.25 0-37.5-7.5-51-21.25l-51.5-51.75c-13.5-13.5-20.75-31.75-20.75-50.75 0-19.75 8-38.5 22-52.25l-22-22c-13.75 14-32.25 22-52 22-19 0-37.5-7.5-51-21l-52-52c-13.75-13.75-21-31.75-21-51 0-19 7.75-37.5 21.25-50.75l36.75-36.5c13.5-13.5 31.75-20.75 50.75-20.75 19.25 0 37.5 7.5 51 21.25l51.5 51.75c13.5 13.5 20.75 31.75 20.75 50.75 0 19.75-8 38.5-22 52.25l22 22c13.75-14 32.25-22 52-22 19 0 37.5 7.5 51 21l52 52c13.75 13.75 21 31.75 21 51z"></path></svg></span><span class="pojo-a11y-toolbar-text">Subrayar enlaces</span>								</a>
							</li>
						
													<li class="pojo-a11y-toolbar-item">
								<a href="#" class="pojo-a11y-toolbar-link pojo-a11y-btn-readable-font" data-action="readable-font" data-action-group="toggle" tabindex="-1">
									<span class="pojo-a11y-toolbar-icon"><svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="1em" viewBox="0 0 448 448"><path fill="currentColor" d="M181.25 139.75l-42.5 112.5c24.75 0.25 49.5 1 74.25 1 4.75 0 9.5-0.25 14.25-0.5-13-38-28.25-76.75-46-113zM0 416l0.5-19.75c23.5-7.25 49-2.25 59.5-29.25l59.25-154 70-181h32c1 1.75 2 3.5 2.75 5.25l51.25 120c18.75 44.25 36 89 55 133 11.25 26 20 52.75 32.5 78.25 1.75 4 5.25 11.5 8.75 14.25 8.25 6.5 31.25 8 43 12.5 0.75 4.75 1.5 9.5 1.5 14.25 0 2.25-0.25 4.25-0.25 6.5-31.75 0-63.5-4-95.25-4-32.75 0-65.5 2.75-98.25 3.75 0-6.5 0.25-13 1-19.5l32.75-7c6.75-1.5 20-3.25 20-12.5 0-9-32.25-83.25-36.25-93.5l-112.5-0.5c-6.5 14.5-31.75 80-31.75 89.5 0 19.25 36.75 20 51 22 0.25 4.75 0.25 9.5 0.25 14.5 0 2.25-0.25 4.5-0.5 6.75-29 0-58.25-5-87.25-5-3.5 0-8.5 1.5-12 2-15.75 2.75-31.25 3.5-47 3.5z"></path></svg></span><span class="pojo-a11y-toolbar-text">Fuente de lectura</span>								</a>
							</li>
																		<li class="pojo-a11y-toolbar-item">
							<a href="#" class="pojo-a11y-toolbar-link pojo-a11y-btn-reset" data-action="reset" tabindex="-1">
								<span class="pojo-a11y-toolbar-icon"><svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="1em" viewBox="0 0 448 448"><path fill="currentColor" d="M384 224c0 105.75-86.25 192-192 192-57.25 0-111.25-25.25-147.75-69.25-2.5-3.25-2.25-8 0.5-10.75l34.25-34.5c1.75-1.5 4-2.25 6.25-2.25 2.25 0.25 4.5 1.25 5.75 3 24.5 31.75 61.25 49.75 101 49.75 70.5 0 128-57.5 128-128s-57.5-128-128-128c-32.75 0-63.75 12.5-87 34.25l34.25 34.5c4.75 4.5 6 11.5 3.5 17.25-2.5 6-8.25 10-14.75 10h-112c-8.75 0-16-7.25-16-16v-112c0-6.5 4-12.25 10-14.75 5.75-2.5 12.75-1.25 17.25 3.5l32.5 32.25c35.25-33.25 83-53 132.25-53 105.75 0 192 86.25 192 192z"></path></svg></span>
								<span class="pojo-a11y-toolbar-text">Reset</span>
							</a>
						</li>
					</ul>
									</div>
			</div>
		</nav>
		  
</body>
</html>
"""

# Rutas relativas del sitio oficial (src="/...", href="/...") -> absolutas.
_BASE = re.sub(r'(src|href)="/(?!/)', r'\1="' + SITIO + '/', _PLANTILLA)
