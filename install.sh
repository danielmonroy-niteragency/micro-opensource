#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
  echo "Micro Open Source solo es compatible con macOS."
  exit 1
fi

if [ "$(uname -m)" != "arm64" ]; then
  echo "Esta version necesita un Mac con chip Apple Silicon (M1 o posterior)."
  exit 1
fi

if ! command -v clang >/dev/null 2>&1; then
  echo "Faltan las herramientas de Apple. Se abrira su instalador; vuelve a ejecutar este archivo cuando termine."
  xcode-select --install
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Instalando uv desde astral.sh..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  PATH="$HOME/.local/bin:$PATH"
  export PATH
fi

echo "Preparando Dictado. La primera instalacion puede tardar varios minutos..."
uv run --python 3.12 "$(dirname "$0")/dictado.py" --instalar

echo
echo "Instalacion terminada."
echo "Abre Dictado desde Aplicaciones y concede Microfono, Monitorizacion de entrada y Accesibilidad."

