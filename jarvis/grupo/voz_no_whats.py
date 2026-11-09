"""A resposta em áudio nos grupos (09/11/2026, pedido do Léo: "se alguém
mandar áudio, eles respondem por áudio também").

A mesma voz do PC (a do Jarvis e a da Friday) gera o som, que vira um .ogg
(Opus, como o do celular) e vai pela ponte como mensagem de voz. Uma fala
por vez: a trava das vozes é a mesma do Locutor do PC.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from jarvis import tts

# Temporário no HD (o SSD vive cheio); sem o HD, o temporário de sempre.
_HD = Path("/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644/Arquivo/tmp-render")

_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


def para_falar(texto: str) -> str:
    """O que não se fala: *negrito*, _itálico_, emoji, link."""
    t = re.sub(r"https?://\S+", "", texto)
    t = _EMOJI.sub("", t)
    t = re.sub(r"[*_~`#]", "", t)
    return " ".join(t.split())


def gravar(voz: tts.Voz, texto: str) -> Path | None:
    """Fala o texto num .ogg (Opus mono, 48 kHz). Devolve o caminho; quem
    usa apaga depois de mandar. None se não saiu som."""
    texto = para_falar(texto)
    if not texto:
        return None
    pcm = bytearray()
    taxa = canais = 0
    with tts.TRAVA_DAS_VOZES:
        for trecho in voz.sintetizar(texto):
            pcm += trecho.pcm
            taxa, canais = trecho.taxa, trecho.canais
    if not pcm:
        return None
    pasta = _HD if _HD.is_dir() else None
    fd, nome = tempfile.mkstemp(prefix="jarvis-voz-", suffix=".ogg", dir=pasta)
    Path(nome).unlink(missing_ok=True)
    try:
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "s16le", "-ar", str(taxa), "-ac", str(canais),
             "-i", "-", "-ac", "1", "-ar", "48000", "-c:a", "libopus", "-b:a", "32k",
             "-application", "voip", nome],
            input=bytes(pcm), capture_output=True, timeout=120, check=True)
    except (subprocess.SubprocessError, OSError):
        Path(nome).unlink(missing_ok=True)
        return None
    finally:
        import os
        os.close(fd)
    return Path(nome)
