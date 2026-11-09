"""Baixa mídia de qualquer lugar e rasga paywall (feito pelo Léo, 09/11/2026).

    python -m jarvis.nucleo.raspagem baixar <url> [audio]
    python -m jarvis.nucleo.raspagem ler <url>      -> o texto da matéria

Os downloads vão para o HD (o SSD vive cheio), na pasta "Jarvis - Downloads".
"""
import subprocess
import sys
import urllib.request
from pathlib import Path

import trafilatura

_HD = Path("/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644/Arquivo")
DESTINO = (_HD if _HD.is_dir() else Path.home() / "Vídeos") / "Jarvis - Downloads"
_NAVEGADOR = {"User-Agent": "Mozilla/5.0"}


def baixar(url: str, audio: bool = False) -> str:
    DESTINO.mkdir(parents=True, exist_ok=True)
    # O yt-dlp da venv (o do sistema é velho e o YouTube recusa).
    cmd = [sys.executable, "-m", "yt_dlp", "-P", str(DESTINO), "-o", "%(title)s.%(ext)s",
           "-f", "bestaudio/best" if audio else "bv*+ba/b"]
    if audio:
        cmd += ["-x", "--audio-format", "mp3"]
    r = subprocess.run(cmd + [url], capture_output=True, text=True, timeout=1800)
    saida = (r.stdout or r.stderr).strip()
    return saida.splitlines()[-1] if saida else ""


def _pagina(url: str) -> str:
    req = urllib.request.Request(url, headers=_NAVEGADOR)
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")


def sem_paywall(url: str) -> str:
    """Primeiro a cópia do archive.ph; se não houver (ou vier a página de
    captcha, que não tem texto), o próprio site."""
    for endereco in (f"https://archive.ph/newest/{url}", url):
        try:
            texto = trafilatura.extract(_pagina(endereco)) or ""
        except Exception:
            continue
        # A página de captcha do archive tem umas palavras: matéria de verdade é maior.
        if len(texto.strip()) >= (200 if "archive.ph" in endereco else 1):
            return texto
    return ""


def main(a: list[str]) -> int:
    if len(a) >= 2 and a[0] == "baixar":
        print(baixar(a[1], audio=len(a) > 2 and a[2] == "audio"))
        print(f"pasta: {DESTINO}")
        return 0
    if len(a) == 2 and a[0] == "ler":
        print(sem_paywall(a[1]) or "não consegui o texto dessa página")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
