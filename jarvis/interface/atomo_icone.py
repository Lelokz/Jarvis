"""O átomo em ícone: a bandeja, a janela na barra de tarefas e o atalho do menu.

O átomo definitivo (27/10/2026, o mesmo do site e da janela), na cor do estado.
A foto dele vem pronta e em branco (`atomo-icone.png`, feita pelo
arte/atomo_png.py com o traço grosso dos ícones); aqui ela é só pintada: a
transparência fica, e a cor vai da cor do estado (onde a luz é fraca) ao
branco (onde ela é forte: as bolinhas e a borda do núcleo), como no 3D.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap

FOTO = Path(__file__).with_name("atomo-icone.png")
_foto: QImage | None = None


def desenhar(cor: QColor, lado: int = 64, aceso: bool = True) -> QPixmap:
    global _foto
    if _foto is None:
        _foto = QImage(str(FOTO)).convertToFormat(QImage.Format_RGBA8888)
    img = _foto.scaled(lado, lado, Qt.KeepAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    px = np.frombuffer(img.constBits(), np.uint8).reshape(h, img.bytesPerLine())[:, : w * 4].reshape(h, w, 4).astype(np.float32)
    alfa = px[..., 3:] / 255
    branco = np.clip((alfa - 0.85) / 0.15, 0, 1) ** 2 * 0.45
    rgb = np.array([cor.red(), cor.green(), cor.blue()], np.float32) * (1 - branco) + 255 * branco
    saida = np.dstack([rgb, px[..., 3:] * (1.35 if aceso else 0.6)]).clip(0, 255).astype(np.uint8)
    saida = np.ascontiguousarray(saida)
    return QPixmap.fromImage(QImage(saida.data, w, h, w * 4, QImage.Format_RGBA8888).copy())


def icone(cor: QColor, aceso: bool = True) -> QIcon:
    """Vários tamanhos num ícone só: o painel e a barra de tarefas escolhem."""
    resultado = QIcon()
    for lado in (16, 22, 24, 32, 48, 64, 128, 256):
        resultado.addPixmap(desenhar(cor, lado, aceso))
    return resultado
