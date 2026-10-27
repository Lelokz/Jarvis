"""Gera os ícones do app e do relógio com o átomo da NOVA (o desenho dos ícones).

    .venv/bin/python celular/gerar_icone.py

O desenho é o do jarvis/interface/icone_atomo.py (o mesmo da bandeja do PC):
- app/src/main/res/drawable-nodpi/ic_frente.png: a frente do ícone adaptativo
  (108 dp; o launcher corta em volta do meio, então o átomo fica nos ~60% do
  centro). O fundo continua o ic_fundo.xml (o degradê escuro).
- app/src/main/res/drawable-nodpi/ic_notificacao.png: o ícone pequeno das
  notificações. O Android só usa a transparência dele, então é a silhueta branca.
O relógio usa os recursos do app (relogio/build.gradle.kts), então vale para os dois.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from jarvis.interface import icone_atomo  # noqa: E402

RES = Path(__file__).resolve().parent / "app/src/main/res"


def no_meio(img: QImage, lado: int) -> QImage:
    """A imagem no meio de um quadrado transparente de `lado`."""
    saida = QImage(lado, lado, QImage.Format_ARGB32_Premultiplied)
    saida.fill(Qt.transparent)
    p = QPainter(saida)
    p.drawImage((lado - img.width()) // 2, (lado - img.height()) // 2, img)
    p.end()
    return saida


def main() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    pasta = RES / "drawable-nodpi"
    pasta.mkdir(exist_ok=True)
    # A frente: 108 dp em xxxhdpi = 432 px; o átomo em ~256 px no meio (as bolinhas não encostam no corte redondo).
    no_meio(icone_atomo.desenhar(256, "#4da3ff"), 432).save(str(pasta / "ic_frente.png"))
    # A notificação: só a transparência conta (o Android pinta).
    icone_atomo.desenhar(96, branco=True).save(str(pasta / "ic_notificacao.png"))
    print("ok:", pasta)


if __name__ == "__main__":
    main()
