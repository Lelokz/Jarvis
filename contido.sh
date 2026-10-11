#!/usr/bin/env bash
# contido.sh — roda um teste que dispara processos DENTRO de uma cerca.
#
#   ./contido.sh [-m MEMORIA] [-p PROCESSOS] [-t SEGUNDOS] -- comando args...
#   padrões:      -m 1G        -p 64          -t 300
#
# Existe por causa de 14/set/2026: um `bisect.py` de rascunho sombreou o
# `bisect` da biblioteca padrão, o PySide6 o importava, e cada filho disparava
# outro filho. 2.176 processos, 13 GB, o OOM matou o Brave e o VS Code e o PC
# travou. O `timeout` só matava o processo de cima; os órfãos continuavam.
#
# As quatro regras que saíram disso, cada uma virando uma checagem aqui:
#   1. nenhum script com nome de módulo da biblioteca padrão  -> recusa
#   2. teto de memória E de processos, no grupo inteiro       -> systemd-run
#   3. teste anterior ainda vivo                              -> recusa
#   4. rascunho mora em rascunho/, dentro do projeto          -> não em /tmp
#
# O teto é do cgroup, então vale para o processo e para TODOS os descendentes.
# Parar a cerca (por tempo, ou `systemctl --user stop 'jarvis-teste-*'`) mata
# o grupo inteiro, e não só o pai.
set -uo pipefail

MEMORIA=1G
PROCESSOS=64
SEGUNDOS=300
while getopts "m:p:t:" opt; do
  case $opt in
    m) MEMORIA=$OPTARG ;;
    p) PROCESSOS=$OPTARG ;;
    t) SEGUNDOS=$OPTARG ;;
    *) exit 2 ;;
  esac
done
shift $((OPTIND - 1))
[ "${1:-}" = "--" ] && shift
if [ $# -eq 0 ]; then
  echo "uso: ./contido.sh [-m 1G] [-p 64] [-t 300] -- comando args..." >&2
  exit 2
fi

RAIZ="$(cd "$(dirname "$0")" && pwd)"
PY="$RAIZ/.venv/bin/python"

# -- regra 3: um teste anterior ainda vivo ---------------------------------
# É o "ps antes de relançar" virando recusa. Relançar por cima de um teste
# travado foi exatamente o que multiplicou as cadeias em 14/set.
vivos=$(systemctl --user list-units --type=scope --state=active --no-legend \
        'jarvis-teste-*' 2>/dev/null | awk '{print $1}')
if [ -n "$vivos" ]; then
  echo "contido: RECUSADO — ainda há teste vivo de uma rodada anterior:" >&2
  for u in $vivos; do
    n=$(systemctl --user show -p TasksCurrent --value "$u")
    echo "   $u  ($n processos)" >&2
  done
  echo "   investigue antes; para matar o grupo: systemctl --user stop 'jarvis-teste-*'" >&2
  exit 3
fi

# -- regra 1: script com nome de módulo da biblioteca padrão ---------------
# O Python põe a pasta do script no começo do sys.path, então QUALQUER .py
# nessa pasta ganha de um módulo da biblioteca com o mesmo nome — em qualquer
# import, inclusive dentro de uma biblioteca que você nem chamou direto.
pastas=("$PWD")
for a in "$@"; do
  case "$a" in *.py) [ -f "$a" ] && pastas+=("$(cd "$(dirname "$a")" && pwd)") ;; esac
done
sombras=$("$PY" - "${pastas[@]}" <<'PYCHK'
import sys
from pathlib import Path
nomes = sys.stdlib_module_names
achados = set()
for pasta in sys.argv[1:]:
    for f in Path(pasta).glob("*.py"):
        if f.stem in nomes:
            achados.add(str(f))
print("\n".join(sorted(achados)))
PYCHK
)
if [ -n "$sombras" ]; then
  echo "contido: RECUSADO — estes arquivos têm nome de módulo da biblioteca padrão" >&2
  echo "e seriam importados no lugar dele:" >&2
  echo "$sombras" | sed 's/^/   /' >&2
  exit 4
