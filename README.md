# Asistente de Voz y Vision para LM Studio

Aplicacion local basada en Flask para conversar con un modelo servido por LM Studio. Permite enviar texto, imagenes y archivos de texto, usar reconocimiento de voz del navegador y leer las respuestas mediante la sintesis de voz del sistema.

## Inicio rapido

Para arrancar la app de forma directa, sigue la guia de [QUICKSTART.md](QUICKSTART.md).

Si quieres empezar en 30 segundos:

```bash
chmod +x start-dev.sh docker-up.sh
./start-dev.sh
# o bien
./docker-up.sh
```

## Requisitos

- Python 3.10 o superior.
- Google Chrome u otro navegador compatible con Web Speech API.
- LM Studio con un modelo compatible activo en el puerto `1234`.
- Docker + Docker Compose si quieres ejecutarlo en contenedor.
- VS Code con soporte para Dev Containers si quieres abrirlo como entorno preparado.

## Instalacion

Desde la raiz del proyecto puedes elegir cualquiera de estas rutas de ejecucion.

### Opcion A: entorno virtual `.venv` (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Despues puedes arrancar la aplicacion con:

```bash
python src/app.py
```

O con el interprete del entorno virtual sin activar la shell:

```bash
./.venv/bin/python src/app.py
```

En Windows:

```powershell
.\.venv\Scripts\python.exe src\app.py
```

En VS Code para Windows, abre la carpeta del proyecto normalmente y selecciona el interprete `.venv\Scripts\python.exe` con `Python: Select Interpreter`. No necesitas Dev Containers para este modo. Si `.venv` aun no existe, ejecuta primero:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Opcion B: Dev Container

El repositorio incluye la configuracion de VS Code para abrirse en contenedor:

- [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json)

Cuando abras la carpeta en VS Code con la opcion "Reopen in Container", el entorno queda preparado para ejecutar la app.
El Dev Container usa el target `dev` de `dhi.io/python:3.11-dev`, monta el repositorio para editarlo y la aplicacion se inicia automaticamente. No ejecutes `start-dev.sh` ni `docker compose up` desde esa terminal, porque crearias una segunda instancia.

### Opcion C: Docker Compose

Desde la raiz del proyecto:

```bash
docker compose up --build
```

Esto levanta la aplicacion en el puerto `5000`.

Compose usa el target `runtime` basado en `dhi.io/python:3.11`. Es una imagen distroless que se ejecuta con el UID no privilegiado `65532`, sin shell ni herramientas de compilacion. El codigo de la aplicacion queda dentro de la imagen y solo se monta `conversaciones_guardadas` para permitir exportaciones.

La imagen se construye con digest fijados. Para actualizar Python o los digest, comprueba primero las nuevas imagenes DHI y vuelve a ejecutar las comprobaciones del proyecto.

### Opcion D: scripts de arranque

El proyecto incluye dos scripts utiles:

- [start-dev.sh](start-dev.sh): crea o usa `.venv`, instala dependencias y arranca la app.
- [docker-up.sh](docker-up.sh): levanta la app con Docker Compose en segundo plano.

```bash
chmod +x start-dev.sh docker-up.sh
./start-dev.sh
# o bien
./docker-up.sh
```

## Ejecucion

1. En LM Studio, carga el modelo y activa el servidor local.
2. Desde la raiz del proyecto, usa la opcion que prefieras:

   En local:

   ```bash
   python src/app.py
   ```

   En Windows PowerShell:

   ```powershell
   python src\app.py
   ```

   O desde el lanzador:

   ```powershell
   src\Iniciar Asistente.bat
   ```

   En Dev Container:

   Abre la carpeta con `Dev Containers: Reopen in Container`. La aplicacion ya queda disponible.

   En Docker:

   ```bash
   docker compose up --build
   ```

3. Abre `http://localhost:5000` en el navegador.

La URL por defecto de LM Studio se define en la aplicacion y admite entorno local, Docker y Dev Container. Si la conexion falla, revisa la variable `LM_STUDIO_URL`.

## Archivos y carpetas generadas

- `conversaciones_guardadas/`: se crea en la raiz del proyecto al usar los botones de exportacion `.MD` o `.TXT`. Los nombres incluyen fecha, hora y microsegundos.
- `archivos_subidos/`: no se crea ni se usa. Las imagenes y archivos de texto se leen en el navegador y se envian a LM Studio en memoria; no se guardan automaticamente en disco.

