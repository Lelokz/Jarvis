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
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .atalhos import normalizar


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


# Volume dito por extenso. Fechada de propósito, e só os valores redondos que
# alguém fala em voz alta — é limpeza mecânica de português, do mesmo tipo que
# o _SUPERFLUAS do atalhos.py, e não trabalho para o modelo.
_POR_EXTENSO = {
    "zero": 0, "dez": 10, "quinze": 15, "vinte": 20, "trinta": 30,
    "quarenta": 40, "cinquenta": 50, "cinquenta e cinco": 55, "sessenta": 60,
    "setenta": 70, "oitenta": 80, "noventa": 90, "cem": 100,
}

_SOBE = ("aumenta", "aumente", "sobe", "suba", "levanta", "mais alto", "mais")
_DESCE = ("abaixa", "abaixe", "baixa", "baixe", "diminui", "diminua",
          "reduz", "mais baixo", "menos")
_MUDO = ("mudo", "muda o som", "muta", "silencio", "silêncio", "sem som",
         "tira o som")


@dataclass(frozen=True)
class PlanoDeVolume:
    """O que o volume VAI virar — antes de virar.

    Existe separado de aplicar porque a §2.3 precisa confirmar antes de agir, e
    não dá para confirmar um número que só será calculado dentro de quem já
    mexeu no som. É o mesmo desenho do evento da Etapa 4 e da renomeação da
    Etapa 5: resolver, perguntar, e só então executar.
    """

    ok: bool
    mensagem: str = ""  # quando não dá, a frase falável
    novo: int = 0
    atual: int = 0
    caminho: str = ""  # "relativo" | "absoluto" | "mudo"


