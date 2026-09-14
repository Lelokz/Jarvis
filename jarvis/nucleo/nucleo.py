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
import datetime as dt

from . import acoes, arquivos as mod_arquivos, midia, quando as mod_quando, sistema
from .agenda import Agenda, ErroDaAgenda
from .ancoragem import ancoragem
from .atalhos import Atalho, Casamento, Desfecho, Tabela, normalizar
from .busca import Achado, Buscador, pastas_que_distinguem
from .cerebro import Cerebro, Confirmacao, ErroDoCerebro

__all__ = ["Nucleo", "Resposta", "ErroDoCerebro"]

# Corte de ancoragem só para a expressão de tempo, mais alto que o dos nomes.
#
# Pode ser mais exigente porque a extração de tempo é fácil para o modelo: nas
# dez frases medidas ele copiou a expressão verbatim 10/10, dando ancoragem
# 1.0. Já as invenções chegam perto do corte comum — "marca dentista" fez ele
# devolver 'agora', que pontua exatos 0.600 contra o texto falado e passaria
# por um fio, marcando um compromisso para agora sem ninguém ter pedido.
ANCORAGEM_QUANDO = 0.75

# Como o Léo manda largar o que estiver pendente.
#
# Existe porque a conversa travou de verdade: com uma busca aberta, ele disse
# "para", "esquece", "aumenta o volume" e "move X pra Y", e TODAS viraram pista
# da busca. Ficou preso até o Jarvis dormir sozinho — e como a janela de 30s
# reinicia a cada resposta dele, e ele respondia a cada tentativa, a janela
# nunca fechava.
#
# O ESCOPO da Etapa 5 já registrava "não há saída falada das perguntas
# pendentes" como limitação, e eu escrevi que só prendia a conversa por 30
# segundos. Estava errado: com a busca, prende até desistir de falar.
#
# Só dispara quando há algo pendente. Sem nada na mesa, "para" continua sendo
# pausar a música — é a lista fechada de mídia que decide, como sempre.
DESISTIR = frozenset(
    {
        "esquece", "esquece isso", "esquece disso", "deixa", "deixa isso",
        "deixa pra la", "cancela", "cancela isso", "cancelar", "para",
        "parar", "para com isso", "chega", "desiste", "desisto",
        "nao quero mais", "nao importa", "tanto faz",
    }
)


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
        # A agenda não conecta agora: autenticar na subida faria o Jarvis
        # depender de rede para acordar. Conecta no primeiro uso.
        self.agenda = Agenda(cfg.agenda, cfg.raiz)
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
        # Ele pediu música sem dizer qual; a próxima fala é o nome.
        self._esperando_musica: str | None = None
        # Evento resolvido esperando o "pode". Guarda título, data já
        # calculada e a descrição falada — a confirmação existe justamente
        # para você ouvir a data antes de ela virar notificação no celular.
        # A descrição fica guardada para ele conseguir dizer O QUE descartou,
        # com as mesmas palavras que você acabou de ouvir.
        self._evento_pendente: tuple[str, dt.datetime, str] | None = None
        # A última pergunta de sim/não feita. Vai junto para o classificador:
        # sem ela, "abre o loft" durante uma confirmação era lido como recusa.
        self._pergunta = ""
        # Ele disse o quê mas não o quando; a próxima fala é a data.
        self._esperando_quando: str | None = None
        # Ele disse o dia mas não a hora. Guarda o título E o que ele já
        # tinha dito, porque a resposta ("às 8") não carrega o dia: quem
        # resolve é a soma das duas falas.
        self._esperando_hora: tuple[str, str] | None = None

        # --- Etapa 5: mexer em arquivo ------------------------------------
        # O que fazer com o candidato que a busca escolher. None = abrir, que
        # é o comportamento de sempre. Reusar a busca em vez de duplicá-la
        # mantém a propriedade cara da Etapa 2: a busca sobrevive à pista ruim.
        self._busca_para: str | None = None
        # O nome novo atravessando a desambiguação, quando ele já foi dito.
        self._nome_novo_pendente: str | None = None
        # "renomeia esse aí" — falta saber qual arquivo.
        self._esperando_qual_arquivo: str | None = None
        # Achou o arquivo, falta o nome novo.
        self._esperando_nome_novo: Path | None = None
        # Renomeação resolvida esperando o "pode". É a §2.3 virando estado.
        self._renomeacao_pendente: tuple[Path, str] | None = None
        # (ação, onde está agora, onde estava antes) — para o "desfaz".
        #
        # **Uma ação só, e na memória.** Eu tinha proposto histórico em disco
        # com pilha e alcance de 24 horas; o Léo desenhou contra, e o
        # argumento derruba a proposta: para chegar num erro das três da tarde
        # depois de mais vinte pedidos, ele teria que desfazer os vinte —
        # desmontar uma tarde de arrumação para consertar uma coisa. O erro
        # percebido horas depois se resolve movendo o arquivo de volta na mão,
        # que é mais simples e mais seguro.
        #
        # Morrer quando o Jarvis dorme, então, não é limitação: é o desenho.
        self._ultima_acao: tuple[str, Path, Path] | None = None
        # Volume acima do limite esperando o "pode". Guarda só o número: o
        # plano já foi decidido e nada foi aplicado ainda.
        self._volume_pendente: int | None = None

        # --- Etapa 5.5: mover e copiar ------------------------------------
        # O destino atravessa a desambiguação da origem, no molde do
        # `_nome_novo_pendente`: o barato é resolvido primeiro e espera.
        self._destino_pendente: Path | None = None
        # (origem, pasta de destino, "mover"|"copiar") esperando o "pode".
        self._movimento_pendente: tuple[Path, Path, str] | None = None
        # Ele disse o arquivo e não o destino; a próxima fala é a pasta.
        self._esperando_destino: tuple[str, str] | None = None
        # Duas pastas com o mesmo nome: (candidatas, origem falada, ação).
        self._esperando_qual_destino: tuple[list[Path], str, str] | None = None
        self._diag: dict = {}

    # ----------------------------------------------------------------------

    def processar(self, texto: str) -> Resposta:
        texto = texto.strip()
        if not texto:
            return Resposta("")

        # Largar o que está pendente vem ANTES de tudo, senão a própria coisa
        # que segura a conversa engole o pedido de soltar.
        if normalizar(texto) in DESISTIR:
            largado = self._largar_tudo()
            if largado:
                return Resposta(
                    self._frase("desisti", o_que=largado),
                    diagnostico={"origem": "desistência", "dito": texto,
                                 "largado": largado},
                )
            # Nada pendente: segue o fluxo normal. "para" vira pausar.

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

        if self._evento_pendente is not None:
            return self._confirmar_evento(texto)

        if self._esperando_quando is not None:
            titulo, self._esperando_quando = self._esperando_quando, None
            return self._agendar(titulo, texto, {"origem": "quando pedido"})

        if self._esperando_hora is not None:
            titulo, ja_dito = self._esperando_hora
            self._esperando_hora = None
            # Junta com o que ele já disse: "amanhã" + "às 8 da noite".
            # Resolver só a resposta perderia o dia.
            return self._agendar(
                titulo, f"{ja_dito} {texto}",
                {"origem": "hora pedida", "ja_dito": ja_dito},
            )

        if self._esperando_musica is not None:
            return self._musica_pedida(texto)

        if self._volume_pendente is not None:
            return self._confirmar_volume(texto)

        if self._movimento_pendente is not None:
            return self._confirmar_movimento(texto)

        if self._esperando_qual_destino is not None:
            candidatas, origem, acao = self._esperando_qual_destino
            self._esperando_qual_destino = None
            return self._escolher_destino_entre(candidatas, texto, origem, acao)

        if self._esperando_destino is not None:
            origem, acao = self._esperando_destino
            self._esperando_destino = None
            return self._movimentar(acao, origem, texto, {"origem_da_vez": "destino pedido"})

        if self._renomeacao_pendente is not None:
            return self._confirmar_renomeacao(texto)

        if self._esperando_qual_arquivo is not None:
            novo, self._esperando_qual_arquivo = self._esperando_qual_arquivo, None
            # O propósito vem do `_busca_para`, que o `_com_destino` já marcou.
            # Sem isto, perguntar "qual arquivo?" no meio de um mover voltaria
            # pelo caminho da renomeação e o destino se perderia.
            return self._escolher_arquivo(
                texto, novo, {"origem": "qual arquivo"},
                para=self._busca_para or "renomear",
            )

        if self._esperando_nome_novo is not None:
            caminho, self._esperando_nome_novo = self._esperando_nome_novo, None
            return self._com_arquivo(caminho, texto)

        # Comando de mídia cru, sem objeto: não passa pelo modelo.
        #
        # Vem DEPOIS de todos os pendentes acima, e a ordem é a defesa: "pausa"
        # dito como pista de uma busca aberta, ou como nome novo de um arquivo,
        # já foi consumido lá em cima e nunca chega aqui. O casamento é contra
        # a fala INTEIRA, então "renomeia o relatório para proposta" — que
        # contém "para" — também não casa.
        #
        # Medido: com o núcleo em 9 funções, "Para!" caía em nada 5/5. E estas
        # falas custavam 0,46s de núcleo nos logs reais, quase tudo o modelo
        # decidindo algo que uma tabela de 17 entradas decide sem errar.
        cru = midia.comando_cru(texto)
        if cru is not None:
            return self._midia(
                {"acao": cru.acao, "qual": cru.qual},
                {"origem": "comando cru de mídia", "dito": texto,
                 "houve_tool_call": False, "funcao": "midia",
                 "qual_player": cru.qual},
                texto,
            )

        interpretacao = self.cerebro.interpretar(texto)
        return self._despachar(interpretacao, texto)

    def _despachar(self, interpretacao, texto: str) -> Resposta:
        """O que fazer com a função que o modelo escolheu.

        Separado do `processar` de propósito: a saída de emergência da busca
        precisa despachar um comando novo, e antes ela só sabia reconhecer o
        `abrir`. Com onze funções, isso virou buraco negro — "aumenta o
        volume", "move X pra Y" e "esquece" eram todos engolidos como pista de
        uma busca aberta, e o Léo ficou preso até o Jarvis dormir sozinho.
        """
        base = {"houve_tool_call": interpretacao.funcao is not None,
                "funcao": interpretacao.funcao, "dito": texto,
                "argumentos": interpretacao.argumentos}

        if interpretacao.funcao is None:
            # "Pode" sem nada na mesa não pode virar nao_sei: foi assim que um
            # dentista deixou de ser marcado sem ninguém notar — o pendente
            # tinha morrido em silêncio duas falas antes. Custa 0,07s e só
            # roda aqui, no caminho em que ele já ia desistir de qualquer jeito.
            if self.cerebro.resposta_solta(texto):
                base["resposta_solta"] = True
                return Resposta(self.cfg.persona.nada_pendente,
                                diagnostico=base)
            return Resposta(self.cfg.persona.nao_sei, diagnostico=base)

        if interpretacao.funcao == "abrir":
            if interpretacao.nome is None:
                return Resposta(self.cfg.persona.nao_entendi, diagnostico=base)
            return self._resolver_nome(interpretacao.nome, dito=texto)

        if interpretacao.funcao == "tocar":
            return self._tocar(interpretacao, texto, base)

        if interpretacao.funcao == "midia":
            return self._midia(interpretacao.argumentos, base, texto)

        if interpretacao.funcao == "criar_evento":
            return self._agendar(
                str(interpretacao.argumentos.get("titulo") or "").strip(),
                str(interpretacao.argumentos.get("quando") or "").strip(),
                base,
            )

        if interpretacao.funcao == "agenda_do_dia":
            return self._listar_agenda(
                str(interpretacao.argumentos.get("quando") or "").strip(), base
            )

        if interpretacao.funcao == "renomear":
            return self._renomear(
                str(interpretacao.argumentos.get("alvo") or "").strip(),
                str(interpretacao.argumentos.get("nome_novo") or "").strip(),
                base, texto,
            )

        if interpretacao.funcao == "criar_pasta":
            return self._criar_pasta(
                str(interpretacao.argumentos.get("nome") or "").strip(),
                str(interpretacao.argumentos.get("dentro_de") or "").strip(),
                base, texto,
            )

        if interpretacao.funcao in ("mover", "copiar"):
            return self._movimentar(
                interpretacao.funcao,
                str(interpretacao.argumentos.get("origem") or "").strip(),
                str(interpretacao.argumentos.get("destino") or "").strip(),
                base, texto,
            )

        if interpretacao.funcao == "desfazer":
            return self._desfazer(base)

        if interpretacao.funcao == "status_pc":
            r = sistema.status_gpu()
            base["detalhe"] = r.detalhe
            return Resposta(r.mensagem, acao="status_pc" if r.ok else None,
                            diagnostico=base)

        # Função que o modelo inventou e nós não temos.
        base["funcao_desconhecida"] = interpretacao.funcao
        return Resposta(self.cfg.persona.nao_sei, diagnostico=base)

    # -- agenda ------------------------------------------------------------

    def _agendar(
        self, titulo: str, expressao: str, diag: dict, dito: str | None = None
    ) -> Resposta:
        if not titulo:
            return Resposta(self.cfg.persona.nao_entendi, diagnostico=diag)

        # O modelo inventa data quando você não diz nenhuma: "marca academia"
        # devolvia quando='/' e "marca dentista" devolvia quando='agora'. Sem
        # esta guarda ele marcava para amanhã de manhã sem você ter pedido.
        #
        # É a mesma ancoragem da Etapa 2, pelo mesmo motivo: o que o modelo
        # devolve tem que estar no que foi falado.
        dito = dito if dito is not None else diag.get("dito")
        if expressao and dito:
            nota = ancoragem(expressao, dito)
            diag["ancoragem_quando"] = round(nota, 3)
            if nota < ANCORAGEM_QUANDO:
                diag["quando_inventado"] = expressao
                expressao = ""

        if not expressao:
            # Disse o quê mas não o quando. Pergunta em vez de chutar hoje.
            self._esperando_quando = titulo
            return Resposta(
                self.cfg.persona.agenda_sem_quando, perguntando=True,
                diagnostico=diag,
            )

        quando = mod_quando.resolver(expressao)
        if quando is None:
            return Resposta(self.cfg.persona.nao_entendi, diagnostico=diag)

        diag["quando"] = {"falado": expressao,
                          "resolvido": quando.inicio.isoformat(),
                          "descricao": quando.descricao}

        # Confirma ANTES de escrever. Erro de data é silencioso — um horário
        # bem formado e errado parece certo —, e a frase diz o dia da semana
        # justamente para você perceber que ele entendeu sábado quando você
        # quis dizer segunda.
        if not quando.disse_hora:
            # Ele disse o dia e não a hora. Marcar às 9 seria inventar um
            # horário que ele não falou — e a confirmação diria só "amanhã,
            # sexta", sem hora nenhuma, então nem dava para perceber o
            # palpite. Perguntar custa uma fala; compromisso na hora errada
            # custa o compromisso.
            self._esperando_hora = (titulo, expressao)
            return Resposta(self.cfg.persona.agenda_sem_hora,
                            perguntando=True, diagnostico=diag)

        self._evento_pendente = (titulo, quando.inicio, quando.descricao)
        pergunta = self._frase("agenda_confirmar", titulo=titulo,
                               quando=quando.descricao)
        self._pergunta = pergunta
        return Resposta(pergunta, perguntando=True, diagnostico=diag)

    def _confirmar_evento(self, texto: str) -> Resposta:
        titulo, inicio, descricao = self._evento_pendente
        self._evento_pendente = None
        resposta = self.cerebro.confirmar(texto, self._pergunta)
        diag = {"origem": "confirmação de evento", "dito": texto,
                "confirmacao": resposta.name, "titulo": titulo,
                "inicio": inicio.isoformat()}

        if resposta is Confirmacao.NAO:
            return Resposta(self.cfg.persona.agenda_cancelado, diagnostico=diag)
        if resposta is not Confirmacao.SIM:
            # Não foi sim nem não: trata como pedido novo, a mesma saída de
            # emergência que a confirmação de atalho já usa.
            #
            # Mas AVISA o que caiu. Descartar aqui é certo — insistir na
            # pergunta antiga seria pior —, só que fazer isso calado deixa
            # você achando que marcou. Foi o que aconteceu: duas falas soltas
            # mataram um dentista pendente, e o "pode" seguinte não tinha mais
            # nada para confirmar.
            nova = self.processar(texto)
            diag["descartado"] = f"{titulo} {descricao}"
            aviso = self._frase("agenda_descartado", titulo=titulo,
                                quando=descricao)
            return Resposta(
                f"{aviso} {nova.texto}".strip(),
                acao=nova.acao,
                perguntando=nova.perguntando,
                diagnostico={**diag, "seguiu_para": nova.diagnostico},
            )

        try:
            r = self.agenda.criar(titulo, inicio)
        except ErroDaAgenda as e:
            return Resposta(str(e).splitlines()[0], diagnostico=diag)
        return Resposta(
            self.cfg.persona.agenda_criado if r.ok else r.mensagem,
            acao=f"agenda:criar:{inicio:%Y-%m-%dT%H:%M}" if r.ok else None,
            diagnostico=diag,
        )

    def _listar_agenda(self, expressao: str, diag: dict) -> Resposta:
        quando = mod_quando.resolver(expressao or "hoje")
        dia = quando.inicio.date() if quando else dt.date.today()
        rotulo = quando.descricao.split(" às ")[0] if quando else "hoje"

        try:
            eventos = self.agenda.do_dia(dia)
        except ErroDaAgenda as e:
            return Resposta(str(e).splitlines()[0], diagnostico=diag)

        # HOJE corta pelo relógio; dia futuro, não. Perguntar "o que eu tenho
        # hoje?" às 18h é perguntar o que ainda vai acontecer.
        #
        # A versão anterior lia os três primeiros CONTADOS DA MEIA-NOITE. Com
        # cinco compromissos ela respondeu "escola às 7h30" — dez horas depois
        # de a escola ter acabado — e escondeu os dois únicos que faltavam,
        # justamente por serem os últimos. A frase dizia "os próximos" e
        # entregava os primeiros.
        #
        # Em dia futuro o corte não existe: lá o dia inteiro está pela frente,
        # e cortar esconderia compromisso.
        #
        # Evento de dia inteiro nunca é cortado. Ele começa 00:00 e contaria
        # como passado a partir do primeiro minuto do dia, sumindo da lista
        # sem nunca ter acontecido.
        agora = dt.datetime.now()
        passados: list = []
        if dia == agora.date():
            passados = [e for e in eventos
                        if not e.dia_inteiro and e.inicio < agora]
            eventos = [e for e in eventos
                       if e.dia_inteiro or e.inicio >= agora]

        diag["agenda"] = {"dia": dia.isoformat(), "restam": len(eventos),
                          "ja_passaram": len(passados)}

        if not eventos:
            # Dia que acabou não é dia vazio, e a diferença importa: dizer
            # "você não tem nada hoje" às 22h é falso sobre o dia inteiro.
            chave = "agenda_acabou" if passados else "agenda_vazia"
            return Resposta(self._frase(chave, dia=rotulo), diagnostico=diag)

        teto = self.cfg.agenda.max_eventos_falados
        falados = eventos[:teto]
        lista = ", ".join(
            f"{e.titulo}, {e.hora_falavel}" if e.dia_inteiro
            else f"{e.titulo} às {e.hora_falavel}"
            for e in falados
        )

        if len(eventos) == 1:
            chave = "agenda_um"
        elif len(eventos) <= teto:
            chave = "agenda_varios"
        else:
            chave = "agenda_muitos"
        return Resposta(
            self._frase(chave, n=len(eventos), mostrados=len(falados),
                        dia=rotulo, eventos=lista),
            acao="agenda:listar",
            diagnostico=diag,
        )

    # -- arquivos (Etapa 5) ------------------------------------------------

    def _movimentar(
        self, acao: str, origem: str, destino: str, diag: dict,
        dito: str | None = None,
    ) -> Resposta:
        """Mover ou copiar: resolve o DESTINO primeiro, a origem depois.

        A ordem não é arbitrária. O destino é barato — casamento de nome contra
        as pastas em memória, sem tocar no disco de verdade. A origem é caro:
        busca no disco com a desambiguação da Etapa 2. Resolvendo o barato
        primeiro, o Léo não desambigua um arquivo para depois descobrir que a
        pasta que ele falou não existe.
        """
        diag["acao_arquivo"] = acao
        if dito:
            for campo, valor in (("origem", origem), ("destino", destino)):
                if not valor:
                    continue
                nota = ancoragem(valor, dito)
                diag[f"ancoragem_{campo}"] = round(nota, 3)
                if nota < self.cfg.llm.ancoragem_minima:
                    diag[f"{campo}_inventado"] = valor
                    if campo == "origem":
                        origem = ""
                    else:
                        destino = ""

        if origem and mod_arquivos.aponta_sem_nomear(origem):
            diag["origem_so_aponta"] = origem
            origem = ""

        if not destino:
            self._esperando_destino = (origem, acao)
            return Resposta(
                self.cfg.persona.arquivo_sem_destino, perguntando=True,
                diagnostico=diag,
            )

        candidatas = mod_arquivos.casar_destino(destino, self.cfg.arquivos)
        diag["destinos_que_casaram"] = [str(c) for c in candidatas]
        if not candidatas:
            # Diferente de "não achei o arquivo": a pasta é que não casou, e
            # dizer a coisa errada faz o Léo repetir o nome do arquivo em vão.
            #
            # E "não casou" ainda tem duas causas, que também são diferentes
            # entre si: a pasta não existe, ou existe e não está liberada.
            # "Não conheço pasta chamada Home" mandou o Léo procurar problema
            # onde não tinha — o comportamento estava certo e a frase mentia.
            motivo = mod_arquivos.explicar_destino(destino, self.cfg.arquivos)
            diag["destino_nao_casou"] = motivo or "nao_existe"
            if motivo:
                qual, nome = motivo
                frase = ("arquivo_destino_vetado" if qual == "vetada"
                         else "arquivo_destino_fora_da_lista")
                return Resposta(
                    self._frase(frase, destino=nome), diagnostico=diag
                )
            return Resposta(
                self._frase("arquivo_destino_desconhecido", destino=destino),
                diagnostico=diag,
            )
        if len(candidatas) > 1:
            return self._perguntar_qual_destino(candidatas, origem, acao, diag)

        return self._com_destino(candidatas[0], origem, acao, diag)

    def _perguntar_qual_destino(
        self, candidatas: list[Path], origem: str, acao: str, diag: dict
    ) -> Resposta:
        """"Músicas" existe na casa e no HD. Quem escolhe é o Léo (§2.2)."""
        self._esperando_qual_destino = (candidatas, origem, acao)
        lugares = ", ".join(f"uma em {c.parent.name}" for c in candidatas)
        return Resposta(
            self._frase("arquivo_qual_destino", n=len(candidatas), lugares=lugares),
            perguntando=True,
            diagnostico=diag,
        )

    def _escolher_destino_entre(
        self, candidatas: list[Path], pista: str, origem: str, acao: str
    ) -> Resposta:
        """Casa a resposta dele contra o CAMINHO das candidatas.

        Contra o caminho inteiro, e não só contra o nome do pai: ele pode
        responder "no HD", "em Midia" ou o caminho todo, e as três funcionam.
        """
        chave = normalizar(pista)
        diag = {"origem_da_vez": "qual destino", "pista": chave}
        restantes = [c for c in candidatas if chave in normalizar(str(c))]
        if len(restantes) == 1:
            return self._com_destino(restantes[0], origem, acao, diag)
        if not restantes:
            return Resposta(self.cfg.persona.pista_ruim, diagnostico=diag)
        return self._perguntar_qual_destino(restantes, origem, acao, diag)

    def _com_destino(
        self, pasta: Path, origem: str, acao: str, diag: dict
    ) -> Resposta:
        """Destino resolvido. Agora acha a origem, que é a parte caro."""
        diag["destino"] = str(pasta)
        if not origem:
            self._esperando_qual_arquivo = ""
            self._destino_pendente = pasta
            self._busca_para = acao
            return Resposta(
                self.cfg.persona.arquivo_qual, perguntando=True, diagnostico=diag
            )
        self._destino_pendente = pasta
        return self._escolher_arquivo(origem, "", diag, para=acao)

    def _com_movimento(self, caminho: Path, pasta: Path, acao: str) -> Resposta:
        """Tem origem e destino. Monta a confirmação — nunca age antes dela."""
        diag = {"origem_da_vez": acao, "de": str(caminho), "para": str(pasta)}
        self._movimento_pendente = (caminho, pasta, acao)
        chave = "arquivo_mover_confirmar" if acao == "mover" else "arquivo_copiar_confirmar"
        pergunta = self._frase(
            chave, origem=mod_arquivos.falar_nome(caminho), destino=pasta.name
        )
        self._pergunta = pergunta
        return Resposta(pergunta, perguntando=True, diagnostico=diag)

    def _confirmar_movimento(self, texto: str) -> Resposta:
        caminho, pasta, acao = self._movimento_pendente
        self._movimento_pendente = None
        resposta = self.cerebro.confirmar(texto, self._pergunta)
        diag = {"origem_da_vez": f"confirmação de {acao}", "dito": texto,
                "confirmacao": resposta.name, "de": str(caminho),
                "para": str(pasta)}

        if resposta is Confirmacao.NAO:
            return Resposta(
                self.cfg.persona.arquivo_movimento_cancelado, diagnostico=diag
            )

        if resposta is not Confirmacao.SIM:
            # Descarta e AVISA, como a Etapa 5 estabeleceu.
            nova = self.processar(texto)
            diag["descartado"] = str(caminho)
            aviso = self._frase(
                "arquivo_movimento_descartado",
                origem=mod_arquivos.falar_nome(caminho),
            )
            return Resposta(
                f"{aviso} {nova.texto}".strip(), acao=nova.acao,
                perguntando=nova.perguntando,
                diagnostico={**diag, "seguiu_para": nova.diagnostico},
            )

        funcao = mod_arquivos.mover if acao == "mover" else mod_arquivos.copiar
        r = funcao(caminho, pasta, self.cfg.arquivos)
        diag["resultado"] = r.detalhe
        if r.ok and acao == "mover" and r.detalhe:
            # Mesma forma da renomeação: onde está AGORA, onde estava antes.
            #
            # **Copiar fica de fora de propósito.** Desfazer uma cópia é apagar
            # um arquivo — destruição nova, e pior que o estrago que repara: se
            # ele editou a cópia, o desfazer come o trabalho. Cópia sobrando é
            # bagunça que se vê, não dano que se descobre tarde.
            self._ultima_acao = (
                "mover", Path(r.detalhe["para"]), Path(r.detalhe["de"])
            )
        return Resposta(
            r.mensagem,
            acao=f"{acao}:{caminho}->{pasta}" if r.ok else None,
            diagnostico=diag,
        )

    def _largar_tudo(self) -> str | None:
        """Solta tudo que estiver pendente. Devolve o que largou, ou None.

        Dizer O QUE foi largado é a lição da Etapa 4 e da 5: descartar calado
        faz o Léo achar que o pedido continua de pé.
        """
        if self._busca is not None:
            o_que = "a busca"
        elif self._movimento_pendente is not None:
            o_que = "o que eu ia mover"
        elif self._renomeacao_pendente is not None:
            o_que = "a renomeação"
        elif self._evento_pendente is not None:
            o_que = "o compromisso"
        elif self._volume_pendente is not None:
            o_que = "o volume"
        elif self._pendente is not None:
            o_que = "a pergunta"
        elif (self._esperando_nome or self._esperando_musica is not None
              or self._esperando_quando is not None
              or self._esperando_hora is not None
              or self._esperando_qual_arquivo is not None
              or self._esperando_nome_novo is not None
              or self._esperando_destino is not None
              or self._esperando_qual_destino is not None):
            o_que = "a pergunta"
        else:
            return None

        # Reusa a limpeza que o cliente já chama ao dormir, em vez de manter
        # duas listas de estado que vão divergir no dia em que alguém esquecer
        # de acrescentar um campo nas duas.
        ultima = self._ultima_acao
        self.reiniciar_conversa()
        self._ultima_acao = ultima  # desistir não é desfazer
        return o_que

    def _soltar_busca(self) -> None:
        """Esquece a busca E o que ela ia fazer com o resultado.

        Os dois juntos, sempre: uma busca que morre deixando o propósito para
        trás faria a próxima busca — de abrir — cair no caminho de renomear.
        """
        self._busca = None
        self._busca_para = None
        self._nome_novo_pendente = None
        self._destino_pendente = None

    def _pode_mexer(self, caminho: Path) -> bool:
        return mod_arquivos.pode_mexer(caminho, self.cfg.arquivos)

    def _renomear(self, alvo: str, nome_novo: str, diag: dict, dito: str) -> Resposta:
        if alvo:
            nota = ancoragem(alvo, dito)
            diag["ancoragem_alvo"] = round(nota, 3)
            if nota < self.cfg.llm.ancoragem_minima:
                diag["alvo_inventado"] = alvo
                alvo = ""

        if nome_novo:
            nota = ancoragem(nome_novo, dito)
            diag["ancoragem_nome_novo"] = round(nota, 3)
            if nota < self.cfg.llm.ancoragem_minima:
                diag["nome_novo_inventado"] = nome_novo
                nome_novo = ""

        # Guarda que a ancoragem não tem como dar: o modelo copia o nome do
        # ALVO para o campo do nome novo. Medido — "muda o nome do print"
        # devolve nome_novo='print' em 3 de 5 rodadas, com ancoragem 1.00,
        # porque a palavra está mesmo na frase. Nome novo igual ao alvo não é
        # nome novo; é o modelo preenchendo campo obrigatório com o que tinha
        # à mão.
        if nome_novo and alvo and normalizar(nome_novo) == normalizar(alvo):
            diag["nome_novo_copiou_alvo"] = nome_novo
            nome_novo = ""

        if alvo and mod_arquivos.aponta_sem_nomear(alvo):
            diag["alvo_so_aponta"] = alvo
            alvo = ""

        if not alvo:
            self._esperando_qual_arquivo = nome_novo
            return Resposta(
                self.cfg.persona.arquivo_qual, perguntando=True, diagnostico=diag
            )

        return self._escolher_arquivo(alvo, nome_novo, diag)

    def _escolher_arquivo(
        self, alvo: str, nome_novo: str, diag: dict, para: str = "renomear"
    ) -> Resposta:
        """Acha o arquivo e entrega para a confirmação. Nunca age."""
        self._termo = alvo
        achados = self.buscador.buscar(alvo)
        def liberados(lista):
            return [a for a in lista if not a.e_pasta and self._pode_mexer(a.caminho)]
        podem = liberados(achados)

        # Achou coisas e nenhuma serve? Pode ser o índice desatualizado
        # devolvendo os homônimos errados. Vai ao disco antes de desistir —
        # é o que salva "cria a pasta X e move algo que está nela".
        if achados and not podem:
            diag["retry_find"] = True
            achados = self.buscador.buscar(alvo, forcar_find=True)
            podem = liberados(achados)
        diag["busca"] = {
            **self.buscador.ultimo_diagnostico,
            "resultados": len(achados),
            "dentro_da_lista_branca": len(podem),
        }
        self._diag = diag

        # Achou e não pode mexer é diferente de não achar. Dizer "não achei"
        # aqui seria mentira, e o Léo ficaria repetindo o nome achando que o
        # Whisper errou.
        if achados and not podem:
            self._soltar_busca()
            # Diz QUANTAS coisas achou, e não só que não pode mexer. A frase
            # antiga descrevia o que ele achou como se fosse o que o Léo pediu,
            # e fazia parecer que a pasta de destino é que estava barrada.
            #
            # E separa as duas formas de "não posso": tudo dentro de um veto da
            # negra não é "fora das pastas que você liberou" — o ESCOPO.md mora
            # em ~/Projetos/Jarvis, e ~/Projetos está liberada.
            todos_vetados = all(
                mod_arquivos.vetado(a.caminho, self.cfg.arquivos) for a in achados
            )
            diag["todos_vetados"] = todos_vetados
            frase = "arquivo_vetado" if todos_vetados else "arquivo_fora_da_lista"
            return Resposta(
                self._frase(frase, n=len(achados)), diagnostico=diag
            )

        self._busca_para = para
        self._nome_novo_pendente = nome_novo
        return self._apresentar(podem, primeira=True)

    def _com_arquivo(self, caminho: Path, nome_novo: str) -> Resposta:
        """Tem o arquivo. Pede o nome que falta, ou monta a confirmação."""
        diag = {"origem": "renomear", "alvo": str(caminho)}
        final = mod_arquivos.nome_final(caminho, nome_novo)
        if not final:
            self._esperando_nome_novo = caminho
            return Resposta(
                self.cfg.persona.arquivo_qual_nome, perguntando=True, diagnostico=diag
            )

        # A extensão só é falada quando MUDA. Ela é preservada sozinha, então
        # dizer ".pdf" toda vez é ruído que o Piper lê mal; mas trocar .txt por
        # .md muda qual programa abre o arquivo, e isso o Léo precisa ouvir.
        destino = caminho.parent / final
        if destino.suffix.lower() != caminho.suffix.lower():
            falado_novo = final
        else:
            falado_novo = mod_arquivos.falar_nome(destino)

        diag["novo"] = final
        self._renomeacao_pendente = (caminho, nome_novo)
        pergunta = self._frase(
            "arquivo_confirmar",
            atual=mod_arquivos.falar_nome(caminho),
            novo=falado_novo,
        )
        self._pergunta = pergunta
        return Resposta(pergunta, perguntando=True, diagnostico=diag)

    def _confirmar_renomeacao(self, texto: str) -> Resposta:
        caminho, nome_novo = self._renomeacao_pendente
        self._renomeacao_pendente = None
        resposta = self.cerebro.confirmar(texto, self._pergunta)
        diag = {
            "origem": "confirmação de renomeação",
            "dito": texto,
            "confirmacao": resposta.name,
            "alvo": str(caminho),
            "novo": nome_novo,
        }

        if resposta is Confirmacao.NAO:
            return Resposta(self.cfg.persona.arquivo_cancelado, diagnostico=diag)

        if resposta is not Confirmacao.SIM:
            # Mesma lição da Etapa 4: descartar aqui é certo, fazer isso calado
            # não. Sumir sem avisar deixa o Léo achando que renomeou.
            nova = self.processar(texto)
            diag["descartado"] = str(caminho)
            aviso = self._frase(
                "arquivo_descartado", atual=mod_arquivos.falar_nome(caminho)
            )
            return Resposta(
                f"{aviso} {nova.texto}".strip(),
                acao=nova.acao,
                perguntando=nova.perguntando,
                diagnostico={**diag, "seguiu_para": nova.diagnostico},
            )

        r = mod_arquivos.renomear(
            caminho, nome_novo, self.cfg.arquivos
        )
        diag["resultado"] = r.detalhe
        if r.ok and r.detalhe:
            # Guarda invertido: de onde ele está AGORA para onde estava antes.
            self._ultima_acao = (
                "renomear",
                Path(r.detalhe["para"]),
                Path(r.detalhe["de"]),
            )
        return Resposta(
            r.mensagem,
            acao=f"renomear:{caminho}" if r.ok else None,
            diagnostico=diag,
        )

    def _desfazer(self, diag: dict) -> Resposta:
        """Volta a última ação da conversa — renomear ou mover.

        As duas passam pela mesma porta porque o Léo diz a mesma palavra para
        as duas. Cada uma é revertida pela função que a fez: renomear pelo
        `reverter`, que devolve o nome EXATO lido do disco em vez de um nome
        parecido reconstruído da fala; mover pelo `mover`, que é a função do
        caminho de ida e traz a invariante e a travessia entre discos junto.
        """
        if self._ultima_acao is None:
            return Resposta(self.cfg.persona.nada_para_desfazer, diagnostico=diag)

        acao, de, para = self._ultima_acao
        diag["desfazendo"] = acao
        self._ultima_acao = None
        if acao == "mover":
            r = mod_arquivos.desfazer_movimento(de, para.parent, self.cfg.arquivos)
        else:
            r = mod_arquivos.reverter(de, para, self.cfg.arquivos)
        diag["resultado"] = r.detalhe
        if not r.ok:
            # Falhou: devolve o desfazer para a mesa. Alguém pode ter ocupado
            # o nome antigo, e a saída é liberar o nome e mandar desfazer de
            # novo — não perder a única chance.
            self._ultima_acao = (acao, de, para)
        return Resposta(
            r.mensagem, acao=f"desfazer:{de}" if r.ok else None, diagnostico=diag
        )

    def _criar_pasta(
        self, nome: str, dentro_de: str, diag: dict, dito: str
    ) -> Resposta:
        if nome:
            nota = ancoragem(nome, dito)
            diag["ancoragem_nome"] = round(nota, 3)
            if nota < self.cfg.llm.ancoragem_minima:
                diag["nome_inventado"] = nome
                nome = ""
        if not nome:
            return Resposta(self.cfg.persona.nao_entendi, diagnostico=diag)

        # O "dentro de" sai da tabela de atalhos, não da busca. Pasta do dia a
        # dia já está lá e resolve instantâneo; e exigir CERTO (0.92) em vez de
        # aceitar sugestão é a §2.2 — criar pasta no lugar errado é bagunça
        # silenciosa, você só descobre quando for procurar.
        atalho = self.tabela.casar(dentro_de).atalho if dentro_de else None
        if (
            atalho is None
            or atalho.tipo != "pasta"
            or self.tabela.casar(dentro_de).desfecho is not Desfecho.CERTO
        ):
            diag["dentro_de_nao_resolveu"] = dentro_de
            return Resposta(
                self.cfg.persona.arquivo_onde_criar, diagnostico=diag
            )

        pai = Path(atalho.alvo).expanduser()
        r = mod_arquivos.criar_pasta(
            nome, pai, self.cfg.arquivos
        )
        diag["resultado"] = r.detalhe
        return Resposta(
            r.mensagem,
            acao=f"criar_pasta:{pai / nome}" if r.ok else None,
            diagnostico=diag,
        )

    # -- mídia -------------------------------------------------------------

    def _tocar(self, interpretacao, dito: str, diag: dict) -> Resposta:
        onde = interpretacao.argumentos.get("onde") or "audio"
        nome = interpretacao.nome

        if nome is None:
            # "toca uma música" sem dizer qual. Mesmo padrão da confirmação e
            # da busca: pergunta e guarda o estado, em vez de desistir.
            self._esperando_musica = onde
            return Resposta(self.cfg.persona.qual_musica, perguntando=True,
                            diagnostico=diag)

        # A mesma guarda do `abrir`: o modelo não pode inventar um nome que
        # não está no que foi falado.
        nota = ancoragem(nome, dito)
        diag["ancoragem"] = round(nota, 3)
        if nota < self.cfg.llm.ancoragem_minima:
            diag["reprovado_por_ancoragem"] = True
            return Resposta(self.cfg.persona.nao_entendi, diagnostico=diag)

        return self._tocar_nome(nome, onde, diag)

    def _musica_pedida(self, texto: str) -> Resposta:
        """A resposta a 'qual música?' — pode trazer o nome e o lugar."""
        onde = self._esperando_musica or "audio"
        self._esperando_musica = None

        # Prompt dedicado, porque a resposta vem sem verbo — "tempo perdido
        # no youtube" não parece comando, e o interpretar() devolvia nada.
        interpretacao = self.cerebro.detalhar_musica(texto)
        diag = {"origem": "qual música", "dito": texto,
                "funcao": interpretacao.funcao,
                "argumentos": interpretacao.argumentos}
        if interpretacao.funcao == "tocar" and interpretacao.nome:
            return self._tocar_nome(
                interpretacao.nome,
                interpretacao.argumentos.get("onde") or onde,
                diag,
            )
        return self._tocar_nome(texto, onde, diag)

    def _tocar_nome(self, nome: str, onde: str, diag: dict) -> Resposta:
        """Atalho primeiro, YouTube depois — o mesmo degrau do `abrir`."""
        casamento = self.tabela.casar(nome)
        if (
            casamento.desfecho is Desfecho.CERTO
            and casamento.atalho is not None
            and casamento.atalho.tipo == "musica"
        ):
            diag["atalho"] = casamento.atalho.nome
            nome = casamento.atalho.alvo

        video = midia.buscar(nome, self.cfg.midia)
        diag["busca_youtube"] = {"termo": nome,
                                 "achou": video.titulo if video else None}
        if video is None:
            return Resposta(
                self._frase("musica_nao_achei", termo=nome), diagnostico=diag
            )

        if onde == "navegador":
            r = midia.tocar_navegador(video, self.cfg.midia)
        else:
            r = midia.tocar_audio(video, self.cfg.midia)
        diag["tocar"] = r.detalhe

        # O `tocar_audio` devolve mensagem vazia quando iniciou e o som não
        # saiu — ele sabe o que houve, mas quem monta frase falada é aqui.
        # Dizer "Tocando" nesse caso era a mentira que o Léo pegou: ele esperou,
        # não veio som, e não tinha como saber se o problema era dele.
        texto = r.mensagem
        if not r.ok and not texto:
            texto = self._frase("musica_nao_saiu", titulo=video.titulo)

        return Resposta(
            texto,
            acao=f"tocar:{onde}:{video.id}" if r.ok else None,
            diagnostico=diag,
        )

    def _midia(self, argumentos: dict, diag: dict, dito: str) -> Resposta:
        acao = (argumentos.get("acao") or "").strip().lower()
        if acao == "volume":
            return self._volume(dito, diag)
        r = midia.controlar(acao, argumentos.get("qual"))
        diag["detalhe"] = r.detalhe
        return Resposta(
            r.mensagem, acao=f"midia:{acao}" if r.ok else None, diagnostico=diag
        )

    def _volume(self, dito: str, diag: dict) -> Resposta:
        """Volume em dois caminhos, e confirmação quando pode doer.

        O `valor` que o modelo devolve **não é usado**, de propósito. Ele
        entregou `valor='100'` para "Pode dar play agora." — um número que não
        existe na frase — e o som foi a 100 no ouvido do Léo. O número agora sai
        da transcrição, que é a única fonte que ele de fato falou.
        """
        plano = sistema.planejar_volume(dito, self.cfg.midia.passo_volume)
        diag["volume"] = {
            "caminho": plano.caminho, "de": plano.atual, "para": plano.novo,
        }
        if not plano.ok:
            return Resposta(plano.mensagem, diagnostico=diag)

        if plano.caminho == "mudo":
            r = sistema.alternar_mudo()
            return Resposta(r.mensagem, acao="midia:mudo" if r.ok else None,
                            diagnostico=diag)

        # A §2.3 exige confirmação para o que pode machucar. Volume alto entra
        # nessa conta, e não entrava: a máquina de confirmação existe desde a
        # Etapa 4 e nunca tinha sido apontada para cá.
        if plano.novo > self.cfg.midia.limite_confirmacao:
            self._volume_pendente = plano.novo
            pergunta = self._frase("volume_confirmar", novo=plano.novo)
            self._pergunta = pergunta
            diag["pediu_confirmacao"] = True
            return Resposta(pergunta, perguntando=True, diagnostico=diag)

        r = sistema.aplicar_volume(plano.novo)
        return Resposta(
            r.mensagem,
            acao=f"midia:volume:{plano.novo}" if r.ok else None,
            diagnostico=diag,
        )

    def _confirmar_volume(self, texto: str) -> Resposta:
        novo = self._volume_pendente
        self._volume_pendente = None
        resposta = self.cerebro.confirmar(texto, self._pergunta)
        diag = {"origem": "confirmação de volume", "dito": texto,
                "confirmacao": resposta.name, "para": novo}

        if resposta is Confirmacao.NAO:
            return Resposta(self.cfg.persona.volume_cancelado, diagnostico=diag)

        if resposta is not Confirmacao.SIM:
            # Mesma lição da Etapa 4 e da 5: descartar é certo, calado não é.
            nova = self.processar(texto)
            diag["descartado"] = novo
            aviso = self.cfg.persona.volume_descartado
            return Resposta(
                f"{aviso} {nova.texto}".strip(),
                acao=nova.acao,
                perguntando=nova.perguntando,
                diagnostico={**diag, "seguiu_para": nova.diagnostico},
            )

        r = sistema.aplicar_volume(novo)
        diag["detalhe"] = r.detalhe
        return Resposta(
            r.mensagem, acao=f"midia:volume:{novo}" if r.ok else None,
            diagnostico=diag,
        )

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
            self._pergunta = f"Você quis dizer {a.nome} ou {b.nome}?"
        else:
            self._pergunta = f"Você quis dizer {casamento.atalho.nome}?"
        return Resposta(self._pergunta, perguntando=True, diagnostico=diag)

    def _responder_confirmacao(self, texto: str) -> Resposta:
        pendente = self._pendente
        self._pendente = None
        assert pendente is not None

        resposta = self.cerebro.confirmar(texto, self._pergunta)
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
            if interpretacao.funcao is not None:
                # QUALQUER função conta, não só o `abrir`.
                #
                # A versão anterior testava `interpretacao.nome is not None`,
                # que só o `abrir` preenche — ela foi escrita na Etapa 2, quando
                # `abrir` era a única função que existia. As dez acrescentadas
                # depois eram invisíveis para ela, e a busca virou buraco
                # negro: "aumenta o volume" e "move X pra Y" eram reconhecidos
                # pelo modelo e ainda assim tratados como pista.
                diag["saida"] = f"comando novo: {interpretacao.funcao}"
                self._soltar_busca()
                return self._despachar(interpretacao, filtro)

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
            self._soltar_busca()
            return Resposta(
                self._frase("busca_nada", termo=self._termo),
                diagnostico=self._diag,
            )

        if len(achados) == 1:
            achado = achados[0]
            if self._busca_para in ("mover", "copiar"):
                # Mesma razão de não agir com um candidato só: o Léo nunca ouviu
                # a lista, e mover é destrutivo do ponto de vista dele — depois
                # ele não sabe onde procurar.
                acao, pasta = self._busca_para, self._destino_pendente
                self._soltar_busca()
                return self._com_movimento(achado.caminho, pasta, acao)
            if self._busca_para == "renomear":
                # Um candidato só é exatamente onde a §2.3 corria risco: abrir
                # direto está certo para abrir, e seria fatal aqui. O Léo nunca
                # ouviu a lista — não sabe que havia um só nem qual era. Então
                # a busca não age: entrega para quem confirma.
                novo = self._nome_novo_pendente or ""
                self._soltar_busca()
                return self._com_arquivo(achado.caminho, novo)
            self._busca = None
            resultado = acoes.abrir_caminho(achado.caminho, self.comandos)
            return Resposta(
                resultado.mensagem,
                acao=f"abrir:busca:{achado.caminho}" if resultado.ok else None,
                diagnostico=self._diag,
            )

        self._busca = achados
        pastas = pastas_que_distinguem(achados)

        # A pasta não distingue: eles estão no mesmo lugar e diferem pelo NOME.
        # Perguntar "em qual pasta?" aqui é uma pergunta sem resposta possível.
        if not pastas:
            nomes = ", ".join(mod_arquivos.falar_nome(a.caminho) for a in achados[:3])
            return Resposta(
                self._frase("busca_mesmo_lugar", n=len(achados), nomes=nomes),
                perguntando=True,
                diagnostico=self._diag,
            )

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

    def carregar(self) -> float:
        """Põe o LLM na VRAM agora, esperando. Devolve quantos segundos levou.

        O cliente chama na subida, ANTES de dizer que está pronto.
        """
        return self.cerebro.carregar()

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
        self._esperando_musica = None
        self._evento_pendente = None
        self._esperando_quando = None
        self._esperando_hora = None
        self._pergunta = ""
        self._soltar_busca()
        self._esperando_qual_arquivo = None
        self._esperando_nome_novo = None
        self._renomeacao_pendente = None
        self._volume_pendente = None
        self._movimento_pendente = None
        self._esperando_destino = None
        self._esperando_qual_destino = None
        # O desfazer morre junto, e isto é o desenho — não mais uma limitação
        # à espera de histórico em disco. A Etapa 5.5 mediu a alternativa e o
        # Léo decidiu contra: pilha com alcance de horas obriga a desfazer
        # vinte acertos para alcançar um erro. O desfazer é da conversa.
        self._ultima_acao = None
        self._termo = ""
        self._diag = {}

    @property
    def descricao(self) -> str:
        return f"{self.cfg.llm.modelo} · {len(self.tabela)} atalhos"