Las rutas de exportacion se calculan a partir de la ubicacion de `src/app.py`, no del directorio actual desde el que se lance Python.

## Adjuntos y limites

- Imagenes: hasta 10 MB.
- Archivos de texto: `.txt`, `.md`, `.csv`, `.json`, `.py`, `.js`, `.html`, `.css` y `.xml`, hasta 1 MB.
- Peticiones completas: hasta 16 MB.

Los nombres de archivo se limpian con `werkzeug.secure_filename` y el servidor vuelve a validar la extension y los datos recibidos. Los adjuntos no se persisten.

## Configuracion

Para Docker Compose, copia `.env.example` como `.env.local` y define los valores locales. No subas `.env.local` a GitHub; esta excluido por `.gitignore`. En PowerShell tambien puedes definir una variable solo para la sesion:

```powershell
$env:ASISTENTE_API_TOKEN = [guid]::NewGuid().ToString('N')
docker compose up --build
```

La rueda dentada del panel lateral permite elegir el idioma de la interfaz, el tema oscuro o claro, la voz disponible en el sistema, el idioma de lectura, la velocidad, el tono, la lectura automatica y un atajo configurable para activar el microfono. Estas preferencias se guardan en el navegador. El estado de Vision, Think y temperatura se guarda en el backend local, se devuelve al cargar la interfaz y se aplica al siguiente payload enviado a LM Studio. Vision decide si se adjuntan imagenes; Think se envia como `chat_template_kwargs.enable_thinking`; y la temperatura se envia por peticion. LM Studio no ofrece una ruta OpenAI compatible universal para cambiar esos valores como ajustes globales del servidor. Encima de cada respuesta se muestran la latencia, los tokens de entrada y salida y el modelo usado, cuando LM Studio incluye esos datos.

La URL de LM Studio esta definida al principio de `src/app.py` y esta limitada a `127.0.0.1`:

```python
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
```

Si LM Studio utiliza otro puerto o ruta compatible, cambia ese valor.

## Comprobaciones

Cada push a `main` o `master` y cada pull request ejecuta el workflow de GitHub Actions en [.github/workflows/ci.yml](.github/workflows/ci.yml). Comprueba Python, `pip-audit`, las dos configuraciones Compose y los targets Docker `runtime` y `dev`. Dependabot mantiene las dependencias Python, las acciones y la imagen Docker bajo revisión en [.github/dependabot.yml](.github/dependabot.yml).

Para comprobar sintaxis e imports desde la raiz, usa los comandos correspondientes al mismo metodo elegido para ejecutar la aplicacion.

Con el entorno virtual activado:

```powershell
python -m py_compile src\app.py
python -c "import flask, requests, werkzeug; print('imports-ok')"
```

Con el entorno virtual sin activar:

```powershell
.\.venv\Scripts\python.exe -m py_compile src\app.py
.\.venv\Scripts\python.exe -c "import flask, requests, werkzeug; print('imports-ok')"
```

Con Python global, usa `python` como en el primer bloque, despues de haber instalado las dependencias globalmente.

La aplicacion se ejecuta con `debug=False` para no activar el depurador interactivo en un uso normal.

## Seguridad y licencias

### Licencia del proyecto

Este proyecto se distribuye bajo la licencia MIT. El texto completo se encuentra en el archivo `LICENSE`.

La licencia MIT permite usar, copiar, modificar, publicar y redistribuir el codigo, siempre que se conserve el aviso de copyright y la licencia. El software se proporciona sin garantia; el usuario es responsable de comprobar que su configuracion y sus datos cumplen la normativa aplicable.

### Estado de seguridad