def _numero_dito(dito: str) -> int | None:
    """O número de volume que está DE VERDADE na fala. None se não houver.

    Esta é a guarda que faltava e que deixou o volume ir a 100. O modelo
    devolveu `valor='100'` para "Pode dar play agora." — um número que não
    existe em lugar nenhum da frase. Procurar na transcrição, e não confiar no
    que o modelo entregou, é a mesma ancoragem que protege nome (Etapa 1) e
    expressão de tempo (Etapa 4).
    """
    texto = dito.lower()
    achado = re.search(r"\b(\d{1,3})\b", texto)
    if achado:
        return max(0, min(100, int(achado.group(1))))
    for palavra, valor in sorted(_POR_EXTENSO.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{palavra}\b", texto):
            return valor
    return None


def planejar_volume(dito: str, passo: int = 10) -> PlanoDeVolume:
    """Decide o volume novo a partir do que foi FALADO. Não mexe em nada.

    Dois caminhos separados, e nenhum chute entre eles:

      ABSOLUTO  só quando há um número na fala. "coloca no 30" -> 30.
      RELATIVO  direção dita, um passo a partir de onde está. 50 -> 60.

    Sem número e sem direção ele **não faz nada**. A versão anterior tinha
    `(alvo or "mais")` como padrão, ou seja: na dúvida, aumentava o som. Foi
    por esse caminho que um "pode dar play agora" virou volume 100.
    """
    atual = volume_atual()
    if atual is None:
        return PlanoDeVolume(False, "Não consegui ler o volume.")

    texto = dito.lower()
    if any(p in texto for p in _MUDO):
        return PlanoDeVolume(True, caminho="mudo", atual=atual, novo=atual)

    numero = _numero_dito(dito)
    if numero is not None:
        return PlanoDeVolume(True, caminho="absoluto", atual=atual, novo=numero)

    sobe = any(p in texto for p in _SOBE)
    desce = any(p in texto for p in _DESCE)
    if sobe and not desce:
        if atual >= 100:
            return PlanoDeVolume(False, "O volume já está no máximo.")
        return PlanoDeVolume(True, caminho="relativo", atual=atual,
                             novo=min(100, atual + passo))
    if desce and not sobe:
        if atual <= 0:
            return PlanoDeVolume(False, "O volume já está no mínimo.")
        return PlanoDeVolume(True, caminho="relativo", atual=atual,
                             novo=max(0, atual - passo))

    # Nem número nem direção: não inventa.
    return PlanoDeVolume(False, "Não entendi o que fazer com o volume.")


def alternar_mudo() -> Resultado:
    if _pactl(["set-sink-mute", _SINK, "toggle"]) is None:
        return Resultado(False, "Não consegui mudar o mudo.")
    return Resultado(True, "Pronto.", {"acao": "mudo"})


def aplicar_volume(novo: int) -> Resultado:
    """Executa um plano já decidido — e, quando precisa, já confirmado."""
    atual = volume_atual()
    novo = max(0, min(100, int(novo)))
    if _pactl(["set-sink-volume", _SINK, f"{novo}%"]) is None:
        return Resultado(False, "Não consegui mudar o volume.")
    return Resultado(True, f"Volume em {novo}.", {"de": atual, "para": novo})


# ---------------------------------------------------------------------------
# bloquear a tela (Etapa 6.6)
# ---------------------------------------------------------------------------

# A fala INTEIRA, normalizada, tem que casar — mesma regra da lista de mídia, e
# pelo mesmo motivo: comando curto em lista fechada custa 0 ms e tira do modelo
# a chance de errar. Foi um erro desses que fez "para a música" cair no `abrir`.
#
# As chaves vêm sem artigo porque o `normalizar()` já os derruba: "bloqueia o
# PC" chega aqui como "bloqueia pc".
#
# **A palavra solta ficou de fora**, decisão do Léo: "bloqueia" e "trava"
# sozinhos não casam. Fala de uma palavra é onde o Whisper mais erra, e aqui o
# erro apaga a tela no meio do que ele estiver fazendo — é a lição do "Para!".
COMANDOS_DE_TELA = {
    "bloqueia pc": "bloquear",
    "bloqueia computador": "bloquear",
    "bloqueia tela": "bloquear",
    "bloqueia maquina": "bloquear",
    "bloquear pc": "bloquear",
    "bloquear tela": "bloquear",
    "trava pc": "bloquear",
    "trava computador": "bloquear",
    "trava tela": "bloquear",
    "travar tela": "bloquear",
    "tranca pc": "bloquear",
    "tranca tela": "bloquear",
}


def comando_de_tela(falado: str) -> str | None:
    """A ação de tela, quando a fala inteira É o comando. None quando não é.

    Casamento contra a fala toda, nunca por pedaço: "bloqueia o relatório"
    normaliza para "bloqueia relatorio" e não casa com nada.
    """
    return COMANDOS_DE_TELA.get(normalizar(falado))


def pode_bloquear(comando: Sequence[str]) -> bool:
    """Se o programa de bloquear existe nesta máquina.

    Conferido ANTES de falar. O contrário — dizer "bloqueando" e não bloquear —
    é o tipo de mentira que este projeto já corrigiu duas vezes.
    """
    return bool(comando) and shutil.which(comando[0]) is not None


def bloquear_tela(
    comando: Sequence[str],
    executar: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Resultado:
    """Tranca a tela. **Não existe destrancar, e isso é decisão fechada.**

    Depois de travado, o assistente fica do lado de dentro do bloqueio e não
    recebe comando — e um assistente que destrava por voz é uma senha que
    qualquer um grita. O desbloqueio é a senha digitada.

    O `executar` é injetável para o teste poder provar que o comando certo
    seria disparado **sem travar a tela de ninguém**.
    """
    if not pode_bloquear(comando):
        faltando = comando[0] if comando else "(nenhum comando configurado)"
        return Resultado(False, "Não consigo bloquear a tela aqui.",
                         {"faltando": faltando})
    try:
        saida = executar(list(comando), capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as e:
        return Resultado(False, f"Não consegui bloquear a tela: {e}")
    if saida.returncode != 0:
        return Resultado(False, "O bloqueio de tela recusou o comando.",
                         {"codigo": saida.returncode})
    return Resultado(True, "", {"comando": list(comando)})
