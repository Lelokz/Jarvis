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
    indo_dormir: str
    parei: str
    limite_acabou: str
    limite_acabou_sem_hora: str
    sem_internet: str
    cerebro_falhou: str
    whats_chegou: str
    whats_chegou_sem_texto: str
    whats_varias: str
    whats_oferta: str


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
    efeito: str = ""
    tom: float = 0.0  # semitons; negativo = mais grave (só Kokoro)
    socket_f5: str = "jarvis-voz.sock"  # o servidor_voz.py (motor "f5")
    socket_rvc: str = "jarvis-rvc.sock"  # o servidor_rvc.py (motor "rvc")


@dataclass(frozen=True)
class Midia:
    comando_mpv: str
    comando_ytdlp: str
    comando_navegador: str
    segundos_busca: int
    passo_volume: int
    limite_confirmacao: int
    segundos_para_o_som: int


@dataclass(frozen=True)
class WakeWord:
    modelo: str
    limiar: float
    piso_registro: float
    refratario_s: float


@dataclass(frozen=True)
class Friday:
    """A segunda persona (25/10/2026): "Hey Friday" chama ela, "hey Jarvis"
    chama ele. As frases fixas dela ficam em [persona_friday]."""
    ligada: bool
    modelo_wake: str
    limiar: float
    socket: str  # o servidor_friday.py (voz da Emilia, F5)
    cor: str


@dataclass(frozen=True)
class Ciclo:
    janela_s: float


@dataclass(frozen=True)
class Agente:
    binario: str
    modelo: str
    modelo_rapido: str
    effort: str
    modo_permissao: str
    casa: str
    validade_pergunta_s: float


@dataclass(frozen=True)
class Log:
    salvar_audio: bool
    max_audios_wake: int


@dataclass(frozen=True)
class Ponte:
    ligada: bool
    socket: str
    fila_max: int


@dataclass(frozen=True)
class Remoto:
    ligada: bool
    porta: int  # só em 127.0.0.1: quem leva para a rede é o `tailscale serve`
    chave: str  # arquivo com a chave que o celular apresenta


@dataclass(frozen=True)
class Whatsapp:
    ativo: bool
    banco: str
    api: str
    avisar_grupos: bool
    ler_conteudo: bool
    intervalo_s: float


@dataclass(frozen=True)
class Config:
    persona: Persona
    audio: Audio
    vad: Vad
    stt: Stt
    tts: Tts
    midia: Midia
    wakeword: WakeWord
    ciclo: Ciclo
    log: Log
    ponte: Ponte
    remoto: Remoto
    whatsapp: "Whatsapp"
    agente: Agente
    raiz: Path
    friday: Friday | None = None
    persona_friday: Persona | None = None

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
    "midia": Midia,
    "wakeword": WakeWord,
    "ciclo": Ciclo,
    "log": Log,
    "ponte": Ponte,
    "remoto": Remoto,
    "whatsapp": Whatsapp,
    "agente": Agente,
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


# Seções que podem faltar (um config.toml antigo continua valendo).
_OPCIONAIS = {"friday": Friday, "persona_friday": Persona}


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
    for nome, classe in _OPCIONAIS.items():
        if nome in bruto:
            secoes[nome] = _montar(nome, classe, bruto[nome])
    return Config(raiz=caminho.parent, **secoes)
