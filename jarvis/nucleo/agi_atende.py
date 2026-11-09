#!/usr/bin/env python3
"""AGI do Asterisk: atende, ouve, anota e te manda o recado (feito pelo Léo,
09/11/2026; ajustado para o Jarvis de verdade).

AINDA NÃO LIGADO: precisa do Asterisk instalado e de uma linha SIP. O som vai
e volta pelo próprio canal da ligação (RECORD FILE / STREAM FILE do AGI),
nunca pelo microfone e pela caixa do PC: quem ligou não ouviria nada.

No extensions.conf:  exten => s,1,AGI(/home/lelokz/Projetos/Jarvis/jarvis/nucleo/agi_atende.py)
"""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis import config, tts  # noqa: E402
from jarvis.grupo.audios import decodificar  # noqa: E402
from jarvis.nucleo import whatsapp_arquivo  # noqa: E402
from jarvis.stt import Transcritor  # noqa: E402

PASTA = Path(tempfile.gettempdir())


def _agi_inicio() -> None:
    # O Asterisk manda as variáveis "agi_*" e uma linha vazia antes de tudo.
    while sys.stdin.readline().strip():
        pass


def cmd(texto: str) -> str:
    print(texto, flush=True)
    return sys.stdin.readline().strip()


def falar(voz: tts.Voz, texto: str) -> None:
    """A voz do Jarvis num wav de 8 kHz que o Asterisk toca na ligação."""
    pcm = bytearray()
    taxa = canais = 0
    with tts.TRAVA_DAS_VOZES:
        for trecho in voz.sintetizar(texto):
            pcm += trecho.pcm
            taxa, canais = trecho.taxa, trecho.canais
    if not pcm:
        return
    base = PASTA / f"jarvis-agi-{time.time_ns()}"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "s16le", "-ar", str(taxa),
                    "-ac", str(canais), "-i", "-", "-ac", "1", "-ar", "8000", f"{base}.wav"],
                   input=bytes(pcm), check=True)
    cmd(f'STREAM FILE {base} ""')
    Path(f"{base}.wav").unlink(missing_ok=True)


def ouvir(segundos: int = 9) -> Path:
    base = PASTA / f"jarvis-agi-{time.time_ns()}"
    # Grava até o silêncio de 2 s ou o tempo acabar; "#" encerra.
    cmd(f'RECORD FILE {base} wav "#" {segundos * 1000} BEEP s=2')
    return Path(f"{base}.wav")


def main() -> None:
    _agi_inicio()
    cfg = config.carregar()
    voz = tts.criar_voz(cfg.tts, cfg.dir_vozes)
    ouvido = Transcritor(cfg.stt)
    cmd("ANSWER")
    falar(voz, "Alô, é o Jarvis, do Léo. Pode falar.")
    gravado = ouvir(9)
    try:
        texto = ouvido.transcrever_mensagem(decodificar(str(gravado))).strip() or "(sem fala)"
    finally:
        gravado.unlink(missing_ok=True)
    whatsapp_arquivo.guardar({"id": f"recado-{time.time()}", "chat": "recado", "autor": "desconhecido",
                              "ts": time.time(), "texto": texto, "tipo": "recado"})
    falar(voz, "Anotado. Ele vai receber.")
    cmd("HANGUP")


if __name__ == "__main__":
    main()
