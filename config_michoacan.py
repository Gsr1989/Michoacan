"""
MICHOACÁN — configuración compartida (módulo base).
Aquí viven: variables de entorno, constantes, cliente de Supabase y el Bot.
No importa ningún otro módulo del proyecto (para evitar imports circulares).
"""
import os
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from supabase import create_client, Client

SUPABASE_URL  = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY", "")
BOT_TOKEN     = os.getenv("BOT_TOKEN", "")
BASE_URL      = os.getenv("BASE_URL", "https://https-michoacan-gob-mx-tramites-permiso.onrender.com").rstrip("/")
ENTIDAD       = "michoacan"
TZ            = "America/Mexico_City"
ADMIN_USER    = os.getenv("ADMIN_USER", "Serg890105tm3")
ADMIN_PASS    = os.getenv("ADMIN_PASS", "Serg890105tm3")
SESSION_SECRET = os.getenv("SESSION_SECRET", "michoacan_clave_super_segura_123456")
STATIC_DIR    = "static"
OUTPUT_DIR    = "documentos"
BUCKET_NAME   = "permisos-michoacan"
PLANTILLA_PDF = "michoacan_permiso.pdf"
FOLIO_PREFIJO  = "MCH"
FOLIO_NUM_PREF = "620"
PAGE_SIZE = 100
C1 = "#4a001f"
C2 = "#3a0018"
C3 = "#6A0F49"

DOMICILIO  = "AV. DE LA CANTERA #728"
COLONIA    = "VILLAS DEL PEDREGAL"
CP         = "58146"
LOCALIDAD  = "MORELIA, MICH."
MUNICIPIO  = "MORELIA, MICH."
MESES_ES   = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
              7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# timeout en SEGUNDOS (int). NO usar aiohttp.ClientTimeout: truena en aiogram 3.
bot = Bot(token=BOT_TOKEN, session=AiohttpSession(timeout=300))
