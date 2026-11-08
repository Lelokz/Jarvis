"""A janela do Monitor do Sistema (PySide6 + QML, no estilo da NOVA)."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal
from PySide6.QtGui import QFontDatabase, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
import shiboken6

from jarvis.interface import atomo_icone
from jarvis.interface.instancia import Instancia
from jarvis.monitor.leitura import LIMITES, Monitor

AQUI = Path(__file__).resolve().parent
FONTES = AQUI.parent / "interface" / "fontes"


class Dados(QObject):
    """Lê o PC a cada segundo numa thread (o nvidia-smi demora um pouco) e avisa o QML."""
    mudou = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._dados: dict = {}
        self._monitor = Monitor()
        threading.Thread(target=self._ler_sempre, daemon=True).start()

    def _ler_sempre(self) -> None:
        while True:
            time.sleep(1)
            self._dados = self._monitor.ler()
            self.mudou.emit()

    def _get(self) -> dict:
        return self._dados

    dados = Property("QVariantMap", _get, notify=mudou)


def abrir(retrato: str | None = None) -> int:
    """`retrato`: tira uma foto da janela depois de 3 s e sai (para conferir sem tela)."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Monitor do Sistema")
    app.setDesktopFileName("monitor-do-sistema")
    app.setWindowIcon(QIcon.fromTheme("jarvis-atomo"))

    instancia = Instancia(nome="jarvis-monitor")
    if retrato is None and not instancia.tomar():
        return 0   # já estava aberta: ela vem para a frente

    for fonte in FONTES.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fonte))

    dados = Dados()
    engine = QQmlApplicationEngine()
    engine.addImageProvider("atomo", atomo_icone.ProvedorDoAtomo())
    engine.rootContext().setContextProperty("monitor", dados)
    engine.rootContext().setContextProperty("limites", {k: list(v) for k, v in LIMITES.items()})
    engine.load(QUrl.fromLocalFile(str(AQUI / "Monitor.qml")))
    if not engine.rootObjects():
        return 1
    raiz = engine.rootObjects()[0]
    janela = shiboken6.wrapInstance(shiboken6.getCppPointer(raiz)[0], QQuickWindow)

    def mostrar() -> None:
        janela.show()
        janela.raise_()
        janela.requestActivate()

    instancia.mostrarPedido.connect(mostrar)
    if retrato:
        from PySide6.QtCore import QTimer

        def foto() -> None:
            try:
                janela.grabWindow().save(retrato)
            finally:
                app.quit()
        QTimer.singleShot(3000, foto)
    codigo = app.exec()
    instancia.soltar()
    return codigo
