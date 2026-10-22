"""O átomo em ícone: a bandeja, a janela na barra de tarefas e o atalho do menu.

O mesmo desenho do `AtomoFixo.qml` (o avatar das respostas): três anéis com o
raio e a inclinação da esfera, e o núcleo. Pedido do Léo (22/10/2026): o
ícone antigo era uma elipse e uma bolinha; agora é igual ao da conversa, na
cor do estado.

**Os anéis são inclinados, e isso não é enfeite.** Um anel horizontal com um
círculo dentro vira um OLHO, símbolo de vigilância (aprendido no 1º ícone).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QRadialGradient

# (raio x, raio y, inclinação) em fração do lado — os do AtomoFixo.qml.
ANEIS = ((0.46, 0.15, 0), (0.39, 0.22, 62), (0.32, 0.12, 121))


def desenhar(cor: QColor, lado: int = 64, aceso: bool = True) -> QPixmap:
    pix = QPixmap(lado, lado)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(lado / 2, lado / 2)
    forca = 1.0 if aceso else 0.5

    # O brilho do núcleo.
    brilho = QRadialGradient(QPointF(0, 0), lado * 0.30)
    brilho.setColorAt(0.0, QColor(cor.red(), cor.green(), cor.blue(), int(150 * forca)))
    brilho.setColorAt(1.0, QColor(cor.red(), cor.green(), cor.blue(), 0))
    p.setPen(Qt.NoPen)
    p.setBrush(brilho)
    p.drawEllipse(QPointF(0, 0), lado * 0.30, lado * 0.30)

    # Os anéis. Ícone pequeno pede traço mais grosso, senão some no painel.
    caneta = QPen(QColor(cor.red(), cor.green(), cor.blue(), int(255 * forca)))
    caneta.setWidthF(max(1.2, lado * 0.055))
    p.setPen(caneta)
    p.setBrush(Qt.NoBrush)
    for rx, ry, angulo in ANEIS:
        p.save()
        p.rotate(angulo)
        p.drawEllipse(QPointF(0, 0), lado * rx, lado * ry)
        p.restore()

    # O núcleo.
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(cor.red(), cor.green(), cor.blue(), int(255 * forca)))
    p.drawEllipse(QPointF(0, 0), lado * 0.11, lado * 0.11)
    p.end()
    return pix


def icone(cor: QColor, aceso: bool = True) -> QIcon:
    """Vários tamanhos num ícone só: o painel e a barra de tarefas escolhem."""
    resultado = QIcon()
    for lado in (16, 22, 24, 32, 48, 64, 128, 256):
        resultado.addPixmap(desenhar(cor, lado, aceso))
    return resultado
