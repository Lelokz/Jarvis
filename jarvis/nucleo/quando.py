"""Converte fala em data e hora.

Existe por medição, não por gosto. Testadas dez frases como o Léo fala, com
hoje sendo sexta 04/09/2026:

    o modelo calcula a data              5/10
    o modelo extrai + este módulo        9/10, todas as datas certas

Os erros do modelo eram **todos de aritmética de dia da semana** — "sexta que
vem" virou quarta, "segunda" virou sábado, "terça" virou domingo. E nenhum se
anuncia: ele devolve um ISO bem formado e errado, que parece certo. Extrair a
expressão verbatim, em contraste, ele faz 10/10.

Então a divisão é: o modelo devolve `"sexta que vem às três"` e quem calcula é
este arquivo.

**Separado da agenda de propósito.** Converter fala em data serve para
lembrete, alarme e qualquer coisa futura com hora. Não é assunto do Google.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass

# "uma da tarde" é 13h, "três" sozinho quase nunca é 3 da manhã.
NUMEROS = {
    "zero": 0, "uma": 1, "um": 1, "duas": 2, "dois": 2, "tres": 3, "quatro": 4,
    "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
    "onze": 11, "doze": 12, "treze": 13, "quatorze": 14, "catorze": 14,
    "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18,
    "dezenove": 19, "vinte": 20, "vinte e um": 21, "vinte e uma": 21,
    "vinte e dois": 22, "vinte e duas": 22, "vinte e tres": 23,
    "vinte e quatro": 24, "vinte e cinco": 25, "vinte e seis": 26,
    "vinte e sete": 27, "vinte e oito": 28, "vinte e nove": 29, "trinta": 30,
    "trinta e um": 31, "meia": 30,
}

DIAS_SEMANA = {
    "segunda": 0, "terca": 1, "quarta": 2, "quinta": 3,
    "sexta": 4, "sabado": 5, "domingo": 6,
}

# Quando ele diz só o período, sem hora.
PERIODOS = {"manha": 9, "tarde": 14, "noite": 19, "madrugada": 3}

# Hora nua de 1 a 6, sem "da manhã/tarde/noite", vira tarde. Ninguém marca
# dentista às 3 da madrugada — foi a única falha das dez frases medidas
# ("sexta que vem às três" caía em 03:00). De 7 a 12 fica como falado.
LIMITE_TARDE = 6


@dataclass(frozen=True)
class Quando:
    inicio: dt.datetime
    # O que foi entendido, para o Jarvis confirmar em voz alta antes de agir.
    # Dizer o dia da semana é o que deixa o Léo perceber que ele entendeu
    # sábado quando queria dizer segunda — erro de data é silencioso.
    descricao: str
    # O usuário disse a hora? Período conta: quem fala "de noite" disse quando
    # quer. A versão anterior marcava período como NÃO dita, e a consequência
    # era a confirmação calar a hora — "marca dedista hoje de noite" resolvia
    # 19:00 certinho e confirmava "dedista hoje". Quem confirma sem ouvir a
    # hora não tem como pegar o erro que a confirmação existe para pegar.
    disse_hora: bool


DIA_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

# Hora usada quando ele não disse nenhuma. Nunca vira compromisso: criar
# evento pergunta a hora. Existe só para "amanhã" ter um datetime de onde
# tirar a data quando alguém pergunta o que tem no dia.
HORA_DE_ENFEITE = 9


def _sem_acento(texto: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )


def _numero(texto: str) -> int | None:
    texto = texto.strip()
    if texto.isdigit():
        return int(texto)
    return NUMEROS.get(texto)


def _descrever(quando: dt.datetime, agora: dt.datetime, explicita: bool) -> str:
    """Como o Jarvis vai falar a data de volta."""
    dias = (quando.date() - agora.date()).days
    if dias == 0:
        dia = "hoje"
    elif dias == 1:
        dia = f"amanhã, {DIA_PT[quando.weekday()]}"
    elif dias == 2:
        dia = f"depois de amanhã, {DIA_PT[quando.weekday()]}"
    elif 0 < dias <= 7:
        dia = DIA_PT[quando.weekday()]
    else:
        dia = f"{DIA_PT[quando.weekday()]}, dia {quando.day}"

    if not explicita:
        return dia
    if quando.minute:
        return f"{dia} às {quando.hour}h{quando.minute:02d}"
    return f"{dia} às {quando.hour}"


# ---------------------------------------------------------------------------


def _resolver_dia(texto: str, agora: dt.datetime) -> dt.date:
    if "depois de amanha" in texto:
        return agora.date() + dt.timedelta(days=2)
    if "amanha" in texto:
        return agora.date() + dt.timedelta(days=1)
    if "hoje" in texto or "agora" in texto:
        return agora.date()

    achado = re.search(r"\bdia ([\w ]+?)(?:\s+(?:as|ao|de|da|a)\b|$)", texto)
    if achado and _numero(achado.group(1)):
        numero = _numero(achado.group(1))
        try:
            dia = agora.date().replace(day=numero)
        except ValueError:
            return agora.date()
        if dia < agora.date():
            # Já passou neste mês: ele quer o mês que vem.
            seguinte = (dia.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
            try:
                dia = seguinte.replace(day=numero)
            except ValueError:
                pass
        return dia

    for nome, indice in DIAS_SEMANA.items():
        if re.search(rf"\b{nome}", texto):
            delta = (indice - agora.weekday()) % 7
            if delta == 0:
                # "segunda" numa segunda é a próxima, não hoje.
                delta = 7
            if "que vem" in texto or "proxima" in texto or "proximo" in texto:
                if delta < 7:
                    delta += 7
            return agora.date() + dt.timedelta(days=delta)

    return agora.date()


def _resolver_hora(texto: str) -> tuple[int, int] | None:
    """Devolve (hora, minuto), ou None quando ele não disse a hora."""
    if "meio-dia" in texto or "meio dia" in texto:
        return 12, 0
    if "meia-noite" in texto or "meia noite" in texto:
        return 0, 0

    hora = minuto = None

    # "14h", "14h30", "às 9h"
    achado = re.search(r"\b(\d{1,2})\s*h(?:oras)?\s*(\d{2})?\b", texto)
    if achado:
        hora = int(achado.group(1))
        minuto = int(achado.group(2)) if achado.group(2) else 0

    if hora is None:
        # "às três", "às dez e meia", "às sete da noite"
        achado = re.search(r"\b(?:as|a|ao)\s+([\w ]+?)(?:\s+(?:da|de|e)\b|$)", texto)
        if not achado:
            achado = re.search(r"\b([\w]+)\s+(?:da|de)\s+(?:manha|tarde|noite|madrugada)", texto)
        if achado:
            hora = _numero(achado.group(1))

    if hora is None:
        for periodo, padrao in PERIODOS.items():
            if re.search(rf"(de|da|a|as|pela)\s+{periodo}", texto):
                return padrao, 0
        # Nem hora nem período: ele não disse quando do dia. Não é papel
        # daqui inventar — quem chama decide se pergunta ou se usa um padrão.
        return None

    if minuto is None:
        meia = re.search(r"\be\s+(meia|trinta|quinze|\d{1,2})\b", texto)
        minuto = _numero(meia.group(1)) if meia else 0
        if minuto is None:
            minuto = 0

    # Ajuste de período: "sete da noite" é 19h.
    if re.search(r"(da|de)\s+(tarde|noite)", texto) and hora < 12:
        hora += 12
    elif re.search(r"(da|de)\s+(manha|madrugada)", texto):
        pass  # já está certo
    elif 0 < hora <= LIMITE_TARDE:
        # Hora nua e pequena: horário civil manda ser tarde.
        hora += 12

    return min(hora, 23), min(minuto, 59)


def resolver(expressao: str, agora: dt.datetime | None = None) -> Quando | None:
    """Converte "sexta que vem às três" numa data e hora concretas."""
    agora = agora or dt.datetime.now()
    texto = _sem_acento(expressao)
    if not texto.strip():
        return None

    # Relativo puro não tem dia nem hora: "daqui a duas horas".
    achado = re.search(r"daqui a ([\w ]+?)\s*(hora|minuto|dia|semana)", texto)
    if achado:
        n = _numero(achado.group(1)) or 1
        unidade = achado.group(2)
        delta = {
            "hora": dt.timedelta(hours=n),
            "minuto": dt.timedelta(minutes=n),
            "dia": dt.timedelta(days=n),
            "semana": dt.timedelta(weeks=n),
        }[unidade]
        inicio = agora + delta
        return Quando(inicio, _descrever(inicio, agora, True), True)

    dia = _resolver_dia(texto, agora)
    marcada = _resolver_hora(texto)
    # Sem hora dita, o horário fica de enfeite: serve para "que dia é esse" —
    # que é tudo que listar precisa —, e criar evento pergunta a hora em vez
    # de usá-lo.
    hora, minuto = marcada if marcada else (HORA_DE_ENFEITE, 0)
    explicita = marcada is not None
    inicio = dt.datetime.combine(dia, dt.time(hora, minuto))

    # Hora que já passou hoje, sem dia dito: ele quer amanhã.
    if inicio < agora and not re.search(r"hoje|agora|dia \w", texto):
        if dia == agora.date():
            inicio += dt.timedelta(days=1)

    return Quando(inicio, _descrever(inicio, agora, explicita), explicita)
