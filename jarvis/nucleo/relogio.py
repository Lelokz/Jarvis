"""Que horas são, que dia é hoje.

Lista fechada antes do modelo, pela lição de sempre: pergunta curta e fixa
custa 0 ms numa tabela e não dá ao modelo chance de errar o roteamento. As
formas tortas ("já tá tarde?") caem no modelo, que recebe a hora no prompt da
memória (ver `memoria.py`).

A hora sai por extenso do jeito que se fala ("três e meia da tarde"), e não
"15:30": o Piper lê mal número com sinal no meio (ESCOPO, Etapa 0).
"""

from __future__ import annotations

import datetime as dt

from .atalhos import normalizar

# Já normalizadas: sem acento, pontuação e artigo ("as horas" vira "horas").
_HORA = {
    "que horas sao", "que hora e", "que horas e", "que horas sao agora",
    "sabe que horas sao", "voce sabe que horas sao", "tem horas",
    "me diz horas", "me fala horas", "diz horas", "horas", "que horas",
    "qual hora", "que horas tem", "ve horas pra mim", "olha horas pra mim",
}
_DATA = {
    "que dia e hoje", "que dia e", "hoje e que dia", "qual dia hoje",
    "qual e dia hoje", "que data e hoje", "qual data hoje", "qual e data hoje",
    "que dia e hoje mesmo", "em que dia estamos", "que dia estamos",
    "dia hoje",
}

_HORAS = ["meia-noite", "uma", "duas", "três", "quatro", "cinco", "seis",
          "sete", "oito", "nove", "dez", "onze"]
_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
           "sexta-feira", "sábado", "domingo"]
_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _sem_nome(falado: str) -> str:
    """Tira um "jarvis" do começo ou do fim: "Jarvis, que horas são?"."""
    palavras = normalizar(falado).split()
    if palavras and palavras[0] == "jarvis":
        palavras = palavras[1:]
    if palavras and palavras[-1] == "jarvis":
        palavras = palavras[:-1]
    return " ".join(palavras)


def pergunta(falado: str) -> str | None:
    """"hora", "data" ou None. Casa contra a fala inteira."""
    chave = _sem_nome(falado)
    if chave in _HORA:
        return "hora"
    if chave in _DATA:
        return "data"
    return None


def hora_falada(agora: dt.datetime) -> str:
    h, m = agora.hour, agora.minute
    if h == 0:
        nome, periodo = "meia-noite", ""
    elif h == 12:
        nome, periodo = "meio-dia", ""
    else:
        nome = _HORAS[h % 12]
        periodo = (" da madrugada" if h < 5 else " da manhã" if h < 12
                   else " da tarde" if h < 18 else " da noite")
    if m == 0:
        minutos = " em ponto"
    elif m == 30:
        minutos = " e meia"
    else:
        minutos = f" e {m}"
    verbo = "É" if h in (0, 1, 12, 13) else "São"
    if m == 0:  # "seis da tarde em ponto", não "seis em ponto da tarde"
        return f"{verbo} {nome}{periodo}{minutos}."
    return f"{verbo} {nome}{minutos}{periodo}."


def data_falada(agora: dt.datetime) -> str:
    return (f"Hoje é {_SEMANA[agora.weekday()]}, "
            f"{agora.day} de {_MESES[agora.month - 1]}.")


def responder(qual: str, agora: dt.datetime | None = None) -> str:
    agora = agora or dt.datetime.now()
    return hora_falada(agora) if qual == "hora" else data_falada(agora)


def data_curta(dia: dt.date) -> str:
    """"sáb 11/10"."""
    return f"{_SEMANA[dia.weekday()][:3]} {dia:%d/%m}"


def agora_por_extenso(agora: dt.datetime | None = None) -> str:
    """Para pôr no prompt do modelo: dia, data e hora numa linha."""
    agora = agora or dt.datetime.now()
    return (f"{_SEMANA[agora.weekday()]}, {agora.day} de "
            f"{_MESES[agora.month - 1]} de {agora.year}, {agora:%H:%M}")
