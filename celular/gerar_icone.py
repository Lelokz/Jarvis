"""Gera os ícones do app e do relógio com o átomo da NOVA (o definitivo, 27/10/2026).

    .venv/bin/python celular/gerar_icone.py

A foto vem do átomo 3D de verdade (arte/atomo_png.py, o mesmo do site):
- app/src/main/res/drawable-nodpi/ic_frente.png: a frente do ícone adaptativo
  (108 dp; o launcher corta em volta do meio, então o átomo fica nos ~61% do
  centro). O fundo continua o ic_fundo.xml (o degradê escuro).
- app/src/main/res/drawable-nodpi/ic_notificacao.png: o ícone pequeno das
  notificações. O Android só usa a transparência dele, então é o átomo em
  branco, com o traço grosso dos ícones.
O relógio usa os recursos do app (relogio/build.gradle.kts), então vale para os dois.
(Os antigos drawable/ic_frente.xml e ic_notificacao.xml saíram: o mesmo nome em
XML e PNG não pode.)
"""

import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "arte"))
import atomo_png  # noqa: E402

RES = Path(__file__).resolve().parent / "app/src/main/res"


def imagem(rgba: np.ndarray) -> QImage:
    rgba = np.ascontiguousarray(rgba)
    h, w = rgba.shape[:2]
    return QImage(rgba.data, w, h, w * 4, QImage.Format_RGBA8888).copy()


def no_meio(img: QImage, lado: int, ocupa: int) -> QImage:
    """A imagem reduzida para `ocupa` px, no meio de um quadrado transparente de `lado`."""
    menor = img.scaled(ocupa, ocupa, Qt.KeepAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGBA8888)
    saida = np.zeros((lado, lado, 4), np.uint8)
    w, h = menor.width(), menor.height()
    px = np.frombuffer(menor.constBits(), np.uint8).reshape(h, menor.bytesPerLine())[:, : w * 4].reshape(h, w, 4)
    x, y = (lado - w) // 2, (lado - h) // 2
    saida[y:y + h, x:x + w] = px
    return imagem(saida)


def main() -> None:
    pasta = RES / "drawable-nodpi"
    pasta.mkdir(exist_ok=True)
    # A frente: 108 dp em xxxhdpi = 432 px; o átomo em ~290 px no meio.
    frente = imagem(atomo_png.transparente(atomo_png.foto("4da3ff", 1024, 5, 1.8, 0.7)))
    no_meio(frente, 432, 290).save(str(pasta / "ic_frente.png"))
    # A notificação: só a transparência conta (o Android pinta).
    rgba = atomo_png.transparente(atomo_png.foto("ffffff", 512, 5, 3, 0.3))
    rgba[..., :3] = 255
    rgba[..., 3] = np.clip(rgba[..., 3].astype(np.float32) * 1.6, 0, 255).astype(np.uint8)
    no_meio(imagem(rgba), 96, 96).save(str(pasta / "ic_notificacao.png"))
    print("ok:", pasta)


if __name__ == "__main__":
    main()
