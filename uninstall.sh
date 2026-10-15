#!/bin/sh
set -eu

if command -v uv >/dev/null 2>&1; then
  uv run --python 3.12 "$(dirname "$0")/dictado.py" --desinstalar
elif [ -x "$HOME/Dictado/venv/bin/python" ]; then
  "$HOME/Dictado/venv/bin/python" "$HOME/Dictado/dictado.py" --desinstalar
else
  echo "No se encontro una instalacion activa de Dictado."
  exit 1
fi

echo "El arranque automatico se ha desactivado. Tus archivos locales se conservan."

