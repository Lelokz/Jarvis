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


def _escrever_wav(caminho: Path, pcm: bytes, taxa: int) -> None:
    """Mono, int16 — o formato que a cadeia inteira usa."""
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(pcm)


@dataclass(frozen=True)
class Registrador:
    caminho_jsonl: Path
    dir_audio: Path | None
    dir_audio_wake: Path | None = None
    max_audios_wake: int = 200

    @classmethod
    def criar(cls, cfg: Config, *, prefixo: str = "etapa0") -> Registrador:
        """Cria o log da sessão.

        `prefixo` separa as execuções por programa: `etapa0-*.jsonl` é o banco
        de medição, `jarvis-*.jsonl` é o assistente com wake word. Um arquivo
        por execução, contando a história inteira em ordem.
        """
        carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
        cfg.dir_logs.mkdir(parents=True, exist_ok=True)

        dir_audio = None
        if cfg.log.salvar_audio:
            dir_audio = cfg.dir_logs / "audio"
            dir_audio.mkdir(parents=True, exist_ok=True)

        # O áudio de wake word não obedece a `salvar_audio`: é dado de
        # operação, não de teste. É o que explica um acordar indevido no meio
        # de um jogo meses depois, e por isso tem pasta e teto próprios.
        dir_audio_wake = cfg.dir_logs / "audio-wake"
        dir_audio_wake.mkdir(parents=True, exist_ok=True)

        registrador = cls(
            caminho_jsonl=cfg.dir_logs / f"{prefixo}-{carimbo}.jsonl",
            dir_audio=dir_audio,
            dir_audio_wake=dir_audio_wake,
            max_audios_wake=cfg.log.max_audios_wake,
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
                "wakeword": {
                    "modelo": cfg.wakeword.modelo,
                    "limiar": cfg.wakeword.limiar,
                    "piso_registro": cfg.wakeword.piso_registro,
                    "refratario_s": cfg.wakeword.refratario_s,
                },
                "ciclo": {"janela_s": cfg.ciclo.janela_s},
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

    def registrar_wake(
        self,
        *,
        pico: float,
        disparou: bool,
        pcm: bytes,
        taxa: int,
        frames: int,
    ) -> Path | None:
        """Grava um evento de wake word — disparo OU quase-acerto.

        Gravar só os disparos foi a decisão errada da Etapa 0.5: quando se
        investiga por que algo *não* acordou, os frames interessantes são
        justamente os que ficaram abaixo do limiar.
        """
        agora = datetime.now()
        # Microssegundos, não milissegundos: dois eventos de wake word podem
        # fechar no mesmo milissegundo (quase-acertos não têm refratário), e aí
        # um .wav sobrescreveria o outro deixando duas linhas do log apontando
        # para o mesmo arquivo. O nome continua ordenável, que é do que o teto
        # depende para saber qual é o mais antigo.
        identificador = agora.strftime("%Y%m%d-%H%M%S-") + f"{agora.microsecond:06d}"

        caminho = None
        if self.dir_audio_wake is not None:
            caminho = self.dir_audio_wake / f"{identificador}.wav"
            _escrever_wav(caminho, pcm, taxa)
            self._aplicar_teto()

        self._escrever(
            {
                "tipo": "wake",
                "id": identificador,
                "momento": agora.isoformat(timespec="milliseconds"),
                "pico": round(pico, 5),
                "disparou": disparou,
                "frames": frames,
                "audio": caminho.name if caminho else None,
            }
        )
        return caminho

    def registrar_estado(self, estado: str, **detalhe: Any) -> None:
        self._escrever(
            {
                "tipo": "estado",
                "momento": datetime.now().isoformat(timespec="milliseconds"),
                "estado": estado,
                **detalhe,
            }
        )

    def _aplicar_teto(self) -> None:
        """Mantém só os N .wav mais recentes de wake word.

        Um processo que fica ligado o dia todo não pode crescer em disco sem
        limite. Os nomes são carimbos de tempo, então a ordem alfabética já é
        a cronológica.
        """
        if self.dir_audio_wake is None or self.max_audios_wake <= 0:
            return
        arquivos = sorted(self.dir_audio_wake.glob("*.wav"))
        for antigo in arquivos[: max(0, len(arquivos) - self.max_audios_wake)]:
            antigo.unlink(missing_ok=True)

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
        _escrever_wav(caminho, segmento.pcm, segmento.taxa)
        return caminho

    def _escrever(self, linha: dict[str, Any]) -> None:
        with self.caminho_jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
