@echo off
setlocal
cd /d "%~dp0"

echo Actualizando Flask, Requests y Werkzeug...
python -m pip install --upgrade Flask requests Werkzeug pip-audit
if errorlevel 1 goto :error

echo.
echo Actualizando requirements.txt con las versiones instaladas...
python -c "import importlib.metadata as m; from pathlib import Path; names=('Flask','requests','Werkzeug'); Path('requirements.txt').write_text('\n'.join(f'{name}=={m.version(name)}' for name in names)+'\n', encoding='utf-8')"
if errorlevel 1 goto :error

echo.
echo Ejecutando auditoria de dependencias...
python -m pip_audit -r requirements.txt
if errorlevel 1 goto :audit_error

echo.
echo Actualizacion y auditoria completadas correctamente.
pause
exit /b 0

:audit_error
echo.
echo La auditoria ha encontrado vulnerabilidades o no pudo completarse.
pause
exit /b 2

:error
echo.
echo No se pudo completar la actualizacion.
pause
exit /b 1
