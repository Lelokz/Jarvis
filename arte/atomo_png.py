"""Fotos paradas do átomo da NOVA, em PNG transparente.

Abre site/prototipo-atomo-foto.html (o átomo 3D de verdade, o site/atomo3d.js)
num navegador sem tela, tira a foto em fundo preto e transforma o preto em
transparência: o átomo é só luz somada, então a transparência de cada pixel é
o canal mais forte dele, e a cor é a do pixel dividida por ela.

    .venv/bin/python arte/atomo_png.py SAIDA.png --cor 4da3ff --lado 512 [--t 5] [--traco 2]

Precisa do Playwright com o chromium (o mesmo das fotos do site).
"""

from __future__ import annotations

import argparse
import functools
import http.server
import threading
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright
from PySide6.QtGui import QImage

SITE = Path(__file__).resolve().parent.parent / "site"
# O 3D sem placa de vídeo (o navegador de foto não tem tela).
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]


def servir() -> http.server.HTTPServer:
    """A pasta do site num servidor local: o navegador não abre módulo JS por file://."""
    class Quieto(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quieto, directory=str(SITE)))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def foto(cor: str, lado: int, t: float, traco: float = 1) -> np.ndarray:
    srv = servir()
    exe = sorted(Path.home().glob(".cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell"))
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=str(exe[-1]) if exe else None, args=ARGS)
        pg = b.new_page(viewport={"width": lado, "height": lado})
        pg.goto(f"http://127.0.0.1:{srv.server_port}/prototipo-atomo-foto.html?cor={cor}&lado={lado}&t={t}&traco={traco}")
        pg.wait_for_selector("body[data-pronto]", state="attached", timeout=60000)
        png = pg.locator("canvas").screenshot()
        b.close()
    srv.shutdown()
    img = QImage.fromData(png).convertToFormat(QImage.Format_RGB888)
    return np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine())[:, : img.width() * 3].reshape(img.height(), img.width(), 3).astype(np.float32)


def transparente(rgb: np.ndarray) -> np.ndarray:
    # O brilho do bloom chega até a borda da foto: sem apagar em roda, a
    # imagem vira um quadrado claro em cima do fundo.
    h, w = rgb.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    r = np.hypot(x - (w - 1) / 2, y - (h - 1) / 2) / (min(w, h) / 2)
    k = np.clip((r - .74) / .26, 0, 1)
    rgb = rgb * (1 - k * k * (3 - 2 * k))[..., None]
    alfa = rgb.max(axis=2)
    cor = np.where(alfa[..., None] > 0, rgb * 255 / np.maximum(alfa, 1)[..., None], 0)
    return np.dstack([cor, alfa]).clip(0, 255).astype(np.uint8)


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("saida")
    a.add_argument("--cor", default="4da3ff")
    a.add_argument("--lado", type=int, default=512)
    a.add_argument("--t", type=float, default=5)
    a.add_argument("--traco", type=float, default=1, help="engrossa o traço (2 nos ícones pequenos)")
    o = a.parse_args()
    rgba = np.ascontiguousarray(transparente(foto(o.cor, o.lado, o.t, o.traco)))
    h, w = rgba.shape[:2]
    QImage(rgba.data, w, h, w * 4, QImage.Format_RGBA8888).save(o.saida)
    print(o.saida)


if __name__ == "__main__":
    main()
