#!/usr/bin/env bash
#
# Jarvis — preparação do ambiente da Etapa 0.
#
# PRÉ-REQUISITO (uma vez, precisa de sudo):
#     sudo apt install python3-venv python3-pip
#
# Depois é só rodar este script. Ele é idempotente: pode rodar de novo.

set -euo pipefail
cd "$(dirname "$0")"

VOZES=(pt_BR-faber-medium pt_BR-cadu-medium pt_BR-jeff-medium)

if ! python3 -c "import ensurepip" 2>/dev/null; then
    echo "FALTA o pacote python3-venv."
    echo "Rode primeiro:  sudo apt install python3-venv python3-pip"
    exit 1
fi

echo "==> criando .venv"
[ -d .venv ] || python3 -m venv .venv

echo "==> instalando dependências (~1,5GB — os wheels do CUDA são grandes)"
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "==> baixando as vozes PT-BR do Piper (~63MB cada)"
mkdir -p vozes
for voz in "${VOZES[@]}"; do
    if [ -f "vozes/${voz}.onnx" ]; then
        echo "    ${voz} — já tenho"
    else
        echo "    ${voz}"
        ./.venv/bin/python -m piper.download_voices "$voz" --data-dir vozes
    fi
done

cat <<'FIM'

==> pronto.

Próximos passos:

  ./.venv/bin/python etapa0.py --listar-dispositivos
      mostra os microfones que o PortAudio enxerga

  ./.venv/bin/python etapa0.py --autoteste
      testa a cadeia TTS -> VAD -> STT sem microfone
      (na primeira vez baixa o Whisper large-v3-turbo, ~1,6GB)

  ./.venv/bin/python etapa0.py
      o loop de verdade: fale e ele repete

FIM
