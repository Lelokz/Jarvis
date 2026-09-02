"""Medição e apresentação dos tempos.

Este módulo é o produto da Etapa 0. O ESCOPO §7 diz que a latência do ciclo
completo é risco de gravidade Alta e manda *"medir na Etapa 0 antes de
investir em qualquer outra coisa"* — o número que sai daqui é o que aprova ou
reprova a etapa.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass

LARGURA = 42
_REGUA = "─" * LARGURA


@dataclass(frozen=True)
class Tempos:
    # Duração do áudio que foi para o Whisper: pré-roll + fala + as pausas
    # internas. É este número, e não só o trecho com voz, que explica o tempo
    # de STT — o Whisper cobra pelo que recebe.
    duracao_segmento_s: float
    espera_silencio_s: float
    stt_s: float
    tts_primeiro_s: float
    tts_total_s: float
    reproducao_s: float

    @property
    def latencia_percebida_s(self) -> float:
        """Fim da fala → primeiro som da resposta.

        É O número. "Fala capturada" é o tempo em que *você* fala e
        "reprodução" é o tempo em que *ele* fala: nenhum dos dois é
        processamento, e somá-los ao total só serve para esconder o que
        importa. O que decide a aprovação é o intervalo em que você está
        parado esperando.
        """
        return self.espera_silencio_s + self.stt_s + self.tts_primeiro_s

    @property
    def ciclo_total_s(self) -> float:
        """Do início da sua fala ao fim da resposta dele."""
        return (
            self.duracao_segmento_s
            + self.espera_silencio_s
            + self.stt_s
            + self.tts_primeiro_s
            + self.reproducao_s
        )

    def como_dict(self) -> dict[str, float]:
        d = asdict(self)
        d["latencia_percebida_s"] = self.latencia_percebida_s
        d["ciclo_total_s"] = self.ciclo_total_s
        return {k: round(v, 4) for k, v in d.items()}


def _linha(rotulo: str, segundos: float) -> str:
    return f"  {rotulo:<20}{segundos:>6.2f} s"


def formatar_bloco(texto: str, t: Tempos) -> str:
    dito = texto if texto else "(nada transcrito)"
    return "\n".join(
        [
            _REGUA,
            f'  você disse:  "{dito}"',
            _REGUA,
            _linha("fala capturada", t.duracao_segmento_s),
            _linha("espera do silêncio", t.espera_silencio_s),
            _linha("STT (whisper)", t.stt_s),
            _linha("TTS 1º áudio", t.tts_primeiro_s),
            _linha("TTS síntese total", t.tts_total_s),
            _linha("reprodução", t.reproducao_s),
            _REGUA,
            _linha("LATÊNCIA PERCEBIDA", t.latencia_percebida_s),
            "  (fim da fala → 1º som da resposta)",
            _linha("ciclo completo", t.ciclo_total_s),
            _REGUA,
        ]
    )


class Resumo:
    """Acumula as medições da sessão. Uma frase só não decide nada."""

    _ETAPAS = (
        ("fala capturada", "duracao_segmento_s"),
        ("espera do silêncio", "espera_silencio_s"),
        ("STT (whisper)", "stt_s"),
        ("TTS 1º áudio", "tts_primeiro_s"),
        ("TTS síntese total", "tts_total_s"),
        ("reprodução", "reproducao_s"),
        ("LATÊNCIA PERCEBIDA", "latencia_percebida_s"),
        ("ciclo completo", "ciclo_total_s"),
    )

    def __init__(self) -> None:
        self._medicoes: list[Tempos] = []

    def adicionar(self, t: Tempos) -> None:
        self._medicoes.append(t)

    def __len__(self) -> int:
        return len(self._medicoes)

    def formatar(self, *, descartados: int = 0, vazias: int = 0) -> str:
        if not self._medicoes:
            return "Nenhuma frase medida nesta sessão."

        linhas = [
            "",
            _REGUA,
            f"  RESUMO — {len(self._medicoes)} frase(s)",
            _REGUA,
            f"  {'':<20}{'mín':>7}{'média':>8}{'máx':>7}",
        ]
        for rotulo, campo in self._ETAPAS:
            vals = [getattr(t, campo) for t in self._medicoes]
            if rotulo == "LATÊNCIA PERCEBIDA":
                linhas.append(_REGUA)
            linhas.append(
                f"  {rotulo:<20}"
                f"{min(vals):>6.2f}s"
                f"{statistics.fmean(vals):>7.2f}s"
                f"{max(vals):>6.2f}s"
            )
        linhas.append(_REGUA)

        if descartados or vazias:
            linhas.append("  descartados antes do Whisper:")
            if descartados:
                linhas.append(f"    curtos demais (ruído)      {descartados}")
            if vazias:
                linhas.append(f"    transcrição vazia          {vazias}")
            linhas.append(_REGUA)
        return "\n".join(linhas)
