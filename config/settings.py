import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Config BD PostgreSQL
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "facturacion_electronica"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "10151941"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

# Config MongoDB
MONGO_CONFIG = {
    "uri": "mongodb://localhost:27017/",
    "database": "facturacion_nosql",
    # Colección principal de trazabilidad de facturas
    "collection_facturacion": "logs_facturacion",
    # Colección para eventos/errores de sistema generales
    "collection_sistema": "logs_sistema",
    # Tamaño máximo colección capped (en bytes). 50MB por defecto.
    "max_size_bytes": int(os.getenv("MONGO_LOG_MAX_SIZE", 50 * 1024 * 1024)),
    # TTL (segundos) para eliminación automática adicional (ej: 30 días)
    "ttl_seconds": int(os.getenv("MONGO_LOG_TTL", 30 * 24 * 3600)),
}

# Directorios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

PENDIENTES_BASE = os.path.join(PROJECT_ROOT, "pendientes/base")
PENDIENTES_DIAN = os.path.join(PROJECT_ROOT, "pendientes/xmldian")
STATIC_PDFS = os.path.join(PROJECT_ROOT, "static/pdfs")
ERROR_DIR = os.path.join(PROJECT_ROOT, "error")
LOG_FILE = os.path.join(PROJECT_ROOT, "logs/facturacion.log")

# Crear carpetas si no existen
os.makedirs(PENDIENTES_BASE, exist_ok=True)
os.makedirs(PENDIENTES_DIAN, exist_ok=True)
os.makedirs(STATIC_PDFS, exist_ok=True)
os.makedirs(ERROR_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
