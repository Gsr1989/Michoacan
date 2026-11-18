"""MICHOACÁN — editor de tablas de Supabase (panel admin)."""
import html as html_lib

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config_michoacan import supabase, PAGE_SIZE, C1
from ui_michoacan import page
from timers_michoacan import cancelar_timer_folio

router = APIRouter()
_esc = html_lib.escape

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

# ===================== TABLAS BD =====================
@router.get("/panel/tablas", response_class=HTMLResponse)
async def admin_tablas(request: Request):
    if not request.session.get("admin"): return RedirectResponse(url="/panel/login", status_code=303)
    cards = "".join([f"""<div class="form-card mb-3">
      <strong style="color:{C1};font-size:15px">🗄️ {info['nombre']}</strong>
      <p style="font-size:12px;color:#888;margin:4px 0 12px"><code>{nombre}</code></p>
      <a href="/panel/tabla/{nombre}" class="btn btn-primary btn-sm" style="width:auto">Ver y editar →</a>
    </div>""" for nombre, info in TABLAS_DISPONIBLES.items()])
    contenido = f'<p class="page-title">🗄️ Tablas Base de Datos</p>{cards}'
    return HTMLResponse(page("Tablas BD","Tablas BD — Michoacán", contenido))

@router.get("/panel/tabla/{nombre_tabla}", response_class=HTMLResponse)
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
            celdas += f'<td><span class="{cls}" data-col="{col}" data-pk="{str(reg.get(pk_col,""))}" data-val="{str(val or "")}" onclick="editCell(this)">{disp[:25]}</span></td>'
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
        <input type="text" name="q" value="{_esc(q)}" placeholder="Buscar..." class="form-control" style="max-width:220px">
        <button type="submit" class="btn btn-primary btn-sm" style="width:auto">🔍</button>
        {"<a href='/panel/tabla/"+nombre_tabla+"' class='btn btn-outline btn-sm'>✕</a>" if q else ""}
      </form>
      <span style="font-size:12px;color:#888;margin-left:auto">{total} registros</span>
    </div>
    <div class="tabla-wrap"><table id="tbl"><thead><tr><th>#</th>{th}</tr></thead><tbody>{tbody}</tbody></table>{pag}</div>
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

@router.post("/panel/api/update_cell")
async def api_update_cell(request: Request):
    if not request.session.get("admin"): return {"ok":False,"error":"no autorizado"}
    d = await request.json(); tabla=d.get("tabla"); pk_col=d.get("pk_col"); pk_val=d.get("pk_val"); col=d.get("col"); val=d.get("val","")
    if tabla not in TABLAS_DISPONIBLES or not col or not pk_val: return {"ok":False,"error":"datos inválidos"}
    try:
        supabase.table(tabla).update({col:val or None}).eq(pk_col,pk_val).execute(); return {"ok":True}
    except Exception as e: return {"ok":False,"error":str(e)}

@router.post("/panel/api/delete_row")
async def api_delete_row(request: Request):
    if not request.session.get("admin"): return {"ok":False,"error":"no autorizado"}
    d = await request.json(); tabla=d.get("tabla"); pk_col=d.get("pk_col"); pk_val=d.get("pk_val")
    if tabla not in TABLAS_DISPONIBLES or not pk_val: return {"ok":False,"error":"datos inválidos"}
    try:
        if tabla == "folios_registrados":
            cancelar_timer_folio(str(pk_val).strip().upper())
        supabase.table(tabla).delete().eq(pk_col,pk_val).execute(); return {"ok":True}
    except Exception as e: return {"ok":False,"error":str(e)}
