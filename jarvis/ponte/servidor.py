"""O servidor da ponte: o lado do assistente.

**A regra que protege o Jarvis do cliente: quem emite nunca espera a rede.** O
`receber()` é chamado na thread de áudio, a cada evento. Ele serializa, põe na
fila de cada cliente e volta — quem fala com o socket é uma thread só dela, com
escrita não bloqueante. Um cliente que parou de ler não segura o laço de áudio:
a fila dele tem teto, o nível do microfone (descartável por natureza) sai
primeiro, e se ainda assim encher, o cliente é desligado.

É a propriedade que o Léo comprou escolhendo dois processos para a interface:
travar do lado de quem mostra não pode levar junto o lado de quem ouve.

**Uma thread só toca no Nucleo, e não é esta.** Texto digitado chega aqui e é
só enfileirado; quem o consome é o laço de áudio, pelo `proximo_texto()`. O
Nucleo guarda estado de conversa — confirmação pendente, busca aberta — e não é
seguro para duas threads.
"""

from __future__ import annotations

import itertools
import json
import os
import queue
import selectors
import socket
import stat
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import protocolo


class ServidorOcupado(RuntimeError):
    """Outro processo já responde neste socket — outro Jarvis ligado."""


_IDS = itertools.count(1)


@dataclass(frozen=True)
class Pedido:
    """O que um cliente pediu para o laço de áudio atender."""
    # "falar" (texto), "ouvir" (arquivo com a fala gravada), ou da janela (v3):
    # "nova", "continuar" (valor = id da conversa), "cerebro" (valor = JSON),
    # "parar" (o botão Parar)
    tipo: str
    valor: str  # o texto, o caminho do arquivo, o id ou o JSON
    cliente: int = 0  # o id de quem pediu
    voz: bool = False  # a resposta sai NELE (o celular), não no PC
    anexos: tuple[str, ...] = ()  # fotos/vídeos/arquivos do celular, já no PC
    mudo: bool = False  # o celular está no mudo: resposta só em texto


@dataclass(eq=False)
class _Cliente:
    sock: socket.socket
    fd: int
    # Número do cliente na sessão (o fd se repete quando um cai e outro entra).
    id: int = field(default_factory=lambda: next(_IDS))
    # Disse "voz": true no "ola": é um corpo (o celular); recebe a voz do que pedir.
    quer_voz: bool = False
    # Disse "janela": true: um corpo que também mostra a janela nova (o app do
    # celular) e quer os eventos dela. Quem não é corpo sempre quer.
    quer_janela: bool = False
    quem: str = ""
    # Quando disse "ola" (time.time()): o pedido de aprovação do grupo só
    # conta como entregue no app se ele já estava conectado antes do pedido.
    desde: float = 0.0
    # Quem não disse "ola" não recebe difusão. É o que garante que tudo o que
    # chega depois do histórico seja novo: sem isso, um evento ao vivo podia
    # escapar pela brecha entre conectar e pedir, e aparecer duas vezes na tela.
    apresentado: bool = False
    # (tipo, bytes) esperando vez. O tipo existe para o descarte saber o que é
    # nível sem precisar decodificar de volta.
    fila: deque = field(default_factory=deque)
    # O que já saiu da fila e ainda não coube no socket. Só a thread da ponte
    # mexe aqui.
    enviando: bytes = b""
    entrada: bytearray = field(default_factory=bytearray)
    condenado: str = ""  # motivo, quando for para desligar
    niveis_descartados: int = 0


