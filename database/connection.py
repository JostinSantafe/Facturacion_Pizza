import psycopg2
from config.settings import DB_CONFIG

def get_connection():
    """
    Retorna una conexión a la base de datos PostgreSQL.
    """
    try:
        conn = psycopg2.connect(
            dbname=DB_CONFIG["dbname"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"]
        )
        print("[+] Conexion exitosa a PostgreSQL")
        return conn
    except Exception as e:
        print("[-] Error de conexion a PostgreSQL:", e)
        return None


def init_databases():
    """
    Inicializa las tablas necesarias en PostgreSQL.
    """
    from models.log import Log
    
    print("[*] Inicializando PostgreSQL...")
    conn = get_connection()
    if conn:
        try:
            Log.create_table(conn)
            print("[+] PostgreSQL inicializado correctamente")
        except Exception as e:
            print(f"[-] Error en PostgreSQL: {e}")
        finally:
            conn.close()
    else:
        print("[-] No se pudo conectar a PostgreSQL")


if __name__ == "__main__":
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
        tablas = cur.fetchall()
        print("[*] Tablas disponibles:", [t[0] for t in tablas])
        cur.close()
        init_databases()
        conn.close()


