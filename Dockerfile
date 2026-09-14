# DHI publica una imagen de desarrollo con shell y otra runtime distroless.
# Los digest fijan exactamente las imágenes verificadas durante esta migración.
FROM dhi.io/python:3.11-dev@sha256:4713e45c9e4081d451f452f724f6b76001dc551fc0688c54bab34fb1d0cf0ea5 AS builder

WORKDIR /build
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --target=/opt/python-deps -r requirements.txt

# Target usado por VS Code Dev Containers.
FROM dhi.io/python:3.11-dev@sha256:4713e45c9e4081d451f452f724f6b76001dc551fc0688c54bab34fb1d0cf0ea5 AS dev

WORKDIR /app
COPY --from=builder /opt/python-deps /opt/python-deps
ENV PYTHONPATH=/opt/python-deps \
	PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1
COPY . .
EXPOSE 5000
CMD ["python", "src/app.py"]

# Target predeterminado para Compose y ejecución local de producción.
# Esta imagen no contiene shell ni herramientas de compilación y se ejecuta
# con el UID no privilegiado definido por DHI.
FROM dhi.io/python:3.11@sha256:a91bc28331c16da33f2dfb60c1b05205f21e7228212eb61f94aa9d13b301ea07 AS runtime

WORKDIR /app
COPY --from=builder /opt/python-deps /opt/python-deps
ENV PYTHONPATH=/opt/python-deps \
	PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1
COPY src ./src
EXPOSE 5000
CMD ["python3", "src/app.py"]
