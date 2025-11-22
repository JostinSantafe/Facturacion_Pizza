#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Verificador de entorno para Facturacion_Pizza.
Se usa desde iniciar.bat y NO debe romper el arranque.
- Verifica versiones y dependencias mínimas
- Garantiza carpetas requeridas
- Prueba (opcional) conexión a PostgreSQL, pero no falla si no está disponible

Salida:
- Código 0 si todo lo esencial está OK
- Código 1 solo si falta Python o dependencias críticas
"""

import sys
import importlib
import os

OK = "[+]"
WARN = "[!]"
ERR = "[-]"


def print_header(msg: str):
    print("\n" + "-" * 60)
    print(msg)
    print("-" * 60)


def check_python(min_major=3, min_minor=8) -> bool:
    print(f"[1] Verificando Python >= {min_major}.{min_minor}...")
    v = sys.version_info
    if (v.major, v.minor) >= (min_major, min_minor):
        print(f"{OK} Python {v.major}.{v.minor} detectado")
        return True
    print(f"{ERR} Python {v.major}.{v.minor} detectado (se requiere {min_major}.{min_minor}+)")
    return False


REQUIRED_MODULES = [
    "flask",
    "psycopg2",  # se usa para logs/DB
    "lxml",
    "dotenv",
    "loguru",
    "requests",
    "pymongo",
]


def check_imports() -> bool:
    print("[2] Verificando dependencias críticas...")
    ok = True
    for mod in REQUIRED_MODULES:
        try:
            importlib.import_module(mod)
            print(f"{OK} {mod}")
        except Exception as e:
            print(f"{ERR} Falta dependencia '{mod}': {e}")
            ok = False
    return ok


def ensure_project_dirs() -> bool:
    print("[3] Verificando/creando carpetas del proyecto...")
    try:
        # settings ya crea las carpetas necesarias al importarse
        from config import settings  # noqa: F401
        print(f"{OK} Directorios verificados en {os.getcwd()}")
        return True
    except Exception as e:
        print(f"{ERR} No se pudieron verificar carpetas: {e}")
        return False


def try_postgres_soft_check():
    print("[4] Prueba rápida de PostgreSQL (opcional)...")
    try:
        from database.connection import get_connection
        conn = get_connection()
        if conn is None:
            print(f"{WARN} PostgreSQL no disponible. Se continuará sin DB.")
            return
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            cur.fetchone()
            print(f"{OK} PostgreSQL responde")
        finally:
            conn.close()
    except Exception as e:
        print(f"{WARN} No se pudo verificar PostgreSQL: {e}")


if __name__ == "__main__":
    # Asegurar cwd en la raíz del proyecto
    try:
        os.chdir(r"c:\\Facturacion_Pizza")
    except Exception:
        pass

    print_header("VERIFICACION DE ENTORNO")

    ok_python = check_python()
    ok_imports = check_imports()
    ok_dirs = ensure_project_dirs()

    # Prueba suave (no altera el exit code)
    try_postgres_soft_check()

    essential_ok = ok_python and ok_imports and ok_dirs
    if essential_ok:
        print("\n[✓] Verificación esencial OK. Listo para iniciar.\n")
        sys.exit(0)
    else:
        print("\n[x] Faltan requisitos esenciales. Revisa los mensajes arriba.\n")
        sys.exit(1)
