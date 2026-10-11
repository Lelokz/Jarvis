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


@dataclass(eq=False)
class _Cliente:
    sock: socket.socket
    fd: int
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
        # Quem responde o pedido "memoria" (o assistente põe aqui). Só lê.
        self.provedor_memoria = None
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
        self._pedidos: queue.SimpleQueue[str] = queue.SimpleQueue()

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
        elif tipo in ("voce_disse", "jarvis_disse"):
            # Guardado ANTES de qualquer saída antecipada: o histórico existe
            # justamente para o tempo em que não havia ninguém conectado.
            self._guardar_fala(evento)
        if not self._clientes:
            return
        dados = protocolo.codificar(evento)
        with self._trava:
            for cliente in self._clientes.values():
                if cliente.apresentado:
                    self._enfileirar(cliente, tipo, dados)
        self._acordar()

    def _guardar_fala(self, evento: dict[str, Any]) -> None:
        fala = {
            "quem": "voce" if evento["ev"] == "voce_disse" else "jarvis",
            "texto": evento.get("texto", ""),
            "quando": round(time.time(), 3),
        }
        if evento["ev"] == "voce_disse":
            fala["origem"] = evento.get("origem", "")
        else:
            fala["acao"] = evento.get("acao")
            fala["perguntando"] = bool(evento.get("perguntando"))
        self._falas.append(fala)

    def proximo_texto(self) -> str | None:
        try:
            return self._pedidos.get_nowait()
        except queue.Empty:
            return None

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
            self._direto(cliente, self._sessao)
            if self._ultimo_estado is not None:
                self._direto(cliente, self._ultimo_estado)
            if self._ultimo_aviso is not None:
                self._direto(cliente, self._ultimo_aviso)
            quantas = dados.get("historico", 0)
            if quantas:
                # Devolve o que TEM, e não o que foi pedido: o anel pode ter
                # menos, e prometer o número do pedido seria mentira.
                falas = list(self._falas)[-quantas:]
                self._direto(cliente, {"ev": "historico", "falas": falas})
        elif tipo == "falar":
            self._pedidos.put(dados["texto"])
        elif tipo == "memoria":
            try:
                conteudo = self.provedor_memoria() if self.provedor_memoria else {}
            except Exception as e:  # um arquivo torto não derruba a ponte
                conteudo = {"fatos": [], "conversas": [], "erro": str(e)}
            self._direto(cliente, {"ev": "memoria", **conteudo})

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
