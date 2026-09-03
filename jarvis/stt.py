"""STT com faster-whisper (large-v3-turbo, GPU, int8).

O `cuda_setup.preparar()` roda ANTES do import do faster_whisper — não é
manha de estilo, é ordem obrigatória: o ctranslate2 resolve as libs CUDA no
momento do import.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from . import cuda_setup
from .config import Stt as ConfigStt


class ErroDeCuda(RuntimeError):
    """CUDA indisponível, com instrução de como resolver."""


@dataclass(frozen=True)
class Transcricao:
    texto: str
    segundos: float
    idioma: str
    probabilidade_idioma: float


class Transcritor:
    def __init__(self, cfg: ConfigStt) -> None:
        self.cfg = cfg

        if cfg.dispositivo == "cuda":
            resultado = cuda_setup.preparar()
            if not resultado.ok:
                raise ErroDeCuda(resultado.ajuda())

        # Import depois do preparar(), de propósito.
        from faster_whisper import WhisperModel

        inicio = time.monotonic()
        self._modelo = WhisperModel(
            cfg.modelo,
            device=cfg.dispositivo,
            compute_type=cfg.compute_type,
        )
        self.segundos_de_carga = time.monotonic() - inicio
        self._vocabulario: str | None = None
        self._hotwords: str | None = None

    # ----------------------------------------------------------------------

    def aquecer(self) -> float:
        """Primeira inferência, descartada.

        A primeira chamada paga inicialização de CUDA e alocação de kernels.
        Sem queimar isso na subida, a primeira medição real sai inflada e a
        decisão de aprovar ou reprovar a etapa sai errada.
        """
        silencio = np.zeros(16000, dtype=np.float32)
        inicio = time.monotonic()
        self._rodar(silencio)
        return time.monotonic() - inicio

    def transcrever(self, audio: np.ndarray) -> Transcricao:
        inicio = time.monotonic()
        texto, info = self._rodar(audio)
        return Transcricao(
            texto=texto,
            segundos=time.monotonic() - inicio,
            idioma=getattr(info, "language", self.cfg.idioma) or "",
            probabilidade_idioma=getattr(info, "language_probability", 0.0) or 0.0,
        )

    # ----------------------------------------------------------------------

    def usar_vocabulario(self, nomes: list[str]) -> None:
        """Prepara o `initial_prompt` com os nomes que o Léo costuma falar.

        Fala rápida é onde o Whisper mais depende de contexto para desambiguar,
        e "loft" não é palavra em português — sem contexto ele tende a inventar
        algo que soe parecido. Dar o vocabulário antes ataca exatamente os
        casos que importam.

        Os nomes vêm da tabela de atalhos, não de uma lista chumbada aqui:
        acrescentar um atalho passa a melhorar a transcrição dele de graça.
        """
        nomes = [n for n in nomes if n.strip()]
        if not nomes or not self.cfg.usar_vocabulario:
            self._vocabulario = None
            self._hotwords = None
            return
        # Os dois mecanismos juntos. Medidos separadamente em áudio sintético
        # rápido: nenhum 4/15, initial_prompt 8/15, hotwords 8/15, os dois
        # 9/15. A diferença de 8 para 9 é ruído numa amostra desse tamanho —
        # mas somar não custa latência, então não há motivo para escolher.
        #
        # O initial_prompt funciona como continuação de texto, por isso vai
        # como frase natural em PT-BR e não como lista de palavras soltas.
        self._vocabulario = (
            "Comandos de voz para o computador. "
            f"Nomes usados: {', '.join(nomes)}."
        )
        self._hotwords = ", ".join(nomes)

    @property
    def vocabulario(self) -> str | None:
        return self._vocabulario

    def _rodar(self, audio: np.ndarray):
        segmentos, info = self._modelo.transcribe(
            audio,
            language=self.cfg.idioma,
            beam_size=self.cfg.beam_size,
            initial_prompt=self._vocabulario,
            hotwords=self._hotwords,
            # Nosso VAD já filtrou. Ligar aqui seria pagar duas vezes.
            vad_filter=False,
            # Sem isto o Whisper repete o texto anterior quando fica em
            # dúvida — é a alucinação em laço que o ESCOPO §7 quer evitar.
            condition_on_previous_text=False,
        )
        texto = " ".join(s.text.strip() for s in segmentos).strip()
        return texto, info

    @property
    def descricao(self) -> str:
        return f"{self.cfg.modelo} · {self.cfg.dispositivo} · {self.cfg.compute_type}"
