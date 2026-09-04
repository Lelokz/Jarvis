"""Leitura do config.toml.

`tomllib` é stdlib desde o Python 3.11, então isto não custa dependência.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Persona:
    nome: str
    saudacao: str
    nao_sei: str
    nao_entendi: str
    o_que_entao: str
    pista_ruim: str
    busca_poucos: str
    busca_muitos: str
    busca_muitos_ainda: str
    busca_nada: str


@dataclass(frozen=True)
class Audio:
    dispositivo_entrada: str
    dispositivo_saida: str
    taxa_amostragem: int
    guarda_pos_fala_ms: int


@dataclass(frozen=True)
class Vad:
    limiar: float
    blocos_para_iniciar: int
    silencio_final_ms: int
    pre_roll_ms: int
    fala_minima_ms: int
    fala_maxima_s: float


@dataclass(frozen=True)
class Stt:
    modelo: str
    dispositivo: str
    compute_type: str
    idioma: str
    beam_size: int
    usar_vocabulario: bool


@dataclass(frozen=True)
class Tts:
    motor: str
    voz: str
    velocidade: float


@dataclass(frozen=True)
class Llm:
    url: str
    modelo: str
    keep_alive: str
    timeout_s: int
    ancoragem_minima: float


@dataclass(frozen=True)
class Acoes:
    comando_site: str
    comando_pasta: str
    comando_vscode: str


@dataclass(frozen=True)
class WakeWord:
    modelo: str
    limiar: float
    piso_registro: float
    refratario_s: float


@dataclass(frozen=True)
class Ciclo:
    janela_s: float


@dataclass(frozen=True)
class Busca:
    raizes: list[str]
    ignorar: list[str]
    max_resultados: int
    segundos_find: int


@dataclass(frozen=True)
class Log:
    salvar_audio: bool
    max_audios_wake: int


@dataclass(frozen=True)
class Config:
    persona: Persona
    audio: Audio
    vad: Vad
    stt: Stt
    tts: Tts
    llm: Llm
    acoes: Acoes
    wakeword: WakeWord
    ciclo: Ciclo
    busca: Busca
    log: Log
    raiz: Path

    @property
    def dir_vozes(self) -> Path:
        return self.raiz / "vozes"

    @property
    def dir_logs(self) -> Path:
        return self.raiz / "logs"

    @property
    def dir_modelos_wake(self) -> Path:
        return self.raiz / "modelos-wakeword"


_SECOES = {
    "persona": Persona,
    "audio": Audio,
    "vad": Vad,
    "stt": Stt,
    "tts": Tts,
    "llm": Llm,
    "acoes": Acoes,
    "wakeword": WakeWord,
    "ciclo": Ciclo,
    "busca": Busca,
    "log": Log,
}


def _montar(nome: str, classe: type, bruto: dict[str, Any]) -> Any:
    """Constrói uma seção reclamando com nome e linha em vez de TypeError cru."""
    esperados = {f.name for f in fields(classe)}
    faltando = esperados - bruto.keys()
    if faltando:
        raise ValueError(
            f"config.toml: faltam chaves em [{nome}]: "
            + ", ".join(sorted(faltando))
        )
    sobrando = bruto.keys() - esperados
    if sobrando:
        raise ValueError(
            f"config.toml: chaves desconhecidas em [{nome}]: "
            + ", ".join(sorted(sobrando))
        )
    return classe(**bruto)


def carregar(caminho: Path | None = None) -> Config:
    caminho = caminho or (RAIZ / "config.toml")
    if not caminho.is_file():
        raise FileNotFoundError(f"config.toml não encontrado em {caminho}")

    with caminho.open("rb") as f:
        bruto = tomllib.load(f)

    faltando = _SECOES.keys() - bruto.keys()
    if faltando:
        raise ValueError(
            "config.toml: faltam seções: "
            + ", ".join(f"[{s}]" for s in sorted(faltando))
        )

    secoes = {
        nome: _montar(nome, classe, bruto[nome])
        for nome, classe in _SECOES.items()
    }
    return Config(raiz=caminho.parent, **secoes)
