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


class VozKokoro(Voz):
    """Kokoro-82M pela placa de vídeo (out/2026, escolha do Léo: `pm_alex`).

    Mais natural que o Piper e, na GPU, mais rápido: 0,27 s para 7,4 s de fala
    (no processador eram 4,2 s). Fala frase por frase: a primeira já toca
    enquanto as outras são geradas.

    Precisa do `onnxruntime-gpu` 1.22 (CUDA 12, o mesmo do Whisper; o 1.31
    pede CUDA 13). Sem placa, roda no processador, mais devagar.
    """

    # Volume: o Kokoro sai ~8 dB abaixo do Piper. Sobe até um pouco ABAIXO do
    # que o Léo já ouvia (RMS 0,17 do faber) e nunca passa disso — o volume
    # já machucou o ouvido dele uma vez (HISTORIA, o volume que foi a 100).
    _RMS_ALVO = 0.14

    def __init__(self, cfg: ConfigTts, dir_vozes: Path) -> None:
        self.cfg = cfg
        modelo, vozes = dir_vozes / "kokoro-v1.0.onnx", dir_vozes / "voices-v1.0.bin"
        if not modelo.is_file() or not vozes.is_file():
            raise FileNotFoundError(
                f"Kokoro não encontrado em {dir_vozes}. Baixe kokoro-v1.0.onnx e "
                "voices-v1.0.bin de github.com/thewh1teagle/kokoro-onnx/releases "
                "(model-files-v1.0).")
        import onnxruntime as rt
        from kokoro_onnx import Kokoro

        inicio = time.monotonic()
        try:
            rt.preload_dlls()  # as bibliotecas CUDA dos pacotes nvidia-* do pip
        except Exception:
            pass
        sessao = rt.InferenceSession(
            str(modelo), providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        self.na_placa = "CUDAExecutionProvider" in sessao.get_providers()
        self._k = Kokoro.from_session(sessao, str(vozes))
        # Aquecimento: a primeira geração na placa custa ~0,9 s; as outras, 0,3.
        self._k.create("Oi.", voice=cfg.voz, speed=1.0, lang="pt-br")
        self.segundos_de_carga = time.monotonic() - inicio

    @property
    def nome(self) -> str:
        onde = "placa" if self.na_placa else "processador"
        efeito = f" + efeito {self.cfg.efeito}" if self.cfg.efeito else ""
        return f"kokoro {self.cfg.voz} ({onde}){efeito}"

    def sintetizar(self, texto: str) -> Iterator[Trecho]:
        import re

        import numpy as np

        frases = [f for f in re.split(r"(?<=[.!?…])\s+", texto.strip()) if f.strip()]
        # Tom: para engrossar sem ficar lento, o Kokoro fala mais rápido na
        # mesma proporção e o áudio é "esticado" de volta. Esticar baixa o tom
        # e os formantes juntos — a voz fica mais grave e encorpada, não só
        # mais baixa (pedido do Léo: a versão com efeito ficou "afeminada").
        fator = 2 ** (self.cfg.tom / 12)          # tom -3 → 0,84
        rapidez = min(2.0, (1.0 / max(0.5, self.cfg.velocidade)) / fator)
        for frase in frases:
            audio, taxa = self._k.create(frase, voice=self.cfg.voz, speed=rapidez,
                                         lang="pt-br")
            audio = np.asarray(audio, dtype=np.float32)
            if fator != 1.0:
                novo = int(len(audio) / fator)
                audio = np.interp(np.linspace(0, len(audio) - 1, novo),
                                  np.arange(len(audio)), audio).astype(np.float32)
            if self.cfg.efeito == "jarvis":
                audio = efeito_jarvis(audio, taxa)
            elif self.cfg.efeito == "suave":
                audio = efeito_suave(audio, taxa)
            rms = float(np.sqrt(np.mean(audio ** 2))) or 1.0
            ganho = min(self._RMS_ALVO / rms, 0.95 / max(float(np.max(np.abs(audio))), 1e-6))
            pcm = np.clip(audio * ganho, -1.0, 1.0)
            # Um respiro curto entre frases, como quem fala.
            pcm = np.concatenate([pcm, np.zeros(int(taxa * 0.12), dtype=np.float32)])
            yield Trecho(pcm=(pcm * 32767).astype(np.int16).tobytes(), taxa=taxa, canais=1)


def efeito_jarvis(audio, taxa: int):
    """Voz de "IA no capacete": ecos curtos e próximos (sala metálica pequena)
    e um reforço leve nos graves. Sutil de propósito: tem que continuar
    natural, só com o ar de máquina do filme.

    A primeira versão realçava os agudos e deixou a voz fina demais; agora é o
    contrário: um passa-baixa simples somado ao sinal dá corpo."""
    import numpy as np

    saida = np.concatenate([audio, np.zeros(int(taxa * 0.12), dtype=np.float32)])
    for atraso_ms, ganho in ((11, 0.30), (23, 0.20), (37, 0.12), (53, 0.07)):
        d = int(taxa * atraso_ms / 1000)
        saida[d:d + len(audio)] += ganho * audio
    # Graves: média móvel de ~2 ms (passa-baixa) somada ao sinal.
    janela = max(1, int(taxa * 0.002))
    graves = np.convolve(saida, np.ones(janela, dtype=np.float32) / janela, mode="same")
    return saida + 0.45 * graves


def efeito_suave(audio, taxa: int):
    """Só corpo nos graves, sem os ecos do "jarvis" (out/2026, pedido do Léo:
    "menos robotizada"). Os ecos curtos somados à voz são um filtro pente:
    é deles o som metálico de máquina."""
    import numpy as np

    janela = max(1, int(taxa * 0.002))
    graves = np.convolve(audio, np.ones(janela, dtype=np.float32) / janela, mode="same")
    return audio + 0.30 * graves


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
    if cfg.motor == "kokoro":
        return VozKokoro(cfg, dir_vozes)
    raise ValueError(f'motor de TTS desconhecido: "{cfg.motor}" (existem "piper" e "kokoro")')
