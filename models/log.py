"""
Modelo para la tabla de logs en la base de datos.
Almacena registros de eventos de la aplicación.
"""

class Log:
    """Representa un registro de log en la base de datos."""
    
    def __init__(self, level, message, module=None, error_details=None):
        """
        Inicializa un objeto de log.
        
        Args:
            level: Nivel del log (INFO, WARNING, ERROR, CRITICAL, DEBUG)
            message: Mensaje principal del log
            module: Módulo desde donde se genera el log
            error_details: Detalles adicionales del error (traceback, etc.)
        """
        self.level = level
        self.message = message
        self.module = module
        self.error_details = error_details
    
    @staticmethod
    def create_table(conn):
        """Crea la tabla de logs en la base de datos si no existe."""
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id SERIAL PRIMARY KEY,
                    level VARCHAR(20) NOT NULL,
                    message TEXT NOT NULL,
                    module VARCHAR(255),
                    error_details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
                CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
                CREATE INDEX IF NOT EXISTS idx_logs_module ON logs(module);
            """)
            conn.commit()
            print("[+] Tabla 'logs' creada o verificada exitosamente")
            cur.close()
        except Exception as e:
            print(f"[-] Error al crear tabla de logs: {e}")
            conn.rollback()
    
    @staticmethod
    def insert(conn, level, message, module=None, error_details=None):
        """
        Inserta un nuevo registro de log en la base de datos.
        
        Args:
            conn: Conexión a la base de datos
            level: Nivel del log
            message: Mensaje del log
            module: Módulo opcional
            error_details: Detalles de error opcionales
            
        Returns:
            int: ID del log insertado o None si hay error
        """
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO logs (level, message, module, error_details)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """, (level, message, module, error_details))
            log_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            return log_id
        except Exception as e:
            print(f"[-] Error al insertar log: {e}")
            conn.rollback()
            return None
    
    @staticmethod
    def get_logs(conn, limit=100, level=None, module=None):
        """
        Recupera logs de la base de datos.
        
        Args:
            conn: Conexión a la base de datos
            limit: Número máximo de logs a recuperar
            level: Filtrar por nivel (opcional)
            module: Filtrar por módulo (opcional)
            
        Returns:
            list: Lista de tuplas con los logs
        """
        try:
            cur = conn.cursor()
            
            query = "SELECT id, level, message, module, error_details, timestamp FROM logs WHERE 1=1"
            params = []
            
            if level:
                query += " AND level = %s"
                params.append(level)
            
            if module:
                query += " AND module = %s"
                params.append(module)
            
            query += " ORDER BY timestamp DESC LIMIT %s;"
            params.append(limit)
            
            cur.execute(query, params)
            logs = cur.fetchall()
            cur.close()
            return logs
        except Exception as e:
            print(f"[-] Error al recuperar logs: {e}")
            return []
