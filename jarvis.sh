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
# Motor "rvc" (out/2026): a Kokoro fala e o servidor_rvc.py, na venv do Applio
# (no HD, junto do treino), troca o timbre pelo do JARVIS.
APPLIO="/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644/Arquivo/Jarvis - Treino da voz dublada/applio"
rvc_ligado() { pgrep -f "$PROJETO/servidor_rvc.py" > /dev/null; }
# A voz da Friday (servidor_friday.py, out/2026): a Emilia dublada (F5) na
# venv da voz; modelo pessoal, fora do projeto. Sem a pasta, ela fala com a
# Kokoro feminina.
FRIDAY="$HOME/.local/share/jarvis/voz-friday"
friday_ligada() { pgrep -f "$PROJETO/servidor_friday.py" > /dev/null; }
FRIDAY_ON="$(sed -n '/^\[friday\]/,/^\[/s/^ligada *= *\(true\|false\).*/\1/p' config.toml | head -1)"
# A porta do celular (porta_remota.py): só em 127.0.0.1; o `tailscale serve`
# a leva para os aparelhos do Léo.
porta_ligada() { pgrep -f "$PROJETO/porta_remota.py" > /dev/null; }
MOTOR="$(sed -n 's/^motor *= *"\(.*\)".*/\1/p' config.toml | head -1)"

if [ "${1:-}" = "--desligar" ]; then
  # O assistente trata SIGTERM como ctrl+c: fecha o microfone, apaga o
  # socket e grava o resumo, em vez de morrer no meio.
  pkill -TERM -f "$PROJETO/assistente.py"
  pkill -TERM -f "^./whatsapp-bridge$"
  pkill -TERM -f "$PROJETO/servidor_voz.py"
  pkill -TERM -f "$PROJETO/servidor_rvc.py"
  pkill -TERM -f "$PROJETO/servidor_friday.py"
  pkill -TERM -f "$PROJETO/porta_remota.py"
  pkill -f "$PROJETO/interface.py"
  # Até 20 s: ao desligar, o assistente resume a conversa em andamento para
  # o diário (uma chamada ao Claude).
  for _ in $(seq 40); do ligado || exit 0; sleep 0.5; done
  pkill -KILL -f "$PROJETO/assistente.py"   # não saiu em 20 s: à força
  exit 0
fi

# Só se já foi pareada alguma vez (tem o banco): num PC novo quem sobe a ponte
# é o Conectar de Ajustes → Conexões, para mostrar o QR (jarvis/conectar.py).
if [ -x "$PONTE_WHATS/whatsapp-bridge" ] && [ -f "$PONTE_WHATS/store/whatsapp.db" ] && ! ponte_ligada; then
  # umask 077: o que a ponte criar (banco, log) só o dono lê.
  ( cd "$PONTE_WHATS" && umask 077 && nohup ./whatsapp-bridge \
      >> "$HOME/.local/share/jarvis/whatsapp-bridge.log" 2>&1 & )
fi

if [ "$MOTOR" = "rvc" ] && [ -f "$VOZ/rvc/jarvis-dublado.pth" ] && [ -x "$APPLIO/.venv/bin/python" ] \
    && ! rvc_ligado; then
  mkdir -p logs
  # De dentro da pasta do Applio: ele acha os modelos dele (rmvpe, contentvec) por ali.
  ( cd "$APPLIO" && PATH="$HOME/.local/share/lelokz-estudio/ffmpeg:$PATH" nohup .venv/bin/python -u \
      "$PROJETO/servidor_rvc.py" --modelo "$VOZ/rvc/jarvis-dublado.pth" \
      --index "$VOZ/rvc/jarvis-dublado.index" >> "$PROJETO/logs/servidor-rvc.log" 2>&1 & )
fi

if [ "$MOTOR" = "f5" ] && [ -f "$VOZ/modelo/jarvis-dublado.safetensors" ] && ! voz_ligada; then
  mkdir -p logs
  # O ffmpeg estático do Estúdio no PATH: a biblioteca de áudio do F5 procura.
  PATH="$HOME/.local/share/lelokz-estudio/ffmpeg:$PATH" nohup "$VOZ/venv/bin/python" -u \
      "$PROJETO/servidor_voz.py" --modelo "$VOZ/modelo/jarvis-dublado.safetensors" \
      --ref "$VOZ/ref/bomdia-limpa.wav" --ref-texto "$(cat "$VOZ/ref/bomdia-limpa.txt")" \
      --nfe 32 --filtro "volume=-6dB,bass=g=4:f=150:w=0.8" \
      >> logs/servidor-voz.log 2>&1 &
fi

if [ "$FRIDAY_ON" = "true" ] && [ -f "$FRIDAY/modelo/friday-emilia-v1.safetensors" ] \
    && [ -x "$VOZ/venv/bin/python" ] && ! friday_ligada; then
  mkdir -p logs
  PATH="$HOME/.local/share/lelokz-estudio/ffmpeg:$PATH" nohup "$VOZ/venv/bin/python" -u \
      "$PROJETO/servidor_friday.py" --modelo friday-emilia-v1 >> logs/servidor-friday.log 2>&1 &
fi

if ! ligado; then
  mkdir -p logs
  echo "=== $(date '+%F %T') ligando ===" >> logs/assistente-terminal.log
  nohup .venv/bin/python -u "$PROJETO/assistente.py" >> logs/assistente-terminal.log 2>&1 &
fi

if ! porta_ligada; then
  mkdir -p logs
  nohup .venv/bin/python -u "$PROJETO/porta_remota.py" >> logs/porta-remota.log 2>&1 &
fi

# A janela sobe na hora e mostra "esperando o Jarvis subir" enquanto o
# assistente carrega (~20 s). Se já estiver aberta, só vem para a frente.
exec .venv/bin/python "$PROJETO/interface.py" "$@"
