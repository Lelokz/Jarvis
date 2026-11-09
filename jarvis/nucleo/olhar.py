"""O Jarvis olha a tela (09/11/2026, pedido do Léo): "o que tá escrito aqui?",
"traduz isso", "que erro é esse?".

Print da tela INTEIRA (todos os monitores), nunca de um pedaço em volta do
mouse: nos jogos o mouse fica preso no meio da tela (decisão do Léo). O
Claude do Jarvis olha a imagem, responde em português e apaga a print. Só
quando o Léo pede; nunca sozinho, nunca guardada.

    python -m jarvis.nucleo.olhar          -> tira a print, escreve o caminho
    python -m jarvis.nucleo.olhar apagar   -> apaga as prints
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from jarvis.nucleo import tela

# Temporário no HD (o SSD vive cheio); sem o HD, o temporário de sempre.
_HD = Path("/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644/Arquivo/tmp-render")
PREFIXO = "jarvis-olhar-"


class SemPrint(Exception):
    pass


def _pasta() -> Path:
    if _HD.is_dir():
        return _HD
    return Path(os.environ.get("TMPDIR", "/tmp"))


def apagar() -> int:
    n = 0
    for p in _pasta().glob(PREFIXO + "*.png"):
        try:
            p.unlink()
            n += 1
        except OSError:
            pass
    return n


def _tamanho(display: str) -> tuple[int, int]:
    """A tela inteira: o X junta todos os monitores numa tela só."""
    from Xlib import display as xdisplay
    d = xdisplay.Display(display)
    try:
        s = d.screen()
        return s.width_in_pixels, s.height_in_pixels
    finally:
        d.close()


def capturar() -> Path:
    if tela.bloqueada():
        raise SemPrint("a tela está bloqueada")
    display = os.environ.get("DISPLAY") or ":0"
    try:
        largura, altura = _tamanho(display)
    except Exception as e:  # noqa: BLE001 - sem X não tem o que olhar
        raise SemPrint(f"não achei a tela ({e})") from None
    apagar()  # nunca acumula print velha
    caminho = _pasta() / f"{PREFIXO}{time.strftime('%Y%m%d-%H%M%S')}.png"
    try:
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "x11grab",
             "-video_size", f"{largura}x{altura}", "-i", f"{display}+0,0",
             "-frames:v", "1", str(caminho)],
            capture_output=True, timeout=20, check=True)
    except (subprocess.SubprocessError, OSError) as e:
        caminho.unlink(missing_ok=True)
        raise SemPrint(f"o ffmpeg não tirou a print ({e})") from None
    if not caminho.exists() or caminho.stat().st_size == 0:
        raise SemPrint("a print saiu vazia")
    return caminho


def main(a: list[str]) -> int:
    if a and a[0] == "apagar":
        print(f"apaguei {apagar()} print(s)")
        return 0
    try:
        print(capturar())
        return 0
    except SemPrint as e:
        print(f"sem print: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
