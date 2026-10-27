"""O átomo em ícone: a bandeja, a janela na barra de tarefas e o atalho do menu.

O desenho é o do icone_atomo.py (o átomo feito para ser lido pequeno), na cor
do estado. Desconectado, ele fica apagado.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtQuick import QQuickImageProvider

from jarvis.interface import icone_atomo


def desenhar(cor: QColor, lado: int = 64, aceso: bool = True) -> QPixmap:
    img = icone_atomo.desenhar(lado, cor)
    if not aceso:
        apagado = QImage(lado, lado, QImage.Format_ARGB32_Premultiplied)
        apagado.fill(Qt.transparent)
        p = QPainter(apagado)
        p.setOpacity(0.5)
        p.drawImage(0, 0, img)
        p.end()
        img = apagado
    return QPixmap.fromImage(img)


def icone(cor: QColor, aceso: bool = True) -> QIcon:
    """Vários tamanhos num ícone só: o painel e a barra de tarefas escolhem."""
    resultado = QIcon()
    for lado in (16, 22, 24, 32, 48, 64, 128, 256):
        resultado.addPixmap(desenhar(cor, lado, aceso))
    return resultado


class ProvedorDoAtomo(QQuickImageProvider):
    """O átomo parado do QML: `image://atomo/<cor>`, no tamanho pedido (sourceSize)."""

    def __init__(self):
        super().__init__(QQuickImageProvider.Image)

    def requestImage(self, id_, tamanho, pedido):
        lado = max(pedido.width(), pedido.height(), 16)
        img = icone_atomo.desenhar(lado, QColor("#" + id_.split("/")[0]))
        tamanho.setWidth(lado)
        tamanho.setHeight(lado)
        return img
