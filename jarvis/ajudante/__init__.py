"""O Modo Ajudante da NOVA (12/11/2026): ela vê a tela e mexe com o cursor DELA.

Os olhos escolhidos pelo Léo (teste às cegas, "Jeito 2"): uma foto da tela e
VÁRIAS ações por olhada. As mãos são o cursor.py (a janela transparente onde
a setinha dela anda e clica), que sobe sozinho na primeira vez.
"""
from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from jarvis.ajudante.cursor import SOCKET

LARGURA_FOTO = 1280          # a foto que o cérebro vê (a tela de verdade é maior)
RAIZ = Path(__file__).resolve().parents[2]


def _conversar(pedido: dict, espera: float = 20.0) -> dict:
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(espera)
        s.connect(str(SOCKET))
        s.sendall((json.dumps(pedido) + "\n").encode())
        return json.loads(s.makefile("rb").readline() or b"{}")


def no_ar() -> bool:
    try:
        return _conversar({"ping": True}, 2).get("ok") is True
    except OSError:
        return False


def garantir() -> None:
    """Sobe o cursor se ele não estiver no ar (processo separado, fica até a NOVA desligar)."""
    if no_ar():
        return
    log = open(RAIZ / "logs" / "cursor-ajudante.log", "ab")
    subprocess.Popen([sys.executable, "-m", "jarvis.ajudante.cursor"], cwd=str(RAIZ), stdout=log, stderr=log,
                     start_new_session=True)
    fim = time.monotonic() + 15
    while time.monotonic() < fim:
        if no_ar():
            return
        time.sleep(0.3)
    raise RuntimeError("o cursor da NOVA não subiu (logs/cursor-ajudante.log)")


def pedir(pedido: dict) -> dict:
    garantir()
    return _conversar(pedido)


def foto() -> tuple[bytes, float]:
    """A tela agora, em JPEG com LARGURA_FOTO de largura. Devolve (jpeg, escala), onde
    escala converte o ponto da foto pro ponto da tela de verdade."""
    from PySide6.QtCore import QBuffer, QIODevice, Qt
    from PySide6.QtGui import QImage
    from Xlib import X, display
    d = display.Display()
    raiz = d.screen().root
    g = raiz.get_geometry()
    bruto = raiz.get_image(0, 0, g.width, g.height, X.ZPixmap, 0xffffffff)
    img = QImage(bruto.data, g.width, g.height, QImage.Format_RGB32)
    escala = g.width / LARGURA_FOTO
    menor = img.scaled(LARGURA_FOTO, round(g.height / escala), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    buf = QBuffer(); buf.open(QIODevice.WriteOnly)
    menor.save(buf, "JPEG", 80)
    d.close()
    return bytes(buf.data()), escala


def fazer(acoes: list[dict], escala: float) -> list[str]:
    """Várias ações seguidas, com as coordenadas da FOTO. Devolve um resumo do que fez."""
    feito = []
    for a in acoes:
        if "clicar" in a or "clicar_duplo" in a or "clicar_direito" in a or "apontar" in a:
            chave = next(k for k in ("clicar", "clicar_duplo", "clicar_direito", "apontar") if k in a)
            x, y = (round(v * escala) for v in a[chave])
            if chave == "apontar":
                r = pedir({"apontar": [x, y]})
            else:
                r = pedir({"clicar": [x, y], "duplo": chave == "clicar_duplo", "botao": 3 if chave == "clicar_direito" else 1})
        elif "digitar" in a:
            r = pedir({"digitar": str(a["digitar"])})
        elif "tecla" in a:
            r = pedir({"tecla": str(a["tecla"])})
        elif "rolar" in a:
            r = pedir({"rolar": int(a["rolar"])})
        elif "esperar" in a:
            time.sleep(min(3.0, float(a["esperar"])))
            r = {"ok": True}
        else:
            r = {"ok": False, "erro": f"ação desconhecida: {a}"}
        feito.append(f"{json.dumps(a, ensure_ascii=False)} -> {'ok' if r.get('ok') else r.get('erro')}")
        if not r.get("ok"):
            break
        time.sleep(0.25)
    return feito


def cor(hexa: str) -> None:
    pedir({"cor": hexa})
