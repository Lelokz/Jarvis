#!/usr/bin/env python3
"""AGI do Asterisk: atende, ouve, anota, e te manda o recado."""
import sys, tempfile, wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis.nucleo import ouvido, whatsapp_arquivo  # noqa: E402


def cmd(texto: str):
    print(texto, flush=True)
    print(flush=True)
    sys.stdin.readline()


def ler(segundos: int = 8) -> np.ndarray:
    import sounddevice as sd
    pcm = sd.rec(int(16_000 * segundos), samplerate=16_000, channels=1, dtype="float32")
    sd.wait()
    return pcm[:, 0]


def falar(texto: str):
    from jarvis.nucleo import tts
    tts.falar(texto)  # ajuste para a assinatura real do seu tts


def main():
    cmd("ANSWER")
    falar("Alô, é o Jarvis, do Léo. Pode falar.")
    pcm = ler(9)
    texto = ouvido._transcrever(pcm)
    whatsapp_arquivo.guardar({"id": f"recado-{__import__('time').time()}", "chat": "recado",
                              "autor": "desconhecido", "texto": texto, "tipo": "recado"})
    falar("Anotado. Ele vai receber.")
    cmd("HANGUP")


if __name__ == "__main__":
    main()