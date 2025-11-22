# -*- coding: utf-8 -*-
import logging
import traceback
import sys
from datetime import datetime
from typing import Optional, List, Dict
from config.settings import LOG_FILE, MONGO_CONFIG
from database.connection import get_connection
from models.log import Log

try:
    from pymongo import MongoClient, ASCENDING
except Exception:
    MongoClient = None  # Se manejará si falta dependencia

# Configurar logging para soportar caracteres especiales en Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Configurar logger estándar de Python (archivos)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding='utf-8'
)

logger = logging.getLogger("facturacion")


class DatabaseLogger:
    """
    Logger que guarda los registros en:
    - Archivo (logs/facturacion.log)
    - PostgreSQL (tabla logs)
    """
    
    def __init__(self, use_postgres=True, use_mongo=True):
        """Inicializa el logger multi-backend.

        Args:
            use_postgres: Guardar en PostgreSQL
            use_mongo: Guardar en MongoDB (capped + TTL)
        """
        self.conn_postgres = None
        self.use_postgres = use_postgres
        self.use_mongo = use_mongo and MongoClient is not None
        self._mongo_client: Optional[MongoClient] = None
        self._mongo_collection_fact = None
        self._mongo_collection_sys = None
        if self.use_mongo:
            self._init_mongo_collections()
    
    def get_postgres_connection(self):
        """Obtiene una conexión a PostgreSQL."""
        if self.use_postgres:
            if self.conn_postgres is None:
                self.conn_postgres = get_connection()
            return self.conn_postgres
        return None
    
    def _log_to_postgres(self, level, message, module=None, error_details=None):
        """Guarda un log en PostgreSQL."""
        try:
            conn = self.get_postgres_connection()
            if conn:
                Log.insert(conn, level, message, module, error_details)
        except Exception as e:
            logger.warning(f"[WARNING] No se pudo guardar log en PostgreSQL: {e}")

    # ---------- MongoDB ----------
    def _init_mongo_collections(self):
        """Crea colecciones capped (facturación y sistema) e índices TTL si no existen."""
        try:
            self._mongo_client = MongoClient(MONGO_CONFIG["uri"], serverSelectionTimeoutMS=3000)
            db = self._mongo_client[MONGO_CONFIG["database"]]
            names = db.list_collection_names()
            fact_name = MONGO_CONFIG["collection_facturacion"]
            sys_name = MONGO_CONFIG["collection_sistema"]

            def ensure(name):
                if name in names:
                    return db[name]
                return db.create_collection(name, capped=True, size=MONGO_CONFIG["max_size_bytes"], max=None)

            self._mongo_collection_fact = ensure(fact_name)
            self._mongo_collection_sys = ensure(sys_name)

            ttl_seconds = MONGO_CONFIG.get("ttl_seconds")
            if ttl_seconds and ttl_seconds > 0:
                for col in (self._mongo_collection_fact, self._mongo_collection_sys):
                    col.create_index([("ts", ASCENDING)], expireAfterSeconds=ttl_seconds, name="idx_ts_ttl", background=True)
            for col in (self._mongo_collection_fact, self._mongo_collection_sys):
                col.create_index([("level", ASCENDING), ("module", ASCENDING)], name="idx_level_module", background=True)
                col.create_index([("uuid", ASCENDING)], name="idx_uuid", background=True)
            logger.info("[MongoLogger] Colecciones Mongo inicializadas correctamente")
        except Exception as e:
            logger.warning(f"[MongoLogger] No se pudo inicializar MongoDB: {e}")
            self.use_mongo = False

    def _insert_mongo(self, collection, doc: Dict):
        try:
            collection.insert_one(doc)
        except Exception as e:
            logger.warning(f"[MongoLogger] Fallo insert Mongo: {e}")

    def _log_to_mongo(self, level: str, message: str, module: Optional[str], error_details: Optional[str], structured: Optional[Dict] = None, category: str = "facturacion"):
        if not self.use_mongo:
            return
        collection = self._mongo_collection_fact if category == "facturacion" else self._mongo_collection_sys
        if collection is None:
            return
        try:
            doc = {
                "ts": datetime.utcnow(),
                "level": level,
                "message": message,
                "module": module,
                "error": error_details,
            }
            if structured:
                # Merge sin sobrescribir claves básicas
                for k, v in structured.items():
                    if k not in doc:
                        doc[k] = v
            self._insert_mongo(collection, doc)
        except Exception as e:
            logger.warning(f"[MongoLogger] Fallo construcción log Mongo: {e}")

    # Métodos estructurados públicos
    def log_facturacion_structured(self, level: str, payload: Dict):
        msg = payload.get("msg") or payload.get("message") or "facturacion_event"
        self._log_to_mongo(level, msg, module="factura_flow", error_details=payload.get("error"), structured=payload, category="facturacion")
        # También a archivo/PostgreSQL resumen
        text = f"[FACT] {payload.get('phase')} {msg} uuid={payload.get('uuid')}"
        if level == "ERROR":
            self.error(text, module="factura_flow")
        elif level == "WARNING":
            self.warning(text, module="factura_flow")
        elif level == "DEBUG":
            self.debug(text, module="factura_flow")
        else:
            self.info(text, module="factura_flow")

    def log_sistema_structured(self, level: str, payload: Dict):
        msg = payload.get("msg") or payload.get("message") or "sistema_event"
        self._log_to_mongo(level, msg, module="sistema", error_details=payload.get("error"), structured=payload, category="sistema")
        text = f"[SYS] {payload.get('phase')} {msg}"
        if level == "ERROR":
            self.error(text, module="sistema")
        elif level == "WARNING":
            self.warning(text, module="sistema")
        elif level == "DEBUG":
            self.debug(text, module="sistema")
        else:
            self.info(text, module="sistema")
    
    def info(self, message, module=None):
        """Registra un mensaje de información."""
        logger.info(message)
        self._log_to_postgres("INFO", message, module)
        self._log_to_mongo("INFO", message, module, None, category="sistema")
    
    def warning(self, message, module=None):
        """Registra una advertencia."""
        logger.warning(message)
        self._log_to_postgres("WARNING", message, module)
        self._log_to_mongo("WARNING", message, module, None, category="sistema")
    
    def error(self, message, module=None, exc_info=False):
        """
        Registra un error.
        
        Args:
            message: Mensaje de error
            module: Módulo donde ocurrió el error
            exc_info: Si es True, incluye el traceback
        """
        logger.error(message, exc_info=exc_info)
        
        error_details = None
        if exc_info:
            error_details = traceback.format_exc()
        
        self._log_to_postgres("ERROR", message, module, error_details)
        self._log_to_mongo("ERROR", message, module, error_details, category="sistema")
    
    def critical(self, message, module=None, exc_info=False):
        """
        Registra un error crítico.
        
        Args:
            message: Mensaje de error crítico
            module: Módulo donde ocurrió el error
            exc_info: Si es True, incluye el traceback
        """
        logger.critical(message, exc_info=exc_info)
        
        error_details = None
        if exc_info:
            error_details = traceback.format_exc()
        
        self._log_to_postgres("CRITICAL", message, module, error_details)
        self._log_to_mongo("CRITICAL", message, module, error_details, category="sistema")
    
    def debug(self, message, module=None):
        """Registra un mensaje de depuración."""
        logger.debug(message)
        self._log_to_postgres("DEBUG", message, module)
        self._log_to_mongo("DEBUG", message, module, None, category="sistema")
    
    def close(self):
        """Cierra la conexión a PostgreSQL."""
        if self.conn_postgres:
            self.conn_postgres.close()
            self.conn_postgres = None
        if self._mongo_client:
            self._mongo_client.close()
            self._mongo_client = None
    
    def get_postgres_logs(self, limit=50, level=None, module=None):
        """
        Obtiene logs de PostgreSQL.
        
        Returns:
            list: Lista de logs de PostgreSQL
        """
        try:
            conn = self.get_postgres_connection()
            if conn:
                return Log.get_logs(conn, limit, level, module)
        except Exception as e:
            logger.error(f"Error al recuperar logs de PostgreSQL: {e}")
        return []

    def get_mongo_logs(self, limit: int = 50, level: Optional[str] = None, module: Optional[str] = None, category: str = "facturacion") -> List[Dict]:
        """Recupera logs desde MongoDB (facturacion o sistema)."""
        if not self.use_mongo:
            return []
        collection = self._mongo_collection_fact if category == "facturacion" else self._mongo_collection_sys
        if collection is None:
            return []
        query: Dict = {}
        if level:
            query["level"] = level
        if module:
            query["module"] = module
        try:
            cursor = collection.find(query).sort("ts", -1).limit(int(limit))
            return [
                {
                    "ts": doc.get("ts"),
                    "level": doc.get("level"),
                    "module": doc.get("module"),
                    "message": doc.get("message"),
                    "error": doc.get("error"),
                    "uuid": doc.get("uuid"),
                    "phase": doc.get("phase"),
                    "data": doc.get("data"),
                }
                for doc in cursor
            ]
        except Exception as e:
            logger.warning(f"[MongoLogger] No se pudo leer logs: {e}")
            return []


# Instancia global del logger de base de datos
db_logger = DatabaseLogger(use_postgres=True, use_mongo=True)