fi

# -- regra 2: a cerca ------------------------------------------------------
# MemorySwapMax=0: sem isso o teste estouraria para os 2 GB de swap e o PC
# engasgaria ANTES de o teto matar alguma coisa.
UNIDADE="jarvis-teste-$(date +%Y%m%d-%H%M%S)-$$"
INICIO=$(date +%s)
echo "contido: $UNIDADE  ·  memória $MEMORIA  ·  processos $PROCESSOS  ·  tempo ${SEGUNDOS}s" >&2

systemd-run --user --scope --quiet --collect --unit="$UNIDADE" \
  -p MemoryMax="$MEMORIA" -p MemorySwapMax=0 \
  -p TasksMax="$PROCESSOS" -p RuntimeMaxSec="$SEGUNDOS" \
  -- bash -c '
    "$@"; rc=$?
    # Lido de DENTRO da cerca, antes de ela fechar: é o número honesto do
    # grupo inteiro, filhos incluídos, e não só do processo principal.
    cg=/sys/fs/cgroup$(cut -d: -f3 /proc/self/cgroup)
    pico=$(cat "$cg/memory.peak" 2>/dev/null || echo 0)
    oom=$(awk "/^oom_kill /{print \$2}" "$cg/memory.events" 2>/dev/null)
    pids=$(awk "/^max /{print \$2}" "$cg/pids.events" 2>/dev/null)
    printf "contido: saída %s  ·  pico de memória %s MB" "$rc" "$((pico / 1048576))" >&2
    [ "${oom:-0}" != 0 ]  && printf "  ·  MORTO PELO TETO DE MEMÓRIA (%s)" "$oom" >&2
    [ "${pids:-0}" != 0 ] && printf "  ·  BATEU NO TETO DE PROCESSOS (%s vezes)" "$pids" >&2
    printf "\n" >&2
    exit $rc
  ' _ "$@"
rc=$?

# -- a causa, lida de quem parou a cerca -----------------------------------
# O código de saída NÃO diz a causa. Quando o kernel mata um processo pelo
# teto de memória, o systemd para a cerca INTEIRA (OOMPolicy=stop, o padrão) —
# e isso derruba também o bash de dentro, antes de ele imprimir o resumo. O
# resultado é o mesmo 143 de um estouro de tempo. A primeira versão desta
# mensagem dizia "tempo ou sinal" e fez eu afirmar que um teste morto pelo teto
# de memória em 1s tinha esperado 30s. Quem sabe a causa é o journal do
# systemd: "Failed with result 'oom-kill'" ou "'timeout'".
#
# E com o sufixo `.scope` no -u: sem ele o journalctl completa o nome como
# `.service`, não acha nada, e a mensagem cai no "sinal de fora" — foi o
# segundo erro desta mesma checagem, pego pelo teste que a verificava.
if [ $rc -ne 0 ]; then
  causa=""
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    causa=$(journalctl --user -u "$UNIDADE.scope" -o cat --since "@$INICIO" --no-pager 2>/dev/null \
            | grep -oE "result '[a-z-]+'" | tail -1)
    [ -n "$causa" ] && break
    sleep 0.2
  done
  case "$causa" in
    *oom-kill*) echo "contido: MORTO PELO TETO DE MEMÓRIA ($MEMORIA) — o grupo inteiro foi encerrado" >&2 ;;
    *timeout*)  echo "contido: ENCERRADO PELO TEMPO (${SEGUNDOS}s) — o grupo inteiro foi encerrado" >&2 ;;
    "")         [ $rc -eq 143 ] || [ $rc -eq 137 ] && \
                echo "contido: encerrado por sinal de fora (saída $rc)" >&2 ;;
  esac
fi
exit $rc