class Servidor:
    def __init__(self, caminho: Path, *, fila_max: int, sessao: dict[str, Any]) -> None:
        self.caminho = Path(caminho)
        self.fila_max = max(8, int(fila_max))
        self._sessao = {"ev": "sessao", **sessao}
        self._ultimo_estado: dict[str, Any] | None = None
        self._ultimo_aviso: dict[str, Any] | None = None
        self._ultimo_cerebro: dict[str, Any] | None = None
        self._ultimo_som: dict[str, Any] | None = None
        self._ultimo_ajustes: dict[str, Any] | None = None
        self._ultimo_uso: dict[str, Any] | None = None
        self._conversa_atual: str = ""
        # Quem responde os pedidos "memoria", "conversas" e "abrir" (o
        # assistente põe aqui). Só leem arquivos: rodam na thread da ponte.
        self.provedor_memoria = None
        self.provedor_conversas = None
        self.provedor_conversa = None
        self.provedor_renomear = None
        self.provedor_apagar = None
        self.provedor_fixar = None
        # O histórico da sessão, para um cliente que chega depois — ou que
        # fechou a janela e voltou. Anel de tamanho fixo: o alcance é a sessão,
        # e memória de processo que roda o dia todo não cresce sem teto.
        #
        # Alimentado pelo `receber()`, que já vê tudo. Não lê o .jsonl: seria
        # uma segunda fonte da mesma verdade, e obrigaria a ponte a conhecer o
        # formato do registro.py.
        self._falas: deque[dict[str, Any]] = deque(maxlen=protocolo.MAX_HISTORICO)

        self._clientes: dict[int, _Cliente] = {}
        self._trava = threading.Lock()
        self._pedidos: queue.SimpleQueue[Pedido] = queue.SimpleQueue()
        # O botão Parar vale NA HORA: o laço de áudio pode estar preso falando
        # e só leria a fila depois. Ele confere isto enquanto fala.
        self._botao_parar = threading.Event()

        self._seletor = selectors.DefaultSelector()
        self._escuta: socket.socket | None = None
        # Par de sockets só para acordar a thread da ponte quando chega evento,
        # sem ela precisar ficar girando.
        self._acorda_r, self._acorda_w = socket.socketpair()
        self._acorda_r.setblocking(False)
        self._acorda_w.setblocking(False)

        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._inode: int | None = None
        # Por que cada cliente caiu. Para diagnóstico e para o teste.
        self.desligados: deque[str] = deque(maxlen=50)

    # -- ciclo de vida -----------------------------------------------------

    def iniciar(self) -> None:
        if os.path.lexists(self.caminho):
            if not stat.S_ISSOCK(os.lstat(self.caminho).st_mode):
                raise OSError(f"{self.caminho} existe e não é um socket — não apago")
            if self._alguem_responde():
                raise ServidorOcupado(str(self.caminho))
            # Sobra de um Jarvis que morreu sem limpar (kill -9, queda de luz).
            self.caminho.unlink()

        escuta = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # O socket nasce já fechado para os outros usuários: sem janela entre o
        # bind e o chmod em que alguém de fora poderia conectar.
        mascara = os.umask(0o177)
        try:
            escuta.bind(str(self.caminho))
        finally:
            os.umask(mascara)
        os.chmod(self.caminho, 0o600)
        escuta.listen(8)
        escuta.setblocking(False)

        self._escuta = escuta
        self._inode = os.stat(self.caminho).st_ino
        self._seletor.register(escuta, selectors.EVENT_READ, "escuta")
        self._seletor.register(self._acorda_r, selectors.EVENT_READ, "acorda")
        self._thread = threading.Thread(target=self._laco, name="ponte", daemon=True)
        self._thread.start()

    def _alguem_responde(self) -> bool:
        """Tem um processo escutando neste socket agora?

        Conectar é o único jeito honesto de saber. O arquivo existir não diz
        nada: um Jarvis morto por kill -9 ou por queda de luz deixa o arquivo
        para trás sem ninguém atrás dele.

        Este método faltava na primeira versão e só o teste do socket morto o
        pegou — justamente o caso que acontece na primeira vez que o Jarvis é
        religado depois de um travamento.
        """
        teste = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        teste.settimeout(0.5)
        try:
            teste.connect(str(self.caminho))
            return True
        except (ConnectionRefusedError, FileNotFoundError):
            return False
        except TimeoutError:
            # Escutando, mas com a fila de conexões cheia: vivo e ocupado.
            return True
        finally:
            teste.close()

    def encerrar(self) -> None:
        self._parar.set()
        self._acordar()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        with self._trava:
            clientes = list(self._clientes.values())
        for cliente in clientes:
            self._desligar(cliente, "o assistente encerrou")
        for s in (self._escuta, self._acorda_r, self._acorda_w):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass
        # Só apaga o socket se ainda for O NOSSO. Se outro Jarvis subiu depois
        # e recriou o arquivo, apagar aqui o deixaria inalcançável.
        try:
            if self._inode is not None and os.stat(self.caminho).st_ino == self._inode:
                self.caminho.unlink()
        except FileNotFoundError:
            pass

    @property
    def n_clientes(self) -> int:
        return len(self._clientes)

    def consumir_parar(self) -> bool:
        """Alguém apertou Parar desde a última vez? (e já desmarca)"""
        if self._botao_parar.is_set():
            self._botao_parar.clear()
            return True
        return False

    def app_desde(self) -> float | None:
        """Desde quando o app do celular (corpo com a janela) está conectado,
        sem cair; None se não está. A conexão morta cai sozinha em ~40 s (o
        ping do WebSocket da porta remota)."""
        apps = [c.desde for c in list(self._clientes.values())
                if c.apresentado and c.quer_voz and c.quer_janela]
        return min(apps) if apps else None

    # -- o lado do laço de áudio -------------------------------------------

    def quer(self, tipo: str) -> bool:
        if tipo not in protocolo.PUBLICOS:
            return False
        if tipo == "nivel":
            return bool(self._clientes)
        return True

    def receber(self, evento: dict[str, Any]) -> None:
        """Assinante do Emissor. Roda na thread de áudio e NUNCA bloqueia."""
        tipo = evento.get("ev")
        if tipo not in protocolo.PUBLICOS:
            return
        if tipo == "estado":
            # Guardado mesmo sem cliente: quem conectar depois precisa saber
            # onde o Jarvis está, e não esperar a próxima mudança.
            self._ultimo_estado = evento
        elif tipo == "aviso":
            self._ultimo_aviso = evento
        elif tipo == "cerebro":
            self._ultimo_cerebro = evento
        elif tipo == "som":
            self._ultimo_som = evento
        elif tipo == "ajustes":
            self._ultimo_ajustes = evento
        elif tipo == "uso":
            self._ultimo_uso = evento
        elif tipo == "conversa_atual":
            # Conversa nova ou retomada: o histórico da ponte passa a ser ela.
            # A linha de atividade fica fora, como no histórico ao vivo (o
            # celular a mostraria como cartão).
            self._conversa_atual = str(evento.get("id") or "")
            self._falas.clear()
            for f in evento.get("falas") or []:
                if f.get("quem") in ("voce", "jarvis", "painel"):
                    self._falas.append(f)
        elif tipo in ("voce_disse", "jarvis_disse", "mostrar"):
            # Guardado ANTES de qualquer saída antecipada: o histórico existe
            # justamente para o tempo em que não havia ninguém conectado.
            self._guardar_fala(evento)
        if not self._clientes:
            return
        dados = protocolo.codificar(evento)
        with self._trava:
            for cliente in self._clientes.values():
                # A voz vai só para o corpo que pediu, e só se ele quer voz.
                if tipo == "voz" and (cliente.id != evento.get("para") or not cliente.quer_voz):
                    continue
                # A conversa inteira e o texto em pedaços são para a janela; o
                # corpo (celular) não usa.
                if tipo in ("conversa_atual", "escrevendo") and cliente.quer_voz \
                        and not cliente.quer_janela:
                    continue
                if cliente.apresentado:
                    self._enfileirar(cliente, tipo, dados)
        self._acordar()

    def _guardar_fala(self, evento: dict[str, Any]) -> None:
        quem = {"voce_disse": "voce", "jarvis_disse": "jarvis"}.get(evento["ev"], "painel")
        fala = {
            "quem": quem,
            "texto": evento.get("texto", ""),
            "quando": round(time.time(), 3),
        }
        if quem == "voce":
            fala["origem"] = evento.get("origem", "")
        elif quem == "painel":
            fala["titulo"] = evento.get("titulo", "")
        else:
            fala["acao"] = evento.get("acao")
            fala["perguntando"] = bool(evento.get("perguntando"))
            if evento.get("opcoes"):
                fala["opcoes"] = list(evento["opcoes"])
        self._falas.append(fala)

    def proximo_pedido(self) -> Pedido | None:
        try:
            return self._pedidos.get_nowait()
        except queue.Empty:
            return None

    def proximo_texto(self) -> str | None:
        """Só o texto do próximo pedido (os testes antigos e o eco usam)."""
        pedido = self.proximo_pedido()
        return pedido.valor if pedido is not None and pedido.tipo == "falar" else None

    def avisar(self, cliente_id: int, motivo: str) -> None:
        """Um {"ev":"erro"} só para quem pediu (ex.: "nova" no meio de uma
        tarefa). Chamado da thread de áudio; não bloqueia."""
        for cliente in list(self._clientes.values()):
            if cliente.id == cliente_id and cliente.apresentado:
                self._direto(cliente, {"ev": "erro", "motivo": motivo})
        self._acordar()

    def conectado(self, cliente_id: int) -> bool:
        return any(c.id == cliente_id for c in list(self._clientes.values()))

    # -- fila --------------------------------------------------------------

    def _enfileirar(self, cliente: _Cliente, tipo: str, dados: bytes) -> None:
        """Chamado com a trava. Nunca bloqueia e nunca cresce sem teto."""
        if cliente.condenado:
            return
        if len(cliente.fila) >= self.fila_max:
            antes = len(cliente.fila)
            cliente.fila = deque(x for x in cliente.fila if x[0] != "nivel")
            cliente.niveis_descartados += antes - len(cliente.fila)
        if len(cliente.fila) >= self.fila_max:
            if tipo == "nivel":
                cliente.niveis_descartados += 1
                return
            cliente.condenado = (
                f"não lê: fila cheia ({self.fila_max}) sem nível para descartar"
            )
            return
        cliente.fila.append((tipo, dados))

    def _direto(self, cliente: _Cliente, evento: dict[str, Any]) -> None:
        with self._trava:
            self._enfileirar(cliente, evento["ev"], protocolo.codificar(evento))

    def _acordar(self) -> None:
        try:
            self._acorda_w.send(b"\0")
        except OSError:
            # Buffer cheio: já há um byte esperando, a thread vai acordar.
            pass

    # -- a thread da ponte -------------------------------------------------

    def _laco(self) -> None:
        while not self._parar.is_set():
            for chave, eventos in self._seletor.select(timeout=0.5):
                if chave.data == "escuta":
                    self._aceitar()
                elif chave.data == "acorda":
                    self._drenar_acorda()
                elif eventos & selectors.EVENT_READ:
                    cliente = chave.data
                    if cliente.fd in self._clientes:
                        self._ler(cliente)
            self._escrever_todos()

    def _aceitar(self) -> None:
        while True:
            try:
                sock, _ = self._escuta.accept()
            except (BlockingIOError, OSError):
                return
            sock.setblocking(False)
            cliente = _Cliente(sock=sock, fd=sock.fileno())
            with self._trava:
                self._clientes[cliente.fd] = cliente
            self._seletor.register(sock, selectors.EVENT_READ, cliente)

    def _drenar_acorda(self) -> None:
        try:
            while self._acorda_r.recv(4096):
                pass
        except OSError:
            pass

    def _ler(self, cliente: _Cliente) -> None:
        try:
            dados = cliente.sock.recv(65536)
        except BlockingIOError:
            return
        except OSError as e:
            self._desligar(cliente, f"erro de leitura: {e}")
            return
        if not dados:
            self._desligar(cliente, "o cliente fechou a conexão")
            return
        cliente.entrada += dados
        while (fim := cliente.entrada.find(b"\n")) >= 0:
            linha = bytes(cliente.entrada[:fim])
            del cliente.entrada[: fim + 1]
            self._tratar(cliente, linha)
        if len(cliente.entrada) > protocolo.MAX_LINHA:
            self._desligar(cliente, "linha longa demais sem quebra")

    def _tratar(self, cliente: _Cliente, linha: bytes) -> None:
        if not linha.strip():
            return
        try:
            tipo, dados = protocolo.ler_pedido(linha)
        except protocolo.ErroDeProtocolo as e:
            self._direto(cliente, {"ev": "erro", "motivo": str(e)})
            return
        if tipo == "ola":
            cliente.apresentado = True
            cliente.desde = time.time()
            cliente.quer_voz = dados.get("voz", False)
            cliente.quer_janela = dados.get("janela", False) or not cliente.quer_voz
            cliente.quem = dados.get("quem", "")
            self._direto(cliente, {**self._sessao, "id": cliente.id})
            if self._ultimo_estado is not None:
                self._direto(cliente, self._ultimo_estado)
            if self._ultimo_aviso is not None:
                self._direto(cliente, self._ultimo_aviso)
            if self._ultimo_cerebro is not None:
                self._direto(cliente, self._ultimo_cerebro)
            if self._ultimo_som is not None and cliente.quer_janela:
                self._direto(cliente, self._ultimo_som)
            if self._ultimo_ajustes is not None and cliente.quer_janela:
                self._direto(cliente, self._ultimo_ajustes)
            if self._ultimo_uso is not None and cliente.quer_janela:
                self._direto(cliente, self._ultimo_uso)
            if self._conversa_atual and cliente.quer_janela:
                self._direto(cliente, {"ev": "conversa_atual", "id": self._conversa_atual})
            quantas = dados.get("historico", 0)
            if quantas:
                # Devolve o que TEM, e não o que foi pedido: o anel pode ter
                # menos, e prometer o número do pedido seria mentira.
                falas = list(self._falas)[-quantas:]
                self._direto(cliente, {"ev": "historico", "falas": falas})
        elif tipo == "falar":
            self._pedidos.put(Pedido("falar", dados["texto"], cliente.id, cliente.quer_voz,
                                     tuple(dados["anexos"]), dados["mudo"]))
        elif tipo == "ouvir":
            self._pedidos.put(Pedido("ouvir", dados["arquivo"], cliente.id, cliente.quer_voz,
                                     tuple(dados["anexos"]), dados["mudo"]))
        elif tipo in ("memorias", "ler_memoria", "salvar_memoria"):
            # As Memórias (jarvis/memorias.py): arquivos de texto, respondidos
            # aqui mesmo, sem passar pelo laço de áudio.
            from jarvis import memorias
            try:
                if tipo == "memorias":
                    resposta = {"ev": "memorias", "lista": memorias.listar()}
                elif tipo == "ler_memoria":
                    resposta = {"ev": "memoria_aberta", **memorias.ler(dados["id"])}
                else:
                    resposta = {"ev": "memoria_salva", **memorias.salvar(dados["id"], dados["texto"], dados["versao"])}
            except (OSError, ValueError) as e:
                resposta = {"ev": "erro", "motivo": f"memória: {e}"}
            self._direto(cliente, resposta)
        elif tipo == "memoria":
            try:
                conteudo = self.provedor_memoria() if self.provedor_memoria else {}
            except Exception as e:  # um arquivo torto não derruba a ponte
                conteudo = {"fatos": [], "conversas": [], "erro": str(e)}
            self._direto(cliente, {"ev": "memoria", **conteudo})
        elif tipo == "conversas":
            try:
                lista = self.provedor_conversas() if self.provedor_conversas else []
            except Exception as e:
                self._direto(cliente, {"ev": "erro", "motivo": f"não li as conversas ({e})"})
                return
            self._direto(cliente, {"ev": "conversas", "lista": lista})
        elif tipo == "abrir":
            try:
                falas = self.provedor_conversa(dados["id"]) if self.provedor_conversa else []
            except Exception as e:
                self._direto(cliente, {"ev": "erro", "motivo": f"não abri a conversa ({e})"})
                return
            self._direto(cliente, {"ev": "conversa", "id": dados["id"], "falas": falas})
        elif tipo in ("renomear", "apagar", "fixar"):
            if tipo == "apagar" and dados["id"] == self._conversa_atual:
                self._direto(cliente, {"ev": "erro", "motivo": "Essa é a conversa de agora: "
                                       "começa um chat novo antes de apagar ela."})
                return
            try:
                if tipo == "renomear" and self.provedor_renomear:
                    self.provedor_renomear(dados["id"], dados["titulo"])
                elif tipo == "apagar" and self.provedor_apagar:
                    self.provedor_apagar(dados["id"])
                elif tipo == "fixar" and self.provedor_fixar:
                    self.provedor_fixar(dados["id"], dados["fixar"])
                lista = self.provedor_conversas() if self.provedor_conversas else []
            except Exception as e:
                self._direto(cliente, {"ev": "erro", "motivo": f"não deu ({e})"})
                return
            self._direto(cliente, {"ev": "conversas", "lista": lista})
        elif tipo in ("nova", "continuar", "cerebro", "parar", "som", "ajustes"):
            if tipo == "parar":
                self._botao_parar.set()
            # "som" também vai para a thread de áudio: trocar o microfone é lá.
            valor = dados.get("id", "") if tipo == "continuar" else \
                json.dumps(dados) if tipo in ("cerebro", "som", "ajustes") else ""
            self._pedidos.put(Pedido(tipo, valor, cliente.id, cliente.quer_voz))

    def _escrever_todos(self) -> None:
        with self._trava:
            clientes = list(self._clientes.values())
        for cliente in clientes:
            if cliente.condenado:
                self._desligar(cliente, cliente.condenado)
                continue
            if not cliente.enviando:
                with self._trava:
                    if cliente.fila:
                        cliente.enviando = b"".join(d for _, d in cliente.fila)
                        cliente.fila.clear()
            if cliente.enviando:
                try:
                    enviados = cliente.sock.send(cliente.enviando)
                    cliente.enviando = cliente.enviando[enviados:]
                except BlockingIOError:
                    pass
                except OSError as e:
                    self._desligar(cliente, f"erro de escrita: {e}")
                    continue
            interesse = selectors.EVENT_READ
            if cliente.enviando or cliente.fila:
                interesse |= selectors.EVENT_WRITE
            try:
                self._seletor.modify(cliente.sock, interesse, cliente)
            except (KeyError, ValueError):
                pass

    def _desligar(self, cliente: _Cliente, motivo: str) -> None:
        with self._trava:
            if cliente.fd not in self._clientes:
                return
            # O motivo é anotado ANTES de o cliente sair da contagem. Na ordem
            # inversa, quem visse a contagem cair podia ler a lista de motivos
            # sem o motivo dele — foi o que o teste do cliente que não lê pegou
            # numa rodada em que as threads se cruzaram.
            self.desligados.append(motivo)
            del self._clientes[cliente.fd]
        try:
            self._seletor.unregister(cliente.sock)
        except (KeyError, ValueError):
            pass
        try:
            cliente.sock.close()
        except OSError:
            pass
