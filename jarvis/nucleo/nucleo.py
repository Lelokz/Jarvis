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
        # (onde está agora, onde estava antes) — para o "desfaz".
        self._ultima_renomeacao: tuple[Path, Path] | None = None
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

        if self._renomeacao_pendente is not None:
            return self._confirmar_renomeacao(texto)

        if self._esperando_qual_arquivo is not None:
            novo, self._esperando_qual_arquivo = self._esperando_qual_arquivo, None
            return self._escolher_arquivo(texto, novo, {"origem": "qual arquivo"})

        if self._esperando_nome_novo is not None:
            caminho, self._esperando_nome_novo = self._esperando_nome_novo, None
            return self._com_arquivo(caminho, texto)

        interpretacao = self.cerebro.interpretar(texto)
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
            return self._midia(interpretacao.argumentos, base)

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

    def _soltar_busca(self) -> None:
        """Esquece a busca E o que ela ia fazer com o resultado.

        Os dois juntos, sempre: uma busca que morre deixando o propósito para
        trás faria a próxima busca — de abrir — cair no caminho de renomear.
        """
        self._busca = None
        self._busca_para = None
        self._nome_novo_pendente = None

    def _pode_mexer(self, caminho: Path) -> bool:
        return mod_arquivos.pode_mexer(caminho, self.cfg.arquivos.onde_pode_mexer)

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

    def _escolher_arquivo(self, alvo: str, nome_novo: str, diag: dict) -> Resposta:
        """Acha o arquivo e entrega para a confirmação. Nunca age."""
        self._termo = alvo
        achados = self.buscador.buscar(alvo)
        podem = [
            a for a in achados if not a.e_pasta and self._pode_mexer(a.caminho)
        ]
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
            return Resposta(
                self.cfg.persona.arquivo_fora_da_lista, diagnostico=diag
            )

        self._busca_para = "renomear"
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
            caminho, nome_novo, self.cfg.arquivos.onde_pode_mexer
        )
        diag["resultado"] = r.detalhe
        if r.ok and r.detalhe:
            # Guarda invertido: de onde ele está AGORA para onde estava antes.
            self._ultima_renomeacao = (
                Path(r.detalhe["para"]),
                Path(r.detalhe["de"]),
            )
        return Resposta(
            r.mensagem,
            acao=f"renomear:{caminho}" if r.ok else None,
            diagnostico=diag,
        )

    def _desfazer(self, diag: dict) -> Resposta:
        if self._ultima_renomeacao is None:
            return Resposta(self.cfg.persona.nada_para_desfazer, diagnostico=diag)

        de, para = self._ultima_renomeacao
        self._ultima_renomeacao = None
        r = mod_arquivos.reverter(de, para, self.cfg.arquivos.onde_pode_mexer)
        diag["resultado"] = r.detalhe
        if not r.ok:
            # Falhou: devolve o desfazer para a mesa. Alguém pode ter ocupado
            # o nome antigo, e a saída é liberar o nome e mandar desfazer de
            # novo — não perder a única chance.
            self._ultima_renomeacao = (de, para)
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
            nome, pai, self.cfg.arquivos.onde_pode_mexer
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
        return Resposta(
            r.mensagem,
            acao=f"tocar:{onde}:{video.id}" if r.ok else None,
            diagnostico=diag,
        )

    def _midia(self, argumentos: dict, diag: dict) -> Resposta:
        acao = (argumentos.get("acao") or "").strip().lower()
        if acao == "volume":
            r = sistema.ajustar_volume(
                argumentos.get("valor"), self.cfg.midia.passo_volume
            )
        else:
            r = midia.controlar(acao)
        diag["detalhe"] = r.detalhe
        return Resposta(
            r.mensagem, acao=f"midia:{acao}" if r.ok else None, diagnostico=diag
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
            if interpretacao.nome is not None:
                diag["saida"] = "comando novo"
                self._soltar_busca()
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
            self._soltar_busca()
            return Resposta(
                self._frase("busca_nada", termo=self._termo),
                diagnostico=self._diag,
            )

        if len(achados) == 1:
            achado = achados[0]
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
        self._esperando_musica = None
        self._evento_pendente = None
        self._esperando_quando = None
        self._esperando_hora = None
        self._pergunta = ""
        self._soltar_busca()
        self._esperando_qual_arquivo = None
        self._esperando_nome_novo = None
        self._renomeacao_pendente = None
        # O desfazer morre junto, e isso é limitação conhecida: renomear, sair
        # por 40 segundos e voltar com "desfaz" não funciona. Um histórico em
        # disco é o que a Etapa 5.5 e a lixeira vão querer.
        self._ultima_renomeacao = None
        self._termo = ""
        self._diag = {}

    @property
    def descricao(self) -> str:
        return f"{self.cfg.llm.modelo} · {len(self.tabela)} atalhos"
