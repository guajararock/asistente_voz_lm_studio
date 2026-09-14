@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Servidor de Voz y Vision - LM Studio
echo ========================================================
echo   Iniciando Interfaz de IA Multimodal Premium
echo ========================================================
echo.

cd /d "%~dp0"
set "PROJECT_ROOT=%~dp0.."
set "PYTHON_EXE=!PROJECT_ROOT!\.venv\Scripts\python.exe"

if exist "!PYTHON_EXE!" (
	"!PYTHON_EXE!" -c "import flask, requests, werkzeug" >nul 2>&1
	if errorlevel 1 set "PYTHON_EXE="
)

if not defined PYTHON_EXE (
	where python >nul 2>&1
	if errorlevel 1 goto :no_python
	set "PYTHON_EXE=python"
	"!PYTHON_EXE!" -c "import flask, requests, werkzeug" >nul 2>&1
	if errorlevel 1 goto :missing_dependencies
)

echo Usando Python: !PYTHON_EXE!
start "" /b "!PYTHON_EXE!" "%~dp0app.py"
timeout /t 2 /nobreak >nul
start "" chrome "http://localhost:5000"
pause
exit /b 0

:no_python
echo No se encontro Python instalado en este equipo.
pause
exit /b 1

:missing_dependencies
echo El Python encontrado no tiene Flask, Requests y Werkzeug instalados.
echo Ejecuta "Actualizar dependencias.bat" desde la raiz del proyecto.
pause
exit /b 1
