#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export FLASK_ENV="${FLASK_ENV:-development}"
export LM_STUDIO_URL="${LM_STUDIO_URL:-http://host.docker.internal:1234/v1/chat/completions}"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt >/dev/null

echo "Arrancando Asistente..."
echo "URL de LM Studio: ${LM_STUDIO_URL}"
python src/app.py
