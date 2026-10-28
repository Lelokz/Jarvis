"""A janela do instalador da NOVA (as 8 telas do protótipo aprovado em 26/10/2026,
mais as Conexões). Roda pelo `instalar-nova.sh`, com o Python e o PySide6 que o
`uv` traz, antes de a NOVA existir no PC.

    uv run --python 3.12 --with pyside6-essentials python -m nova_instalador
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QFontDatabase, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from nova_instalador import checar

AQUI = Path(__file__).resolve().parent
# O código da NOVA veio junto (o zip do GitHub): o tema, as fontes e o átomo da janela.
NOVA = AQUI.parent.parent
INTERFACE = NOVA / "jarvis" / "interface"


class Instalador(QObject):
    """O que a janela pede ao Python: conferir o PC, o espaço livre, as escolhas."""

    checou = Signal("QVariant")

    def __init__(self) -> None:
        super().__init__()
        self._escolhas: dict = {}

    @Slot()
    def checar(self) -> None:
        # Em outra thread: o "internet" pode levar uns segundos.
        threading.Thread(target=lambda: self.checou.emit(checar.tudo()), daemon=True).start()

    @Slot(str, result=int)
    def discoLivre(self, pasta: str) -> int:
        return checar.disco(pasta)["livre_gb"]

    @Slot(str, result=str)
    def caminhoDe(self, url: str) -> str:
        """A pasta que o seletor devolve (file:///...) como caminho."""
        return QUrl(url).toLocalFile() or url

    @Slot("QVariant")
    def guardarEscolhas(self, escolhas) -> None:
        self._escolhas = dict(escolhas.toVariant() if hasattr(escolhas, "toVariant") else escolhas)

    def _pasta_padrao(self) -> str:
        return str(Path.home() / "NOVA")

    pastaPadrao = Property(str, _pasta_padrao, constant=True)

    def _nome_padrao(self) -> str:
        # O primeiro nome da conta do sistema, só como sugestão.
        try:
            import pwd
            nome = pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0].split()[0]
        except (ImportError, KeyError, IndexError):
            nome = os.environ.get("USER", "") or os.environ.get("USERNAME", "")
        return nome[:30].capitalize()

    nomePadrao = Property(str, _nome_padrao, constant=True)


def main() -> int:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Instalador da NOVA")
    app.setDesktopFileName("nova-instalador")
    app.setWindowIcon(QIcon(str(INTERFACE / "icone.png")))
    for fonte in (INTERFACE / "fontes").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fonte))
    instalador = Instalador()
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(INTERFACE / "qml"))
    engine.rootContext().setContextProperty("instalador", instalador)
    engine.rootContext().setContextProperty("pastaQmlDaNova", QUrl.fromLocalFile(str(INTERFACE / "qml") + "/"))
    engine.load(QUrl.fromLocalFile(str(AQUI / "qml" / "Instalador.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
