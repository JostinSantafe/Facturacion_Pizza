#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de inicio para Facturacion_Pizza
Ejecutar: python start.py
"""
import os
import sys
import webbrowser
import time
import threading

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

os.chdir(r'c:\Facturacion_Pizza')
sys.path.insert(0, r'c:\Facturacion_Pizza')

print("\n" + "="*60)
print("INICIANDO FACTURACION_PIZZA")
print("="*60 + "\n")

# Paso 1: Verificar PostgreSQL
print("[1/2] Verificando PostgreSQL...")
try:
    import psycopg2
    from config.settings import DB_CONFIG
    
    conn = psycopg2.connect(
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"]
    )
    print("[+] PostgreSQL conectado")
    
    from models.log import Log
    Log.create_table(conn)
    print("[+] Tabla de logs lista")
    conn.close()
except Exception as e:
    print(f"[-] Error al conectar con PostgreSQL: {e}")
    print("[*] Continuando sin PostgreSQL...")

# Paso 2: Abrir navegador automáticamente
def open_browser():
    time.sleep(2)  # Esperar a que Flask esté listo
    url = "http://127.0.0.1:5000"
    print(f"\n[+] Abriendo navegador: {url}\n")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[*] No se pudo abrir navegador automáticamente: {e}")

# Iniciar thread para abrir navegador
browser_thread = threading.Thread(target=open_browser, daemon=True)
browser_thread.start()

# Paso 3: Iniciar Flask
print("[2/2] Iniciando Flask...\n")

try:
    from app import app
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=True)
except KeyboardInterrupt:
    print("\n[*] Servidor detenido")
    sys.exit(0)
except Exception as e:
    print(f"[-] Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


