"""O ícone da bandeja: o Jarvis no painel, com a janela aberta ou fechada.

**O ícone pertence ao PROCESSO da interface, não à janela.** Enquanto
`interface.py` estiver rodando, ele está no painel: fechar a janela no X a
esconde e o ícone continua lá, que é por onde ela volta. O ícone só some quando
a interface encerra — pelo menu, ou se o processo morrer.

**"Fechar a interface" encerra só este processo.** O assistente por voz continua
rodando, que é o ponto inteiro dos dois processos. O rótulo não diz "Sair do
Jarvis" porque isso mentiria sobre o alcance — e derrubar o assistente daqui não
existe: seria ação destrutiva pela §2.3 e um clique errado num menu aberto todo
dia não pode matar o Jarvis inteiro em silêncio.

**A cor vem da janela**, e não de uma paleta copiada para cá: quem manda na cor
de cada estado é o `Tema.qml`. Duas paletas divergiriam no dia em que alguém
mexesse numa só, e o ícone passaria a mentir sobre o estado.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

# Só o texto da dica de ferramenta. O vocabulário de estados é do protocolo.
_DICAS = {
    "dormindo": "dormindo",
    "ouvindo": "ouvindo",
    "escutando": "escutando você",
    "pensando": "pensando",
    "falando": "falando",
}


def _desenhar(cor: QColor, aceso: bool) -> QIcon:
    """O mesmo átomo da esfera, em 64 pixels: uma órbita inclinada e um núcleo.

    **O aro é inclinado, e isso não é enfeite.** Na primeira versão ele era
    horizontal, e um anel horizontal com um círculo dentro vira um OLHO —
    símbolo de vigilância, o oposto do que este ícone deve dizer. Inclinado,
    lê-se como órbita, que é o que a esfera da janela mostra.
    """
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    caneta = p.pen()
    caneta.setColor(QColor(cor.red(), cor.green(), cor.blue(), 230 if aceso else 120))
    caneta.setWidth(5)
    p.setPen(caneta)
    p.setBrush(Qt.NoBrush)
    p.translate(32, 32)
    p.rotate(-30)
    p.drawEllipse(-28, -13, 56, 26)       # a órbita
    p.resetTransform()

    p.setPen(Qt.NoPen)
    p.setBrush(QColor(cor.red(), cor.green(), cor.blue(), 255 if aceso else 140))
    p.drawEllipse(22, 22, 20, 20)         # o núcleo
    p.end()
    return QIcon(pix)


class Bandeja(QObject):
    mostrarPedido = Signal()
    alternarPedido = Signal()
    encerrarPedido = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._icone = QSystemTrayIcon(self)

        menu = QMenu()
        mostrar = QAction("Mostrar janela", menu)
        mostrar.triggered.connect(self.mostrarPedido.emit)
        fechar = QAction("Fechar a interface", menu)
        fechar.triggered.connect(self.encerrarPedido.emit)
        menu.addAction(mostrar)
        menu.addSeparator()
        menu.addAction(fechar)
        # O menu tem que viver enquanto o ícone viver: solto, some no primeiro
        # passeio do coletor de lixo e o botão direito para de abrir.
        self._menu = menu
        self._icone.setContextMenu(menu)

        self._icone.activated.connect(self._acionado)
        self.definir(QColor("#3c4a63"), "dormindo", False)
        self._icone.show()

    @staticmethod
    def disponivel() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    @Slot(QColor, str, bool)
    def definir(self, cor: QColor, estado: str, conectado: bool) -> None:
        """Cor e dica seguem o estado — dá para saber o que ele está fazendo
        sem abrir a janela."""
        self._icone.setIcon(_desenhar(cor, conectado))
        if conectado:
            self._icone.setToolTip(f"Jarvis — {_DICAS.get(estado, estado)}")
        else:
            self._icone.setToolTip("Jarvis — sem conexão com o assistente")

    def esconder(self) -> None:
        self._icone.hide()

    def _acionado(self, motivo) -> None:
        # Clique esquerdo alterna mostrar e esconder; o resto é do menu.
        if motivo == QSystemTrayIcon.Trigger:
            self.alternarPedido.emit()
