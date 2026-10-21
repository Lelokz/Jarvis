"""Quem está falando: o Léo ou outra pessoa? (out/2026)

A impressão de voz (ECAPA, do SpeechBrain) comparada com o perfil do Léo, feito
com 21 min de áudios dele no WhatsApp (medicoes/voz-do-leo.md). Roda sem o
PyTorch: o espectrograma é numpy (a janela e o banco de filtros tirados do
próprio SpeechBrain) e o ECAPA é ONNX. Tudo isso mora fora do git, em
~/.local/share/jarvis/voz-leo/ (é a voz dele).

A nota é o cosseno com o perfil: o Léo fica em 0,5–0,65; a mais alta de outra
pessoa medida foi 0,27. Fala curta demais não dá para saber.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

PASTA = Path.home() / ".local/share/jarvis/voz-leo"
TAXA = 16000


@dataclass(frozen=True)
class Voz:
    quem: str        # "leo", "outra" ou "curta"
    nota: float      # o cosseno com o perfil (0 se curta)
    segundos: float


class QuemFala:
    # minimo_s: abaixo disso a nota não vale (21/10/2026: o "pode" do Léo,
    # 1,2 s, deu 0,33 e a trava barrou ele mesmo; na medição, 1,5 s já errava
    # 8-15%). A fala curta herda a voz do pedido (assistente.py).
    def __init__(self, limiar: float = 0.35, minimo_s: float = 2.0, pasta: Path = PASTA) -> None:
        import onnxruntime as ort

        self.limiar = limiar
        self.minimo_s = minimo_s
        f = np.load(pasta / "fbank.npz")
        self._janela, self._banco = f["janela"], f["banco"]
        # No processador: é uma conta por frase (~50 ms), e a placa de vídeo
        # já está com o Whisper e a voz.
        self._sessao = ort.InferenceSession(str(pasta / "ecapa.onnx"),
                                            providers=["CPUExecutionProvider"])
        perfil = pasta / "perfil.npy"
        self.perfil = np.load(perfil) if perfil.exists() else None

    def fbank(self, audio: np.ndarray) -> np.ndarray:
        """O Fbank do SpeechBrain: STFT centrada (zeros), Hamming 400, passo
        160, potência, 80 mels, 10·log10 e corte 80 dB abaixo do máximo."""
        x = np.pad(audio.astype(np.float32), (200, 200))
        n = 1 + (len(x) - 400) // 160
        idx = np.arange(400)[None, :] + 160 * np.arange(n)[:, None]
        pot = np.abs(np.fft.rfft(x[idx] * self._janela, n=400)) ** 2
        db = 10 * np.log10(np.maximum(pot @ self._banco, 1e-10))
        return np.maximum(db, db.max() - 80).astype(np.float32)

    def impressao(self, audio: np.ndarray) -> np.ndarray:
        e = self._sessao.run(None, {"fbank": self.fbank(audio)[None]})[0][0]
        return e / np.linalg.norm(e)

    def quem(self, audio: np.ndarray) -> Voz:
        """`audio`: float32 16 kHz, de -1 a 1."""
        segundos = len(audio) / TAXA
        if self.perfil is None or segundos < self.minimo_s:
            return Voz("curta", 0.0, segundos)
        nota = float(self.impressao(audio) @ self.perfil)
        return Voz("leo" if nota >= self.limiar else "outra", nota, segundos)
