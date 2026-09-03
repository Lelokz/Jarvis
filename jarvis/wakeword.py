"""Wake word: openWakeWord com o modelo pré-treinado `hey_jarvis`.

A peça foi escolhida e medida na Etapa 0.5 — 20/20 de acerto na pronúncia
inglesa, zero falso positivo em 10 minutos, limiar 0.50 num platô que vai de
0.45 a 0.50. Os parâmetros de carga aqui são os mesmos daquela medição, e é por
isso que o experimento e o assistente importam desta função em vez de cada um
ter a sua cópia: se divergirem, a medição da 0.5 deixa de valer para o que roda
de verdade.

Dois números que não se encaixam e mandam no desenho deste módulo: o
openWakeWord consome **1280 amostras** (80ms) e o Silero VAD consome **512**
(32ms). O microfone roda em 512 — o valor que a Etapa 0 provou sem estouros — e
o `Detector` acumula bytes até fechar frames de 1280. Como 512×5 = 1280×2, a
cada 5 blocos saem exatamente 2 frames: o acumulador nunca cresce.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import WakeWord as ConfigWakeWord

AMOSTRAS_POR_FRAME = 1280
BYTES_POR_FRAME = AMOSTRAS_POR_FRAME * 2  # int16
DURACAO_FRAME_S = AMOSTRAS_POR_FRAME / 16000

# Contexto guardado em volta de um evento, para o .wav servir de auditoria.
PRE_ROLL_S = 2.0
POS_ROLL_S = 1.0


def carregar_modelo(caminho_modelo: Path, dir_modelos: Path):
    """Instancia o openWakeWord forçando ONNX.

    `inference_framework="onnx"` não é preferência: o wheel do tflite-runtime
    não existe para Python 3.12, e é só com onnx que o import preguiçoso do
    tflite nunca é acionado. Os caminhos dos modelos são explícitos para tudo
    ficar em modelos-wakeword/, em vez de escondido dentro da .venv.
    """
    from openwakeword.model import Model

    return Model(
        wakeword_models=[str(caminho_modelo)],
        melspec_model_path=str(dir_modelos / "melspectrogram.onnx"),
        embedding_model_path=str(dir_modelos / "embedding_model.onnx"),
        inference_framework="onnx",
        # Desligado de propósito. Na Etapa 0.5 era para medir o falso positivo
        # bruto do modelo; aqui continua desligado porque quem filtra fala é o
        # nosso Silero, depois de acordar — não antes.
        vad_threshold=0,
    )


class ModeloAusente(FileNotFoundError):
    pass


@dataclass(frozen=True)
class Evento:
    """Uma rajada de frames acima do piso — tenha disparado ou não."""

    pico: float
    disparou: bool
    pcm: bytes
    momento: float  # time.monotonic()
    frames: int


class Detector:
    """Pontua o áudio e agrupa as rajadas em eventos com áudio anexado."""

    def __init__(
        self,
        cfg: ConfigWakeWord,
        dir_modelos: Path,
        *,
        amostras_por_bloco: int,
        taxa: int = 16000,
    ) -> None:
        self.cfg = cfg
        self.taxa = taxa
        self.amostras_por_bloco = amostras_por_bloco
        self.bytes_por_bloco = amostras_por_bloco * 2
        self.duracao_bloco_s = amostras_por_bloco / taxa

        caminho = dir_modelos / f"{cfg.modelo}.onnx"
        if not caminho.is_file():
            raise ModeloAusente(
                f"Modelo de wake word não encontrado: {caminho}\n"
                "  Baixe com:\n"
                "    ./.venv/bin/python -c \"import openwakeword.utils as u; "
                "u.download_models(model_names=['hey_jarvis'], "
                f"target_directory='{dir_modelos.name}')\""
            )

        inicio = time.monotonic()
        self._oww = carregar_modelo(caminho, dir_modelos)
        self.segundos_de_carga = time.monotonic() - inicio
        self._rotulo = next(iter(self._oww.models.keys()))

        # Acumulador de bytes: o microfone entrega 512 amostras, o modelo quer
        # 1280. Ver o docstring do módulo.
        self._sobra = b""

        # Contexto de áudio em volta do evento.
        self._pre_roll: deque[bytes] = deque(
            maxlen=max(1, round(PRE_ROLL_S / self.duracao_bloco_s))
        )
        self._blocos_pos = max(1, round(POS_ROLL_S / self.duracao_bloco_s))

        self._coletando: list[bytes] | None = None
        self._pico = 0.0
        self._frames_do_grupo = 0
        self._abaixo_seguidos = 0
        self._disparou_no_grupo = False
        self._t_grupo = 0.0
        self._ultimo_disparo = -1e9

        self.ultimo_score = 0.0

    # ----------------------------------------------------------------------

    @property
    def rotulo(self) -> str:
        return self._rotulo

    @property
    def descricao(self) -> str:
        return f"{self.cfg.modelo} · onnx · limiar {self.cfg.limiar:g}"

    def reiniciar(self) -> None:
        """Zera o estado do modelo e os buffers.

        Chamar em toda transição e depois de toda fala. O openWakeWord guarda
        2-3s de features internas: se ele acumulou o "hey Jarvis" antes de
        acordarmos, esse áudio continua lá e pontua de novo assim que o ciclo
        voltar a dormir — acordando sozinho em laço, sem o microfone ter
        captado nada. O portão anti-eco impede que ele *ouça* a resposta, mas
        não limpa o que já entrou.
        """
        self._oww.reset()
        self._sobra = b""
        self._pre_roll.clear()
        self._coletando = None
        self._pico = 0.0
        self._frames_do_grupo = 0
        self._abaixo_seguidos = 0
        self._disparou_no_grupo = False
        self.ultimo_score = 0.0

    # ----------------------------------------------------------------------

    def processar(self, bloco: bytes) -> tuple[bool, Evento | None]:
        """Consome um bloco do microfone.

        Devolve (disparou_agora, evento_fechado). O evento sai com um bloco de
        atraso em relação ao disparo, porque ainda coletamos o pós-roll — por
        isso os dois são independentes: o acordar é imediato, o áudio vem
        depois.
        """
        self._pre_roll.append(bloco)

        # Acumula até fechar um ou mais frames de 1280 amostras.
        self._sobra += bloco
        disparou = False
        while len(self._sobra) >= BYTES_POR_FRAME:
            frame, self._sobra = (
                self._sobra[:BYTES_POR_FRAME],
                self._sobra[BYTES_POR_FRAME:],
            )
            score = float(
                self._oww.predict(np.frombuffer(frame, dtype=np.int16))[self._rotulo]
            )
            self.ultimo_score = score
            if self._avaliar(score):
                disparou = True

        return disparou, self._coletar(bloco)

    # ----------------------------------------------------------------------

    def _avaliar(self, score: float) -> bool:
        """Atualiza o grupo corrente e diz se este frame é um disparo."""
        agora = time.monotonic()

        if score >= self.cfg.piso_registro:
            if self._coletando is None:
                self._coletando = list(self._pre_roll)
                self._t_grupo = agora
                self._pico = 0.0
                self._frames_do_grupo = 0
                self._disparou_no_grupo = False
            self._abaixo_seguidos = 0
            self._pico = max(self._pico, score)
            self._frames_do_grupo += 1

        # Refratário: um "hey Jarvis" pontua alto por vários frames seguidos e
        # não pode virar vários acordares.
        if (
            score >= self.cfg.limiar
            and agora - self._ultimo_disparo >= self.cfg.refratario_s
        ):
            self._ultimo_disparo = agora
            self._disparou_no_grupo = True
            return True
        return False

    def _coletar(self, bloco: bytes) -> Evento | None:
        """Junta o pós-roll e fecha o evento quando a rajada acaba."""
        if self._coletando is None:
            return None

        self._coletando.append(bloco)
        if self.ultimo_score >= self.cfg.piso_registro:
            return None

        self._abaixo_seguidos += 1
        if self._abaixo_seguidos < self._blocos_pos:
            return None

        evento = Evento(
            pico=self._pico,
            disparou=self._disparou_no_grupo,
            pcm=b"".join(self._coletando),
            momento=self._t_grupo,
            frames=self._frames_do_grupo,
        )
        self._coletando = None
        self._pico = 0.0
        self._frames_do_grupo = 0
        self._abaixo_seguidos = 0
        self._disparou_no_grupo = False
        return evento

    def fechar_pendente(self) -> Evento | None:
        """Fecha à força um evento em coleta, com o áudio que já houver.

        Obrigatório ao acordar: no instante do disparo o evento ainda está
        juntando o pós-roll, e o ciclo sai de DORMINDO logo em seguida — daí
        em diante ninguém mais alimenta este detector. Sem fechar aqui, o
        `.wav` do despertar de verdade, que é o dado mais importante de todos,
        seria descartado no `reiniciar()`.

        Também vale na saída do programa, para não perder o último evento.
        """
        if self._coletando is None:
            return None
        evento = Evento(
            pico=self._pico,
            disparou=self._disparou_no_grupo,
            pcm=b"".join(self._coletando),
            momento=self._t_grupo,
            frames=self._frames_do_grupo,
        )
        self._coletando = None
        self._pico = 0.0
        self._frames_do_grupo = 0
        self._abaixo_seguidos = 0
        self._disparou_no_grupo = False
        return evento
