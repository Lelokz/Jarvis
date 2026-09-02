"""VAD Silero: transforma o fluxo do microfone em segmentos de fala.

ESCOPO §2.6, regra inviolável: *"O STT nunca roda sem VAD na frente. O Whisper
alucina texto em trechos de silêncio e ruído — num assistente sempre ligado,
isso vira comando fantasma."*

Só o que sai daqui chega ao stt.py. Segmentos curtos demais (estalo, tosse,
porta batendo) morrem antes de virar transcrição.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto

import numpy as np
from pysilero_vad import SileroVoiceActivityDetector

from .config import Vad as ConfigVad

# int16 -> float32 em [-1, 1], que é o que o Whisper espera.
_ESCALA_INT16 = 32768.0


class _Estado(Enum):
    SILENCIO = auto()
    FALANDO = auto()


class MotivoDoFim(Enum):
    SILENCIO = "silêncio"
    DURACAO_MAXIMA = "duração máxima"


@dataclass(frozen=True)
class Segmento:
    """Um trecho de fala aprovado pelo VAD."""

    audio: np.ndarray  # float32 [-1, 1], pronto para o Whisper
    pcm: bytes  # int16 cru, para gravar o .wav de auditoria
    taxa: int
    duracao_total_s: float  # inclui o pré-roll
    duracao_fala_s: float  # só o trecho com fala detectada
    espera_silencio_s: float  # do fim da fala até o VAD fechar o segmento
    fechado_em: float  # time.monotonic() — aqui começa o relógio da latência
    motivo: MotivoDoFim


class DetectorDeFala:
    def __init__(self, cfg: ConfigVad, taxa: int) -> None:
        self.cfg = cfg
        self.taxa = taxa
        self._vad = SileroVoiceActivityDetector()

        # O tamanho do bloco vem do próprio detector em vez de ser chumbado:
        # é ele quem manda, e o microfone se alinha a este número.
        self.amostras_por_bloco: int = self._vad.chunk_samples()
        self.bytes_por_bloco: int = self._vad.chunk_bytes()
        self.duracao_bloco_s: float = self.amostras_por_bloco / taxa

        # Pré-roll: o VAD só reage depois que a fala já começou. Sem guardar o
        # áudio anterior, a primeira sílaba some e o Whisper recebe "estando o
        # jarvis" no lugar de "testando o jarvis".
        blocos_pre_roll = max(
            1, round(cfg.pre_roll_ms / 1000 / self.duracao_bloco_s)
        )
        self._pre_roll: deque[bytes] = deque(maxlen=blocos_pre_roll)

        self._blocos_para_fechar = max(
            1, round(cfg.silencio_final_ms / 1000 / self.duracao_bloco_s)
        )
        self._max_blocos = max(
            1, round(cfg.fala_maxima_s / self.duracao_bloco_s)
        )

        self._estado = _Estado.SILENCIO
        self._blocos_de_fala = 0  # candidatos consecutivos, ainda em SILENCIO
        self._acumulado: list[bytes] = []
        self._silencio_seguido = 0
        self._blocos_com_fala = 0
        self._t_inicio = 0.0
        self._t_ultima_fala = 0.0

        self.descartados_curtos = 0

    # ----------------------------------------------------------------------

    def processar(self, bloco: bytes) -> Segmento | None:
        """Consome um bloco do microfone. Devolve o segmento quando fecha um."""
        if len(bloco) != self.bytes_por_bloco:
            raise ValueError(
                f"bloco de {len(bloco)} bytes; o Silero exige "
                f"{self.bytes_por_bloco}"
            )

        tem_fala = self._vad(bloco) >= self.cfg.limiar
        agora = time.monotonic()

        if self._estado is _Estado.SILENCIO:
            self._pre_roll.append(bloco)
            if tem_fala:
                self._blocos_de_fala += 1
                if self._blocos_de_fala >= self.cfg.blocos_para_iniciar:
                    self._abrir(agora)
            else:
                self._blocos_de_fala = 0
            return None

        # FALANDO
        self._acumulado.append(bloco)
        if tem_fala:
            self._silencio_seguido = 0
            self._blocos_com_fala += 1
            self._t_ultima_fala = agora
        else:
            self._silencio_seguido += 1

        if self._silencio_seguido >= self._blocos_para_fechar:
            return self._fechar(agora, MotivoDoFim.SILENCIO)
        if len(self._acumulado) >= self._max_blocos:
            return self._fechar(agora, MotivoDoFim.DURACAO_MAXIMA)
        return None

    # ----------------------------------------------------------------------

    def _abrir(self, agora: float) -> None:
        self._estado = _Estado.FALANDO
        # O pré-roll já contém os blocos que dispararam o gatilho.
        self._acumulado = list(self._pre_roll)
        self._pre_roll.clear()
        self._blocos_de_fala = 0
        self._silencio_seguido = 0
        self._blocos_com_fala = self.cfg.blocos_para_iniciar
        self._t_inicio = agora
        self._t_ultima_fala = agora

    def _fechar(self, agora: float, motivo: MotivoDoFim) -> Segmento | None:
        pcm = b"".join(self._acumulado)
        blocos_com_fala = self._blocos_com_fala
        t_ultima_fala = self._t_ultima_fala

        self._estado = _Estado.SILENCIO
        self._acumulado = []
        self._pre_roll.clear()
        self._silencio_seguido = 0
        self._blocos_com_fala = 0
        self._blocos_de_fala = 0
        # O Silero é uma LSTM: zerar o estado evita que o segmento anterior
        # influencie o próximo.
        if hasattr(self._vad, "reset"):
            self._vad.reset()

        duracao_fala_s = blocos_com_fala * self.duracao_bloco_s
        if duracao_fala_s * 1000 < self.cfg.fala_minima_ms:
            # Ruído curto. Morre aqui — não vira transcrição, não vira comando.
            self.descartados_curtos += 1
            return None

        audio = (
            np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
            / _ESCALA_INT16
        )
        return Segmento(
            audio=audio,
            pcm=pcm,
            taxa=self.taxa,
            duracao_total_s=len(audio) / self.taxa,
            duracao_fala_s=duracao_fala_s,
            espera_silencio_s=max(0.0, agora - t_ultima_fala),
            fechado_em=agora,
            motivo=motivo,
        )
