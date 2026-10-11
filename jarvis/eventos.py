"""Eventos do cliente de voz: quem emite não sabe quem escuta.

Passada 2 da Etapa 6. Até aqui o `Ciclo` imprimia direto no terminal, e o
terminal era o único jeito de saber o que ele estava fazendo. Com a interface
chegando como segundo cliente, o terminal deixa de ser O destino e vira UM
assinante — ao lado da ponte, que repassa aos clientes conectados.

**Isto é camada de cliente** (ESCOPO §4). O núcleo não emite nada e não sabe que
isto existe: quem emite é o laço de voz, sobre o que o laço de voz faz.

Os assinantes rodam na thread de quem emite, que é a thread de áudio. Por isso
um assinante tem que ser rápido e não pode bloquear — a ponte, que fala com
socket, só enfileira e volta.
"""

from __future__ import annotations

import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Evento = dict[str, Any]


@dataclass
class _Assinante:
    receber: Callable[[Evento], None]
    quer: Callable[[str], bool]
    nome: str
    falhas: int = 0


class Emissor:
    def __init__(self) -> None:
        self._assinantes: list[_Assinante] = []

    def assinar(
        self,
        receber: Callable[[Evento], None],
        *,
        quer: Callable[[str], bool] | None = None,
        nome: str = "",
    ) -> None:
        self._assinantes.append(
            _Assinante(receber, quer or (lambda _tipo: True), nome or "?")
        )

    def quer(self, tipo: str) -> bool:
        """Alguém quer este tipo AGORA?

        Serve para não calcular o que ninguém vai ler. O nível do microfone
        sai ~15 vezes por segundo; sem cliente conectado, a conta nem é feita.
        """
        return any(a.quer(tipo) for a in self._assinantes)

    def emitir(self, tipo: str, **dados: Any) -> None:
        evento: Evento = {"ev": tipo, **dados}
        for a in self._assinantes:
            if not a.quer(tipo):
                continue
            try:
                a.receber(evento)
            except Exception:
                # Um assinante quebrado não pode derrubar o laço de áudio. É a
                # mesma propriedade que o Léo comprou escolhendo dois processos
                # para a interface: um defeito do lado de quem mostra não pode
                # levar junto o lado de quem ouve.
                a.falhas += 1
                if a.falhas == 1:
                    print(f"\n  [eventos] o assinante '{a.nome}' falhou em "
                          f"{tipo!r} (só esta vez é mostrada):", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
