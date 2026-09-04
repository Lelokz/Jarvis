"""O núcleo: texto entra, decisão acontece, texto sai.

Toda a interface que um cliente precisa conhecer são duas coisas:

    resposta = nucleo.processar("abre o loft")
    resposta.texto   # o que dizer

O cliente de voz sintetiza no Piper. Um cliente de celular, no dia em que
existir, mostra na tela — e a única coisa que faltará escrever é o transporte.
Este módulo **não imprime e não fala**: devolve texto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config import Config
from . import acoes
from .ancoragem import ancoragem
from .atalhos import Atalho, Casamento, Desfecho, Tabela, normalizar
from .busca import Achado, Buscador, pastas_que_distinguem
from .cerebro import Cerebro, Confirmacao, ErroDoCerebro

__all__ = ["Nucleo", "Resposta", "ErroDoCerebro"]


@dataclass(frozen=True)
class Resposta:
    texto: str
    acao: str | None = None  # o que foi executado, para o log da §2.5
    perguntando: bool = False  # há uma confirmação pendente
    # Tudo que o cliente precisa para registrar o que aconteceu por dentro.
    # O núcleo não escreve log — devolve os dados e quem grava é quem já grava.
    diagnostico: dict = field(default_factory=dict)


class Nucleo:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.tabela = Tabela.carregar(cfg.raiz / "atalhos.toml")
        self.cerebro = Cerebro(cfg.llm)
        self.cerebro.conferir()
        self.cerebro.usar_atalhos([a.nome for a in self.tabela.atalhos])
        self.buscador = Buscador(cfg.busca)
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
        # Mesma natureza: os candidatos de uma busca esperando você estreitar.
        self._busca: list[Achado] | None = None
        self._termo = ""
        # Ele negou sem dizer o que queria; a próxima fala é o nome.
        self._esperando_nome = False
        self._diag: dict = {}

    # ----------------------------------------------------------------------

    def processar(self, texto: str) -> Resposta:
        texto = texto.strip()
        if not texto:
            return Resposta("")

        # Uma busca aberta tem prioridade: a fala seguinte é a pista que
        # estreita. Não passa pelo LLM — é texto casado contra os caminhos,
        # mais rápido e sem nada que possa errar.
        if self._busca is not None:
            return self._estreitar(texto)

        if self._pendente is not None:
            return self._responder_confirmacao(texto)

        if self._esperando_nome:
            self._esperando_nome = False
            return self._resolver_nome(texto, origem="correção")

        interpretacao = self.cerebro.interpretar(texto)
        if interpretacao.nome is None:
            return Resposta(
                self.cfg.persona.nao_sei,
                diagnostico={"houve_tool_call": False, "dito": texto},
            )
        return self._resolver_nome(interpretacao.nome, dito=texto)

    def _resolver_nome(
        self,
        nome: str,
        *,
        dito: str | None = None,
        origem: str = "comando",
        rejeitado: Atalho | None = None,
    ) -> Resposta:
        """Valida a ancoragem e segue: atalhos primeiro, busca depois."""
        dito = dito if dito is not None else nome
        nota = ancoragem(nome, dito)
        diag = {
            "houve_tool_call": True,
            "origem": origem,
            "dito": dito,
            "extraiu": nome,
            "ancoragem": round(nota, 3),
        }

        if nota < self.cfg.llm.ancoragem_minima:
            # O modelo devolveu um nome que não está no que foi falado —
            # forçou a entrada para dentro da lista do prompt. Descartar é
            # obrigatório: foi assim que "abridança.ppxt" virou "Abrindo loft".
            diag["reprovado_por_ancoragem"] = True
            return Resposta(self.cfg.persona.nao_entendi, diagnostico=diag)

        casamento = self.tabela.casar(nome)
        diag["casamento"] = {
            "desfecho": casamento.desfecho.name,
            "nota": round(casamento.pontuacao, 3),
            "atalho": casamento.atalho.nome if casamento.atalho else None,
        }

        # Ele acabou de recusar este atalho. Sugerir o mesmo de novo criaria
        # um laço: "abre configurações" → "quis dizer gravações?" → "não, quis
        # dizer configurações" → "quis dizer gravações?". Recusado uma vez,
        # vai direto para a busca.
        if rejeitado is not None and casamento.atalho == rejeitado:
            diag["atalho_rejeitado"] = rejeitado.nome
            return self._procurar(nome, diag)

        return self._resolver(casamento, nome, diag)

    # ----------------------------------------------------------------------

    def _resolver(self, casamento: Casamento, falado: str, diag: dict) -> Resposta:
        if casamento.desfecho is Desfecho.NADA or casamento.atalho is None:
            # Não está na tabela: procura no disco. É o degrau seguinte do
            # atalho, não um comando novo — o modelo continua vendo uma
            # função só.
            return self._procurar(falado, diag)

        if casamento.desfecho is Desfecho.CERTO:
            return self._executar(casamento.atalho, diag)

        # SUGESTAO — pergunta antes de agir. É a §2.2: não chutar.
        self._pendente = casamento.atalho
        if casamento.empatados:
            a, b = casamento.empatados
            return Resposta(
                f"Você quis dizer {a.nome} ou {b.nome}?",
                perguntando=True,
                diagnostico=diag,
            )
        return Resposta(
            f"Você quis dizer {casamento.atalho.nome}?",
            perguntando=True,
            diagnostico=diag,
        )

    def _responder_confirmacao(self, texto: str) -> Resposta:
        pendente = self._pendente
        self._pendente = None
        assert pendente is not None

        resposta = self.cerebro.confirmar(texto)
        diag = {"origem": "confirmação", "dito": texto,
                "confirmacao": resposta.name, "sugerido": pendente.nome}

        if resposta is Confirmacao.SIM:
            return self._executar(pendente, diag)

        if resposta is Confirmacao.NAO:
            # Negar não pode ser beco sem saída. O Léo costuma dizer o nome
            # certo na mesma frase — "não, eu quis dizer configurações" — e
            # jogar isso fora obrigava ele a repetir o comando inteiro.
            correcao = self.cerebro.corrigir(texto)
            diag["correcao"] = correcao
            if correcao:
                return self._resolver_nome(
                    correcao, dito=texto, origem="correção", rejeitado=pendente
                )
            # Negou sem dizer o que queria: pergunta, em vez de encerrar.
            self._esperando_nome = True
            return Resposta(
                self.cfg.persona.o_que_entao, perguntando=True, diagnostico=diag
            )

        # Não foi sim nem não: trata como pedido novo, em vez de insistir na
        # pergunta antiga. Ficar preso numa confirmação seria pior que errar.
        return self.processar(texto)

    def _executar(self, atalho: Atalho, diag: dict | None = None) -> Resposta:
        resultado = acoes.executar(atalho, self.comandos)
        return Resposta(
            resultado.mensagem,
            acao=f"abrir:{atalho.tipo}:{atalho.nome}" if resultado.ok else None,
            diagnostico=diag or {},
        )

    # -- busca -------------------------------------------------------------

    def _procurar(self, termo: str, diag: dict) -> Resposta:
        self._termo = termo
        achados = self.buscador.buscar(termo)
        diag["busca"] = dict(self.buscador.ultimo_diagnostico)
        diag["busca"]["resultados"] = len(achados)
        self._diag = diag
        return self._apresentar(achados, primeira=True)

    def _estreitar(self, filtro: str) -> Resposta:
        candidatos = self._busca or []
        restantes = self.buscador.estreitar(candidatos, filtro)
        diag = {
            "origem": "filtro",
            "dito": filtro,
            "pista": normalizar(filtro),
            "candidatos_antes": len(candidatos),
            "candidatos_depois": len(restantes),
        }

        if not restantes:
            # A pista não casou. Duas coisas muito diferentes chegam aqui, e
            # a versão antiga tratava as duas como uma: jogava a busca fora e
            # reprocessava como comando novo. Foi assim que "Screenshots"
            # virou "isso eu ainda não sei fazer" e matou a desambiguação.
            #
            # Agora perguntamos ao modelo qual dos dois casos é. Errar a pista
            # é o comum; desistir no meio é o raro.
            interpretacao = self.cerebro.interpretar(filtro)
            if interpretacao.nome is not None:
                diag["saida"] = "comando novo"
                self._busca = None
                return self._resolver_nome(interpretacao.nome, dito=filtro)

            diag["saida"] = "pista ruim — busca mantida"
            return Resposta(
                self.cfg.persona.pista_ruim, perguntando=True, diagnostico=diag
            )

        self._diag = diag
        return self._apresentar(restantes, primeira=False)

    def _apresentar(self, achados: list[Achado], *, primeira: bool) -> Resposta:
        """Zero, um, ou pede filtro. Nunca lista tudo.

        Ler dez caminhos em voz alta é insuportável, e escolher sozinho está
        proibido pela §2.2. Então: um resultado abre; vários viram uma pergunta
        que devolve a escolha ao Léo com o mínimo de informação necessária.
        """
        if not achados:
            self._busca = None
            return Resposta(
                self._frase("busca_nada", termo=self._termo),
                diagnostico=self._diag,
            )

        if len(achados) == 1:
            self._busca = None
            achado = achados[0]
            resultado = acoes.abrir_caminho(achado.caminho, self.comandos)
            return Resposta(
                resultado.mensagem,
                acao=f"abrir:busca:{achado.caminho}" if resultado.ok else None,
                diagnostico=self._diag,
            )

        self._busca = achados
        pastas = pastas_que_distinguem(achados)

        # Poucos candidatos: dizer onde cada um está já É o pedido de filtro.
        # A frase precisa carregar a explicação — a versão anterior era só
        # "Achei três. Em qual pasta?", que o Léo entendeu como "qual pasta
        # você quer de dentro daí" e respondeu errado em todos os testes.
        if len(pastas) <= 3:
            lugares = ", ".join(f"um em {p}" for p in pastas[:-1])
            lugares = f"{lugares} e um em {pastas[-1]}" if lugares else f"um em {pastas[-1]}"
            return Resposta(
                self._frase("busca_poucos", n=len(achados), lugares=lugares),
                perguntando=True,
                diagnostico=self._diag,
            )

        chave = "busca_muitos" if primeira else "busca_muitos_ainda"
        return Resposta(
            self._frase(chave, n=len(achados)),
            perguntando=True,
            diagnostico=self._diag,
        )

    def _frase(self, chave: str, **dados) -> str:
        """Monta uma frase da persona a partir do config.toml.

        Se o Léo editar o template e errar um campo, a conversa não pode
        quebrar no meio: cai numa versão crua em vez de estourar.
        """
        modelo = getattr(self.cfg.persona, chave)
        try:
            return modelo.format(**dados)
        except (KeyError, IndexError, ValueError):
            return modelo

    # ----------------------------------------------------------------------

    def aquecer(self) -> None:
        """Pede ao LLM que se carregue. O cliente chama ao acordar."""
        self.cerebro.aquecer()

    def reiniciar_conversa(self) -> None:
        """Esquece confirmação e busca pendentes.

        O cliente chama ao dormir. Necessário porque a busca agora sobrevive a
        uma pista ruim — e o que sobrevive à pista ruim também sobreviveria ao
        abandono: o Léo desiste, o Jarvis dorme, e a primeira fala do próximo
        despertar viraria filtro de uma busca de meia hora atrás.
        """
        self._pendente = None
        self._busca = None
        self._esperando_nome = False
        self._termo = ""
        self._diag = {}

    @property
    def descricao(self) -> str:
        return f"{self.cfg.llm.modelo} · {len(self.tabela)} atalhos"
