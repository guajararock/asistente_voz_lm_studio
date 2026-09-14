# Quickstart

Este proyecto permite usar un asistente multimodal con Flask y LM Studio.

## Requisitos

- Python 3.10+
- Docker + Docker Compose (opcional, para contenedor)
- VS Code con soporte para Dev Containers (opcional)
- LM Studio activo con un modelo cargado en `http://127.0.0.1:1234`

## Opcion 1: Ejecutar en el Dev Container

En VS Code, ejecuta `Dev Containers: Reopen in Container`. El Dev Container usa el servicio `asistente-voz` de `docker-compose.yml`, por lo que la aplicacion se inicia automaticamente.

No ejecutes `start-dev.sh` ni `docker compose up` dentro del Dev Container: eso iniciaria una segunda instancia de la aplicacion.

El Dev Container utiliza `dhi.io/python:3.11-dev` y monta el codigo fuente para permitir la edicion desde VS Code. La app usa por defecto esta URL de LM Studio:

```text
http://host.docker.internal:1234/v1/chat/completions
```

Si necesitas cambiarla, usa:

```bash
LM_STUDIO_URL=http://host.docker.internal:1234/v1/chat/completions ./start-dev.sh
```

## Opcion 2: Ejecutar con Docker Compose

Usa esta opcion si no vas a abrir el proyecto dentro de un Dev Container.

Desde la raiz del proyecto:

```bash
chmod +x docker-up.sh
./docker-up.sh
```

O directamente:

```bash
docker compose up --build
```

Luego abre:

```text
http://localhost:5000
```

Compose construye el target runtime basado en `dhi.io/python:3.11`, una imagen distroless que ejecuta como usuario no privilegiado. La imagen usa un filesystem de solo lectura y solo mantiene escribible `conversaciones_guardadas` para las exportaciones.

El target de desarrollo y el runtime se mantienen separados en `Dockerfile`; el override `.devcontainer/docker-compose.dev.yml` selecciona el target de desarrollo automaticamente al abrir VS Code.

## Opcion 3: Ejecutar en local con Python

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python src/app.py
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python src\app.py
```

En VS Code abierto normalmente en Windows, selecciona `.venv\Scripts\python.exe` con `Python: Select Interpreter`. No es necesario usar Dev Containers para ejecutar la aplicacion localmente.

## Opcion 4: Usar el bat en Windows

```powershell
src\Iniciar Asistente.bat
```

## Comprobaciones rapidas

```bash
python -m py_compile src/app.py
python -c "import sys; sys.path.insert(0, 'src'); import app; print('import-ok')"
```

## Variables de entorno utiles

- `LM_STUDIO_URL`: URL del endpoint de chat de LM Studio.
- `ASISTENTE_API_TOKEN`: token opcional para proteger rutas internas.
- `FLASK_ENV`: usa `development` o `production`.

Para preparar la configuracion local de Docker, copia `.env.example` a `.env.local`. Ese archivo esta excluido de Git y no debe subirse a GitHub.

## Solucion de problemas

- Si la app no conecta con LM Studio en Windows, asegúrate de que el servidor local este iniciado y comprueba el puerto:

```powershell
Test-NetConnection 127.0.0.1 -Port 1234
```

Debe mostrar `TcpTestSucceeded : True`. Desde Docker y Dev Container la aplicacion usa `http://host.docker.internal:1234/v1/chat/completions`.
- Si abriste el proyecto en un Dev Container, no ejecutes tambien `start-dev.sh` ni `docker compose up`: la aplicacion ya la inicia el servicio Compose conectado por VS Code.
- Si falla la dependencia `flask`, ejecuta `python -m pip install -r requirements.txt`.
- Si docker no levanta bien, prueba `docker compose config` y luego `docker compose up --build`.

## Archivos importantes

- [src/app.py](src/app.py): aplicacion principal
- [docker-compose.yml](docker-compose.yml): configuracion de contenedor
- [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json): configuracion del Dev Container
- [start-dev.sh](start-dev.sh): arranque rapido del entorno local
- [docker-up.sh](docker-up.sh): arranque con Docker Compose
