@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d c:\Facturacion_Pizza

set "VENV_PY=.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
	py -3 -m venv .venv || (echo [-] No se pudo crear .venv & pause & exit /b 1)
)
"%VENV_PY%" start.py
pause
