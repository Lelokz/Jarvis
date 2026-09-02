"""Registro da sessão: um .jsonl de medições e um .wav por segmento.

O .jsonl guarda o que o Whisper *entendeu*. O .wav guarda o que o microfone
*captou*. Quando uma transcrição sair errada, é o cruzamento dos dois que diz
se o problema foi o microfone ou o modelo — e essa distinção decide se a
correção é de hardware ou de configuração. Sem o áudio, a análise vira chute.

Os dois compartilham o mesmo identificador de tempo, então dá para ir de uma
linha do log direto ao áudio dela.
"""

from __future__ import annotations

import json
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Config
from .cronometro import Tempos
from .vad import Segmento


@dataclass(frozen=True)
class Registrador:
    caminho_jsonl: Path
    dir_audio: Path | None

    @classmethod
    def criar(cls, cfg: Config) -> Registrador:
        carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
        cfg.dir_logs.mkdir(parents=True, exist_ok=True)

        dir_audio = None
        if cfg.log.salvar_audio:
            dir_audio = cfg.dir_logs / "audio"
            dir_audio.mkdir(parents=True, exist_ok=True)

        registrador = cls(
            caminho_jsonl=cfg.dir_logs / f"etapa0-{carimbo}.jsonl",
            dir_audio=dir_audio,
        )
        # Cabeçalho com a configuração: é o que permite comparar duas sessões
        # (int8 vs int8_float16, voz A vs voz B) sem depender de memória.
        registrador._escrever(
            {
                "tipo": "sessao",
                "momento": datetime.now().isoformat(timespec="seconds"),
                "stt": {
                    "modelo": cfg.stt.modelo,
                    "dispositivo": cfg.stt.dispositivo,
                    "compute_type": cfg.stt.compute_type,
                    "idioma": cfg.stt.idioma,
                    "beam_size": cfg.stt.beam_size,
                },
                "tts": {"motor": cfg.tts.motor, "voz": cfg.tts.voz},
                "vad": {
                    "limiar": cfg.vad.limiar,
                    "silencio_final_ms": cfg.vad.silencio_final_ms,
                    "pre_roll_ms": cfg.vad.pre_roll_ms,
                    "fala_minima_ms": cfg.vad.fala_minima_ms,
                },
            }
        )
        return registrador

    # ----------------------------------------------------------------------

    def registrar_frase(
        self,
        *,
        segmento: Segmento,
        texto: str,
        tempos: Tempos,
        idioma: str,
        probabilidade_idioma: float,
    ) -> Path | None:
        agora = datetime.now()
        identificador = agora.strftime("%Y%m%d-%H%M%S-") + f"{agora.microsecond // 1000:03d}"

        caminho_audio = self._salvar_wav(identificador, segmento)
        self._escrever(
            {
                "tipo": "frase",
                "id": identificador,
                "momento": agora.isoformat(timespec="milliseconds"),
                "texto": texto,
                "audio": caminho_audio.name if caminho_audio else None,
                "idioma": idioma,
                "probabilidade_idioma": round(probabilidade_idioma, 4),
                "fim_do_segmento": segmento.motivo.value,
                "tempos": tempos.como_dict(),
            }
        )
        return caminho_audio

    def registrar_descarte(self, motivo: str, detalhe: dict[str, Any]) -> None:
        self._escrever(
            {
                "tipo": "descarte",
                "momento": datetime.now().isoformat(timespec="milliseconds"),
                "motivo": motivo,
                **detalhe,
            }
        )

    # ----------------------------------------------------------------------

    def _salvar_wav(self, identificador: str, segmento: Segmento) -> Path | None:
        if self.dir_audio is None:
            return None
        caminho = self.dir_audio / f"{identificador}.wav"
        with wave.open(str(caminho), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)  # int16
            w.setframerate(segmento.taxa)
            w.writeframes(segmento.pcm)
        return caminho

    def _escrever(self, linha: dict[str, Any]) -> None:
        with self.caminho_jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
