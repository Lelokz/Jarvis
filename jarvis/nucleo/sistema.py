"""Status do PC e volume do sistema.

Duas leituras que já existiam espalhadas e agora têm lugar: o `nvidia-smi`, que
o `assistente.py` já chamava para imprimir VRAM na subida, e o `pactl`, que o
ESCOPO §4 prevê para o ducking.

Por enquanto só GPU. CPU, RAM e disco entram quando o Léo pedir — o §5 lista os
três, mas ele restringiu esta rodada de propósito.

**A resposta é falada.** Um despejo de números serve para terminal, não para
voz: "47 graus e 45 por cento de uso" é uma frase; "47, 45 %, 473 MiB, 12288
MiB, 0 %, 21.06 W" não é.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Resultado:
    ok: bool
    mensagem: str
    detalhe: dict | None = None


def status_gpu() -> Resultado:
    if shutil.which("nvidia-smi") is None:
        return Resultado(False, "Não consigo ler a GPU: o nvidia-smi não está aqui.")
    try:
        saida = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return Resultado(False, "Não consegui falar com a GPU.")

    partes = [p.strip() for p in saida.stdout.strip().splitlines()[0].split(",")]
    if len(partes) < 4:
        return Resultado(False, "A GPU respondeu algo que não entendi.")

    temp, uso, usada, total = (int(float(p)) for p in partes[:4])
    return Resultado(
        True,
        f"A GPU está em {temp} graus, com {uso} por cento de uso "
        f"e {usada / 1024:.1f} de {total / 1024:.0f} giga de memória.",
        {"temperatura_c": temp, "uso_pct": uso, "vram_usada_mb": usada,
         "vram_total_mb": total},
    )


# ---------------------------------------------------------------------------
# volume do sistema
# ---------------------------------------------------------------------------

# Volume do SISTEMA, não do player. É o que faz sentido com jogo aberto: mexe
# no som geral do PC, e funciona igual esteja tocando o que for. O MPRIS tem
# volume próprio de player, deixado de fora de propósito.
_SINK = "@DEFAULT_SINK@"


def _pactl(args: list[str]) -> str | None:
    if shutil.which("pactl") is None:
        return None
    try:
        saida = subprocess.run(
            ["pactl", *args], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return saida.stdout if saida.returncode == 0 else None


def volume_atual() -> int | None:
    saida = _pactl(["get-sink-volume", _SINK])
    if not saida:
        return None
    achado = re.search(r"(\d+)%", saida)
    return int(achado.group(1)) if achado else None


def ajustar_volume(alvo: str | None, passo: int = 10) -> Resultado:
    """`alvo` pode ser um número ("50"), "mais", "menos" ou "mudo"."""
    atual = volume_atual()
    if atual is None:
        return Resultado(False, "Não consegui ler o volume.")

    texto = (alvo or "mais").strip().lower()
    if texto in ("mudo", "mute", "silencio", "silêncio"):
        if _pactl(["set-sink-mute", _SINK, "toggle"]) is None:
            return Resultado(False, "Não consegui mudar o mudo.")
        return Resultado(True, "Pronto.", {"acao": "mudo"})

    numero = re.search(r"\d+", texto)
    if numero:
        novo = max(0, min(100, int(numero.group(0))))
    elif texto.startswith(("menos", "abaixa", "diminui", "baixa")):
        novo = max(0, atual - passo)
    else:
        novo = min(100, atual + passo)

    if _pactl(["set-sink-volume", _SINK, f"{novo}%"]) is None:
        return Resultado(False, "Não consegui mudar o volume.")
    return Resultado(True, f"Volume em {novo}.", {"de": atual, "para": novo})
