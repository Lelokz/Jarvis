"""Reflexos: o pouco que responde em 0 s, sem passar pelo Claude.

Decisão do Léo (out/2026): o Jarvis passa a ser o Claude Code inteiro, e as
listas fechadas saem. Ficam só pausa/volta/próxima e volume, porque pelo
agente "pausa a música" levou 14 s (medido: ele descobre o sistema do zero) e
é o comando que mais se repete. O "dorme aí" fica no próprio ciclo de voz.

A regra que segura isto: casa a fala INTEIRA, nunca um pedaço. "Para a música
e abre o Spotify" não é reflexo: vai para o Claude, que entende as duas coisas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from jarvis.nucleo import midia, sistema
from jarvis.nucleo.atalhos import normalizar


@dataclass(frozen=True)
class Reflexo:
    fala: str
    acao: str | None


# Volume só com a frase inteira de volume. Mais que o limite (70) não é
# reflexo: vai para o Claude, que confirma antes (já machucou o ouvido do Léo).
# Contra o texto já normalizado: sem acento, sem pontuação e sem "o", "no",
# "um" ("Volume no 30." chega como "volume 30").
_VOLUME = re.compile(
    r"^(aumenta|aumente|sobe|abaixa|abaixe|baixa|diminui|diminua)( (um )?pouco)? "
    r"(volume|som)( (um )?pouco)?$"
    r"|^((coloca|poe|bota) )?(volume|som)( (em|pra|para|a))? \d+( por cento)?$"
)


def reflexo(falado: str, limite_volume: int = 70, passo: int = 10) -> Reflexo | None:
    """A resposta pronta, ou None para mandar ao Claude."""
    cru = midia.comando_cru(falado)
    if cru is not None:
        r = midia.controlar(cru.acao, cru.qual)
        return Reflexo(r.mensagem, f"midia:{cru.acao}" if r.ok else None)

    if _VOLUME.match(normalizar(falado)):
        plano = sistema.planejar_volume(falado, passo)
        if not plano.ok or plano.caminho == "mudo" or plano.novo > limite_volume:
            return None
        r = sistema.aplicar_volume(plano.novo)
        return Reflexo(r.mensagem, f"midia:volume:{plano.novo}" if r.ok else None)
    return None
