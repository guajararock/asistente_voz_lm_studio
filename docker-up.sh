#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export ASISTENTE_API_TOKEN="${ASISTENTE_API_TOKEN:-}"

docker compose up --build -d

echo "Contenedor levantado."
echo "Abre: http://localhost:5000"
