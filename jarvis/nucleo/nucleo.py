"""O núcleo: texto entra, decisão acontece, texto sai.

Toda a interface que um cliente precisa conhecer são duas coisas:

    resposta = nucleo.processar("abre o loft")
    resposta.texto   # o que dizer

O cliente de voz sintetiza no Piper. Um cliente de celular, no dia em que
existir, mostra na tela — e a única coisa que faltará escrever é o transporte.
Este módulo **não imprime e não fala**: devolve texto.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from . import acoes
from .atalhos import Atalho, Casamento, Desfecho, Tabela
from .cerebro import Cerebro, Confirmacao, ErroDoCerebro

__all__ = ["Nucleo", "Resposta", "ErroDoCerebro"]


@dataclass(frozen=True)
class Resposta:
    texto: str
    acao: str | None = None  # o que foi executado, para o log da §2.5
    perguntando: bool = False  # há uma confirmação pendente


class Nucleo:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.tabela = Tabela.carregar(cfg.raiz / "atalhos.toml")
        self.cerebro = Cerebro(cfg.llm)
        self.cerebro.conferir()
        self.cerebro.usar_atalhos([a.nome for a in self.tabela.atalhos])
        self.comandos = acoes.Comandos(
            site=cfg.acoes.comando_site,
            pasta=cfg.acoes.comando_pasta,
            vscode=cfg.acoes.comando_vscode,
        )

        # A confirmação pendente mora aqui, e não no cliente, porque o celular
        # vai precisar dela igual. Hoje há uma conversa só, então é um campo
        # simples; quando o segundo cliente chegar, isto vira estado por
        # sessão. É a única costura que a linha núcleo/cliente vai custar, e
        # está nomeada de propósito em vez de resolvida por antecipação.
        self._pendente: Atalho | None = None

    # ----------------------------------------------------------------------

    def processar(self, texto: str) -> Resposta:
        texto = texto.strip()
        if not texto:
            return Resposta("")

        if self._pendente is not None:
            return self._responder_confirmacao(texto)

        interpretacao = self.cerebro.interpretar(texto)
        if interpretacao.nome is None:
            return Resposta(self.cfg.persona.nao_sei)

        return self._resolver(self.tabela.casar(interpretacao.nome), interpretacao.nome)

    # ----------------------------------------------------------------------

    def _resolver(self, casamento: Casamento, falado: str) -> Resposta:
        if casamento.desfecho is Desfecho.NADA or casamento.atalho is None:
            return Resposta(f'Não conheço "{falado}".')

        if casamento.desfecho is Desfecho.CERTO:
            return self._executar(casamento.atalho)

        # SUGESTAO — pergunta antes de agir. É a §2.2: não chutar.
        self._pendente = casamento.atalho
        if casamento.empatados:
            a, b = casamento.empatados
            return Resposta(
                f"Você quis dizer {a.nome} ou {b.nome}?", perguntando=True
            )
        return Resposta(
            f"Você quis dizer {casamento.atalho.nome}?", perguntando=True
        )

    def _responder_confirmacao(self, texto: str) -> Resposta:
        pendente = self._pendente
        self._pendente = None
        assert pendente is not None

        resposta = self.cerebro.confirmar(texto)
        if resposta is Confirmacao.SIM:
            return self._executar(pendente)
        if resposta is Confirmacao.NAO:
            return Resposta("Beleza, deixa pra lá.")

        # Não foi sim nem não: trata como pedido novo, em vez de insistir na
        # pergunta antiga. Ficar preso numa confirmação seria pior que errar.
        return self.processar(texto)

    def _executar(self, atalho: Atalho) -> Resposta:
        resultado = acoes.executar(atalho, self.comandos)
        return Resposta(
            resultado.mensagem,
            acao=f"abrir:{atalho.tipo}:{atalho.nome}" if resultado.ok else None,
        )

    # ----------------------------------------------------------------------

    @property
    def descricao(self) -> str:
        return f"{self.cfg.llm.modelo} · {len(self.tabela)} atalhos"
