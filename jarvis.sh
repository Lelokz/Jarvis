#!/usr/bin/env bash
# jarvis.sh — liga e desliga o Jarvis sem terminal.
#
#   ./jarvis.sh              liga o assistente (se já não estiver ligado) e abre a janela
#   ./jarvis.sh --desligar   desliga o assistente e fecha a janela
#
# É o que os ícones "Jarvis" e "Desligar Jarvis" do menu chamam. O que o
# assistente imprimiria no terminal vai para logs/assistente-terminal.log.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
PROJETO="$PWD"

ligado() { pgrep -f "$PROJETO/assistente.py" > /dev/null; }

if [ "${1:-}" = "--desligar" ]; then
  # O assistente trata SIGTERM como ctrl+c: fecha o microfone, apaga o
  # socket e grava o resumo, em vez de morrer no meio.
  pkill -TERM -f "$PROJETO/assistente.py"
  pkill -f "$PROJETO/interface.py"
  for _ in $(seq 20); do ligado || exit 0; sleep 0.5; done
  pkill -KILL -f "$PROJETO/assistente.py"   # não saiu em 10 s: à força
  exit 0
fi

if ! ligado; then
  mkdir -p logs
  echo "=== $(date '+%F %T') ligando ===" >> logs/assistente-terminal.log
  nohup .venv/bin/python -u "$PROJETO/assistente.py" >> logs/assistente-terminal.log 2>&1 &
fi

# A janela sobe na hora e mostra "esperando o Jarvis subir" enquanto o
# assistente carrega (~20 s). Se já estiver aberta, só vem para a frente.
exec .venv/bin/python "$PROJETO/interface.py"
