#!/usr/bin/env bash
# jarvis.sh — liga e desliga o Jarvis sem terminal.
#
#   ./jarvis.sh              liga o assistente (se já não estiver ligado) e abre a janela
#   ./jarvis.sh --desligar   desliga o assistente e fecha a janela
#   ./jarvis.sh --na-bandeja liga com a janela escondida (é o que roda ao ligar o PC)
#
# É o que os ícones "Jarvis" e "Desligar Jarvis" do menu chamam. O que o
# assistente imprimiria no terminal vai para logs/assistente-terminal.log.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
PROJETO="$PWD"

ligado() { pgrep -f "$PROJETO/assistente.py" > /dev/null; }

# A ponte do WhatsApp (whatsapp-mcp), fora do projeto: o banco dela tem as
# conversas do Léo. Sobe e desce junto com o Jarvis.
PONTE_WHATS="$HOME/.local/share/jarvis/whatsapp-mcp/whatsapp-bridge"
ponte_ligada() { pgrep -f "^./whatsapp-bridge$" > /dev/null; }

# A voz do JARVIS dublado (servidor_voz.py), na venv da voz, FORA do projeto:
# o modelo é pessoal (ESCOPO §4). Sem a pasta, o Jarvis fala com a Kokoro.
VOZ="$HOME/.local/share/jarvis/voz-jarvis"
voz_ligada() { pgrep -f "$PROJETO/servidor_voz.py" > /dev/null; }

if [ "${1:-}" = "--desligar" ]; then
  # O assistente trata SIGTERM como ctrl+c: fecha o microfone, apaga o
  # socket e grava o resumo, em vez de morrer no meio.
  pkill -TERM -f "$PROJETO/assistente.py"
  pkill -TERM -f "^./whatsapp-bridge$"
  pkill -TERM -f "$PROJETO/servidor_voz.py"
  pkill -f "$PROJETO/interface.py"
  # Até 20 s: ao desligar, o assistente resume a conversa em andamento para
  # o diário (uma chamada ao Claude).
  for _ in $(seq 40); do ligado || exit 0; sleep 0.5; done
  pkill -KILL -f "$PROJETO/assistente.py"   # não saiu em 20 s: à força
  exit 0
fi

if [ -x "$PONTE_WHATS/whatsapp-bridge" ] && ! ponte_ligada; then
  # umask 077: o que a ponte criar (banco, log) só o Léo lê.
  ( cd "$PONTE_WHATS" && umask 077 && nohup ./whatsapp-bridge \
      >> "$HOME/.local/share/jarvis/whatsapp-bridge.log" 2>&1 & )
fi

if [ -f "$VOZ/modelo/jarvis-dublado.safetensors" ] && ! voz_ligada; then
  mkdir -p logs
  # O ffmpeg estático do Estúdio no PATH: a biblioteca de áudio do F5 procura.
  PATH="$HOME/.local/share/lelokz-estudio/ffmpeg:$PATH" nohup "$VOZ/venv/bin/python" -u \
      "$PROJETO/servidor_voz.py" --modelo "$VOZ/modelo/jarvis-dublado.safetensors" \
      --ref "$VOZ/ref/bomdia-limpa.wav" --ref-texto "$(cat "$VOZ/ref/bomdia-limpa.txt")" \
      --nfe 32 --filtro "volume=-6dB,bass=g=4:f=150:w=0.8" \
      >> logs/servidor-voz.log 2>&1 &
fi

if ! ligado; then
  mkdir -p logs
  echo "=== $(date '+%F %T') ligando ===" >> logs/assistente-terminal.log
  nohup .venv/bin/python -u "$PROJETO/assistente.py" >> logs/assistente-terminal.log 2>&1 &
fi

# A janela sobe na hora e mostra "esperando o Jarvis subir" enquanto o
# assistente carrega (~20 s). Se já estiver aberta, só vem para a frente.
exec .venv/bin/python "$PROJETO/interface.py" "$@"