- Flask, Requests y Werkzeug se instalan con versiones fijadas en `requirements.txt`.
- El servidor y la conexion con LM Studio escuchan exclusivamente en `127.0.0.1` y no se publican en la red local.
- Las rutas internas requieren un token aleatorio generado en cada ejecucion y se envia exclusivamente mediante la cabecera `X-Asistente-Token`.
- Se puede proporcionar un token fijo mediante la variable de entorno `ASISTENTE_API_TOKEN`.
- Las excepciones internas no se muestran al navegador.
- El backend valida el formato y tamano de las imagenes, el tamano de los adjuntos de texto y el contenido de las peticiones, ademas de aplicar limites al historial en memoria.
- Los nombres de archivo se limpian antes de usarse y las extensiones permitidas se validan.
- El servidor incluido es el servidor de desarrollo de Flask. No debe exponerse a Internet ni utilizarse como servidor de produccion.
- La imagen runtime de Compose usa Docker Hardened Images (DHI), se ejecuta como UID `65532`, tiene un filesystem de solo lectura, elimina todas las capacidades Linux y activa `no-new-privileges`.
- El target de desarrollo usa `dhi.io/python:3.11-dev` y tiene herramientas adicionales para VS Code; esas herramientas no forman parte de la imagen runtime.
- `.dockerignore` excluye secretos, entornos virtuales, datos generados y archivos de desarrollo del contexto de construccion.
- El Dev Container aplica un override separado porque necesita montar el codigo fuente; ese modo no debe usarse como imagen de produccion.
- Esta autenticacion esta pensada para uso local; no convierte el servidor de desarrollo en una aplicacion preparada para Internet ni sustituye HTTPS, gestion de usuarios o proteccion CSRF para un despliegue publico.
- El registro de acceso de Werkzeug esta desactivado para no conservar rutas ni actividad de una aplicacion que maneja texto e imagenes privados.
- Flask limita el tamano total de la peticion y el numero de partes de formularios; el proceso se ejecuta con un solo hilo para mantener bajo el consumo local.

### Actualizar y auditar dependencias

Ejecuta `Actualizar dependencias.bat` desde la raiz del proyecto cuando quieras actualizar Flask, Requests y Werkzeug. El script actualiza esas dependencias y ejecuta `pip-audit` contra `requirements.txt`. Revisa los cambios y vuelve a ejecutar las comprobaciones antes de publicar.

### Acceso desde otro dispositivo

Actualmente el acceso esta limitado al propio ordenador. Para acceder desde otro dispositivo de la misma red habria que cambiar el host de `src/app.py` a `0.0.0.0`, permitir el puerto elegido en el Firewall de Windows y abrir desde el otro dispositivo:

```text
http://IP_DEL_ORDENADOR:5000
```

No se recomienda activar esta opcion en redes publicas o no confiables. Antes de hacerlo se debe configurar un valor secreto y fijo para `ASISTENTE_API_TOKEN`, por ejemplo en PowerShell:

```powershell
$env:ASISTENTE_API_TOKEN = "cambia-esta-clave-por-una-larga-y-aleatoria"
python src\app.py
```

El token protege las rutas de la aplicacion, pero esta version no proporciona HTTPS. Cualquier persona con acceso a la red podria observar el trafico, por lo que no deben enviarse contrasenas, claves API ni datos sensibles al usarla de esta forma.

### Privacidad y datos

- El texto, las imagenes y los archivos adjuntos se envian al servidor local de LM Studio configurado en `LM_STUDIO_URL`.
- Los adjuntos no se guardan automaticamente en disco.
- El historial permanece en memoria mientras el proceso esta activo y se elimina al reiniciar o usar "Nuevo chat".
- Las exportaciones se guardan localmente en `conversaciones_guardadas/` cuando el usuario las solicita.
- Los iconos de la interfaz se sirven desde `src/static/icons.css`; no se necesita una fuente, CDN ni solicitud externa para mostrarlos.
- La sintesis y el reconocimiento de voz dependen del navegador y del sistema operativo; sus politicas de privacidad son independientes de este proyecto.

### Dependencias y componentes externos

- Flask, Requests y Werkzeug son proyectos de software libre con sus propias licencias, instalados con versiones fijadas en `requirements.txt`.
- Los iconos locales se representan mediante CSS y simbolos Unicode, sin dependencias de terceros.
- LM Studio no forma parte de este repositorio y sus condiciones de uso deben consultarse por separado.
- La licencia del modelo descargado en LM Studio es responsabilidad del usuario y puede variar entre modelos.
- Google Chrome, otros navegadores y sus servicios de voz tienen terminos y licencias independientes.

Este README describe la configuracion de este repositorio y no constituye asesoramiento legal ni una auditoria de seguridad certificada.
