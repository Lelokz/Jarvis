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

from PySide6.QtCore import QObject, QUrl, Signal, Slot

from jarvis.ponte import recebidos
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
    memoriaRecebida = Signal(list, list)   # fatos, conversas (mais nova primeiro)
    avisoMudou = Signal(str, float)        # "ok"|"limite"|"offline", volta_em (época, 0 = não sei)
    mostrar = Signal(str, str)             # título, texto em markdown (vai para a janela)
    atividade = Signal(str)                # o que o Claude está fazendo agora
    anexoFalhou = Signal(str)              # não deu para copiar/mandar o anexo

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

    @Slot(str, list, result=bool)
    def enviarComAnexos(self, texto: str, arquivos: list) -> bool:
        """O texto com os anexos do clipe (ou arrastados para a janela). Os
        arquivos são copiados para a pasta de recebidos (a única de onde a ponte
        aceita anexo) numa thread, para um vídeo grande não travar a janela."""
        cliente = self._cliente
        if cliente is None:
            return False
        caminhos = [Path(QUrl(str(a)).toLocalFile() or str(a)) for a in arquivos]

        def copiar_e_mandar() -> None:
            try:
                copiados = [str(recebidos.copiar(c)) for c in caminhos if c.is_file()]
                cliente.enviar_texto(texto.strip() or "Olha isso.", copiados)
            except OSError as e:
                self.anexoFalhou.emit(f"não consegui mandar o anexo ({e.strerror or e})")

        threading.Thread(target=copiar_e_mandar, name="anexos", daemon=True).start()
        return True

    @Slot(result=bool)
    def pedirMemoria(self) -> bool:
        cliente = self._cliente
        if cliente is None:
            return False
        try:
            cliente.pedir_memoria()
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
        elif tipo == "memoria":
            self.memoriaRecebida.emit(list(ev.get("fatos") or []),
                                      list(ev.get("conversas") or []))
        elif tipo == "aviso":
            self.avisoMudou.emit(str(ev.get("situacao") or "ok"), float(ev.get("volta_em") or 0))
        elif tipo == "mostrar":
            self.mostrar.emit(str(ev.get("titulo") or ""), str(ev.get("texto") or ""))
        elif tipo == "atividade":
            self.atividade.emit(str(ev.get("texto") or ""))
        elif tipo == "historico":
            self.historicoRecebido.emit(list(ev.get("falas") or []))
        elif tipo == "sessao":
            self.sessaoRecebida.emit(str(ev.get("nome", "")), str(ev.get("log", "")))
