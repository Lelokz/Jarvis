"""Baixa mídia de qualquer lugar e rasga paywall."""
import subprocess
from pathlib import Path

import trafilatura
import urllib.request

DESTINO = Path.home() / "Vídeos/Jarvis"


def baixar(url: str, audio: bool = False) -> str:
    DESTINO.mkdir(parents=True, exist_ok=True)
    cmd = ["yt-dlp", "-P", str(DESTINO), "-o", "%(title)s.%(ext)s",
           "-f", "bestaudio/best" if audio else "bv*+ba/b"]
    if audio:
        cmd += ["-x", "--audio-format", "mp3"]
    r = subprocess.run(cmd + [url], capture_output=True, text=True, timeout=1800)
    return (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else ""


def sem_paywall(url: str) -> str:
    try:
        req = urllib.request.Request(f"https://archive.ph/newest/{url}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        html = urllib.request.urlopen(urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8", "ignore")
    return trafilatura.extract(html) or ""