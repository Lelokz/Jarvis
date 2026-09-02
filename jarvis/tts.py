"""TTS atrás de uma interface.

ESCOPO §4: o Piper é *"peça deliberadamente trocável: manter atrás de uma
interface"*, porque o upgrade previsto é o Kokoro-82M. Trocar de motor deve
ser escrever outra classe `Voz` — sem encostar no etapa0.py.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import sounddevice as sd

from .config import Tts as ConfigTts


@dataclass(frozen=True)
class Trecho:
    pcm: bytes  # int16 cru
    taxa: int
    canais: int


@dataclass(frozen=True)
class TemposDaFala:
    primeiro_audio_s: float  # do pedido até o 1º trecho pronto
    sintese_total_s: float  # só o tempo do motor, sem a reprodução
    reproducao_s: float
    duracao_audio_s: float


class Voz(ABC):
    """Contrato mínimo de um motor de voz.

    Quem implementar deve preencher `segundos_de_carga` no __init__ — é um
    dos custos de partida que a Etapa 0 reporta à parte.
    """

    segundos_de_carga: float = 0.0

    @property
    @abstractmethod
    def nome(self) -> str: ...

    @abstractmethod
    def sintetizar(self, texto: str) -> Iterator[Trecho]: ...


class VozPiper(Voz):
    def __init__(self, cfg: ConfigTts, dir_vozes: Path) -> None:
        self.cfg = cfg
        caminho = dir_vozes / f"{cfg.voz}.onnx"
        if not caminho.is_file():
            raise FileNotFoundError(
                f"Voz não encontrada: {caminho}\n"
                f"  Baixe com:\n"
                f"    python -m piper.download_voices {cfg.voz} "
                f"--data-dir {dir_vozes}"
            )

        from piper import PiperVoice, SynthesisConfig

        inicio = time.monotonic()
        self._voz = PiperVoice.load(str(caminho))
        self.segundos_de_carga = time.monotonic() - inicio
        # length_scale: maior = mais devagar.
        self._sintese = SynthesisConfig(length_scale=cfg.velocidade)

    @property
    def nome(self) -> str:
        return self.cfg.voz

    def sintetizar(self, texto: str) -> Iterator[Trecho]:
        for chunk in self._voz.synthesize(texto, syn_config=self._sintese):
            yield Trecho(
                pcm=chunk.audio_int16_bytes,
                taxa=chunk.sample_rate,
                canais=chunk.sample_channels,
            )


def falar(
    voz: Voz,
    texto: str,
    *,
    dispositivo: int | None = None,
) -> TemposDaFala:
    """Sintetiza e toca, medindo síntese e reprodução separadamente.

    Os trechos vão para a saída conforme saem do motor, em vez de esperar a
    frase inteira ficar pronta — isso derruba o tempo até o primeiro som.
    Para medir honesto apesar disso, cronometramos só as chamadas ao gerador
    (síntese pura); o `write`, que bloqueia enquanto a placa consome, conta
    como reprodução.
    """
    pedido_em = time.monotonic()
    gerador = voz.sintetizar(texto)

    primeiro_audio_s = 0.0
    sintese_total_s = 0.0
    amostras = 0
    taxa = 0
    stream: sd.RawOutputStream | None = None
    inicio_reproducao = 0.0

    try:
        while True:
            marca = time.monotonic()
            try:
                trecho = next(gerador)
            except StopIteration:
                sintese_total_s += time.monotonic() - marca
                break
            sintese_total_s += time.monotonic() - marca

            if stream is None:
                primeiro_audio_s = time.monotonic() - pedido_em
                taxa = trecho.taxa
                stream = sd.RawOutputStream(
                    samplerate=trecho.taxa,
                    channels=trecho.canais,
                    dtype="int16",
                    device=dispositivo,
                )
                stream.start()
                inicio_reproducao = time.monotonic()

            stream.write(trecho.pcm)
            amostras += len(trecho.pcm) // (2 * trecho.canais)

        if stream is None:  # texto vazio ou sem áudio
            return TemposDaFala(0.0, sintese_total_s, 0.0, 0.0)

        # O write só bloqueia até caber no buffer: ao sair do laço ainda há
        # áudio na fila da placa. Esperar o resto evita cortar o fim da frase
        # e, principalmente, evita reabrir o microfone com o Jarvis ainda
        # falando — o que realimentaria o VAD.
        duracao_audio_s = amostras / taxa
        restante = duracao_audio_s - (time.monotonic() - inicio_reproducao)
        if restante > 0:
            time.sleep(restante)

        return TemposDaFala(
            primeiro_audio_s=primeiro_audio_s,
            sintese_total_s=sintese_total_s,
            reproducao_s=time.monotonic() - inicio_reproducao,
            duracao_audio_s=duracao_audio_s,
        )
    finally:
        if stream is not None:
            stream.stop()
            stream.close()


def criar_voz(cfg: ConfigTts, dir_vozes: Path) -> Voz:
    if cfg.motor == "piper":
        return VozPiper(cfg, dir_vozes)
    raise ValueError(
        f'motor de TTS desconhecido: "{cfg.motor}" — na Etapa 0 só existe "piper"'
    )
