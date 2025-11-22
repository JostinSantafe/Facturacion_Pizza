@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set "PYTHONUTF8=1"

cd /d c:\Facturacion_Pizza

echo.
echo =============================================================
echo INICIANDO FACTURACION_PIZZA
echo =============================================================
echo.

REM Detectar/crear entorno virtual
set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo [1/5] Creando entorno virtual .venv...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo [-] No se pudo crear el entorno virtual
        pause & exit /b 1
    )
) else (
    echo [1/5] Entorno virtual detectado
)

echo [2/5] Instalando/actualizando dependencias...
"%VENV_PY%" -m pip install --upgrade pip >nul
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [-] Error instalando dependencias
    pause & exit /b 1
)
echo [+] Dependencias OK

echo.
echo [3/5] Verificando configuracion...
"%VENV_PY%" verificar.py
if errorlevel 1 (
    echo.
    echo [-] Error en verificacion
    pause & exit /b 1
)

echo.
echo [4/5] Limpiando cache de Python...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" >nul 2>&1
echo [+] Cache limpiado

echo.
echo [5/5] Iniciando servidor...
echo.
"%VENV_PY%" start.py

pause




