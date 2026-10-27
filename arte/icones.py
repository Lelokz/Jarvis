"""Os PNGs do átomo (o desenho dos ícones, jarvis/interface/icone_atomo.py).

    .venv/bin/python arte/icones.py           # o logo e o ícone da aba do site
    .venv/bin/python arte/icones.py --menu    # e o ícone do menu deste PC

O app e o relógio têm o deles: celular/gerar_icone.py.
"""

import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from jarvis.interface import icone_atomo  # noqa: E402

AZUL, ROSA = "#4da3ff", "#ff6fb5"


def main() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    img = RAIZ / "site/img"
    # O logo aparece com 26 a 30 px: em 64, ele fica nítido também nas telas de 2x.
    icone_atomo.desenhar(64, AZUL).save(str(img / "logo-azul.png"))
    icone_atomo.desenhar(64, ROSA).save(str(img / "logo-rosa.png"))
    icone_atomo.desenhar(32, AZUL).save(str(img / "favicon.png"))
    print("ok:", img)
    if "--menu" in sys.argv:
        temas = Path.home() / ".local/share/icons/hicolor"
        for lado in (16, 22, 24, 32, 48, 64, 128, 256):
            pasta = temas / f"{lado}x{lado}/apps"
            pasta.mkdir(parents=True, exist_ok=True)
            icone_atomo.desenhar(lado, AZUL).save(str(pasta / "jarvis-atomo.png"))
        subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(temas)], capture_output=True)
        print("ok:", temas)


if __name__ == "__main__":
    main()
