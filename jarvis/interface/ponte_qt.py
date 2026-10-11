"""A ponte vista pelo Qt: evento do socket vira sinal.

Uma thread só conversa com o socket; ela emite os sinais, e o Qt entrega na
thread da interface (conexão automática = enfileirada quando as threads são
diferentes). O QML só enxerga sinais e um método para mandar texto.

A reconexão mora aqui, e não na janela: o Léo testou abrir a interface ANTES
do assistente existir, e é assim que ele vai usar — abrir a janela sem se
importar se o Jarvis já está rodando.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from jarvis.ponte.cliente import Cliente

ESPERA_ENTRE_TENTATIVAS_S = 1.0
# Quantas falas anteriores a janela pede ao conectar. O assistente guarda até
# 200 e devolve o que tiver — este número é o que a conversa mostra ao abrir,
# inclusive quando a janela foi fechada e reaberta no meio do dia.
PEDIR_HISTORICO = 80


class PonteQt(QObject):
    estadoMudou = Signal(str)
    nivelMudou = Signal(float)
    voceDisse = Signal(str, str)           # texto, origem
    jarvisDisse = Signal(str, str, bool)   # texto, ação, perguntando
    conexaoMudou = Signal(bool)
    sessaoRecebida = Signal(str, str)      # nome do Jarvis, caminho do log
    historicoRecebido = Signal(list)       # a conversa que já existia
    avisoMudou = Signal(str, float)        # "ok"|"limite"|"offline", volta_em (época, 0 = não sei)

    def __init__(self, caminho: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._caminho = Path(caminho)
        self._cliente: Cliente | None = None
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._laco, name="ponte", daemon=True)

    def iniciar(self) -> None:
        self._thread.start()

    def encerrar(self) -> None:
        self._parar.set()
        cliente = self._cliente
        if cliente is not None:
            cliente.fechar()

    @Slot(str, result=bool)
    def enviarTexto(self, texto: str) -> bool:
        """Chamado pelo QML. Devolve False quando não há ninguém do outro lado."""
        cliente = self._cliente
        if cliente is None or not texto.strip():
            return False
        try:
            cliente.enviar_texto(texto)
        except OSError:
            return False
        return True

    # ----------------------------------------------------------------------

    def _laco(self) -> None:
        while not self._parar.is_set():
            cliente = Cliente(self._caminho, quem="interface")
            try:
                cliente.conectar(historico=PEDIR_HISTORICO)
            except OSError:
                time.sleep(ESPERA_ENTRE_TENTATIVAS_S)
                continue
            self._cliente = cliente
            self.conexaoMudou.emit(True)
            try:
                for evento in cliente.eventos():
                    self._tratar(evento)
                    if self._parar.is_set():
                        break
            except (OSError, ValueError):
                pass
            self._cliente = None
            self.conexaoMudou.emit(False)
            cliente.fechar()

    def _tratar(self, ev: dict) -> None:
        tipo = ev.get("ev")
        if tipo == "estado":
            self.estadoMudou.emit(str(ev.get("estado", "")))
        elif tipo == "nivel":
            self.nivelMudou.emit(float(ev.get("v", 0.0)))
        elif tipo == "voce_disse":
            self.voceDisse.emit(str(ev.get("texto", "")), str(ev.get("origem", "")))
        elif tipo == "jarvis_disse":
            self.jarvisDisse.emit(str(ev.get("texto", "")), str(ev.get("acao") or ""),
                                  bool(ev.get("perguntando")))
        elif tipo == "aviso":
            self.avisoMudou.emit(str(ev.get("tipo") or "ok"), float(ev.get("volta_em") or 0))
        elif tipo == "historico":
            self.historicoRecebido.emit(list(ev.get("falas") or []))
        elif tipo == "sessao":
            self.sessaoRecebida.emit(str(ev.get("nome", "")), str(ev.get("log", "")))
