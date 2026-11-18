"""MICHOACÁN — generación de folios (contador + watermark en Supabase)."""
import asyncio
import random

from config_michoacan import supabase, ENTIDAD, FOLIO_PREFIJO, FOLIO_NUM_PREF

_folio_counter = {"siguiente": 1}
_folio_lock    = asyncio.Lock()

def _sb_leer_watermark():
    try:
        r = supabase.table("folio_watermark").select("ultimo_asignado").eq("prefijo", FOLIO_PREFIJO).execute()
        return r.data[0]["ultimo_asignado"] if r.data else None
    except: return None

def _sb_guardar_watermark(numero):
    try: supabase.table("folio_watermark").upsert({"prefijo": FOLIO_PREFIJO, "ultimo_asignado": numero}).execute()
    except Exception as e: print(f"[ERROR] guardar_watermark: {e}")

def _sb_inicializar_folio():
    wm = _sb_leer_watermark()
    if wm is not None:
        _folio_counter["siguiente"] = wm + 1; return
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
        else: _folio_counter["siguiente"] = 1
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

async def _generar_folio_async():
    async with _folio_lock:
        return await asyncio.to_thread(_generar_folio_sync)

def generar_folio(): return _generar_folio_sync()
