"""MICHOACÁN — QR, PDF (PyMuPDF) y Storage de Supabase."""
import os
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo

import qrcode
import fitz

from config_michoacan import (
    supabase, BASE_URL, TZ, OUTPUT_DIR, BUCKET_NAME, PLANTILLA_PDF,
    DOMICILIO, COLONIA, CP, LOCALIDAD, MUNICIPIO, MESES_ES,
)

def subir_pdf_a_storage(ruta_local: str, folio: str) -> str:
    try:
        if not os.path.exists(ruta_local): return ""
        with open(ruta_local, "rb") as f: contenido = f.read()
        nombre = f"{folio}.pdf"
        supabase.storage.from_(BUCKET_NAME).upload(path=nombre, file=contenido,
            file_options={"content-type": "application/pdf", "upsert": "true"})
        url = supabase.storage.from_(BUCKET_NAME).get_public_url(nombre)
        print(f"[STORAGE] ✅ Subido: {url}"); return url
    except Exception as e:
        print(f"[STORAGE] ❌ Error {folio}: {e}"); return ""

# ===================== QR =====================
def _generar_qr(folio: str):
    try:
        url = f"{BASE_URL}/consulta/{folio}"
        qr  = qrcode.QRCode(version=2, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=1)
        qr.add_data(url); qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        print(f"[QR] Generado para {folio}"); return img
    except Exception as e:
        print(f"[QR] Error: {e}"); return None

# ===================== PDF — COORDENADAS EXACTAS =====================
def generar_pdf(datos: dict) -> str:
    folio = datos["folio"]
    out   = os.path.join(OUTPUT_DIR, f"{folio}.pdf")
    tz    = ZoneInfo(TZ)

    try:
        fecha_dt = datos["fecha_exp_dt"]
        if isinstance(fecha_dt, str):
            fecha_dt = datetime.fromisoformat(fecha_dt.replace("Z", "+00:00"))
        if fecha_dt.tzinfo is None: fecha_dt = fecha_dt.replace(tzinfo=tz)
        else: fecha_dt = fecha_dt.astimezone(tz)
    except: fecha_dt = datetime.now(tz)

    fecha_texto = f"Morelia, {fecha_dt.day} de {MESES_ES[fecha_dt.month]} del {fecha_dt.year}"

    nombre = str(datos.get("nombre","")).upper()
    marca  = str(datos.get("marca","")).upper()
    linea  = str(datos.get("linea","")).upper()
    tipo   = str(datos.get("tipo","")).upper()
    clase  = str(datos.get("clase","")).upper()
    modelo = str(datos.get("anio",""))
    serie  = str(datos.get("serie","")).upper()
    motor  = str(datos.get("motor","")).upper()

    F  = "helv"
    FB = "hebo"
    S  = 9
    SF = 11

    try:
        if os.path.exists(PLANTILLA_PDF):
            doc = fitz.open(PLANTILLA_PDF)
            pg  = doc[0]

            # Vigencia
            pg.insert_text((270, 151), "30 DIAS",    fontsize=S,  fontname=FB, color=(0,0,0))
            # Folio
            pg.insert_text((470, 151), str(folio),   fontsize=SF, fontname=FB, color=(0.55,0.06,0.12))
            # Nombre
            pg.insert_text((185, 190), nombre,        fontsize=S,  fontname=F,  color=(0,0,0))
            # Domicilio (hardcoded)
            pg.insert_text((148, 211), DOMICILIO,     fontsize=S,  fontname=F,  color=(0,0,0))
            # Colonia / CP / Localidad (hardcoded)
            pg.insert_text((148, 236), COLONIA,       fontsize=S,  fontname=F,  color=(0,0,0))
            pg.insert_text((315, 236), CP,            fontsize=S,  fontname=F,  color=(0,0,0))
            pg.insert_text((463, 236), LOCALIDAD,     fontsize=8,  fontname=F,  color=(0,0,0))
            # Municipio / Fecha (hardcoded/auto)
            pg.insert_text((148, 256), MUNICIPIO,     fontsize=S,  fontname=F,  color=(0,0,0))
            pg.insert_text((455, 256), fecha_texto,   fontsize=7,  fontname=F,  color=(0,0,0))
            # Marca
            pg.insert_text((148, 295), marca,         fontsize=S,  fontname=F,  color=(0,0,0))
            # Linea / Tipo
            pg.insert_text((148, 315), linea,         fontsize=S,  fontname=F,  color=(0,0,0))
            pg.insert_text((320, 315), tipo,          fontsize=S,  fontname=F,  color=(0,0,0))
            # Clase / Modelo
            pg.insert_text((148, 336), clase,         fontsize=S,  fontname=F,  color=(0,0,0))
            pg.insert_text((330, 336), modelo,        fontsize=S,  fontname=F,  color=(0,0,0))
            # Serie
            pg.insert_text((148, 357), serie,         fontsize=S,  fontname=F,  color=(0,0,0))

            # QR — lado derecho junto al folio, 60x60 pts
            img_qr = _generar_qr(folio)
            if img_qr:
                buf = BytesIO(); img_qr.save(buf, format="PNG"); buf.seek(0)
                pg.insert_image(fitz.Rect(538, 128, 598, 188), pixmap=fitz.Pixmap(buf.read()), overlay=True)

            doc.save(out)
            doc.close()
            print(f"[PDF] ✅ {out}")
        else:
            print(f"[PDF] ⚠️ Plantilla no encontrada")
            doc = fitz.open(); pg = doc.new_page(width=612, height=792)
            pg.insert_text((50,50), f"PLANTILLA NO ENCONTRADA — Folio: {folio}", fontsize=10)
            doc.save(out); doc.close()
    except Exception as e:
        print(f"[PDF] ❌ Error: {e}")
        doc_fb = fitz.open()
        doc_fb.new_page().insert_text((50,50), f"ERROR - Folio: {folio}", fontsize=12)
        doc_fb.save(out); doc_fb.close()

    return out

def generar_subir_y_guardar_pdf(datos_pdf: dict) -> str:
    folio    = datos_pdf["folio"]
    ruta_pdf = generar_pdf(datos_pdf)
    url_pdf  = subir_pdf_a_storage(ruta_pdf, folio)
    if url_pdf:
        try: supabase.table("folios_registrados").update({"pdf_url": url_pdf}).eq("folio", folio).execute()
        except Exception as e: print(f"[DB] ❌ Error pdf_url: {e}")
    return url_pdf