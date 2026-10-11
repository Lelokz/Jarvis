"""Uma interface só, e a segunda tentativa faz a primeira aparecer.

Fechar a janela para a bandeja torna fácil esquecer que ela está aberta e
mandar abrir de novo. Sem isto, o segundo `interface.py` sobe uma segunda
janela, com um segundo ícone no painel e duas conversas em paralelo.

O cadeado é um socket no `$XDG_RUNTIME_DIR`, do lado do socket da ponte: quem
consegue escutar é a primeira; quem não consegue avisa a que está lá e sai.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def caminho_do_cadeado() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(base) / "jarvis-interface.sock"


class Instancia(QObject):
    mostrarPedido = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._nome = str(caminho_do_cadeado())
        self._servidor: QLocalServer | None = None

    def tomar(self) -> bool:
        """True = sou a primeira. False = já havia outra, e ela foi avisada."""
        sonda = QLocalSocket()
        sonda.connectToServer(self._nome)
        if sonda.waitForConnected(300):
            sonda.write(b"mostrar\n")
            sonda.flush()
            sonda.waitForBytesWritten(300)
            sonda.disconnectFromServer()
            return False

        # Ninguém atendeu: ou não havia interface, ou ela morreu sem limpar o
        # arquivo. É o mesmo caso do socket que sobra de um Jarvis morto.
        QLocalServer.removeServer(self._nome)
        self._servidor = QLocalServer(self)
        self._servidor.newConnection.connect(self._chegou)
        self._servidor.listen(self._nome)
        return True

    def soltar(self) -> None:
        if self._servidor is not None:
            self._servidor.close()
            QLocalServer.removeServer(self._nome)

    def _chegou(self) -> None:
        conexao = self._servidor.nextPendingConnection()
        if conexao is None:
            return
        conexao.readyRead.connect(lambda: self._ler(conexao))

    def _ler(self, conexao) -> None:
        conexao.readAll()
        conexao.disconnectFromServer()
        self.mostrarPedido.emit()
