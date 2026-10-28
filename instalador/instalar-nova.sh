#!/usr/bin/env bash
# instalar-nova.sh — o que o convidado baixa pelo site (nova-ia.web.app, só com
# convite). Pequeno de propósito: baixa o `uv` (Astral, oficial) e o código da
# NOVA (GitHub), e abre a janela do instalador. Nada de sudo, nada no sistema.
#
# Este é o MODELO que fica no git (público): VOZES_DRIVE vazio. A cópia que vai
# no convite tem o endereço do pacote de vozes preenchido e nunca entra no git.
set -euo pipefail

VOZES_DRIVE=""
CODIGO="https://github.com/Lelokz/Jarvis/archive/refs/heads/main.tar.gz"
PASTA="${XDG_CACHE_HOME:-$HOME/.cache}/nova-instalador"

echo "Preparando o instalador da NOVA (só da primeira vez demora um pouco)…"
mkdir -p "$PASTA"

if [ ! -x "$PASTA/uv/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh \
    | env UV_INSTALL_DIR="$PASTA/uv" UV_NO_MODIFY_PATH=1 sh > /dev/null
fi

rm -rf "$PASTA/codigo" && mkdir -p "$PASTA/codigo"
curl -LsSf "$CODIGO" | tar -xz -C "$PASTA/codigo" --strip-components=1

cd "$PASTA/codigo/instalador"
export NOVA_VOZES_DRIVE="$VOZES_DRIVE" NOVA_UV="$PASTA/uv/uv" UV_CACHE_DIR="$PASTA/uv-cache" UV_PYTHON_INSTALL_DIR="$PASTA/python"
exec "$PASTA/uv/uv" run --no-project --python 3.12 --with pyside6-essentials==6.11.2 --with numpy==2.5.2 \
  python -m nova_instalador
